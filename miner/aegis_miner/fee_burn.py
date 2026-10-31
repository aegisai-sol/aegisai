"""Pay-to-verify AGIS burn (pov-r/fee-burn/1) -- BME+ demand sink.

When a customer pays for a verification in AGIS, that AGIS is committed to burn (destroyed), not recycled into the
miner pool. This module emits a domain-separated Ed25519 burn voucher bound to scheme + receipt_id + payer_id +
agis_burned (+ fee_quoted). Each receipt_id can be burned once. Fail closed: bad input raises ValueError and nothing
is consumed. Separate from reservoir.SPLIT_BPS "burn" (5% fee-split accounting) and from credit_settle miner pay.
Off-chain ledger only: no mint, no on-chain tx, no network. BurnLedger is in-memory (restart forgets burned ids;
persist or anchor before production, same limitation as credit_settle).
"""
import json
from . import card_attest as ca

SCHEME = "pov-r/fee-burn/1"
DOMAIN = b"AEGIS/fee-burn/burn-voucher/v1"
FIELDS = ("receipt_id", "payer_id", "agis_burned", "fee_quoted")

def _pos(x): return not isinstance(x, bool) and isinstance(x, int) and x > 0

def voucher_message(v):
    core = {k: v.get(k) for k in FIELDS}
    return DOMAIN + b"\n" + SCHEME.encode() + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

class BurnLedger:
    def __init__(self): self.burned, self.total_burned = {}, 0
    def is_burned(self, receipt_id): return receipt_id in self.burned

_DEFAULT = BurnLedger()

def burn_for_verify(job_receipt_id, agis_amount, payer_id, burn_key, fee_quoted=None, ledger=None):
    ledger = _DEFAULT if ledger is None else ledger
    if not isinstance(job_receipt_id, str) or not job_receipt_id: raise ValueError("receipt_id required")
    if not isinstance(payer_id, str) or not payer_id: raise ValueError("payer_id required")
    if not _pos(agis_amount): raise ValueError("agis_amount must be positive whole AGIS")
    if fee_quoted is None: fee_quoted = agis_amount
    if not _pos(fee_quoted) or agis_amount != fee_quoted: raise ValueError("amount must equal quoted fee")
    if ledger.is_burned(job_receipt_id): raise ValueError("receipt already burned")
    ed, _ = ca._ed()
    if ed is None or not ca._hexn(burn_key, 64): raise ValueError("bad signing key or ed25519 unavailable")
    v = {"scheme": SCHEME, "receipt_id": job_receipt_id, "payer_id": payer_id, "agis_burned": agis_amount,
         "fee_quoted": fee_quoted}
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(burn_key)).sign(voucher_message(v)).hex()
    ledger.burned[job_receipt_id] = agis_amount; ledger.total_burned += agis_amount
    return {**v, "pubkey": ca.pubkey_from_seed(burn_key), "sig": sig}

def verify_burn_voucher(voucher, trusted_pubkey):
    """True iff trusted signature over intact fields and agis_burned == fee_quoted > 0. Never raises."""
    try:
        keys = {trusted_pubkey} if isinstance(trusted_pubkey, str) else set(trusted_pubkey)
        v = voucher
        if v.get("scheme") != SCHEME or v.get("pubkey") not in keys: return False
        if not (isinstance(v["receipt_id"], str) and v["receipt_id"] and isinstance(v["payer_id"], str) and v["payer_id"]):
            return False
        if not (_pos(v["agis_burned"]) and v["agis_burned"] == v["fee_quoted"]): return False
        ed, _ = ca._ed()
        ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(v["pubkey"])).verify(bytes.fromhex(v["sig"]), voucher_message(v))
        return True
    except Exception:
        return False
