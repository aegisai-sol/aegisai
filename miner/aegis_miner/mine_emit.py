"""pov-r/mine-emit/1 — AGIS emission schedule (off-chain preview library).

Plain rules: max 1,000,000,000 AGIS. 85% is created only by mining, 10% team
(slow vest), 5% ecosystem/pool. Mining reward halves every ~2 years (era).

Formula (Bitcoin-style geometric): amounts are integer *base units*
(9 decimals, like SPL tokens). Era 0 emits ~half the mining pool:
    rate0 = (MINE_ALLOC_BASE // 2) // EMISSION_ERA_SECONDS
    emission_per_second(era) = rate0 >> era
Sum over all eras < 2*rate0*ERA <= MINE_ALLOC_BASE, so the cap can never be
exceeded. Integer math only; no floats, no RPC, no keys.
"""
SCHEME_ID = "pov-r/mine-emit/1"
DECIMALS = 9
BASE = 10 ** DECIMALS
MAX_SUPPLY = 1_000_000_000
MINE_BPS, TEAM_BPS, ECO_BPS = 8500, 1000, 500
assert MINE_BPS + TEAM_BPS + ECO_BPS == 10000
TEAM_ALLOC = MAX_SUPPLY * TEAM_BPS // 10000  # 100_000_000
ECO_ALLOC = MAX_SUPPLY * ECO_BPS // 10000    # 50_000_000
MINE_ALLOC = MAX_SUPPLY - TEAM_ALLOC - ECO_ALLOC  # 850_000_000
MINE_ALLOC_BASE = MINE_ALLOC * BASE
EMISSION_ERA_SECONDS = 2 * 365 * 24 * 3600  # ~2 years
RATE0 = (MINE_ALLOC_BASE // 2) // EMISSION_ERA_SECONDS
MAX_BOOST_BPS = 20000  # stake can at most double speed
ONE_X_BPS = 10000


def _int(x, name):
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError(f"{name} must be int")
    return x


def era_index(now: int, genesis: int) -> int:
    now, genesis = _int(now, "now"), _int(genesis, "genesis")
    if genesis < 0 or now < genesis:
        raise ValueError("now before genesis")
    return (now - genesis) // EMISSION_ERA_SECONDS


def emission_per_second(era: int) -> int:
    """Base units of AGIS minted per second during `era`."""
    era = _int(era, "era")
    if era < 0:
        raise ValueError("era < 0")
    return RATE0 >> era if era < 256 else 0


def emitted_until(now: int, genesis: int) -> int:
    """Cumulative base units the schedule allows by `now` (never > pool)."""
    era = era_index(now, genesis)
    total = sum(emission_per_second(e) * EMISSION_ERA_SECONDS for e in range(min(era, 256)))
    into = (now - genesis) - era * EMISSION_ERA_SECONDS
    return total + emission_per_second(era) * into


def reward_for_work(work_units: int, miner_stake_boost: int = 0, *, now: int, genesis: int) -> int:
    """Base units earned for a work slice. 1 work unit = 1 second of current
    emission. Boost in bps (0 => 1x, 10000..20000); stake only speeds up."""
    work_units = _int(work_units, "work_units")
    boost = _int(miner_stake_boost, "miner_stake_boost")
    if work_units < 0:
        raise ValueError("negative work")
    if boost == 0:
        boost = ONE_X_BPS
    if boost < ONE_X_BPS:
        raise ValueError("boost below 1x")
    boost = min(boost, MAX_BOOST_BPS)
    if work_units == 0:
        return 0
    return emission_per_second(era_index(now, genesis)) * work_units * boost // ONE_X_BPS


def preview_allocations() -> dict:
    return {"scheme": SCHEME_ID, "max": MAX_SUPPLY, "mine": MINE_ALLOC,
            "team": TEAM_ALLOC, "eco": ECO_ALLOC, "decimals": DECIMALS}
