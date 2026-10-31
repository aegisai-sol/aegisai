import json
import pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

SEED, OTHER = "11" * 32, "22" * 32
PK = ca.pubkey_from_seed(SEED)

def _rec(ts=100.0):
    r = {"receipt_id": "r1", "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(4)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(ts=100.0): return ca.sign_card(token_bridge.receipt_proof(_rec(ts)), SEED)

def test_revocation_roundtrip():
    rv = ca.make_revocation(SEED, "retired", 200)
    assert ca.check_revocation(rv) == (PK, "retired", 200) and rv["scheme"] == ca.REVOKE_SCHEME

def test_compromised_kills_all_cards_even_backdated():
    rv = ca.make_revocation(SEED, "compromised", 200)
    for ts in (1.0, 100.0, 300.0):
        v = ca.verify_card(_card(ts), [PK], [rv]); assert not v["ok"] and "compromised" in v["reason"]

def test_retired_keeps_earlier_cards():
    rv = ca.make_revocation(SEED, "retired", 200)
    assert ca.verify_card(_card(100.0), [PK], [rv])["ok"]
    assert "retired" in ca.verify_card(_card(200.0), [PK], [rv])["reason"]
    assert not ca.verify_card(_card(300.0), [PK], [rv])["ok"]

def test_third_party_cannot_revoke():
    rv = ca.make_revocation(OTHER, "compromised", 0); rv["pubkey"] = PK  # forger relabels own revocation
    assert ca.check_revocation(rv) is None and ca.verify_card(_card(), [PK], [rv])["ok"]

@pytest.mark.parametrize("field,val", [("reason", "retired"), ("revoked_at", 999), ("scheme", "x"), ("sig", "zz")])
def test_tampered_revocation_ignored(field, val):
    rv = ca.make_revocation(SEED, "compromised", 0); rv[field] = val
    assert ca.check_revocation(rv) is None

def test_other_key_revocation_does_not_affect():
    rv = ca.make_revocation(OTHER, "compromised", 0)
    assert ca.verify_card(_card(), [PK], [rv])["ok"]

def test_malformed_revocations_never_raise():
    for rv in (None, [], "x", {}, {"scheme": ca.REVOKE_SCHEME, "pubkey": PK, "reason": "compromised", "revoked_at": True, "sig": "0" * 128}):
        assert ca.check_revocation(rv) is None
    assert ca.verify_card(_card(), [PK], [None, "x", {}])["ok"]

@pytest.mark.parametrize("args", [("lost", 1), ("retired", -1), ("retired", True), ("retired", "1")])
def test_make_revocation_rejects_bad_input(args):
    with pytest.raises(ValueError): ca.make_revocation(SEED, *args)

def test_retired_card_with_nonnumeric_ts_fails_closed():
    rv = ca.make_revocation(SEED, "retired", 200)
    c = ca.sign_card(dict(token_bridge.receipt_proof(_rec()), ts="early"), SEED)
    assert not ca.verify_card(c, [PK], [rv])["ok"]

def test_offline_cli_revocation(tmp_path):
    r = _rec(); (tmp_path / "c.json").write_text(json.dumps(_card())); (tmp_path / "d.json").write_text(json.dumps(cm.disclose(r, 1)))
    (tmp_path / "rv.json").write_text(json.dumps(ca.make_revocation(SEED, "compromised", 0)))
    base = [str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--pubkey", PK]
    assert ov.main(base) == 0
    assert ov.main(base + ["--revocation", str(tmp_path / "rv.json")]) == 1
    v = ov.verify_offline(cm.disclose(r, 1), _card(), pubkeys=[PK], revocations=[ca.make_revocation(SEED, "compromised", 0)])
    assert not v["ok"] and "revoked" in v["reason"]
