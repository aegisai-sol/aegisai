import json, threading, urllib.request, pytest
from aegis_miner import gate, consensus
from test_nonce_replay import _rec

def test_batch_nonce_binding(tmp_path):
    s = str(tmp_path); _rec(s, "a", "Sky is blue", nonce="nonce-aaaa"); _rec(s, "b", "Grass is green")
    assert gate.decide_batch("publish", s, ["sky is blue"], nonce="nonce-aaaa")["decision"] == "ALLOW"
    r = gate.decide_batch("publish", s, ["sky is blue", "grass is green"], nonce="nonce-aaaa")
    assert r["decision"] == "REQUIRE_RECEIPT" and r["nonce"] == "nonce-aaaa"
    assert gate.decide_batch("publish", s, ["sky is blue", "grass is green"])["decision"] == "ALLOW"
    with pytest.raises(ValueError): gate.decide_batch("publish", s, ["x"], nonce="bad!")

def test_batch_duplicate_nonce_deny(tmp_path):
    s = str(tmp_path); _rec(s, "a", "Sky is blue", nonce="nonce-dupe"); _rec(s, "b", "Sky is blue", nonce="nonce-dupe")
    r = gate.decide_batch("publish", s, ["sky is blue"], nonce="nonce-dupe")
    assert r["decision"] == "DENY" and "replay" in r["results"][0]["reason"]
    assert gate.decide_batch("publish", s, ["sky is blue"])["decision"] == "DENY"

def test_batch_http_nonce(tmp_path, monkeypatch):
    from aegis_miner import coordinator
    s = str(tmp_path); _rec(s, "a", "Sky is blue", nonce="nonce-aaaa")
    monkeypatch.setattr(coordinator, "RECEIPTS", s)
    from http.server import HTTPServer
    srv = HTTPServer(("127.0.0.1", 0), coordinator.H if hasattr(coordinator, "H") else coordinator.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    def post(body):
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/v1/gate/batch", json.dumps(body).encode(), {"Content-Type": "application/json"})
        try: return 200, json.loads(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
    try:
        r0 = post({"action": "publish", "claims": ["sky is blue"], "nonce": "nonce-aaaa"}); assert r0[1].get("decision") == "ALLOW", r0
        assert post({"action": "publish", "claims": ["sky is blue"], "nonce": "nonce-zzzz"})[1]["decision"] == "REQUIRE_RECEIPT"
        assert post({"action": "publish", "claims": ["sky is blue"], "nonce": "bad!"})[0] == 400
    finally: srv.shutdown()

def test_peer_compat():
    e = ("pov-r/1", 1)
    assert consensus.peer_compat({"ok": True, "protocol_version": "pov-r/1", "claim_schema": 1}, e) == (True, None)
    assert consensus.peer_compat({"ok": True}, e) == (True, None)  # legacy
    assert consensus.peer_compat({"protocol_version": "pov-r/2"}, e) == (False, "protocol_mismatch")
    assert consensus.peer_compat({"protocol_version": "pov-r/1", "claim_schema": 2}, e) == (False, "claim_schema_mismatch")

def test_ping_refuses_mismatch_and_marks_dead():
    hs = {"a": {"ok": True, "protocol_version": "pov-r/1", "claim_schema": 1}, "b": {"ok": True, "protocol_version": "pov-r/9"}}
    res = consensus.ping_peers(["a", "b"], getter=lambda e, t: hs[e], expect=("pov-r/1", 1))
    assert res[0]["ok"] and not res[1]["ok"] and res[1]["error"] == "protocol_mismatch"
    ph = consensus.PeerHealth(1, 1); ph.observe_pings(["a", "b"], res)
    assert ph.alive_endpoints(["a", "b"]) == ["a"]

def test_health_advertises_schema():
    from aegis_miner import coordinator
    h = coordinator.health()
    assert h["protocol_version"] == coordinator.PROTOCOL_VERSION and h["claim_schema"] == coordinator.CLAIM_SCHEMA
