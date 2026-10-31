import pytest
from aegis_miner import fee_burn as fb, card_attest as ca

SEED, OTHER = "22" * 32, "33" * 32
PK, OPK = ca.pubkey_from_seed(SEED), ca.pubkey_from_seed(OTHER)

@pytest.mark.parametrize("amt", [0, -5, True, 1.5])
def test_bad_amount_fails_nothing_consumed(amt):
    L = fb.BurnLedger()
    with pytest.raises(ValueError): fb.burn_for_verify("r1", amt, "p", SEED, ledger=L)
    assert not L.is_burned("r1") and L.total_burned == 0

def test_empty_receipt_and_payer_fail():
    L = fb.BurnLedger()
    for rid, p in (("", "p"), ("r", "")):
        with pytest.raises(ValueError): fb.burn_for_verify(rid, 5, p, SEED, ledger=L)
    assert L.total_burned == 0 and not L.burned

def test_bad_key_consumes_nothing():
    L = fb.BurnLedger()
    with pytest.raises(ValueError): fb.burn_for_verify("r1", 5, "p", "zz", ledger=L)
    assert not L.is_burned("r1")

def test_happy_path_and_double_burn():
    L = fb.BurnLedger()
    v = fb.burn_for_verify("r1", 40, "cust", SEED, ledger=L)
    assert v["agis_burned"] == 40 and v["scheme"] == "pov-r/fee-burn/1" and fb.verify_burn_voucher(v, PK)
    with pytest.raises(ValueError): fb.burn_for_verify("r1", 40, "cust", SEED, ledger=L)
    assert L.total_burned == 40

def test_amount_must_match_quote():
    L = fb.BurnLedger()
    with pytest.raises(ValueError): fb.burn_for_verify("r1", 30, "p", SEED, fee_quoted=40, ledger=L)
    assert not L.burned

@pytest.mark.parametrize("field,val", [("receipt_id", "r2"), ("payer_id", "x"), ("agis_burned", 41),
                                       ("fee_quoted", 41), ("scheme", "other"), ("sig", "00" * 64)])
def test_tampered_fails(field, val):
    v = fb.burn_for_verify("r1", 40, "cust", SEED, ledger=fb.BurnLedger())
    assert not fb.verify_burn_voucher({**v, field: val}, PK)

def test_amount_mismatch_both_changed_fails():
    v = fb.burn_for_verify("r1", 40, "cust", SEED, ledger=fb.BurnLedger())
    assert not fb.verify_burn_voucher({**v, "agis_burned": 41, "fee_quoted": 41}, PK)

def test_foreign_key_fails():
    v = fb.burn_for_verify("r1", 40, "cust", OTHER, ledger=fb.BurnLedger())
    assert not fb.verify_burn_voucher(v, PK) and fb.verify_burn_voucher(v, OPK)
    assert not fb.verify_burn_voucher({**v, "pubkey": PK}, PK)

def test_verify_never_raises():
    for junk in (None, {}, "x", {"scheme": fb.SCHEME, "pubkey": PK}): assert fb.verify_burn_voucher(junk, PK) is False

def test_totals_reconcile():
    L = fb.BurnLedger()
    vs = [fb.burn_for_verify(f"r{i}", i + 1, "p", SEED, ledger=L) for i in range(5)]
    assert L.total_burned == sum(v["agis_burned"] for v in vs) == 15 == sum(L.burned.values())
    assert all(fb.verify_burn_voucher(v, [PK]) for v in vs)
