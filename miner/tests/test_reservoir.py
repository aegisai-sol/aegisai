import pytest
from aegis_miner import reservoir as R
def test_split_reconciles():
    r = R.split_fee(1_000_001, {"a": 2, "b": 1})
    assert sum(r["parts"].values()) == 1_000_001 and r["payouts"]["a"] > r["payouts"]["b"]
def test_flagged_goes_to_reservoir():
    r = R.split_fee(1000, {"a": 1}, flagged=True)
    assert r["payouts"] == {} and r["parts"]["reservoir"] == 900
def test_no_votes():
    assert R.split_fee(1000, {})["parts"]["miners"] == 0
def test_ledger_no_double_settle():
    L = R.Ledger(); L.settle("r1", 10000, {"a": 1})
    assert L.balances["a"] == 7000 and L.totals["burn"] == 500
    with pytest.raises(ValueError): L.settle("r1", 10000, {"a": 1})
def test_negative():
    with pytest.raises(ValueError): R.split_fee(-1, {})
