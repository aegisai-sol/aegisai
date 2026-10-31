import json, os
from aegis_miner import gate, token_bridge

def _rec(store, rid, text, vote="TRUE", nonce=None, ts=1000.0):
    r = {"receipt_id": rid, "client_id": "t", "ts": ts, "claims": [{"text": text, "vote": vote}], "credits_awarded": 1}
    if nonce: r["nonce"] = nonce
    r["digest"] = token_bridge.receipt_digest(r)
    os.makedirs(store, exist_ok=True); json.dump(r, open(os.path.join(store, rid + ".json"), "w")); return r

def test_digest_binds_nonce_and_ts():
    r = {"receipt_id": "a", "client_id": "c", "claims": [], "credits_awarded": 0, "ts": 1.0}
    legacy = token_bridge.receipt_digest(r)
    assert token_bridge.receipt_digest(dict(r, ts=2.0)) == legacy  # legacy receipts unchanged
    n = dict(r, nonce="abcdefgh")
    assert token_bridge.receipt_digest(n) != legacy
    assert token_bridge.receipt_digest(dict(n, ts=9e9)) != token_bridge.receipt_digest(n)

def test_ts_edit_on_nonce_receipt_is_tamper(tmp_path):
    s = str(tmp_path); r = _rec(s, "a", "Fresh fact", nonce="nonce-0001")
    r["ts"] = 9e9; json.dump(r, open(os.path.join(s, "a.json"), "w"))
    assert gate.decide("publish", s, "fresh fact")["decision"] == "DENY"

def test_nonce_binding(tmp_path):
    s = str(tmp_path); _rec(s, "a", "Sky is blue", nonce="nonce-aaaa"); _rec(s, "b", "Grass is green")
    assert gate.decide("publish", s, "sky is blue", nonce="nonce-aaaa")["decision"] == "ALLOW"
    assert gate.decide("publish", s, "sky is blue", nonce="nonce-bbbb")["decision"] == "REQUIRE_RECEIPT"
    assert gate.decide("publish", s, "grass is green", nonce="nonce-aaaa")["decision"] == "REQUIRE_RECEIPT"
    assert gate.decide("publish", s, "grass is green")["decision"] == "ALLOW"
    import pytest
    with pytest.raises(ValueError): gate.decide("publish", s, "x", nonce="bad nonce!")

def test_duplicate_nonce_is_replay(tmp_path):
    s = str(tmp_path); _rec(s, "a", "X is Y", nonce="dup-nonce-1"); _rec(s, "b", "X is Y", nonce="dup-nonce-1")
    r = gate.decide("pay", s, "x is y"); assert r["decision"] == "DENY" and "replay" in r["reason"]
    assert gate.nonce_owners(s, "dup-nonce-1") == {"a", "b"}

def test_verify_http_nonce(tmp_path, monkeypatch):
    import threading, urllib.request
    from http.server import ThreadingHTTPServer
    from aegis_miner import coordinator, verify
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path)); monkeypatch.setattr(coordinator, "CREDITS", str(tmp_path / "cr"), raising=False)
    monkeypatch.setattr(verify, "check_claim", lambda c, **k: {"vote": "UNSURE"})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    def post(b):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/v1/verify", json.dumps(b).encode())))
        except urllib.error.HTTPError as e: return e.code
    try:
        r = post({"text": "Water is wet.", "nonce": "client-nonce-1"})
        assert r["nonce"] == "client-nonce-1" and r["digest"] == token_bridge.receipt_digest(r)
        assert post({"text": "Water is wet.", "nonce": "client-nonce-1"}) == 409
        assert post({"text": "Water is wet.", "nonce": "x"}) == 400
        assert len(post({"text": "Water is wet."})["nonce"]) == 32
    finally: srv.shutdown()
