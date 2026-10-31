import json, threading, urllib.request, urllib.error
import pytest
from aegis_miner import token_bridge, coordinator

def _rec(rid="abc1", secret=None):
    r = {"receipt_id": rid, "client_id": "secret-client", "ts": 1.0, "nonce": "nonce-1234",
         "claims": [{"text": "Sky is blue", "vote": "TRUE", "evidence": "private"}, {"text": "x", "vote": "false"},
                    {"text": "y"}, {"text": "canary", "vote": "TRUE", "canary": True}],
         "credits_awarded": 1, "calibration": {"ok": True, "failed": []}, "flagged": False,
         "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r)
    if secret: r["mac"] = token_bridge.receipt_mac(r, secret)
    return r

def test_proof_tally_excludes_canaries(monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    p = token_bridge.receipt_proof(_rec())
    assert p["claim_count"] == 3 and p["votes"] == {"FALSE": 1, "TRUE": 1, "UNSURE": 1}
    assert p["audit"]["intact"] and p["calibration_ok"] is True and p["nonce"] == "nonce-1234"

def test_proof_leaks_nothing_private():
    r = _rec(secret=b"k"); p = token_bridge.receipt_proof(r, secret=b"k")
    blob = json.dumps(p)
    for s in ("secret-client", "Sky is blue", "private", r["mac"]): assert s not in blob
    assert p["mac_present"] and p["audit"]["mac"] == "valid"

def test_proof_flags_tamper(monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    r = _rec(); r["credits_awarded"] = 99
    assert not token_bridge.receipt_proof(r)["audit"]["intact"]

def test_proof_rejects_non_receipt():
    with pytest.raises(ValueError): token_bridge.receipt_proof(["x"])

@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path))
    (tmp_path / "abc1.json").write_text(json.dumps(_rec()))
    (tmp_path / "bad1.json").write_text("{not json")
    from http.server import ThreadingHTTPServer
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()

def _get(u):
    try:
        with urllib.request.urlopen(u) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())

def test_http_proof(srv):
    c, b = _get(srv + "/v1/receipts/abc1/proof")
    assert c == 200 and b["receipt_id"] == "abc1" and b["audit"]["intact"]
    assert "client_id" not in b and b["claim_count"] == 3

def test_http_proof_404_and_traversal(srv):
    assert _get(srv + "/v1/receipts/nope/proof")[0] == 404
    assert _get(srv + "/v1/receipts/..%2Fabc1/proof")[0] == 404
    assert _get(srv + "/v1/receipts/bad1/proof")[0] == 500

def test_single_receipt_route_still_works(srv):
    c, b = _get(srv + "/v1/receipts/abc1")
    assert c == 200 and b["client_id"] == "secret-client"

def test_openapi_lists_proof():
    assert "/v1/receipts/{id}/proof" in coordinator.OPENAPI["paths"]
