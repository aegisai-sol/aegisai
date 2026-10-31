import json
import pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, B, X = "11" * 32, "22" * 32, "44" * 32
PA, PB, PX = (ca.pubkey_from_seed(s) for s in (A, B, X))

def _rec(ts, rid="r1"):
    r = {"receipt_id": rid, "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(seed, ts, rid="r1"): return ca.sign_card(token_bridge.receipt_proof(_rec(ts, rid)), seed)

def test_retraction_kills_card_offline():
    card = _card(A, 100); d = cm.disclose(_rec(100), 0)
    assert ov.verify_offline(d, card, pubkeys=[PA])["ok"]
    rt = ca.make_retraction(A, card, "source_withdrawn", 500)
    v = ov.verify_offline(d, card, pubkeys=[PA], retractions=[rt])
    assert not v["ok"] and v["retracted"] and "source_withdrawn" in v["reason"] and v["retracted_by"] == PA

def test_bound_to_receipt_and_digest():
    card = _card(A, 100); other = _card(A, 100, "r2")
    rt = ca.make_retraction(A, other, "error", 500)
    assert not ca.check_card_retracted(card, [rt], [PA])["retracted"]
    moved = dict(rt, receipt_id="r1")  # retarget -> bad sig
    assert ca.check_retraction(moved) is None and not ca.check_card_retracted(card, [moved], [PA])["retracted"]
    reissued = _card(A, 101)  # same receipt_id, different digest
    assert not ca.check_card_retracted(reissued, [ca.make_retraction(A, card, "error", 500)], [PA])["retracted"]

def test_stranger_cannot_retract_and_compromised_key_ignored():
    card = _card(A, 100)
    assert not ca.check_card_retracted(card, [ca.make_retraction(X, card, "error", 5)], [PA])["retracted"]
    rot = ca.make_rotation(A, B, 200); comp = ca.make_revocation(B, "compromised", 0)
    rb = ca.make_retraction(B, card, "error", 300)
    assert ca.check_card_retracted(card, [rb], [PA], [rot])["retracted"]  # successor may retract predecessor's card
    assert not ca.check_card_retracted(card, [rb], [PA], [rot], [comp])["retracted"]

def test_retired_key_may_still_retract():
    card = _card(A, 100); rot = ca.make_rotation(A, B, 200)
    assert ca.check_card_retracted(card, [ca.make_retraction(A, card, "error", 900)], [PA], [rot])["retracted"]

def test_superseded_and_deterministic_pick():
    card = _card(A, 100)
    s = ca.make_retraction(A, card, "superseded", 400, "r9"); e = ca.make_retraction(A, card, "error", 300)
    r = ca.check_card_retracted(card, [s, e], [PA])
    assert r["reason"] == "error" and r["retracted_at"] == 300
    assert ca.check_card_retracted(card, [e, s], [PA]) == r
    assert ca.check_card_retracted(card, [s], [PA])["superseded_by"] == "r9"

@pytest.mark.parametrize("args", [("error", -1), ("nope", 1), ("superseded", 1), ("superseded", 1, "r1"), ("error", 1, "r9"), ("error", True)])
def test_make_rejects_bad_input(args):
    with pytest.raises(ValueError): ca.make_retraction(A, _card(A, 100), *args)
    with pytest.raises(ValueError): ca.make_retraction(A, {"receipt_id": "r1"}, "error", 1)

@pytest.mark.parametrize("junk", [None, 1, "x", [], {}, {"scheme": ca.RETRACT_SCHEME}, {"scheme": ca.RETRACT_SCHEME, "signer": 1, "sig": None}])
def test_malformed_never_raises(junk):
    card = _card(A, 100)
    assert ca.check_retraction(junk) is None
    assert ca.check_card_retracted(card, [junk], [PA]) == {"retracted": False}
    assert ca.check_card_retracted(junk, [junk], [PA]) == {"retracted": False}

def test_cli_retraction(tmp_path, capsys):
    card = _card(A, 100); d = cm.disclose(_rec(100), 1)
    dp, cp, rp = tmp_path / "d.json", tmp_path / "c.json", tmp_path / "r.json"
    dp.write_text(json.dumps(d)); cp.write_text(json.dumps(card))
    rp.write_text(json.dumps(ca.make_retraction(A, card, "superseded", 300, "r7")))
    assert ov.main([str(dp), "--card", str(cp), "--pubkey", PA]) == 0; capsys.readouterr()
    assert ov.main([str(dp), "--card", str(cp), "--pubkey", PA, "--retraction", str(rp)]) == 1
    out = json.loads(capsys.readouterr().out); assert out["retracted"] and out["superseded_by"] == "r7"
    assert ov.main([str(dp), "--card", str(cp), "--retraction", str(rp)]) == 1
