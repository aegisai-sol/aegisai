import pytest
from aegis_miner import credit_settle as cs, card_attest as ca, token_bridge

SEED = "11" * 32
PK = ca.pubkey_from_seed(SEED)

def _rec(miner, credits=2, rid="job-1"):
    r = {"receipt_id": rid, "client_id": miner, "ts": 1.0, "nonce": "nonce-1234", "credits_awarded": credits,
         "claims": [{"text": "c", "vote": "TRUE", "evidence": "e"}]}
    r["digest"] = token_bridge.receipt_digest(r); return r

def test_paid_job_pro_rata_70pct():
    j = cs.Job("job-1", 10000, True, [_rec("m1", 1), _rec("m2", 3)])
    a, b = cs.settle_credits(j, "m1", SEED), cs.settle_credits(j, "m2", SEED)
    assert (a["agis_out"], b["agis_out"]) == (1750, 5250) and j.paid_out <= 7000
    assert cs.verify_voucher(a, [PK]) and cs.verify_voucher(b, [PK])

def test_unpaid_is_reputation_only():
    j = cs.Job("job-1", 10000, False, [_rec("m1")])
    v = cs.settle_credits(j, "m1", SEED)
    assert v["agis_out"] == 0 and v["job_fee"] == 0 and cs.verify_voucher(v, [PK])
    assert not cs.verify_voucher({**v, "agis_out": 1}, [PK])

def test_no_cross_job_dilution():
    big = cs.Job("job-2", 10000, True, [_rec("x", 10**6, "job-2")])
    j = cs.Job("job-1", 10000, True, [_rec("m1")])
    assert cs.settle_credits(j, "m1", SEED)["agis_out"] == 7000 and big.preview("x") == 7000
    assert not hasattr(cs, "compute_settle_rate") and not hasattr(cs, "Period")

def test_missing_bad_or_foreign_receipt_fails():
    bad = _rec("m1"); bad["credits_awarded"] = 99
    for recs in ([], [bad], [{"receipt_id": "job-1"}], [_rec("m1", rid="other")], [_rec("m1"), _rec("m1")]):
        with pytest.raises(ValueError): cs.Job("job-1", 100, True, recs)
    j = cs.Job("job-1", 100, True, [_rec("m1")])
    with pytest.raises(ValueError): cs.settle_credits(j, "stranger", SEED)
    with pytest.raises(ValueError): cs.settle_credits(j, "m1", "zz")
    assert not j.settled and j.paid_out == 0

def test_double_settle_fails():
    j = cs.Job("job-1", 1000, True, [_rec("m1")])
    cs.settle_credits(j, "m1", SEED)
    with pytest.raises(ValueError): cs.settle_credits(j, "m1", SEED)

def test_cannot_exceed_miner_share():
    j = cs.Job("job-1", 1000, True, [_rec("m1")])
    j.paid_out = 700
    with pytest.raises(ValueError): cs.settle_credits(j, "m1", SEED)

def test_voucher_tamper_and_untrusted_key():
    v = cs.settle_credits(cs.Job("job-1", 1000, True, [_rec("m1"), _rec("m2")]), "m1", SEED)
    assert cs.verify_voucher(v, [PK])
    assert not cs.verify_voucher(v, [ca.pubkey_from_seed("22" * 32)])
    for k, x in (("agis_out", v["agis_out"] + 1), ("miner_id", "evil"), ("receipt_id", "job-9"), ("job_fee", 10**9),
                 ("credits_in", 1), ("paid", False)):
        assert not cs.verify_voucher({**v, k: x}, [PK])
    assert not cs.verify_voucher(None, [PK])
