from app.collectors import parse_nginx

CONF = """
upstream backend { server 127.0.0.1:9000; }
server {
    listen 443 ssl;
    server_name a.com;
    ssl_certificate /x.crt;
    location / { proxy_pass http://127.0.0.1:8081; }
}
server {
    listen [::]:8080;
}
"""


def test_sites():
    s = parse_nginx(CONF)
    assert len(s) == 2
    a, b = s
    assert a["server_names"] == ["a.com"] and a["ssl"] is True
    assert a["listen"] == [{"addr": "0.0.0.0", "port": 443, "flags": ["ssl"]}]
    assert a["proxy_pass"] == ["http://127.0.0.1:8081"]
    assert b["listen"][0]["addr"] == "::" and b["listen"][0]["port"] == 8080
    assert b["ssl"] is False and b["proxy_pass"] == []
