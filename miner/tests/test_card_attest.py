import json, threading, urllib.request, urllib.error
import pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov, coordinator

SEED = "11" * 32
OTHER = "22" * 32

def _rec(rid="abc1", n=5):
    r = {"receipt_id": rid, "client_id": "c", "ts": 1.0, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(n)] + [{"text": "k", "vote": "TRUE", "canary": True}],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _signed(r, seed=SEED): return ca.sign_card(token_bridge.receipt_proof(r), seed)
PK = ca.pubkey_from_seed(SEED)

def test_sign_verify_roundtrip():
    c = _signed(_rec()); v = ca.verify_card(c, [PK])
    assert v["ok"] and v["signer"] == PK and c["attestation"]["scheme"] == ca.SCHEME and len(c["attestation"]["sig"]) == 128

@pytest.mark.parametrize("field,val", [("claims_root", "0" * 64), ("claim_count", 99), ("receipt_id", "zzz"),
                                       ("votes", {"TRUE": 9}), ("flagged", True), ("digest", "f" * 64), ("nonce", "n2")])
def test_any_pinned_edit_breaks_signature(field, val):
    c = _signed(_rec()); c[field] = val
    assert ca.verify_card(c, [PK])["reason"] == "bad signature"

def test_audit_intact_flip_breaks_signature():
    c = _signed(_rec()); c["audit"] = dict(c["audit"], intact=False)
    assert not ca.verify_card(c, [PK])["ok"]

def test_forger_own_key_not_trusted():
    c = _signed(_rec(), OTHER); assert ca.verify_card(c, [PK])["reason"] == "signer not trusted"
    c["attestation"]["pubkey"] = PK  # claim the real key with the forger's signature
    assert ca.verify_card(c, [PK])["reason"] == "bad signature"

def test_malformed_never_raises():
    for card, keys in ((None, [PK]), ([], [PK]), ({}, [PK]), (_signed(_rec()), []), (_signed(_rec()), ["xyz"]),
                       ({"attestation": {"scheme": "other"}}, [PK]), ({"attestation": {"scheme": ca.SCHEME, "pubkey": PK, "sig": "zz"}}, [PK]),
                       ({"attestation": "x"}, [PK])):
        assert ca.verify_card(card, keys)["ok"] is False

def test_bad_seed_rejected():
    with pytest.raises(ValueError): ca.sign_card({}, "abc")
    assert ca.pubkey_from_seed("nothex") is None

def test_unsigned_extras_not_covered_but_sig_stable():
    c = _signed(_rec()); c2 = ca.sign_card(c, SEED)  # re-signing a signed card replaces, not nests
    assert c2["attestation"]["sig"] == c["attestation"]["sig"] and "attestation" not in json.dumps(c2["attestation"])

def test_offline_requires_valid_attestation_with_pubkey():
    r = _rec(); card = _signed(r); d = cm.disclose(r, 2)
    v = ov.verify_offline(d, card, pubkeys=[PK]); assert v["ok"] and v["trusted"] and v["card_signed"] is True and v["signer"] == PK
    # forged card: attacker builds own receipt with same id, signs with own key
    fake = _rec(n=5); fake["claims"][2]["text"] = "lie"; fake["digest"] = token_bridge.receipt_digest(fake)
    fcard = _signed(fake, OTHER); fd = cm.disclose(fake, 2)
    assert ov.verify_offline(fd, fcard)["ok"]  # without pubkey a forged card still "verifies" -> exactly the gap
    v = ov.verify_offline(fd, fcard, pubkeys=[PK]); assert not v["ok"] and "signer not trusted" in v["reason"]
    unsigned = token_bridge.receipt_proof(r)
    assert "not attested" in ov.verify_offline(d, unsigned, pubkeys=[PK])["reason"]
    assert "needs a proof card" in ov.verify_offline(d, None, pubkeys=[PK])["reason"]
    assert ov.verify_offline(d, card)["card_signed"] == "unchecked"
    assert ov.verify_offline(d, unsigned)["card_signed"] is False

def test_offline_cli_pubkey(tmp_path, capsys):
    r = _rec(); (tmp_path / "c.json").write_text(json.dumps(_signed(r))); (tmp_path / "d.json").write_text(json.dumps(cm.disclose_multi(r, [0, 4])))
    assert ov.main([str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--pubkey", PK]) == 0
    assert ov.main([str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--pubkey", ca.pubkey_from_seed(OTHER)]) == 1

def test_attest_card_env():
    card = token_bridge.receipt_proof(_rec())
    assert coordinator.attest_card(card, {}) is card
    assert ca.verify_card(coordinator.attest_card(card, {"AEGIS_CARD_SIGNING_KEY": SEED.upper()}), [PK])["ok"]
    bad = coordinator.attest_card(card, {"AEGIS_CARD_SIGNING_KEY": "short"})
    assert bad["attestation"] is None and "short" not in json.dumps(bad)
    assert coordinator.card_pubkey({}) is None and coordinator.card_pubkey({"AEGIS_CARD_SIGNING_KEY": SEED}) == PK

@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_RECEIPT_HMAC", raising=False)
    monkeypatch.setenv("AEGIS_CARD_SIGNING_KEY", SEED)
    monkeypatch.setattr(coordinator, "RECEIPTS", str(tmp_path))
    (tmp_path / "abc1.json").write_text(json.dumps(_rec()))
    from http.server import ThreadingHTTPServer
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()

def _get(u):
    try:
        with urllib.request.urlopen(u) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())

def test_http_signed_card_and_key(srv, monkeypatch):
    st, key = _get(srv + "/v1/card-key"); assert st == 200 and key["pubkey"] == PK and SEED not in json.dumps(key)
    st, card = _get(srv + "/v1/receipts/abc1/proof"); assert st == 200 and ca.verify_card(card, [key["pubkey"]])["ok"]
    st, d = _get(srv + "/v1/receipts/abc1/claims/1")
    assert ov.verify_offline(d, card, pubkeys=[key["pubkey"]])["ok"]
    monkeypatch.delenv("AEGIS_CARD_SIGNING_KEY")
    assert _get(srv + "/v1/card-key")[0] == 404
    st, card = _get(srv + "/v1/receipts/abc1/proof"); assert st == 200 and "attestation" not in card
    st, spec = _get(srv + "/v1/openapi.json"); assert "/v1/card-key" in spec["paths"]
