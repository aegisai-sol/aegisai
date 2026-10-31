import pytest
from aegis_miner import mine_emit as m

G = 1_700_000_000
E = m.EMISSION_ERA_SECONDS

def test_alloc():
    assert m.preview_allocations()["mine"] == 850_000_000
    assert m.TEAM_ALLOC == 100_000_000 and m.ECO_ALLOC == 50_000_000
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
    assert m.reward_for_work(10, now=G, genesis=G) == 10 * r
    assert m.reward_for_work(10, 15000, now=G, genesis=G) == 15 * r
    assert m.reward_for_work(10, 90000, now=G, genesis=G) == 20 * r
    assert m.reward_for_work(0, now=G, genesis=G) == 0
    assert m.reward_for_work(10, now=G + E, genesis=G) == 10 * (r // 2)

@pytest.mark.parametrize("args", [(-1, 0), (1.5, 0), (1, 5000), (True, 0), (1, "x")])
def test_fail_closed(args):
    with pytest.raises(ValueError):
        m.reward_for_work(*args, now=G, genesis=G)
