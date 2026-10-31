import pytest
from aegis_miner import credit_settle as cs, card_attest as ca, token_bridge

SEED = "11" * 32
PK = ca.pubkey_from_seed(SEED)

def _rec(rid, credits=2, miner="m1"):
    r = {"receipt_id": rid, "client_id": miner, "ts": 1.0, "nonce": "nonce-1234", "credits_awarded": credits,
         "claims": [{"text": "c", "vote": "TRUE", "evidence": "e"}], "calibration": {"ok": True, "failed": []},
         "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def test_zero_fee_inflow_settles_zero():
    p = cs.Period("2026-10", 0, 1000, 10**9)
    v = cs.settle_credits(p, "m1", [_rec("a")], SEED)
    assert v["agis_out"] == 0 and v["credits_in"] == 2 and cs.verify_voucher(v, [PK])

def test_fee_inflow_raises_rate():
    low = cs.Period("p", 1000, 100, 10**9).preview(10)
    high = cs.Period("p", 5000, 100, 10**9).preview(10)
    assert low == 100 and high == 500

def test_zero_credits_earned_denominator_is_one():
    assert cs.compute_settle_rate(7, 0) == (7, 1)

def test_reservoir_cap_and_depletion():
    p = cs.Period("p", 10**6, 2, 300)
    v = cs.settle_credits(p, "m1", [_rec("a")], SEED)
    assert v["agis_out"] == 300 and p.available == 0
    assert cs.settle_credits(p, "m1", [_rec("b")], SEED)["agis_out"] == 0

def test_tampered_receipt_fails_closed():
    r = _rec("a"); r["credits_awarded"] = 99
    p = cs.Period("p", 1000, 10, 10**6)
    with pytest.raises(ValueError): cs.settle_credits(p, "m1", [r], SEED)
    assert not p.consumed and p.available == 10**6

def test_missing_or_foreign_receipt_fails():
    p = cs.Period("p", 1000, 10, 10**6)
    with pytest.raises(ValueError): cs.settle_credits(p, "m1", [], SEED)
    with pytest.raises(ValueError): cs.settle_credits(p, "m1", [{"receipt_id": "x"}], SEED)
    with pytest.raises(ValueError): cs.settle_credits(p, "m1", [_rec("a", miner="m2")], SEED)

def test_double_settle_fails():
    p = cs.Period("p", 1000, 10, 10**6)
    cs.settle_credits(p, "m1", [_rec("a")], SEED)
    with pytest.raises(ValueError): cs.settle_credits(p, "m1", [_rec("a")], SEED)
    with pytest.raises(ValueError): cs.settle_credits(p, "m1", [_rec("b"), _rec("b")], SEED)

def test_voucher_tamper_and_untrusted_key():
    v = cs.settle_credits(cs.Period("p", 1000, 10, 10**6), "m1", [_rec("a")], SEED)
    assert cs.verify_voucher(v, [PK])
    assert not cs.verify_voucher(v, [ca.pubkey_from_seed("22" * 32)])
    assert not cs.verify_voucher({**v, "agis_out": v["agis_out"] + 1}, [PK])
    assert not cs.verify_voucher({**v, "miner_id": "evil"}, [PK])
    assert not cs.verify_voucher({**v, "fee_inflow_basis": 10**9}, [PK])
    assert not cs.verify_voucher(None, [PK])
