import json, threading, urllib.request, urllib.error
import pytest
from aegis_miner import token_bridge

def _rec(rid, nonce=None, secret=None):
    r = {"receipt_id": rid, "client_id": "t", "claims": [], "credits_awarded": 1, "nonce": nonce or f"nonce-{rid}",
         "ts": 1.0, "protocol_version": "pov-r/1"}
    r["digest"] = token_bridge.receipt_digest(r)
    if secret: r["mac"] = token_bridge.receipt_mac(r, secret)
    return r

@pytest.fixture(autouse=True)
def _nokey(monkeypatch): monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)

def test_all_intact():
    a = token_bridge.audit_batch([_rec("a1"), _rec("b2")])
    assert a["all_intact"] and a["count"] == 2 and a["intact_count"] == 2 and [x["index"] for x in a["results"]] == [0, 1]

def test_tampered_item_isolated():
    bad = _rec("b2"); bad["credits_awarded"] = 9
    a = token_bridge.audit_batch([_rec("a1"), bad])
    assert not a["all_intact"] and a["intact_count"] == 1 and a["results"][0]["intact"] and not a["results"][1]["digest_ok"]

def test_malformed_item_gets_error_not_raise():
    a = token_bridge.audit_batch([_rec("a1"), {"receipt_id": 5}, None])
    assert a["count"] == 3 and a["intact_count"] == 1 and "error" in a["results"][1] and "error" in a["results"][2]

def test_duplicate_id_flagged_second_only():
    r = _rec("a1"); a = token_bridge.audit_batch([r, dict(r)])
    assert a["results"][0]["intact"] and not a["results"][1]["intact"] and a["results"][1]["duplicate"]
    assert a["duplicate_ids"] == ["a1"] and not a["all_intact"]

def test_duplicate_nonce_across_ids_flagged():
    a = token_bridge.audit_batch([_rec("a1", "shared-nonce"), _rec("b2", "shared-nonce")])
    assert a["results"][1]["duplicate"] and a["duplicate_nonces_count"] == 1 and a["intact_count"] == 1

def test_limits():
    for bad in (None, [], {"x": 1}, "s"):
        with pytest.raises(ValueError): token_bridge.audit_batch(bad)
    with pytest.raises(ValueError): token_bridge.audit_batch([_rec(f"r{i}") for i in range(51)])
    assert token_bridge.audit_batch([_rec(f"r{i}") for i in range(50)])["count"] == 50

def test_mac_checked_per_item_and_secret_not_leaked():
    a = token_bridge.audit_batch([_rec("a1", secret=b"s3cret"), _rec("b2")], secret=b"s3cret")
    assert a["results"][0]["mac"] == "valid" and a["results"][1]["mac"] == "missing" and a["intact_count"] == 1
    assert "s3cret" not in json.dumps(a)

def test_store_forgery_detected(tmp_path):
    r = _rec("abc1"); json.dump(r, open(tmp_path / "abc1.json", "w"))
    f = dict(r, credits_awarded=50); f["digest"] = token_bridge.receipt_digest(f)
    a = token_bridge.audit_batch([r, _rec("zz9")], store_dir=str(tmp_path))
    assert a["results"][0]["known"] is True and a["results"][1]["known"] is None
    assert token_bridge.audit_batch([f], store_dir=str(tmp_path))["results"][0]["known"] is False

@pytest.fixture
def server(tmp_path, monkeypatch):
    from aegis_miner import coordinator
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path))
    from http.server import ThreadingHTTPServer
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s
    s.shutdown()

def _post(s, body):
    req = urllib.request.Request(f"http://127.0.0.1:{s.server_address[1]}/v1/receipts/verify", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, json.load(e)

def test_http_batch(server):
    st, b = _post(server, {"receipts": [_rec("a1"), _rec("a1")]})
    assert st == 200 and b["count"] == 2 and b["duplicate_ids"] == ["a1"]
    st, b = _post(server, {"receipts": []}); assert st == 400
    st, b = _post(server, {"receipt": _rec("a1")}); assert st == 200 and b["intact"]
