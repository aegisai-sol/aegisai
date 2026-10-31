import json, os, threading, urllib.request, urllib.error
import pytest
from aegis_miner import token_bridge

def _rec(rid="abc1", secret=None):
    r = {"receipt_id": rid, "client_id": "t", "claims": [{"text": "Sky is blue", "vote": "TRUE"}], "credits_awarded": 1,
         "nonce": "nonce-1234", "ts": 1.0, "protocol_version": "pov-r/1"}
    r["digest"] = token_bridge.receipt_digest(r)
    if secret: r["mac"] = token_bridge.receipt_mac(r, secret)
    return r

def test_clean_receipt_no_key(monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    a = token_bridge.audit_receipt(_rec())
    assert a["intact"] and a["digest_ok"] and a["mac"] == "absent" and a["known"] is None

def test_tampered_credits_detected(monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    r = _rec(); r["credits_awarded"] = 99
    a = token_bridge.audit_receipt(r)
    assert not a["intact"] and not a["digest_ok"]

def test_tampered_ts_on_nonce_receipt_detected(monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    r = _rec(); r["ts"] = 999.0
    assert not token_bridge.audit_receipt(r)["digest_ok"]

def test_mac_states():
    good = _rec(secret=b"k")
    assert token_bridge.audit_receipt(good, secret=b"k")["mac"] == "valid"
    assert token_bridge.audit_receipt(good, secret=b"other")["mac"] == "invalid"
    assert token_bridge.audit_receipt(_rec(), secret=b"k")["mac"] == "missing"
    assert not token_bridge.audit_receipt(_rec(), secret=b"k")["intact"]

def test_unchecked_when_no_key_but_mac_present(monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    a = token_bridge.audit_receipt(_rec(secret=b"k"))
    assert a["mac"] == "unchecked" and a["intact"]

def test_known_store_match_and_mismatch(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    r = _rec("abc1"); json.dump(r, open(tmp_path / "abc1.json", "w"))
    assert token_bridge.audit_receipt(r, store_dir=str(tmp_path))["known"] is True
    # self-consistent forgery reusing a real id: digest recomputes but differs from stored copy
    f = dict(r, credits_awarded=50); f.pop("digest"); f["digest"] = token_bridge.receipt_digest(f)
    a = token_bridge.audit_receipt(f, store_dir=str(tmp_path))
    assert a["digest_ok"] and a["known"] is False and not a["intact"]
    assert token_bridge.audit_receipt(_rec("zz9"), store_dir=str(tmp_path))["known"] is None

def test_path_traversal_id_not_looked_up(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    r = _rec("../etc"); assert token_bridge.audit_receipt(r, store_dir=str(tmp_path))["known"] is None

def test_bad_input():
    for bad in (None, [], {"digest": "x"}, {"receipt_id": 5}):
        with pytest.raises(ValueError): token_bridge.audit_receipt(bad)

def test_secret_never_returned():
    assert "s3cret" not in json.dumps(token_bridge.audit_receipt(_rec(secret=b"s3cret"), secret=b"s3cret"))

@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    from aegis_miner import coordinator
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path))
    from http.server import ThreadingHTTPServer
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s, tmp_path
    s.shutdown()

def _post(s, body):
    req = urllib.request.Request(f"http://127.0.0.1:{s.server_address[1]}/v1/receipts/verify", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, json.load(e)

def test_http_endpoint(server):
    s, d = server
    r = _rec("abc1"); json.dump(r, open(d / "abc1.json", "w"))
    code, a = _post(s, {"receipt": r}); assert code == 200 and a["intact"] and a["known"] is True
    code, a = _post(s, r); assert code == 200 and a["intact"]  # bare body also accepted
    code, a = _post(s, {"receipt": dict(r, credits_awarded=7)}); assert code == 200 and not a["intact"]
    code, a = _post(s, {"receipt": {"nope": 1}}); assert code == 400

def test_openapi_lists_endpoint():
    from aegis_miner import coordinator
    assert "/v1/receipts/verify" in json.dumps(coordinator.OPENAPI)
