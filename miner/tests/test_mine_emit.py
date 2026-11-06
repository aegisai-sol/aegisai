import pytest
from aegis_miner import mine_emit as m

G = 1_700_000_000
E = m.EMISSION_ERA_SECONDS

def test_alloc():
    assert m.preview_allocations()["mine"] == 8_500_000_000
    assert m.TEAM_ALLOC == 1_000_000_000 and m.ECO_ALLOC == 500_000_000
    assert m.MINE_ALLOC + m.TEAM_ALLOC + m.ECO_ALLOC == m.MAX_SUPPLY

def test_era():
    assert m.era_index(G, G) == 0
    assert m.era_index(G + E - 1, G) == 0
    assert m.era_index(G + E, G) == 1
    with pytest.raises(ValueError):
        m.era_index(G - 1, G)

def test_halving():
    assert m.emission_per_second(1) == m.emission_per_second(0) // 2
    assert m.emission_per_second(300) == 0

def test_total_never_exceeds():
    far = G + E * 400
    total = m.emitted_until(far, G)
    assert total <= m.MINE_ALLOC_BASE
    assert total > m.MINE_ALLOC_BASE * 99 // 100
    assert m.emitted_until(G + E, G) <= m.MINE_ALLOC_BASE // 2

def test_reward():
    r = m.emission_per_second(0)
    # UNIT_BPS soft-go: unit earn = rate * units * UNIT_BPS / 10000 (matches claim-server)
    assert m.UNIT_BPS == 1
    pay = lambda n, boost=m.ONE_X_BPS, rate=r: rate * n * boost * m.UNIT_BPS // (m.ONE_X_BPS * 10000)
    assert m.reward_for_work(10, now=G, genesis=G) == pay(10)
    assert m.reward_for_work(10, 15000, now=G, genesis=G) == pay(10, 15000)
    assert m.reward_for_work(10, 90000, now=G, genesis=G) == pay(10, m.MAX_BOOST_BPS)
    assert m.reward_for_work(0, now=G, genesis=G) == 0
    assert m.reward_for_work(10, now=G + E, genesis=G) == pay(10, rate=r // 2)
    assert abs(pay(1) / m.BASE - 0.0067383307965) < 1e-9

@pytest.mark.parametrize("args", [(-1, 0), (1.5, 0), (1, 5000), (True, 0), (1, "x")])
def test_fail_closed(args):
    with pytest.raises(ValueError):
        m.reward_for_work(*args, now=G, genesis=G)

def test_10b_fits_u64_and_no_month_dump():
    assert m.MAX_SUPPLY == 10_000_000_000
    assert m.MAX_SUPPLY * m.BASE < 2**64
    month = 30 * 24 * 3600
    assert m.emitted_until(G + month, G) < m.MINE_ALLOC_BASE * 3 // 100  # <3% in first month
