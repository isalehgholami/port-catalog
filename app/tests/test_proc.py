from app.collectors import parse_proc_net

TCP = """  sl  local_address rem_address   st tx_queue rx_queue
   0: 0100007F:1F91 00000000:0000 0A 00000000:00000000 00:00000000 00000000
   1: 0100007F:1F92 0100007F:C000 01 00000000:00000000 00:00000000 00000000
"""
TCP6 = """  sl  local_address rem_address   st
   0: 00000000000000000000000001000000:1F90 00000000000000000000000000000000:0000 0A
"""


def test_only_listen_kept():
    rows = parse_proc_net(TCP, "tcp")
    assert rows == [{"proto": "tcp", "bind_ip": "127.0.0.1", "port": 8081}]


def test_ipv6_loopback():
    assert parse_proc_net(TCP6, "tcp6")[0]["bind_ip"] == "::1"


def test_udp_keeps_all():
    assert len(parse_proc_net(TCP, "udp")) == 2
