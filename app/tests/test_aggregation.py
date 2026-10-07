import pytest
from fastapi.testclient import TestClient

from app import main


def _c(name, project, ports):
    return {"name": name, "id": "x", "image": "img", "state": "running", "host_network": False,
            "compose_project": project, "compose_service": "web", "compose_dir": None,
            "ports": [{"container_port": "8000/tcp", "host_ip": ip, "host_port": hp} for ip, hp in ports],
            "networks": {}}


@pytest.fixture
def cat(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PORT_RANGE_START", "8080")
    monkeypatch.setenv("PORT_RANGE_END", "8090")
    cs = [_c("a", "blog", [("127.0.0.1", 8081)]), _c("b", "shop", [("", 8082), ("::", 8082)])]
    monkeypatch.setattr(main, "collect_docker", lambda: (cs, None))
    monkeypatch.setattr(main, "collect_ufw", lambda: ([{"family": "ipv4", "action": "allow", "proto": "tcp",
        "dst_port": "8081", "dst": "0.0.0.0/0", "src": "1.2.3.4", "direction": "in"}], None))
    monkeypatch.setattr(main, "collect_nginx", lambda: ([{"file": "f", "server_names": ["a.com"], "listen": [],
        "proxy_pass": ["http://127.0.0.1:8081"], "ssl": False}], None))
    monkeypatch.setattr(main, "collect_host_sockets", lambda: ([
        {"proto": "tcp", "bind_ip": "0.0.0.0", "port": 22},
        {"proto": "tcp6", "bind_ip": "::", "port": 22},
        {"proto": "tcp", "bind_ip": "127.0.0.1", "port": 8081},
        {"proto": "udp", "bind_ip": "0.0.0.0", "port": 8080}], None))
    return main.build_catalog()


def test_rows_and_order(cat):
    assert [(r["host_port"], r["origin"]) for r in cat["port_rows"]] == [
        (8081, "docker"), (8082, "docker"), (22, "host service")]


def test_notes(cat):
    blog, shop, ssh = cat["port_rows"]
    t = [n["text"] for n in blog["notes"]]
    assert t[0].startswith("Loopback-only") and any(x.startswith("nginx → a.com") for x in t)
    assert any(x.startswith("UFW: allow tcp from 1.2.3.4") for x in t)
    assert [n["level"] for n in shop["notes"]] == ["warn", "info", "warn"]
    assert shop["notes"][0]["text"].startswith("Published on 0.0.0.0 — reachable")
    assert shop["notes"][2]["text"].startswith("No matching UFW rule")
    assert ssh["notes"][0]["text"] == "Host process listening (not Docker)."


def test_free_ports(cat):
    assert cat["next_free_ports"] == [8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090]


def test_api_token_and_annotation(cat, monkeypatch):
    monkeypatch.setenv("PORTCATALOG_TOKEN", "s3")
    c = TestClient(main.app)
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/api/catalog").status_code == 401
    h = {"Authorization": "Bearer s3"}
    assert c.post("/api/annotations", json={"port": "8081", "text": "prod"}, headers=h).json() == {"ok": True}
    assert c.get("/api/catalog", headers=h).json()["port_rows"][0]["annotation"] == "prod"
    c.post("/api/annotations", json={"port": "8081", "text": " "}, headers=h)
    assert c.get("/api/catalog", headers=h).json()["port_rows"][0]["annotation"] is None
    assert c.post("/api/annotations", json={"port": "x"}, headers=h).status_code == 400
