"""pov-r/mine-claim/1 -- wallet-bound mining reward claims (off-chain ledger).

Plain rules: no wallet, no mining. A miner binds a Solana wallet pubkey to a
device_id, then claims AGIS for a work slice. Reward grows with device power
(power_score, 1..MAX_POWER) and time connected (online_seconds), capped per
slice, and stays inside the mine_emit halving schedule.

Human-configured AI bots are allowed. Blocked (fail closed, ValueError, nothing
recorded): zero useful work, overlapping/replayed slices, one wallet faking
more devices than MAX_DEVICES_PER_WALLET, slices from the future, bad wallet.
Optional Ed25519: if a device pubkey was bound, each claim must be signed.
Integer math only; no RPC, no mint here (on-chain mint is a separate step).
"""
import json
from . import mine_emit as me

SCHEME = "pov-r/mine-claim/1"
DOMAIN = b"AEGIS/mine-claim/v1"
MAX_POWER = 100            # power_score 1..100 (phone ~1-10, server up to 100)
MAX_SLICE_SECONDS = 3600   # one claim covers at most 1h online
MAX_DEVICES_PER_WALLET = 16
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


def claim_message(c):
    core = {k: c[k] for k in ("wallet", "device_id", "start", "online_seconds", "power_score", "verified_tasks")}
    return DOMAIN + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()


class ClaimLedger:
    def __init__(self, genesis):
        self.genesis = _int(genesis, "genesis")
        self.devices = {}     # device_id -> (wallet, device_pubkey|None)
        self.last_end = {}    # device_id -> end ts of last slice
        self.balances = {}    # wallet -> base units
        self.total = 0

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
        amt = me.reward_for_work(units, now=start, genesis=self.genesis)
        if self.total + amt > me.emitted_until(now, self.genesis):
            raise ValueError("exceeds emission schedule")
        self.last_end[did] = start + secs
        self.balances[c["wallet"]] = self.balances.get(c["wallet"], 0) + amt
        self.total += amt
        return {"scheme": SCHEME, "wallet": c["wallet"], "units": units, "agis_base": amt}
