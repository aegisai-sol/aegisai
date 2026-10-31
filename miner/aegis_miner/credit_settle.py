"""Proof Credits auto-settle into signed AGIS claim vouchers (pov-r/credit-settle/1).

Economics: Proof Credits stay NON-TRANSFERABLE work receipts and never convert 1:1 into free AGIS. They settle only
against the Reservoir fee pool of a period:

    rate = fee_inflow_agis / max(1, credits_earned_this_period)
    agis_out = min(credits_in * rate, reservoir_available)

More paid verifies -> better rate; credits minted with zero fee inflow settle at zero (anti-inflation). Settling
consumes the credits (each receipt_id settles at most once) and emits an Ed25519 voucher, domain separated, bound to
miner_id + period + credits_in + agis_out + fee_inflow_basis + receipt ids. Credits must be backed by intact receipts
(digest recomputes) or settlement fails closed. Pure Python; no mint, no network. Amounts are integer base units.
"""
import json
from . import card_attest as ca, token_bridge

SCHEME = "pov-r/credit-settle/1"
VOUCHER_FIELDS = ("miner_id", "period", "credits_in", "agis_out", "fee_inflow_basis", "credits_earned_period",
                  "receipt_ids")

def _int(x): return not isinstance(x, bool) and isinstance(x, int) and x >= 0

def compute_settle_rate(fee_inflow_agis, credits_earned_period):
    """Return (numerator, denominator) of the AGIS-per-credit rate (exact integer math)."""
    if not _int(fee_inflow_agis) or not _int(credits_earned_period): raise ValueError("non-negative ints required")
    return fee_inflow_agis, max(1, credits_earned_period)

def voucher_message(v):
    core = {k: v.get(k) for k in VOUCHER_FIELDS}
    return SCHEME.encode() + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

def _receipt_ok(r, miner_id):
    try:
        return (isinstance(r, dict) and r.get("client_id") == miner_id and _int(r.get("credits_awarded"))
                and r["credits_awarded"] > 0 and r.get("digest") == token_bridge.receipt_digest(r))
    except Exception:
        return False

class Period:
    """One settlement period: fee inflow into the Reservoir, credits earned, available balance, consumed receipts."""
    def __init__(self, period, fee_inflow_agis, credits_earned, reservoir_available):
        for x in (fee_inflow_agis, credits_earned, reservoir_available):
            if not _int(x): raise ValueError("non-negative ints required")
        self.period, self.fee_inflow, self.credits_earned = period, fee_inflow_agis, credits_earned
        self.available, self.consumed = reservoir_available, set()

    def preview(self, credits_in):
        n, d = compute_settle_rate(self.fee_inflow, self.credits_earned)
        return min(credits_in * n // d, self.available)

def settle_credits(period, miner_id, receipts, seed_hex):
    """Consume the credits on `receipts` and return a signed voucher. Raises ValueError (fail closed) on any bad,
    foreign, duplicate or already-settled receipt; nothing is consumed on failure."""
    if not isinstance(miner_id, str) or not miner_id: raise ValueError("miner_id required")
    if not receipts: raise ValueError("no receipts")
    ids = []
    for r in receipts:
        if not _receipt_ok(r, miner_id): raise ValueError("receipt not intact or not owned by miner")
        rid = r["receipt_id"]
        if rid in period.consumed or rid in ids: raise ValueError(f"receipt {rid} already settled")
        ids.append(rid)
    credits_in = sum(r["credits_awarded"] for r in receipts)
    agis_out = period.preview(credits_in)
    v = {"scheme": SCHEME, "miner_id": miner_id, "period": period.period, "credits_in": credits_in,
         "agis_out": agis_out, "fee_inflow_basis": period.fee_inflow, "credits_earned_period": period.credits_earned,
         "receipt_ids": sorted(ids)}
    ed, _ = ca._ed()
    if ed is None or not ca._hexn(seed_hex, 64): raise ValueError("bad signing key or ed25519 unavailable")
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(voucher_message(v)).hex()
    period.consumed.update(ids); period.available -= agis_out
    return {**v, "pubkey": ca.pubkey_from_seed(seed_hex), "sig": sig}

def verify_voucher(v, trusted_pubkeys):
    """True iff the voucher is signed by a trusted key and internally consistent (agis_out never exceeds the rate).
    Never raises."""
    try:
        if v.get("scheme") != SCHEME or v.get("pubkey") not in set(trusted_pubkeys): return False
        if not all(_int(v[k]) for k in ("credits_in", "agis_out", "fee_inflow_basis", "credits_earned_period")): return False
        n, d = compute_settle_rate(v["fee_inflow_basis"], v["credits_earned_period"])
        if v["agis_out"] > v["credits_in"] * n // d: return False
        ed, _ = ca._ed()
        ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(v["pubkey"])).verify(bytes.fromhex(v["sig"]), voucher_message(v))
        return True
    except Exception:
        return False
