"""Sample data so the UI can be tried without Docker, UFW or nginx (``--demo``)."""
from __future__ import annotations

import os
import tempfile


def _c(name, project, service, image, ports, host_network=False):
    return {
        "name": name, "id": "abc123def456", "image": image, "state": "running",
        "host_network": host_network, "compose_project": project,
        "compose_service": service, "compose_dir": f"/srv/{project}" if project else None,
        "ports": [{"container_port": cp, "host_ip": ip, "host_port": hp} for cp, ip, hp in ports],
        "networks": {"bridge": "172.17.0.2"},
    }


def install(main) -> None:
    """Replace the collectors on the given main module with static fakes."""
    os.environ.setdefault("DATA_DIR", os.path.join(tempfile.gettempdir(), "port-catalog-demo"))
    containers = [
        _c("blog-django-1", "blog", "web", "blog:latest", [("8000/tcp", "127.0.0.1", 8081)]),
        _c("blog-redis-1", "blog", "redis", "redis:7", [("6379/tcp", None, None)]),
        _c("shop-django-1", "shop", "web", "shop:2.4", [("8000/tcp", "", 8082)]),
        _c("shop-django-2", "shop", "admin", "shop:2.4", [("8000/tcp", "127.0.0.1", 8083)]),
        _c("wiki-app-1", "wiki", "app", "wikijs:2", [("3000/tcp", "0.0.0.0", 8090)]),
        _c("grafana", None, None, "grafana/grafana", [("3000/tcp", "127.0.0.1", 8095)]),
        _c("node-exporter", None, None, "prom/node-exporter", [], host_network=True),
    ]
    ufw = [{"family": "ipv4", "action": "allow", "proto": "tcp", "dst_port": "8090",
            "dst": "0.0.0.0/0", "src": "10.0.0.0/8", "direction": "in"},
           {"family": "ipv4", "action": "limit", "proto": "tcp", "dst_port": "22",
            "dst": "0.0.0.0/0", "src": "0.0.0.0/0", "direction": "in"}]
    sites = [
        {"file": "/etc/nginx/sites-enabled/blog", "server_names": ["blog.example.com"],
         "listen": [{"addr": "0.0.0.0", "port": 443, "flags": ["ssl"]}],
         "proxy_pass": ["http://127.0.0.1:8081"], "ssl": True},
        {"file": "/etc/nginx/sites-enabled/shop", "server_names": ["shop.example.com", "www.shop.example.com"],
         "listen": [{"addr": "0.0.0.0", "port": 443, "flags": ["ssl"]}],
         "proxy_pass": ["http://127.0.0.1:8082"], "ssl": True},
    ]
    socks = [{"proto": "tcp", "bind_ip": "0.0.0.0", "port": 22},
             {"proto": "tcp6", "bind_ip": "::", "port": 22},
             {"proto": "tcp", "bind_ip": "0.0.0.0", "port": 443},
             {"proto": "tcp", "bind_ip": "127.0.0.1", "port": 5432},
             {"proto": "tcp", "bind_ip": "0.0.0.0", "port": 9100},
             {"proto": "tcp", "bind_ip": "127.0.0.1", "port": 9780},
             {"proto": "udp", "bind_ip": "0.0.0.0", "port": 8084}]
    main.collect_docker = lambda: (containers, None)
    main.collect_ufw = lambda: (ufw, None)
    main.collect_nginx = lambda: (sites, None)
    main.collect_host_sockets = lambda: (socks, None)
