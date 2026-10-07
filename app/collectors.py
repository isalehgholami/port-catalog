"""Read-only collectors for Docker, UFW, nginx and host sockets.

Every collector returns ``(data, error_or_None)`` and never raises.
"""
from __future__ import annotations

import os
import re
import socket
import struct
from typing import Any


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# ---------------------------------------------------------------- Docker
def collect_docker() -> tuple[list[dict[str, Any]], str | None]:
    """List all containers with their published/exposed ports."""
    try:
        import docker

        client = docker.from_env()
        out: list[dict[str, Any]] = []
        for c in client.containers.list(all=True):
            attrs = c.attrs or {}
            cfg = attrs.get("Config") or {}
            labels = cfg.get("Labels") or {}
            net = attrs.get("NetworkSettings") or {}
            ports: list[dict[str, Any]] = []
            for cport, bindings in (net.get("Ports") or {}).items():
                if not bindings:
                    ports.append({"container_port": cport, "host_ip": None, "host_port": None})
                    continue
                for b in bindings:
                    hp = b.get("HostPort")
                    ports.append({
                        "container_port": cport,
                        "host_ip": b.get("HostIp") or "",
                        "host_port": int(hp) if hp and str(hp).isdigit() else None,
                    })
            image = cfg.get("Image") or ""
            out.append({
                "name": c.name,
                "id": c.id[:12],
                "image": image,
                "state": (attrs.get("State") or {}).get("Status", ""),
                "host_network": (attrs.get("HostConfig") or {}).get("NetworkMode") == "host",
                "compose_project": labels.get("com.docker.compose.project"),
                "compose_service": labels.get("com.docker.compose.service"),
                "compose_dir": labels.get("com.docker.compose.project.working_dir"),
                "ports": ports,
                "networks": {
                    n: (v or {}).get("IPAddress", "")
                    for n, v in (net.get("Networks") or {}).items()
                },
            })
        return out, None
    except Exception as e:  # noqa: BLE001
        return [], f"docker unavailable: {e}"


# ------------------------------------------------------------------- UFW
def parse_ufw_line(line: str, family: str = "ipv4") -> dict[str, str] | None:
    """Parse a ``### tuple ###`` line into a rule dict."""
    if "### tuple ###" not in line:
        return None
    p = line.split()
    if len(p) < 10:
        return None
    return {
        "family": family, "action": p[3], "proto": p[4], "dst_port": p[5],
        "dst": p[6], "src": p[8], "direction": p[9],
    }


def collect_ufw(ufw_dir: str | None = None) -> tuple[list[dict[str, str]], str | None]:
    """Read UFW user rules."""
    d = ufw_dir or _env("UFW_DIR", "/etc/ufw")
    try:
        if not os.path.isdir(d):
            return [], f"{d} not mounted (UFW view disabled)"
        rules: list[dict[str, str]] = []
        for fn, fam in (("user.rules", "ipv4"), ("user6.rules", "ipv6")):
            path = os.path.join(d, fn)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    r = parse_ufw_line(line.strip(), fam)
                    if r:
                        rules.append(r)
        return rules, None
    except Exception as e:  # noqa: BLE001
        return [], f"ufw read failed: {e}"


# ----------------------------------------------------------------- nginx
_LISTEN_RE = re.compile(r"\blisten\s+([^;]+);")
_NAME_RE = re.compile(r"\bserver_name\s+([^;]+);")
_PROXY_RE = re.compile(r"\bproxy_pass\s+([^;]+);")


def _parse_listen(spec: str) -> dict[str, Any] | None:
    toks = spec.split()
    if not toks:
        return None
    first, flags = toks[0], toks[1:]
    if first.startswith("["):
        m = re.match(r"\[([^\]]*)\]:(\d+)$", first)
        if not m:
            return None
        addr, port = "::", int(m.group(2))
    elif ":" in first:
        a, _, pt = first.rpartition(":")
        if not pt.isdigit():
            return None
        addr, port = (a or "0.0.0.0"), int(pt)
        if addr == "*":
            addr = "0.0.0.0"
    elif first.isdigit():
        addr, port = "0.0.0.0", int(first)
    else:
        return None
    return {"addr": addr, "port": port, "flags": flags}


def parse_nginx(text: str, file: str = "") -> list[dict[str, Any]]:
    """Extract server blocks from nginx config text."""
    sites: list[dict[str, Any]] = []
    for m in re.finditer(r"\bserver\b", text):
        rest = text[m.end(): m.end() + 10]
        off = rest.find("{")
        if off < 0 or rest[:off].strip():
            continue
        start = m.end() + off
        depth, i = 0, start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start + 1: i]
        if "listen" not in body:
            continue
        listens = [x for x in (_parse_listen(s) for s in _LISTEN_RE.findall(body)) if x]
        names: list[str] = []
        for s in _NAME_RE.findall(body):
            names += s.split()
        sites.append({
            "file": file,
            "server_names": names,
            "listen": listens,
            "proxy_pass": [s.strip() for s in _PROXY_RE.findall(body)],
            "ssl": "ssl_certificate" in body,
        })
    return sites


def collect_nginx(nginx_dir: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
    """Walk the nginx dir and parse all server blocks."""
    d = nginx_dir or _env("NGINX_DIR", "/etc/nginx")
    try:
        if not os.path.isdir(d):
            return [], f"{d} not mounted (nginx view disabled)"
        sites: list[dict[str, Any]] = []
        for root, _dirs, files in os.walk(d):
            for fn in sorted(files):
                if fn.endswith((".key", ".crt", ".pem")):
                    continue
                path = os.path.join(root, fn)
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                if "listen" not in text:
                    continue
                sites.extend(parse_nginx(text, path))
        return sites, None
    except Exception as e:  # noqa: BLE001
        return [], f"nginx read failed: {e}"


# ----------------------------------------------------------- host sockets
def _hex_ip(h: str) -> str:
    if len(h) == 8:
        return socket.inet_ntoa(struct.pack("<I", int(h, 16)))
    words = [bytes.fromhex(h[i:i + 8])[::-1] for i in range(0, 32, 8)]
    return socket.inet_ntop(socket.AF_INET6, b"".join(words))


def parse_proc_net(text: str, proto: str) -> list[dict[str, Any]]:
    """Parse the content of a /proc/net/{tcp,udp}[6] file."""
    out: list[dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        if proto.startswith("tcp") and parts[3] != "0A":
            continue
        try:
            h, p = parts[1].split(":")
            inode = int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0
            out.append({"proto": proto, "bind_ip": _hex_ip(h), "port": int(p, 16), "inode": inode})
        except (ValueError, OSError):
            continue
    return out


def collect_host_sockets(proc_dir: str = "/proc/net") -> tuple[list[dict[str, Any]], str | None]:
    """Collect listening sockets from /proc/net."""
    out: list[dict[str, Any]] = []
    missing = []
    for name in ("tcp", "tcp6", "udp", "udp6"):
        try:
            with open(os.path.join(proc_dir, name), encoding="utf-8") as f:
                out += parse_proc_net(f.read(), name)
        except OSError:
            missing.append(name)
    err = "cannot read /proc/net (Linux host required)" if len(missing) == 4 else None
    return out, err


# -------------------------------------------------------------- processes
WELL_KNOWN = {
    22: "ssh", 25: "smtp", 53: "dns", 80: "http", 443: "https", 3306: "mysql",
    5432: "postgres", 6379: "redis", 27017: "mongodb", 5672: "rabbitmq",
    9200: "elasticsearch", 11211: "memcached",
}


def collect_processes(inodes: set[int], proc_dir: str = "/proc") -> tuple[dict[int, dict[str, Any]], str | None]:
    """Map socket inodes to the owning process (needs root, and ``pid: host`` in Docker)."""
    found: dict[int, dict[str, Any]] = {}
    try:
        pids = sorted((d for d in os.listdir(proc_dir) if d.isdigit()), key=int)
    except OSError as e:
        return {}, f"process names unavailable: {e}"
    denied = 0
    for pid in pids:
        if len(found) == len(inodes):
            break
        fd_dir = os.path.join(proc_dir, pid, "fd")
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            denied += 1
            continue
        mine: list[int] = []
        for fd in fds:
            try:
                link = os.readlink(os.path.join(fd_dir, fd))
            except OSError:
                continue
            if link.startswith("socket:[") and int(link[8:-1]) in inodes:
                mine.append(int(link[8:-1]))
        mine = [i for i in mine if i not in found]
        if not mine:
            continue
        try:
            with open(os.path.join(proc_dir, pid, "comm"), encoding="utf-8") as f:
                name = f.read().strip()
            with open(os.path.join(proc_dir, pid, "cmdline"), "rb") as f:
                cmd = f.read().replace(bytes(1), b" ").decode("utf-8", "replace").strip()
        except OSError:
            name, cmd = "?", ""
        for i in mine:
            found[i] = {"pid": int(pid), "name": name, "cmdline": cmd[:160]}
    err = None
    if inodes and not found and denied:
        err = "process names unavailable (run as root; in Docker add pid: host)"
    return found, err
