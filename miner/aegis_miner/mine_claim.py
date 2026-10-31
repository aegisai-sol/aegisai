"""pov-r/mine-claim/1 -- wallet-bound mining reward claims (off-chain ledger).

Plain rules: no wallet, no mining. A miner binds a Solana wallet pubkey to a
device_id, then claims AGIS for a work slice. Reward grows with device power
(power_score, 1..MAX_POWER) and time connected (online_seconds), capped per
slice, and stays inside the mine_emit halving schedule.

Human-configured AI bots are allowed. Blocked (fail closed, ValueError, nothing
recorded): zero useful work, overlapping/replayed slices, one wallet faking
more devices than MAX_DEVICES_PER_WALLET, slices from the future, bad wallet.
Optional Ed25519: if a device pubkey was bound, each claim must be signed.
Daily caps mirror the live claim server: a wallet earns at most
DAILY_CAP_BASE and the network at most GLOBAL_DAILY_CAP_BASE per UTC day
(keyed by claim time `now`); an over-cap claim is clipped, and once a cap is
full the claim fails closed ("daily cap reached") without consuming the slice.
Difficulty grows with the network: up to DIFFICULTY_FREE_DEVICES distinct
devices claiming in a UTC day get full reward; beyond that every slice is scaled
by FREE/active (bps), so more miners share the same emission instead of
printing more. Integer math only; no RPC, no mint here (on-chain mint is a
separate step).
"""
import json
from . import mine_emit as me

SCHEME = "pov-r/mine-claim/1"
DOMAIN = b"AEGIS/mine-claim/v1"
MAX_POWER = 100            # power_score 1..100 (phone ~1-10, server up to 100)
MAX_SLICE_SECONDS = 3600   # one claim covers at most 1h online
MAX_DEVICES_PER_WALLET = 16
DAY_SECONDS = 86400
DAILY_CAP_BASE = 100 * me.BASE          # per wallet per UTC day (matches live claim server)
GLOBAL_DAILY_CAP_BASE = 100_000 * me.BASE  # whole network per UTC day
DIFFICULTY_FREE_DEVICES = 100              # full reward until this many devices/day
B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def _int(x, n):
    if isinstance(x, bool) or not isinstance(x, int):
        raise ValueError(f"{n} must be int")
    return x


def valid_wallet(pk):
    return isinstance(pk, str) and 32 <= len(pk) <= 44 and set(pk) <= B58


def work_units(power_score, online_seconds, verified_tasks):
    """1 unit ~ 1 second of current emission at power 1. Light: power scales
    with sqrt so a server is not 100x a phone; must have done >=1 real task."""
    p, s, v = _int(power_score, "power_score"), _int(online_seconds, "online_seconds"), _int(verified_tasks, "verified_tasks")
    if not 1 <= p <= MAX_POWER:
        raise ValueError("power_score out of range")
    if not 0 < s <= MAX_SLICE_SECONDS:
        raise ValueError("online_seconds out of range")
    if v <= 0:
        raise ValueError("zero useful work")
    root = 1
    while (root + 1) * (root + 1) <= p * 100:
        root += 1
    return s * root // 10  # sqrt(p) scaled, power 1 -> s units


def difficulty_bps(active_devices, free_devices=DIFFICULTY_FREE_DEVICES):
    """Reward multiplier in bps (10000 = 1x). Shrinks as the network grows."""
    a, f = _int(active_devices, "active_devices"), _int(free_devices, "free_devices")
    if a < 0 or f <= 0:
        raise ValueError("bad difficulty input")
    return me.ONE_X_BPS if a <= f else me.ONE_X_BPS * f // a


def claim_message(c):
    core = {k: c[k] for k in ("wallet", "device_id", "start", "online_seconds", "power_score", "verified_tasks")}
    return DOMAIN + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()


class ClaimLedger:
    def __init__(self, genesis, daily_cap=DAILY_CAP_BASE, global_daily_cap=GLOBAL_DAILY_CAP_BASE):
        self.genesis = _int(genesis, "genesis")
        self.daily_cap = _int(daily_cap, "daily_cap")
        self.global_daily_cap = _int(global_daily_cap, "global_daily_cap")
        if self.daily_cap <= 0 or self.global_daily_cap <= 0:
            raise ValueError("caps must be positive")
        self.day_used = {}    # (day, wallet|"*") -> base units
        self.devices = {}     # device_id -> (wallet, device_pubkey|None)
        self.last_end = {}    # device_id -> end ts of last slice
        self.balances = {}    # wallet -> base units
        self.total = 0
        self.day_devices = {}  # day -> set(device_id) that claimed that UTC day

    def bind(self, wallet, device_id, device_pubkey=None):
        if not valid_wallet(wallet):
            raise ValueError("wallet required")
        if not isinstance(device_id, str) or not device_id:
            raise ValueError("device_id required")
        if device_id in self.devices and self.devices[device_id][0] != wallet:
            raise ValueError("device bound to another wallet")
        n = sum(1 for w, _ in self.devices.values() if w == wallet)
        if device_id not in self.devices and n >= MAX_DEVICES_PER_WALLET:
            raise ValueError("too many devices for wallet")
        self.devices[device_id] = (wallet, device_pubkey)

    def claim(self, c, now, signature=None):
        now = _int(now, "now")
        did = c.get("device_id")
        if did not in self.devices or self.devices[did][0] != c.get("wallet"):
            raise ValueError("unbound device/wallet")
        start, secs = _int(c.get("start"), "start"), _int(c.get("online_seconds"), "online_seconds")
        if start < self.genesis or start + secs > now:
            raise ValueError("slice outside genesis..now")
        if start < self.last_end.get(did, self.genesis):
            raise ValueError("overlapping or replayed slice")
        units = work_units(c.get("power_score"), secs, c.get("verified_tasks"))
        pub = self.devices[did][1]
        if pub is not None:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            try:
                Ed25519PublicKey.from_public_bytes(pub).verify(signature or b"", claim_message(c))
            except Exception:
                raise ValueError("bad signature")
        day, w = now // DAY_SECONDS, c["wallet"]
        active = len(self.day_devices.get(day, set()) | {did})
        dbps = difficulty_bps(active)
        amt = me.reward_for_work(units, now=start, genesis=self.genesis) * dbps // me.ONE_X_BPS
        if amt <= 0:
            raise ValueError("reward rounds to zero")
        used, gused = self.day_used.get((day, w), 0), self.day_used.get((day, "*"), 0)
        amt = min(amt, self.daily_cap - used, self.global_daily_cap - gused)
        if amt <= 0:
            raise ValueError("daily cap reached")
        if self.total + amt > me.emitted_until(now, self.genesis):
            raise ValueError("exceeds emission schedule")
        self.last_end[did] = start + secs
        self.balances[w] = self.balances.get(w, 0) + amt
        self.day_used[(day, w)] = used + amt
        self.day_used[(day, "*")] = gused + amt
        self.total += amt
        self.day_devices.setdefault(day, set()).add(did)
        return {"scheme": SCHEME, "wallet": w, "units": units, "agis_base": amt,
                "difficulty_bps": dbps, "active_devices": active}

    def remaining_today(self, wallet, now):
        """Base units `wallet` can still earn in the UTC day containing `now`."""
        day = _int(now, "now") // DAY_SECONDS
        return max(0, min(self.daily_cap - self.day_used.get((day, wallet), 0),
                          self.global_daily_cap - self.day_used.get((day, "*"), 0)))
