# Discovery — `port-catalog`

**Version:** 1.0 (v1 scope) · **Status:** ready for implementation
**Audience:** coding agent. Implement exactly this spec. Where the spec allows a
choice, pick the simplest option and note it in the PR/commit message.

---

## 1. One-liner

A tiny dockerized, **read-only** tool that catalogs every listening/published port
on a host — merging Docker publish mappings, UFW rules, nginx server blocks and raw
host sockets — and suggests the next free host ports.
Three interfaces: **web UI**, **JSON API**, **one-shot CLI**.

## 2. Problem

- One server runs many docker-compose stacks; several Django apps all use container
  port `8000`, each mapped to a different host port behind a **non-dockerized** nginx.
- Nobody remembers which host port belongs to which project; UFW rules drift;
  engineers re-run `ss -tlnp` + `docker ps` + grep nginx configs every time.
- Need one page answering: *what's listening, who owns it, is it public,
  and what host port is free for the next stack?*

## 3. Goals

| # | Goal |
|---|---|
| G1 | Live catalog of all Docker-published ports + host listening sockets (TCP/UDP) |
| G2 | Correlate each port with compose project/service, container, image, UFW rules, nginx server_names + proxy_pass |
| G3 | Warn when a port is published externally (Docker bypasses UFW — see D1) |
| G4 | Suggest next free host ports in a configurable range |
| G5 | Per-port user annotations, persisted in a volume |
| G6 | Web UI + JSON API + CLI (`--once`) |
| G7 | Single small image, no DB, no external services; graceful degradation when a source is missing |
| G8 | Safe defaults: binds `127.0.0.1`, docker.sock mounted read-only |

## 4. Non-goals

- N1: Never modifies UFW / nginx / Docker. The ONLY file it writes is
  `$DATA_DIR/annotations.json`.
- N2: No multi-host / remote-agent mode (single host per instance).
- N3: No user management. Optional static bearer token only.
- N4: Not a firewall editor and not a reverse-proxy config generator.

## 5. Domain facts the implementation MUST reflect

- **D1:** Docker publishes ports via iptables (`DOCKER` chain) and **bypasses UFW**.
  A published port can be reachable even with no UFW allow rule → the UI must warn
  on external binds (`""`, `0.0.0.0`, `::`, `*`).
- **D2:** Recommended pattern (show as a hint in notes):
  `ports: ["127.0.0.1:<host>:<container>"]` + nginx `proxy_pass http://127.0.0.1:<host>;`
- **D3:** `docker.sock` ≈ root on the host → mount `:ro`; README must recommend a
  read-only docker-socket-proxy for hardening.
- **D4:** Container IPs change on recreate → never suggest container IPs as nginx
  upstreams. Host-loopback publish (D2) is the only recommended pattern.

## 6. Runtime & dependencies

- Python 3.12. Dependencies (exactly these, pinned with minimums):
  `fastapi>=0.110`, `uvicorn>=0.29`, `docker>=7.0`. Everything else = stdlib.
- Single container, `network_mode: host` (so `/proc/net/*` shows real host sockets).
- Dev-only extra: `pytest` in `requirements-dev.txt` (NOT installed in the image).

## 7. Mounts & configuration

### 7.1 Mounts (tool's own compose, see §14)

| Host path | Container path | Mode | Optional |
|---|---|---|---|
| `/var/run/docker.sock` | `/var/run/docker.sock` | `ro` | no |
| `/etc/ufw` | `/etc/ufw` | `ro` | yes |
| `/etc/nginx` | `/etc/nginx` | `ro` | yes |
| `./data` | `/data` | `rw` | no |

If UFW/nginx dirs are absent → the app must still work; that collector returns
`([], "<dir> not mounted (<name> view disabled)")` and the error surfaces in
`errors` + a UI chip.

### 7.2 Environment variables

| Var | Default | Meaning |
|---|---|---|
| `PORTCATALOG_BIND` | `127.0.0.1` | uvicorn bind address |
| `PORTCATALOG_PORT` | `9780` | uvicorn port; also excluded from port suggestions |
| `UFW_DIR` | `/etc/ufw` | host UFW config mount point |
| `NGINX_DIR` | `/etc/nginx` | host nginx config mount point |
| `DATA_DIR` | `/data` | annotations persistence dir |
| `PORT_RANGE_START` | `8000` | suggestion range start |
| `PORT_RANGE_END` | `9999` | suggestion range end |
| `PORTCATALOG_TOKEN` | *(unset)* | if set: all `/api/*` require `Authorization: Bearer <token>`, else 401. The HTML page itself stays open. |

## 8. Collectors (`app/collectors.py`)

Pure functions. Each returns `(data, error_or_None)`. Never raise; catch everything.

### 8.1 Docker

- SDK: `docker.from_env()`; iterate `client.containers.list(all=True)`.
- Per container extract:
  - `name`, `id` (first 12 chars), `image`, `state` (`State.Status`)
  - `host_network`: `HostConfig.NetworkMode == "host"`
  - labels: `com.docker.compose.project`, `com.docker.compose.service`,
    `com.docker.compose.project.working_dir` (may be absent → `None`)
  - `networks`: `{net_name: IPAddress}` from `NetworkSettings.Networks`
  - `ports`: from `NetworkSettings.Ports`:
    - binding present → `{"container_port": "8000/tcp", "host_ip": <raw or "">,
      "host_port": <int>}`
    - exposed but unpublished (null bindings) → `{"container_port": ..., "host_ip": None, "host_port": None}`
- Output: list of container dicts (schema in §12).

### 8.2 UFW

- Files: `$UFW_DIR/user.rules` (ipv4) and `$UFW_DIR/user6.rules` (ipv6).
- Only lines containing `### tuple ###`. After `.split()`, indices:
  `3`=action (`allow|reject|limit`), `4`=proto, `5`=dst_port, `6`=dst,
  `8`=src, `9`=direction (`in|out`). Store values as strings.
- Fixture line for tests (exact): `### tuple ### allow tcp 8081 0.0.0.0/0 any 0.0.0.0/0 in`

### 8.3 nginx

- Walk `$NGINX_DIR` recursively; skip files ending `.key|.crt|.pem`; skip files not
  containing the substring `listen`.
- Extract `server { … }` blocks:
  - find every `\bserver\b`; require the next `{` within 10 chars (this skips
    `upstream` blocks' `server …;` directives);
  - brace-count from that `{` to the matching `}` to get the block body;
  - keep only blocks containing `listen`.
- Per block:
  - `listen` specs via regex `\blisten\s+([^;]+);` → parse each:
    supports `IP:PORT`, `[::]:PORT`, bare `PORT` (+ flags). addr defaults to
    `0.0.0.0`; IPv6 → `::`. Drop entries without a numeric port.
  - `server_name` via `\bserver_name\s+([^;]+);` → split on whitespace.
  - `proxy_pass` via `\bproxy_pass\s+([^;]+);` → list of raw URLs (stripped).
  - `ssl`: boolean, true iff `ssl_certificate` appears in the block.
- Output: `{file, server_names, listen, proxy_pass, ssl}` per site.

### 8.4 Host sockets (`/proc/net/{tcp,tcp6,udp,udp6}`)

- Line format: whitespace-split; `parts[1]` = local address (`HEXIP:HEXPORT`),
  `parts[3]` = state.
- TCP: keep only state `0A` (LISTEN). UDP: keep all rows (stateless).
- IPv4 hex IP is little-endian: `socket.inet_ntoa(struct.pack("<I", int(h, 16)))`.
  Check: `0100007F:1F91` → `127.0.0.1:8081`.
- IPv6: decode properly — split the 32-hex-char address into 4 groups of 8 chars,
  reverse byte order within each 4-byte word, concatenate, `socket.inet_ntop(AF_INET6, …)`
  (so `…01000000` decodes to `::1`).
- Output: `{proto, bind_ip, port}`.

### 8.5 Aggregation (`build_catalog` in `app/main.py`)

1. Run all collectors; load annotations (`$DATA_DIR/annotations.json`:
   `{ "8081": "prod django", … }`, keys = `str(host_port)`).
2. `ufw_by_port`: `int(dst_port)` → rules (only when dst_port is numeric).
3. `nginx_by_port`: for each site × each proxy_pass URL: if the text after the
   last `:` is all digits → key = that int; value = `{"server": joined names or
   "(unnamed)", "upstream": url}`.
4. `used` = set of host listener ports ∪ set of Docker `host_port` (non-null).
5. Rows:
   - one row per Docker binding with `host_port` (origin `"docker"`);
   - one row per **TCP** host listener whose port is NOT a published docker port
     (origin `"host service"`, all docker-ish fields `null`). UDP listeners only
     count toward `used`, no rows (v1).
6. Generate `notes` per §9; annotate from the annotations map.
7. `next_free_ports`: first 12 free ints in `[PORT_RANGE_START, PORT_RANGE_END]`,
   excluding `used` and `PORTCATALOG_PORT`.
8. Sort rows by `(project or "zzz-host", host_port)` → host services last.

## 9. Notes engine (exact rules)

Levels: `ok` / `info` / `warn`. Each note = `{"level", "text"}`. Apply in order:

| # | Condition | Level | Text |
|---|---|---|---|
| R1 | docker row, external bind | warn | `Published on {bind or '0.0.0.0'} — reachable externally. Docker bypasses UFW for published ports.` |
| R2 | docker row, external bind | info | `Safer: ports: ["127.0.0.1:{host}:{container}"] → nginx proxy_pass http://127.0.0.1:{host};` |
| R3 | docker row, loopback bind | ok | `Loopback-only. nginx: proxy_pass http://127.0.0.1:{host}; — no firewall rule needed.` |
| R4 | host-service row | info | `Host process listening (not Docker).` |
| R5 | nginx matches exist | ok | `nginx → {server} ({upstream}); …` (max 4 joined) |
| R6 | ufw rules exist | info | `UFW: {action} {proto} from {src}; …` (max 3 joined) |
| R7 | docker + external bind + no ufw rule | warn | `No matching UFW rule — but Docker bypasses UFW; the port may still be open externally.` |

External bind set: `{"", "0.0.0.0", "::", "*"}` (Docker SDK returns `""` for
unspecified IPv4 — treat as external).

## 10. HTTP API

- `GET /api/health` → `200 {"status": "ok"}` (used by HEALTHCHECK).
- `GET /api/catalog` → full catalog JSON (§12); recomputed per request, no cache.
- `POST /api/annotations` body `{"port": "8081", "text": "prod django"}` → `{"ok": true}`.
  Empty/whitespace text deletes the key. Invalid body → 400.
- Bearer token behavior per §7.2.
- FastAPI configured with `docs_url=None, redoc_url=None, openapi_url=None`.

## 11. Web UI

One HTML page served by `GET /` (inline template string, vanilla JS, **no CDN /
no frameworks** — must work offline on an air-gapped server).

- Dark GitHub-like palette: bg `#0d1117`, card `#161b22`, line `#30363d`,
  fg `#c9d1d9`, muted `#8b949e`, accent `#58a6ff`, ok `#3fb950`,
  warn `#d29922`, bad `#f85149`.
- Header: title + hostname + `generated_at` + "auto-refresh 30s".
- Chips row: total ports; "N exposed publicly" (red) or "nothing exposed publicly"
  (green); next 5 free ports; one red chip per collector error.
- Filter input: case-insensitive substring over the JSON of each row.
- Main content: tables grouped by compose project (alphabetical), a final group
  `host services (non-docker)`. Columns: Host port (click = copy) / `→` /
  Container port / Container (+ service, image) / Bind IP (tag: warn if external,
  ok if loopback) / UFW (yes/—) / Nginx (server name tags) / Notes + annotation.
  Notes rendered with colored level tags.
- "annotate" link per row → `prompt()` prefilled → POST → reload.
- Extra section: containers **without** published ports (name, exposed container
  ports, networks; `host network` tag when applicable).
- ALL dynamic strings HTML-escaped (host-derived data is hostile input).

## 12. Catalog JSON schema (exact keys)

```json
{
  "generated_at": "2025-01-01T12:00:00",
  "host": "srv1",
  "port_range": [8000, 9999],
  "next_free_ports": [8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090, 8091, 8092, 8093, 8094],
  "port_rows": [
    {
      "host_port": 8081,
      "bind_ip": "127.0.0.1",
      "container_port": "8000/tcp",
      "container": "blog-django-1",
      "service": "web",
      "project": "blog",
      "image": "blog:latest",
      "compose_dir": "/srv/blog",
      "origin": "docker",
      "host_network": false,
      "ufw": [{"family": "ipv4", "action": "allow", "proto": "tcp", "dst_port": "8081",
               "dst": "0.0.0.0/0", "src": "0.0.0.0/0", "direction": "in"}],
      "nginx": [{"server": "blog.example.com", "upstream": "http://127.0.0.1:8081"}],
      "annotation": "prod django",
      "notes": [{"level": "ok", "text": "Loopback-only. …"}]
    }
  ],
  "containers": [
    {"name": "blog-django-1", "id": "abc123def456", "image": "blog:latest",
     "state": "running", "host_network": false,
     "compose_project": "blog", "compose_service": "web", "compose_dir": "/srv/blog",
     "ports": [{"container_port": "8000/tcp", "host_ip": "127.0.0.1", "host_port": 8081}],
     "networks": {"bridge": "172.17.0.2"}}
  ],
  "nginx_sites": [
    {"file": "/etc/nginx/sites-enabled/blog", "server_names": ["blog.example.com"],
     "listen": [{"addr": "0.0.0.0", "port": 443, "flags": ["ssl"]}],
     "proxy_pass": ["http://127.0.0.1:8081"], "ssl": true}
  ],
  "ufw_rules": [],
  "errors": {"docker": null, "ufw": null, "nginx": null, "host_sockets": null}
}
```

Host-service rows: `container_port/container/service/project/image/compose_dir`
= `null`, `origin = "host service"`.

## 13. CLI

`python -m app.main --once [--json PATH]`

- Prints: header (host, timestamp) → per-project groups → per row:
  `host_port  bind_ip -> container_port  source  ufw=?  nginx=…`,
  then `Next free host ports: …`.
- `--json PATH` writes the full catalog JSON to PATH.
- When `--once` is present, the server must NOT start.

## 14. Packaging

### 14.1 Dockerfile requirements

- `FROM python:3.12-slim`; copy `requirements.txt` first (layer cache), then `pip
  install --no-cache-dir`, then copy `app/`.
- OCI labels: title `port-catalog`, description, `licenses=MIT`.
- `ENV PORTCATALOG_BIND=127.0.0.1 PORTCATALOG_PORT=9780`; `EXPOSE 9780`.
- HEALTHCHECK (every 30s, timeout 3s):

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:9780/api/health',timeout=2)" || exit 1
```

- `CMD ["python", "-m", "app.main"]`.
- Runs as root (required to talk to docker.sock) — document why in README.

### 14.2 `docker-compose.yml` (the tool itself) — verbatim

```yaml
services:
  port-catalog:
    build: .
    image: port-catalog:latest
    container_name: port-catalog
    restart: unless-stopped
    network_mode: host
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /etc/ufw:/etc/ufw:ro
      - /etc/nginx:/etc/nginx:ro
      - ./data:/data
    environment:
      PORTCATALOG_BIND: "127.0.0.1"
      PORTCATALOG_PORT: "9780"
      PORT_RANGE_START: "8000"
      PORT_RANGE_END: "9999"
```

### 14.3 Repo layout (deliverables)

```
port-catalog/
├── discovery.md            (this file)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt    (pytest)
├── README.md
├── LICENSE                 (MIT)
├── .gitignore              (data/, __pycache__/)
├── app/
│   ├── __init__.py
│   ├── collectors.py
│   ├── main.py
│   └── tests/
│       ├── test_ufw.py
│       ├── test_nginx.py
│       ├── test_proc.py
│       └── test_aggregation.py
└── data/                   (runtime only)
```

### 14.4 README.md must contain

Problem statement (2–3 sentences) → quick start (`docker compose up -d --build`)
→ SSH tunnel usage (`ssh -N -L 9780:127.0.0.1:9780 user@server`) → CLI example
→ env var table → security section (docker.sock = root; socket-proxy
recommendation; never expose the UI publicly; UFW-bypass explanation).

## 15. Security requirements

- S1: default bind `127.0.0.1`; docs/examples never expose it publicly.
- S2: docker.sock mounted `:ro`; socket-proxy note in README.
- S3: strictly read-only except `$DATA_DIR/annotations.json`.
- S4: HTML-escape every host-derived string in the UI.
- S5: optional bearer token (§7.2).
- S6: no secrets baked into the image.

## 16. Tests (pytest, fixture-based, no Docker/systemd required)

1. `test_ufw.py`: the tuple line from §8.2 → exact dict
   (`action="allow"`, `proto="tcp"`, `dst_port="8081"`, `src="0.0.0.0/0"`, `direction="in"`).
2. `test_nginx.py`: fixture config with (a) an `upstream` block that must NOT be
   detected as a site, (b) one server `listen 443 ssl; server_name a.com;
   proxy_pass http://127.0.0.1:8081;` with `ssl_certificate`, (c) one server
   `listen [::]:8080;`. Assert counts, names, ports, `ssl` flags, proxy_pass lists.
3. `test_proc.py`: fixture `/proc/net/tcp` lines including LISTEN (`0A`) and
   ESTABLISHED (`01`); assert only LISTEN kept; `0100007F:1F91` → `127.0.0.1:8081`.
4. `test_aggregation.py`: monkeypatch collectors with fakes → assert rows,
   note rules R1–R7, `next_free_ports` exclusions, sort order.

## 17. Acceptance criteria (manual, on a real server)

- AC1: container with `127.0.0.1:8081:8000` → row: host 8081, bind `127.0.0.1`,
  container `8000/tcp`, project from compose label, note R3.
- AC2: container with `0.0.0.0:8082:8000` → warn notes R1+R2 (+R7 if no UFW rule);
  "exposed publicly" chip counts it.
- AC3: `next_free_ports` excludes every published port, host listener, and 9780.
- AC4: an UFW allow rule for a port shows on that row and as note R6.
- AC5: nginx `proxy_pass http://127.0.0.1:8081` in a server block with
  `server_name a.com` → appears on row 8081 and as note R5.
- AC6: sshd on :22 appears under "host services", exactly once; a host listener
  that equals a published docker port does NOT create a duplicate row.
- AC7: without `/etc/ufw` mounted → app runs, `errors.ufw` is a friendly string,
  UI shows an error chip.
- AC8: POST annotation persists to `/data/annotations.json`, survives restart,
  renders in UI; empty text deletes it.
- AC9: `docker compose run --rm port-catalog python -m app.main --once --json /data/catalog.json`
  prints the table and writes the JSON.
- AC10: `/api/health` returns `{"status": "ok"}`; server binds `127.0.0.1` by default.
- AC11: a `network_mode: host` container is flagged `host_network: true` and is
  not double-counted (its sockets come from §8.4).
- AC12: with `PORTCATALOG_TOKEN` set, `/api/catalog` without the header → 401.

## 18. Implementation order (for the agent)

1. `collectors.py` + unit tests (§8, §16.1–16.3)
2. Aggregation + notes engine (§8.5, §9) + `test_aggregation.py`
3. FastAPI endpoints + CLI (§10, §13)
4. Web UI (§11)
5. Dockerfile + compose (§14)
6. README, LICENSE, .gitignore

Conventions: type hints + docstrings everywhere; conventional commits
(`feat:`, `test:`, `docs:`, `chore:`); one commit per step. Match JSON keys and
note texts EXACTLY — the UI and future consumers depend on them.

## 19. Future / v2+ (do NOT implement now)

Docker-label-based descriptions (`port-catalog.description`), Markdown export,
snapshot diffing ("what changed since yesterday"), Go rewrite (~10 MB static
binary), integrated read-only docker-socket-proxy mode, Prometheus metrics
endpoint, per-project port ranges.
