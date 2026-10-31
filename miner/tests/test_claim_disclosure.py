import json, threading, urllib.request, urllib.error
import pytest
from aegis_miner import claim_merkle as cm, token_bridge, coordinator

def _rec(n=5, rid="r1"):
    claims = [{"text": f"claim {i}", "vote": ["TRUE", "FALSE", "UNSURE"][i % 3], "evidence": f"ev-{i}-private"} for i in range(n)]
    claims.insert(1, {"text": "canary", "vote": "TRUE", "canary": True})
    r = {"receipt_id": rid, "client_id": "cid-secret", "ts": 1.0, "claims": claims, "credits_awarded": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 13])
def test_every_leaf_verifies(n):
    r = _rec(n); root = cm.claims_root(r)
    for i in range(n):
        d = cm.disclose(r, i); v = cm.verify_disclosure(d, root)
        assert v["ok"] and v["root_source"] == "expected" and d["leaf_count"] == n

def test_canaries_excluded_and_privacy():
    r = _rec(4); d = cm.disclose(r, 0); blob = json.dumps(d)
    assert d["leaf_count"] == 4 and "canary" not in blob
    for s in ("cid-secret", "ev-0-private", "claim 1", "claim 2"): assert s not in blob

def test_tamper_detected():
    r = _rec(5); root = cm.claims_root(r); d = cm.disclose(r, 2)
    for mut in (lambda x: x["claim"].update(vote="TRUE" if x["claim"]["vote"] != "TRUE" else "FALSE"),
                lambda x: x["claim"].update(text="forged"), lambda x: x.update(index=3),
                lambda x: x.update(salt="0" * 64), lambda x: x["path"].pop(),
                lambda x: x["path"].append({"side": "R", "hash": "a" * 64}),
                lambda x: x["path"][0].update(side="L" if x["path"][0]["side"] == "R" else "R"),
                lambda x: x.update(leaf_count=99)):
        x = json.loads(json.dumps(d)); mut(x); assert not cm.verify_disclosure(x, root)["ok"]

def test_wrong_root_and_embedded_flag():
    r = _rec(3); d = cm.disclose(r, 1)
    assert not cm.verify_disclosure(d, cm.claims_root(_rec(3, rid="other")))["ok"]
    assert cm.verify_disclosure(d)["root_source"] == "embedded(untrusted)"

def test_salt_depends_on_private_evidence():
    a, b = _rec(2), _rec(2); b["claims"][0]["evidence"] = "different"
    assert cm.claims_root(a) != cm.claims_root(b)

def test_malformed_never_raises():
    for bad in (None, [], {"index": True, "leaf_count": 1}, {"index": 0, "leaf_count": 1, "salt": "zz", "path": [], "claim": {}},
                {"index": 0, "leaf_count": 2, "salt": "0" * 64, "path": "x", "claim": {}}):
        assert cm.verify_disclosure(bad, "0" * 64)["ok"] is False
    with pytest.raises(IndexError): cm.disclose(_rec(2), 2)
    assert cm.claims_root({"receipt_id": "x", "claims": []}) is None

def test_proof_card_has_root():
    r = _rec(3); assert token_bridge.receipt_proof(r)["claims_root"] == cm.claims_root(r)

@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path))
    (tmp_path / "r1.json").write_text(json.dumps(_rec(4)))
    from http.server import ThreadingHTTPServer
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()

def _req(u, body=None):
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(u, data=data, headers={"Content-Type": "application/json"})) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())

def test_http_disclose_and_verify(srv):
    c, d = _req(srv + "/v1/receipts/r1/claims/3"); assert c == 200 and d["index"] == 3
    c, card = _req(srv + "/v1/receipts/r1/proof"); assert d["claims_root"] == card["claims_root"]
    c, v = _req(srv + "/v1/claims/verify-disclosure", {"disclosure": d}); assert c == 200 and v["ok"] and v["root_source"] == "stored"
    d["claims_root"] = "f" * 64; d["claim"]["vote"] = "TRUE" if d["claim"]["vote"] != "TRUE" else "FALSE"
    assert _req(srv + "/v1/claims/verify-disclosure", {"disclosure": d})[1]["ok"] is False  # stored root beats forged embedded root

def test_http_errors(srv):
    assert _req(srv + "/v1/receipts/r1/claims/9")[0] == 404
    assert _req(srv + "/v1/receipts/r1/claims/x")[0] == 400
    assert _req(srv + "/v1/receipts/nope/claims/0")[0] == 404
    assert _req(srv + "/v1/receipts/..%2Fr1/claims/0")[0] == 404
    assert _req(srv + "/v1/claims/verify-disclosure", [1])[0] == 400
    assert "/v1/receipts/{id}/claims/{index}" in coordinator.OPENAPI["paths"]
