# port-catalog

One server, many docker-compose stacks, a non-dockerized nginx in front: nobody remembers which host port belongs to which project. **port-catalog** is a tiny, read-only tool that merges Docker publish mappings, UFW rules, nginx server blocks and raw host sockets into one page, and suggests the next free host ports.

Web UI, JSON API and a one-shot CLI. No database, no CDN, works offline.

## Quick start

**Docker (recommended on the server)**

```bash
docker compose up -d --build
ssh -N -L 9780:127.0.0.1:9780 user@server   # from your laptop
# open http://127.0.0.1:9780
```

**No image, just [uv](https://docs.astral.sh/uv/)**

```bash
./run.sh            # serve the UI on 127.0.0.1:9780
./run.sh --once     # print the catalog and exit
./run.sh --demo     # try the UI with sample data (no Docker needed)
```

`run.sh` needs no install step: uv fetches the three dependencies on the fly. It reads `/etc/ufw`, `/etc/nginx` and the Docker socket directly, so run it as a user that can read them (usually root or `sudo ./run.sh`).

## CLI

```bash
docker compose run --rm port-catalog python -m app.main --once --json /data/catalog.json
```

Prints the ports grouped by compose project plus the next free host ports, and writes the full catalog JSON to the given path.

## API

| Endpoint | |
|---|---|
| `GET /api/health` | `{"status": "ok"}` (never needs the token) |
| `GET /api/catalog` | full catalog, recomputed on every request |
| `POST /api/annotations` | `{"port": "8081", "text": "prod django"}`; empty text deletes the note |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PORTCATALOG_BIND` | `127.0.0.1` | bind address |
| `PORTCATALOG_PORT` | `9780` | port; also excluded from suggestions |
| `UFW_DIR` | `/etc/ufw` | host UFW config mount |
| `NGINX_DIR` | `/etc/nginx` | host nginx config mount |
| `DATA_DIR` | `/data` | where `annotations.json` is stored |
| `PORT_RANGE_START` / `PORT_RANGE_END` | `8000` / `9999` | range used for suggestions and the port map |
| `PORTCATALOG_TOKEN` | unset | if set, `/api/catalog` and `/api/annotations` need `Authorization: Bearer <token>`. The page asks for it when needed. |

If UFW or nginx aren't mounted the app still runs; the missing source shows up as a red chip.

## Security

- **docker.sock is root.** Anyone who can talk to it controls the host. It is mounted `:ro`, but that only makes the socket file read-only, not the API. For hardening, point `DOCKER_HOST` at a read-only [docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) (allow `CONTAINERS=1` only). The container runs as root because the socket requires it.
- **Docker bypasses UFW.** Published ports go through iptables' `DOCKER` chain, so a port can be reachable from outside with no UFW allow rule. The UI warns on every external bind. Prefer `ports: ["127.0.0.1:8081:8000"]` plus `proxy_pass http://127.0.0.1:8081;`. Never use container IPs as upstreams; they change on recreate.
- **Don't expose the UI publicly.** It lists your whole attack surface. It binds `127.0.0.1` by default; use an SSH tunnel.
- `pid: host` is set in the compose file so the tool can read `/proc/<pid>/fd` and name the process behind each host port (nginx, postgres, sshd…). It only reads; if you'd rather not share the PID namespace, remove it and ports fall back to a guess from the port number.
- The only file written is `$DATA_DIR/annotations.json`.

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python -m app.main --demo
```

## Notes on the spec

- `/api/health` is exempt from the bearer token so the image HEALTHCHECK keeps working.
- The same container mapping published on both IPv4 and IPv6 is shown once.
- The catalog carries one extra key, `used_ports`, which feeds the port map in the UI.
- `--demo` is an addition for trying the UI without a Docker host.
