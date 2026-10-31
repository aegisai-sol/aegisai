import json
from aegis_miner import claim_merkle as cm, coordinator
from test_claim_disclosure import srv, _req, _rec  # noqa: F401

def test_http_multiproof_roundtrip(srv):
    c, m = _req(srv + "/v1/receipts/r1/claims?indices=3,0")
    assert c == 200 and m["indices"] == [0, 3] and m["scheme"] == "pov-r/claim-multiproof/1"
    _, card = _req(srv + "/v1/receipts/r1/proof"); assert m["claims_root"] == card["claims_root"]
    c, v = _req(srv + "/v1/claims/verify-disclosure", {"multiproof": m})
    assert c == 200 and v["ok"] and v["count"] == 2 and v["leaf_count"] == 4
    assert v["root_source"] == "stored" and v["leaf_count_source"] == "stored"
    assert "cid-secret" not in json.dumps(m) and "private" not in json.dumps(m)

def test_http_multiproof_binding_and_forgery(srv):
    _, m = _req(srv + "/v1/receipts/r1/claims?indices=1,2")
    f = json.loads(json.dumps(m)); f["claims_root"] = "f" * 64; f["claims"][0]["text"] = "forged"
    assert _req(srv + "/v1/claims/verify-disclosure", {"multiproof": f})[1]["ok"] is False  # stored root wins
    lc = {**m, "leaf_count": 5}  # inflated N caught by stored leaf_count even if replay shape matched
    assert _req(srv + "/v1/claims/verify-disclosure", {"multiproof": lc})[1]["ok"] is False
    v = _req(srv + "/v1/claims/verify-disclosure", {"multiproof": m, "expected_leaf_count": 9})[1]
    assert v["ok"] is False and "disagree" in v["reason"]
    v = _req(srv + "/v1/claims/verify-disclosure", {"multiproof": m, "expected_root": "a" * 64})[1]
    assert v["ok"] is False
    assert _req(srv + "/v1/claims/verify-disclosure", {"multiproof": m, "expected_leaf_count": True})[0] == 400

def test_http_multiproof_unknown_receipt_uses_expected(srv):
    r = _rec(6, rid="zz9"); m = cm.disclose_multi(r, [0, 5])  # not stored on this coordinator
    v = _req(srv + "/v1/claims/verify-disclosure", {"multiproof": m, "expected_root": cm.claims_root(r), "expected_leaf_count": 6})[1]
    assert v["ok"] and v["root_source"] == "expected" and v["leaf_count_source"] == "expected"
    v = _req(srv + "/v1/claims/verify-disclosure", {"multiproof": m})[1]
    assert v["ok"] and v["root_source"] == "embedded(untrusted)"
    assert _req(srv + "/v1/claims/verify-disclosure", {"multiproof": "x"})[1]["ok"] is False

def test_http_multiproof_errors(srv):
    for q, code in (("indices=", 400), ("indices=0,0", 400), ("indices=a", 400), ("indices=-1", 400), ("x=1", 400),
                    ("indices=4", 404), ("indices=" + ",".join(["0"] * 300), 400)):
        assert _req(srv + "/v1/receipts/r1/claims?" + q)[0] == code, q
    assert _req(srv + "/v1/receipts/nope/claims?indices=0")[0] == 404
    assert _req(srv + "/v1/receipts/..%2Fr1/claims?indices=0")[0] == 404
    assert "/v1/receipts/{id}/claims" in coordinator.OPENAPI["paths"]
