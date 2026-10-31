import pytest
from aegis_miner import mine_claim as mc, mine_emit as me

G = 1_700_000_000
W = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
W2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"

def C(**k):
    c = dict(wallet=W, device_id="d1", start=G, online_seconds=60, power_score=1, verified_tasks=1); c.update(k); return c

def L():
    l = mc.ClaimLedger(G); l.bind(W, "d1"); return l

def test_claim_pays_wallet():
    l = L(); r = l.claim(C(), now=G + 600)
    assert r["agis_base"] > 0 and l.balances[W] == r["agis_base"]

def test_more_power_and_time_more_reward():
    assert mc.work_units(4, 60, 1) == 2 * mc.work_units(1, 60, 1)
    assert mc.work_units(1, 120, 1) == 2 * mc.work_units(1, 60, 1)
    assert mc.work_units(100, 60, 1) == 10 * mc.work_units(1, 60, 1)

def test_wallet_required():
    l = mc.ClaimLedger(G)
    for bad in ("", "0OIl" * 10, None):
        with pytest.raises(ValueError): l.bind(bad, "d1")
    with pytest.raises(ValueError): l.claim(C(), now=G + 600)

@pytest.mark.parametrize("kw", [dict(verified_tasks=0), dict(power_score=0), dict(power_score=101),
    dict(online_seconds=0), dict(online_seconds=3601), dict(start=G - 1), dict(start=G + 10_000), dict(power_score=1.5)])
def test_fail_closed(kw):
    l = L()
    with pytest.raises(ValueError): l.claim(C(**kw), now=G + 600)
    assert l.total == 0

def test_replay_blocked():
    l = mc.ClaimLedger(G, daily_cap=10**30, global_daily_cap=10**30); l.bind(W, "d1"); l.claim(C(), now=G + 600)
    with pytest.raises(ValueError): l.claim(C(), now=G + 600)
    l.claim(C(start=G + 60), now=G + 600)

def test_device_cap_and_steal():
    l = mc.ClaimLedger(G)
    for i in range(mc.MAX_DEVICES_PER_WALLET): l.bind(W, f"d{i}")
    with pytest.raises(ValueError): l.bind(W, "extra")
    with pytest.raises(ValueError): l.bind(W2, "d0")

def test_halving_applies():
    l = mc.ClaimLedger(G, daily_cap=10**30, global_daily_cap=10**30); l.bind(W, "d1"); E = me.EMISSION_ERA_SECONDS
    a = l.claim(C(), now=G + 600)["agis_base"]
    b = l.claim(C(start=G + E), now=G + E + 600)["agis_base"]
    assert b == a // 2 or abs(b * 2 - a) <= 60

def test_ed25519_optional():
    ed = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    from cryptography.hazmat.primitives import serialization as s
    k = ed.Ed25519PrivateKey.generate()
    pub = k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
    l = mc.ClaimLedger(G); l.bind(W, "d1", pub)
    with pytest.raises(ValueError): l.claim(C(), now=G + 600, signature=b"x" * 64)
    assert l.claim(C(), now=G + 600, signature=k.sign(mc.claim_message(C())))["agis_base"] > 0


def test_daily_wallet_cap_clips_then_blocks():
    l = L(); D = mc.DAY_SECONDS; now = G + 3 * D  # same UTC day for all claims below
    r = l.claim(C(start=G + 3 * D - 4000, online_seconds=3600, power_score=100), now=now)
    assert r["agis_base"] == mc.DAILY_CAP_BASE and l.remaining_today(W, now) == 0
    with pytest.raises(ValueError, match="daily cap"):
        l.claim(C(start=G + 3 * D - 300, online_seconds=60), now=now)
    assert l.balances[W] == mc.DAILY_CAP_BASE and l.last_end["d1"] == G + 3 * D - 400
    nxt = l.claim(C(start=G + 3 * D - 300, online_seconds=60), now=now + D)  # next day: slice not burned
    assert nxt["agis_base"] > 0

def test_global_cap_shared_across_wallets():
    l = mc.ClaimLedger(G, daily_cap=10**30, global_daily_cap=5 * me.BASE)
    l.bind(W, "d1"); l.bind(W2, "d2"); now = G + 600
    a = l.claim(C(), now=now)["agis_base"]
    assert a == 5 * me.BASE
    with pytest.raises(ValueError, match="daily cap"):
        l.claim(C(wallet=W2, device_id="d2"), now=now)
    assert l.remaining_today(W2, now) == 0 and l.total == a

def test_caps_must_be_positive():
    for kw in (dict(daily_cap=0), dict(global_daily_cap=-1), dict(daily_cap=1.0)):
        with pytest.raises(ValueError): mc.ClaimLedger(G, **kw)
