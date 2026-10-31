import pytest
from aegis_miner import mine_claim as mc

G = 1_700_000_000
BIG = 10**30
A = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijk"

def wallet(i):
    s = A[i % len(A)] + A[(i // len(A)) % len(A)]
    return (s + "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9Pus")[:44]

def C(w, d, start=G):
    return dict(wallet=w, device_id=d, start=start, online_seconds=60, power_score=1, verified_tasks=1)

def test_difficulty_curve():
    assert mc.difficulty_bps(0) == 10000 and mc.difficulty_bps(100) == 10000
    assert mc.difficulty_bps(200) == 5000 and mc.difficulty_bps(1000) == 1000
    for bad in (-1, 1.5, True):
        with pytest.raises(ValueError): mc.difficulty_bps(bad)
    with pytest.raises(ValueError): mc.difficulty_bps(5, 0)

def test_monotonic_non_increasing():
    vals = [mc.difficulty_bps(n) for n in range(0, 2000, 7)]
    assert all(a >= b for a, b in zip(vals, vals[1:]))

def test_ledger_scales_when_network_grows():
    l = mc.ClaimLedger(G, daily_cap=BIG, global_daily_cap=BIG)
    first = None
    for i in range(200):
        w, d = wallet(i), f"d{i}"
        l.bind(w, d)
        r = l.claim(C(w, d), now=G + 20_000)
        if i == 0: first = r["agis_base"]
        if i < 100: assert r["difficulty_bps"] == 10000
    assert r["active_devices"] == 200 and r["difficulty_bps"] == 5000
    assert r["agis_base"] == first * 5000 // 10000

def test_same_device_not_double_counted_and_new_day_resets():
    l = mc.ClaimLedger(G, daily_cap=BIG, global_daily_cap=BIG)
    l.bind(wallet(0), "d0")
    r1 = l.claim(C(wallet(0), "d0"), now=G + 600)
    r2 = l.claim(C(wallet(0), "d0", start=G + 60), now=G + 600)
    assert r1["active_devices"] == r2["active_devices"] == 1
    r3 = l.claim(C(wallet(0), "d0", start=G + 120), now=G + 600 + mc.DAY_SECONDS)
    assert r3["active_devices"] == 1

def test_failed_claim_does_not_count_device():
    l = mc.ClaimLedger(G, daily_cap=BIG, global_daily_cap=BIG)
    l.bind(wallet(0), "d0")
    with pytest.raises(ValueError): l.claim(dict(C(wallet(0), "d0"), verified_tasks=0), now=G + 600)
    assert not l.day_devices
