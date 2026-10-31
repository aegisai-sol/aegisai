import json, threading, urllib.request, pytest
from http.server import ThreadingHTTPServer
from aegis_miner import consensus as c, coordinator as co
from aegis_miner.consensus import PeerHealth, _env_floor

def test_floor_lifts_dissenter_not_dead():
    h = PeerHealth(weight_floor=0.5)
    for _ in range(4): h.observe_vote("a", False)
    b = h.breakdown("a"); assert b["weight"] == 0.5 and b["floored"] and b["dissent"] == 1/16
    for _ in range(3): h.observe("a", False)
    b = h.breakdown("a"); assert b["weight"] == 0.0 and not b["floored"]
    assert PeerHealth().weight_floor == 0.0 and PeerHealth().breakdown("x")["floored"] is False
    h2 = PeerHealth(weight_floor=0.5)
    for _ in range(10): h2.observe("b", True)
    assert h2.weight("b") == 2.0 and not h2.breakdown("b")["floored"]

def test_floor_validation_and_env():
    for bad in (-0.1, 1.5, True, "0.5", float("nan")):
        with pytest.raises(ValueError): PeerHealth(weight_floor=bad)
    assert _env_floor(env={}) == 0.0
    assert _env_floor(env={"AEGIS_WEIGHT_FLOOR": "0.25"}) == 0.25
    assert _env_floor(env={"AEGIS_WEIGHT_FLOOR": "7"}) == 1.0
    for bad in ("-1", "abc", "inf", "nan"): assert _env_floor(env={"AEGIS_WEIGHT_FLOOR": bad}) == 0.0
    assert "weight_floor" in PeerHealth(weight_floor=0.3).summary([])

def test_health_peer_weights_ids_only(monkeypatch):
    monkeypatch.setenv("AEGIS_PEERS", "http://p1:8787,http://p2:8787")
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        h = json.load(urllib.request.urlopen(f"http://127.0.0.1:{s.server_port}/v1/health"))
        pw = h["peer_weights"]; assert set(pw) == {"peer0", "peer1"}
        assert set(pw["peer0"]) >= {"bonus", "fade", "dissent", "weight", "alive", "floored"}
        assert "p1:" not in json.dumps(h)
    finally: s.shutdown()

def test_weights_used_snapshot():
    h = PeerHealth()
    def nf(nid, ep):
        return c.local_node(nid)
    rec = c.consensus_alive("https://example.com", "x", ["http://a"], health=h, node_factory=nf, weighted=True)
    assert rec.get("weights_used", {}).get("self") == 1.0 and "peer0" in rec["weights_used"]
    rec2 = c.consensus_alive("https://example.com", "x", ["http://a"], health=h, node_factory=nf, weighted=False)
    assert "weights_used" not in rec2
