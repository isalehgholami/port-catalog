"""port-catalog: read-only catalog of listening and published ports."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from .collectors import collect_docker, collect_host_sockets, collect_nginx, collect_ufw
from .ui import PAGE

EXTERNAL_BINDS = {"", "0.0.0.0", "::", "*"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# ----------------------------------------------------------- annotations
def _ann_path() -> str:
    return os.path.join(os.environ.get("DATA_DIR", "/data"), "annotations.json")


def load_annotations() -> dict[str, str]:
    """Load ``{port: text}``; missing or corrupt file means no annotations."""
    try:
        with open(_ann_path(), encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_annotation(port: str, text: str) -> None:
    """Set an annotation, or delete it when ``text`` is blank."""
    ann = load_annotations()
    text = text.strip()
    if text:
        ann[port] = text
    else:
        ann.pop(port, None)
    path = _ann_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ann, f, indent=2, sort_keys=True, ensure_ascii=False)
    os.replace(tmp, path)


# --------------------------------------------------------------- catalog
def _notes(row: dict[str, Any]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    host, docker = row["host_port"], row["origin"] == "docker"
    external = row["bind_ip"] in EXTERNAL_BINDS
    if docker and external:
        bind = row["bind_ip"] or "0.0.0.0"
        notes.append({"level": "warn", "text": f"Published on {bind} — reachable externally. Docker bypasses UFW for published ports."})
        cport = (row["container_port"] or "").split("/")[0]
        notes.append({"level": "info", "text": f'Safer: ports: ["127.0.0.1:{host}:{cport}"] → nginx proxy_pass http://127.0.0.1:{host};'})
    elif docker:
        notes.append({"level": "ok", "text": f"Loopback-only. nginx: proxy_pass http://127.0.0.1:{host}; — no firewall rule needed."})
    else:
        notes.append({"level": "info", "text": "Host process listening (not Docker)."})
    if row["nginx"]:
        joined = "; ".join(f"{n['server']} ({n['upstream']})" for n in row["nginx"][:4])
        notes.append({"level": "ok", "text": f"nginx → {joined}"})
    if row["ufw"]:
        joined = "; ".join(f"{r['action']} {r['proto']} from {r['src']}" for r in row["ufw"][:3])
        notes.append({"level": "info", "text": f"UFW: {joined}"})
    elif docker and external:
        notes.append({"level": "warn", "text": "No matching UFW rule — but Docker bypasses UFW; the port may still be open externally."})
    return notes


def build_catalog() -> dict[str, Any]:
    """Run all collectors and merge them into the catalog document."""
    containers, e_docker = collect_docker()
    ufw_rules, e_ufw = collect_ufw()
    sites, e_nginx = collect_nginx()
    socks, e_sock = collect_host_sockets()
    ann = load_annotations()

    ufw_by_port: dict[int, list[dict]] = {}
    for r in ufw_rules:
        if str(r["dst_port"]).isdigit():
            ufw_by_port.setdefault(int(r["dst_port"]), []).append(r)

    nginx_by_port: dict[int, list[dict]] = {}
    for s in sites:
        for url in s["proxy_pass"]:
            m = re.search(r":(\d+)(?:/.*)?$", url)
            if m:
                nginx_by_port.setdefault(int(m.group(1)), []).append(
                    {"server": " ".join(s["server_names"]) or "(unnamed)", "upstream": url})

    docker_ports = {p["host_port"] for c in containers for p in c["ports"] if p["host_port"]}
    used = {s["port"] for s in socks} | docker_ports

    rows: list[dict[str, Any]] = []
    seen: dict[tuple, dict] = {}
    for c in containers:
        for p in c["ports"]:
            if not p["host_port"]:
                continue
            key = (c["name"], p["host_port"], p["container_port"])
            if key in seen:  # same mapping published on both IPv4 and IPv6
                if p["host_ip"] in EXTERNAL_BINDS and seen[key]["bind_ip"] not in EXTERNAL_BINDS:
                    seen[key]["bind_ip"] = p["host_ip"]
                continue
            row = {
                "host_port": p["host_port"], "bind_ip": p["host_ip"] or "",
                "container_port": p["container_port"], "container": c["name"],
                "service": c["compose_service"], "project": c["compose_project"],
                "image": c["image"], "compose_dir": c["compose_dir"], "origin": "docker",
                "host_network": c["host_network"],
            }
            seen[key] = row
            rows.append(row)

    host_rows: dict[int, dict] = {}
    for s in socks:
        if not s["proto"].startswith("tcp") or s["port"] in docker_ports:
            continue
        cur = host_rows.get(s["port"])
        if cur is None:
            host_rows[s["port"]] = {
                "host_port": s["port"], "bind_ip": s["bind_ip"], "container_port": None,
                "container": None, "service": None, "project": None, "image": None,
                "compose_dir": None, "origin": "host service", "host_network": False,
            }
        elif cur["bind_ip"] in ("127.0.0.1", "::1") and s["bind_ip"] not in ("127.0.0.1", "::1"):
            cur["bind_ip"] = s["bind_ip"]
    rows += host_rows.values()

    for row in rows:
        row["ufw"] = ufw_by_port.get(row["host_port"], [])
        row["nginx"] = nginx_by_port.get(row["host_port"], [])
        row["annotation"] = ann.get(str(row["host_port"]))
        row["notes"] = _notes(row)
    rows.sort(key=lambda r: (r["project"] or ("zzz-docker" if r["origin"] == "docker" else "zzzz-host"), r["host_port"]))

    start, end = _int_env("PORT_RANGE_START", 8000), _int_env("PORT_RANGE_END", 9999)
    skip = used | {_int_env("PORTCATALOG_PORT", 9780)}
    free = [p for p in range(start, end + 1) if p not in skip][:12]

    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "port_range": [start, end],
        "next_free_ports": free,
        "used_ports": sorted(p for p in skip if start <= p <= end),
        "port_rows": rows,
        "containers": containers,
        "nginx_sites": sites,
        "ufw_rules": ufw_rules,
        "errors": {"docker": e_docker, "ufw": e_ufw, "nginx": e_nginx, "host_sockets": e_sock},
    }


# ------------------------------------------------------------------- API
def _auth(authorization: str | None = Header(default=None)) -> None:
    token = os.environ.get("PORTCATALOG_TOKEN")
    if token and authorization != f"Bearer {token}":
        raise HTTPException(401, "Missing or invalid bearer token")


app = FastAPI(title="port-catalog", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the single-page UI."""
    return PAGE


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe (exempt from the token so HEALTHCHECK works)."""
    return {"status": "ok"}


@app.get("/api/catalog", dependencies=[Depends(_auth)])
def catalog() -> dict[str, Any]:
    """Return the full, freshly computed catalog."""
    return build_catalog()


@app.post("/api/annotations", dependencies=[Depends(_auth)])
async def annotate(request: Request) -> dict[str, bool]:
    """Set or clear the annotation for a port."""
    try:
        body = await request.json()
        port, text = str(body["port"]).strip(), body["text"]
        if not port.isdigit() or not isinstance(text, str) or len(text) > 500:
            raise ValueError
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Body must be {\"port\": \"8081\", \"text\": \"...\"}")
    save_annotation(port, text)
    return {"ok": True}


# ------------------------------------------------------------------- CLI
def print_report(cat: dict[str, Any], out=sys.stdout) -> None:
    """Print a plain-text report of the catalog."""
    w = lambda s="": print(s, file=out)  # noqa: E731
    w(f"port-catalog on {cat['host']} at {cat['generated_at']}")
    group = object()
    for r in cat["port_rows"]:
        name = r["project"] or ("host services" if r["origin"] != "docker" else "(no compose project)")
        if name != group:
            group = name
            w(f"\n[{name}]")
        src = r["container"] or "host process"
        ufw = "yes" if r["ufw"] else "no"
        ngx = ",".join(n["server"] for n in r["nginx"]) or "-"
        w(f"  {r['host_port']:<6} {r['bind_ip'] or '0.0.0.0':<15} -> {r['container_port'] or '-':<10} {src}  ufw={ufw}  nginx={ngx}")
    for k, v in cat["errors"].items():
        if v:
            w(f"! {k}: {v}")
    w(f"\nNext free host ports: {', '.join(map(str, cat['next_free_ports']))}")


def main(argv: list[str] | None = None) -> None:
    """Entry point: ``--once`` prints a report, otherwise serve the UI."""
    ap = argparse.ArgumentParser(prog="port-catalog", description=__doc__)
    ap.add_argument("--once", action="store_true", help="print the catalog and exit")
    ap.add_argument("--json", metavar="PATH", help="with --once: also write the catalog JSON")
    ap.add_argument("--demo", action="store_true", help="use built-in sample data (no Docker needed)")
    args = ap.parse_args(argv)
    if args.demo:
        from . import demo
        demo.install(sys.modules[__name__])
    if args.once:
        cat = build_catalog()
        print_report(cat)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(cat, f, indent=2)
        return
    import uvicorn
    host = os.environ.get("PORTCATALOG_BIND", "127.0.0.1")
    port = _int_env("PORTCATALOG_PORT", 9780)
    print(f"port-catalog listening on http://{host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
