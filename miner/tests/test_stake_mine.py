import pytest
from aegis_miner import stake_mine as sm

def L(): return sm.StakeLedger()

def test_stake_accumulates():
    l = L(); l.stake("m1", 100); r = l.stake("m1", 44)
    assert r["staked"] == 144 and r["scheme"] == "pov-r/stake-mine/1" and l.total_staked == 144

@pytest.mark.parametrize("amt", [0, -1, 1.5, True, "5", None])
def test_stake_bad_amount(amt):
    l = L()
    with pytest.raises(ValueError): l.stake("m1", amt)
    assert l.total_staked == 0 and l.staked == {}

@pytest.mark.parametrize("mid", ["", None, 5])
def test_empty_id(mid):
    with pytest.raises(ValueError): L().stake(mid, 10)

def test_over_unstake_rejected_nothing_mutated():
    l = L(); l.stake("m1", 10)
    with pytest.raises(ValueError): l.request_unstake("m1", 11, now=0)
    with pytest.raises(ValueError): l.request_unstake("m1", 0, now=0)
    with pytest.raises(ValueError): l.request_unstake("ghost", 1, now=0)
    assert l.active_stake("m1") == 10 and l.unlocking_stake("m1") == 0 and l.total_staked == 10

def test_cooldown_blocks_then_finalizes():
    l = L(); l.stake("m1", 100)
    r = l.request_unstake("m1", 40, now=1000, cooldown_sec=60)
    assert r["unlock_at"] == 1060 and l.active_stake("m1") == 60 and l.unlocking_stake("m1") == 40
    assert l.finalize_unstake("m1", 1059) == 0 and l.unlocking_stake("m1") == 40
    assert l.finalize_unstake("m1", 1060) == 40 and l.unlocking_stake("m1") == 0
    assert l.finalize_unstake("m1", 9999) == 0

def test_multiple_lots_partial_release():
    l = L(); l.stake("m1", 100)
    l.request_unstake("m1", 10, now=0, cooldown_sec=10)
    l.request_unstake("m1", 20, now=5, cooldown_sec=10)
    assert l.finalize_unstake("m1", 12) == 10 and l.unlocking_stake("m1") == 20
    assert l.finalize_unstake("m1", 15) == 20

def test_default_cooldown():
    l = L(); l.stake("m1", 5); r = l.request_unstake("m1", 5, now=0)
    assert r["unlock_at"] == sm.DEFAULT_COOLDOWN_SEC

def test_weight_ignores_unlocking():
    l = L(); l.stake("m1", 100); assert l.mining_weight("m1") == 11
    l.request_unstake("m1", 100, now=0)
    assert l.mining_weight("m1") == 0 and not l.eligible("m1")

def test_weight_formula_edges():
    w = sm.weight_for_stake
    assert w(0) == 0 and w(1) == 2 and w(3) == 2 and w(4) == 3
    assert w(10**12) == sm.DEFAULT_SATURATING_AT
    assert w(10**6, floor=1, saturating_at=1001) == 1001 and w(10**6, saturating_at=500) == 500
    assert w(1, floor=5, saturating_at=5) == 5
    for bad in [(-1,), (1.0,), (True,)]:
        with pytest.raises(ValueError): w(*bad)
    with pytest.raises(ValueError): w(1, floor=10, saturating_at=5)
    with pytest.raises(ValueError): w(1, saturating_at=0)

def test_weight_monotone():
    ws = [sm.weight_for_stake(s) for s in range(0, 5000, 7)]
    assert ws == sorted(ws)

def test_unknown_miner_weight_zero():
    assert L().mining_weight("nobody") == 0
