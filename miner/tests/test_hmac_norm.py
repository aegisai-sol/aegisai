import json, os
from aegis_miner import gate, token_bridge

def _rec(store, rid, secret=None, mac=None):
    r = {"receipt_id": rid, "client_id": "t", "claims": [{"text": "Sky is blue", "vote": "TRUE"}], "credits_awarded": 1}
    r["digest"] = token_bridge.receipt_digest(r)
    m = mac if mac is not None else token_bridge.receipt_mac(r, secret) if secret else None
    if m: r["mac"] = m
    os.makedirs(store, exist_ok=True); json.dump(r, open(os.path.join(store, rid + ".json"), "w"))

def test_no_secret_no_mac_required(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    _rec(str(tmp_path), "a")
    assert gate.decide("publish", str(tmp_path), "sky is blue")["decision"] == "ALLOW"

def test_good_mac_allows(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_RECEIPT_HMAC", "t3st-secret")
    _rec(str(tmp_path), "a", secret=b"t3st-secret")
    r = gate.decide("publish", str(tmp_path), "sky is blue")
    assert r["decision"] == "ALLOW" and "t3st-secret" not in json.dumps(r)

def test_missing_mac_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_RECEIPT_HMAC", "k1")
    _rec(str(tmp_path), "a")
    assert gate.decide("publish", str(tmp_path), "sky is blue")["decision"] == "DENY"

def test_wrong_key_and_forged_mac_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_RECEIPT_HMAC", "k1")
    _rec(str(tmp_path), "a", secret=b"other")
    assert gate.decide("publish", str(tmp_path), "sky is blue")["decision"] == "DENY"
    _rec(str(tmp_path / "x"), "b", mac="hmac-sha256:" + "0" * 64)
    assert gate.decide("publish", str(tmp_path / "x"), "sky is blue")["decision"] == "DENY"

def test_mac_binds_digest():
    r = {"receipt_id": "a", "client_id": "t", "claims": [], "credits_awarded": 0}
    m = token_bridge.receipt_mac(r, b"s")
    r["mac"] = m; assert token_bridge.mac_ok(r, b"s")
    r["credits_awarded"] = 5; assert not token_bridge.mac_ok(r, b"s")

def test_norm_v2_unicode():
    assert gate.claim_digest("It\u2019s  \u201cfine\u201d.") == gate.claim_digest("it's \"fine\"")
    assert gate.claim_digest("ab\u200bc") == gate.claim_digest("abc")
    assert gate.claim_digest("Paris is the capital.", 1) == gate.claim_digest("paris is the capital", 2)

def test_norm_backcompat_v1_digest(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    s = str(tmp_path)
    r = {"receipt_id": "q", "client_id": "t", "claims": [{"text": "It\u2019s ok", "vote": "TRUE"}], "credits_awarded": 1}
    r["digest"] = token_bridge.receipt_digest(r); json.dump(r, open(os.path.join(s, "q.json"), "w"))
    assert gate.decide("cite", s, digest=gate.claim_digest("It\u2019s ok", 1))["decision"] == "ALLOW"
    assert gate.decide("cite", s, "it's ok")["decision"] == "ALLOW"
