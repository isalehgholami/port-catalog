from app.collectors import parse_ufw_line


def test_tuple_line():
    r = parse_ufw_line("### tuple ### allow tcp 8081 0.0.0.0/0 any 0.0.0.0/0 in")
    assert r["action"] == "allow" and r["proto"] == "tcp" and r["dst_port"] == "8081"
    assert r["src"] == "0.0.0.0/0" and r["direction"] == "in" and r["dst"] == "0.0.0.0/0"


def test_non_tuple_ignored():
    assert parse_ufw_line("-A ufw-user-input -p tcp --dport 22 -j ACCEPT") is None
