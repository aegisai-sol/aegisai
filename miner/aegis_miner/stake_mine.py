"""Stake-to-mine (pov-r/stake-mine/1) -- BME+ miner eligibility.

A miner locks whole AGIS to earn mining weight on verify jobs. Weight formula (integer, documented):
    stake == 0  -> weight 0 (not eligible)
    stake  > 0  -> weight = min(saturating_at, floor + isqrt(stake))
floor keeps tiny stakes non-zero; isqrt gives diminishing returns; saturating_at caps whales.
Only active stake counts; stake in an unstake cool-down ("unlocking") earns nothing and is freed by finalize_unstake
once unlock_at <= now. Fail closed: bad input raises ValueError and nothing is mutated. In-memory, off-chain only:
no mint, no tx, no network (persist/anchor before production). Miner pay stays job-scoped in credit_settle.
"""
import math, time

SCHEME = "pov-r/stake-mine/1"
DEFAULT_COOLDOWN_SEC = 7 * 24 * 3600
DEFAULT_FLOOR = 1
DEFAULT_SATURATING_AT = 1000

def _int(x): return not isinstance(x, bool) and isinstance(x, int)
def _pos(x): return _int(x) and x > 0
def _id(m):
    if not isinstance(m, str) or not m: raise ValueError("miner_id required")
def _now(now):
    if now is None: return int(time.time())
    if not _int(now) or now < 0: raise ValueError("now must be non-negative int seconds")
    return now

def weight_for_stake(stake, floor=DEFAULT_FLOOR, saturating_at=DEFAULT_SATURATING_AT):
    if not _int(stake) or stake < 0: raise ValueError("stake must be non-negative int")
    if not _int(floor) or floor < 0 or not _pos(saturating_at) or floor > saturating_at:
        raise ValueError("need 0 <= floor <= saturating_at, saturating_at > 0")
    return 0 if stake == 0 else min(saturating_at, floor + math.isqrt(stake))

class StakeLedger:
    def __init__(self): self.staked, self.unlocking, self.total_staked = {}, {}, 0

    def stake(self, miner_id, amount, now=None):
        _id(miner_id); _now(now)
        if not _pos(amount): raise ValueError("amount must be positive whole AGIS")
        self.staked[miner_id] = self.staked.get(miner_id, 0) + amount
        self.total_staked += amount
        return {"scheme": SCHEME, "event": "stake", "miner_id": miner_id, "amount": amount,
                "staked": self.staked[miner_id]}

    def request_unstake(self, miner_id, amount, now, cooldown_sec=DEFAULT_COOLDOWN_SEC):
        _id(miner_id)
        if now is None: raise ValueError("now required")
        now = _now(now)
        if not _pos(amount): raise ValueError("amount must be positive whole AGIS")
        if not _int(cooldown_sec) or cooldown_sec < 0: raise ValueError("cooldown_sec must be non-negative int")
        if amount > self.staked.get(miner_id, 0): raise ValueError("unstake exceeds active stake")
        lot = {"amount": amount, "unlock_at": now + cooldown_sec}
        self.staked[miner_id] -= amount; self.total_staked -= amount
        self.unlocking.setdefault(miner_id, []).append(lot)
        return {"scheme": SCHEME, "event": "unstake_requested", "miner_id": miner_id, **lot}

    def finalize_unstake(self, miner_id, now):
        _id(miner_id)
        if now is None: raise ValueError("now required")
        now = _now(now)
        lots = self.unlocking.get(miner_id, [])
        freed = sum(l["amount"] for l in lots if l["unlock_at"] <= now)
        self.unlocking[miner_id] = [l for l in lots if l["unlock_at"] > now]
        return freed

    def active_stake(self, miner_id): return self.staked.get(miner_id, 0)
    def unlocking_stake(self, miner_id): return sum(l["amount"] for l in self.unlocking.get(miner_id, []))

    def mining_weight(self, miner_id, floor=DEFAULT_FLOOR, saturating_at=DEFAULT_SATURATING_AT):
        _id(miner_id)
        return weight_for_stake(self.active_stake(miner_id), floor, saturating_at)

    def eligible(self, miner_id): return self.mining_weight(miner_id) > 0
