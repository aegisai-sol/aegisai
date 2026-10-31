import json, os, threading, urllib.request
from http.server import ThreadingHTTPServer
import pytest
from aegis_miner import gate, coordinator, token_bridge

def _rec(store, rid, claims, flagged=False, tamper=False):
    r = {"receipt_id": rid, "client_id": "t", "claims": claims, "credits_awarded": 1, "flagged": flagged}
    r["digest"] = token_bridge.receipt_digest(r)
    if tamper: r["claims"][0]["vote"] = "TRUE"
    os.makedirs(store, exist_ok=True); json.dump(r, open(os.path.join(store, rid + ".json"), "w"))

def test_digest_normalizes():
    assert gate.claim_digest("Paris is  the capital.") == gate.claim_digest("paris is the capital")

def test_decisions(tmp_path):
    s = str(tmp_path)
    assert gate.decide("publish", s, "x is y")["decision"] == "REQUIRE_RECEIPT"
    _rec(s, "a", [{"text": "Water boils at 100 C.", "vote": "TRUE"}, {"text": "Moon is cheese.", "vote": "FALSE"}, {"text": "Maybe.", "vote": "UNSURE"}])
    r = gate.decide("publish claim", s, "water boils at 100 c")
    assert r["decision"] == "ALLOW" and r["receipt_id"] == "a"
    assert gate.decide("post", s, "Moon is cheese")["decision"] == "DENY"
    assert gate.decide("cite", s, "Maybe")["decision"] == "REQUIRE_RECEIPT"
    assert gate.decide("publish", s, digest=gate.claim_digest("Water boils at 100 C"))["decision"] == "ALLOW"

def test_flagged_and_tampered_and_canary(tmp_path):
    s = str(tmp_path)
    _rec(s, "f", [{"text": "A is B", "vote": "TRUE"}], flagged=True)
    _rec(s, "c", [{"text": "C is D", "vote": "TRUE", "canary": True}])
    assert gate.decide("publish", s, "A is B")["decision"] == "REQUIRE_RECEIPT"
    assert gate.decide("publish", s, "C is D")["decision"] == "REQUIRE_RECEIPT"
    _rec(s, "t", [{"text": "E is F", "vote": "FALSE"}], tamper=True)
    r = gate.decide("publish", s, "E is F"); assert r["decision"] == "DENY" and "tampered" in r["reason"]

def test_bad_input(tmp_path):
    with pytest.raises(ValueError): gate.decide("mint", str(tmp_path), "x")
    with pytest.raises(ValueError): gate.decide("publish", str(tmp_path))
    with pytest.raises(ValueError): gate.decide("publish", str(tmp_path), digest="zz")

def test_http(tmp_path, monkeypatch):
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path))
    _rec(str(tmp_path), "h", [{"text": "Sky is blue", "vote": "TRUE"}])
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    u = f"http://127.0.0.1:{s.server_port}/v1/gate"
    def post(b):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, json.dumps(b).encode(), {"Content-Type": "application/json"})))
        except urllib.error.HTTPError as e: return e.code
    assert post({"action": "publish", "claim": "sky is blue."})["decision"] == "ALLOW"
    assert post({"action": "publish", "claim": "grass is red"})["decision"] == "REQUIRE_RECEIPT"
    assert post({"action": "mint", "claim": "x"}) == 400
    s.shutdown()

def test_ttl(tmp_path, monkeypatch):
    s = str(tmp_path); _rec(s, "old", [{"text": "Old fact", "vote": "TRUE"}])
    r = json.load(open(os.path.join(s, "old.json"))); r["ts"] = 1000; r["digest"] = token_bridge.receipt_digest(r)
    json.dump(r, open(os.path.join(s, "old.json"), "w"))
    assert gate.decide("publish", s, "old fact", now=2000)["decision"] == "ALLOW"
    monkeypatch.setenv("AEGIS_RECEIPT_TTL", "500")
    x = gate.decide("publish", s, "old fact", now=2000); assert x["decision"] == "REQUIRE_RECEIPT" and x["matches"][0]["expired"]
    assert gate.decide("publish", s, "old fact", now=1400)["decision"] == "ALLOW"

def test_batch(tmp_path):
    s = str(tmp_path); _rec(s, "b", [{"text": "P", "vote": "TRUE"}, {"text": "Q", "vote": "FALSE"}])
    assert gate.decide_batch("publish", s, ["P"])["decision"] == "ALLOW"
    assert gate.decide_batch("publish", s, ["P", "unknown"])["decision"] == "REQUIRE_RECEIPT"
    r = gate.decide_batch("publish", s, ["P", "unknown", "digest:" + gate.claim_digest("Q")]); assert r["decision"] == "DENY" and r["count"] == 3
    with pytest.raises(ValueError): gate.decide_batch("publish", s, [])
    with pytest.raises(ValueError): gate.decide_batch("publish", s, ["x"] * 51)
