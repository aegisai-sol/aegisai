"""Proof Credits -> AGIS, JOB-SCOPED (pov-r/credit-settle/1, job-scoped revision).

Plain rule: AGIS only ever comes out of ONE concrete, PAID verification job's fee. That job's fee splits exactly like
the Reservoir ledger (reservoir.SPLIT_BPS): 70% miners / 20% reservoir / 5% treasury / 5% burn. The 70% miner pool is
shared pro-rata only among the miners who earned credits on THAT receipt. Free/demo/unpaid verifies still mint
non-transferable Proof Credits, but as reputation only: they have no AGIS settle path (agis_out is always 0).

There is deliberately NO period-wide rate (fee_inflow / credits_earned): a miner's payout can't be diluted by credits
on unrelated jobs, and nobody can farm a shared pool. Settling consumes that miner's credits on that receipt once and
emits an Ed25519 voucher (domain separated) bound to miner_id + receipt_id + job_fee + agis_out. Fail closed on
missing/tampered receipts, double settle, or anything that would exceed the job's miner share. Pure Python, integer
base units; no mint, no network.
"""
import json
from . import card_attest as ca, token_bridge, reservoir

SCHEME = "pov-r/credit-settle/1"
DOMAIN = b"AEGIS/credit-settle/job-voucher/v1"
VOUCHER_FIELDS = ("miner_id", "receipt_id", "job_fee", "paid", "credits_in", "job_credits_total", "agis_out")

def _int(x): return not isinstance(x, bool) and isinstance(x, int) and x >= 0

def miner_pool(job_fee):
    """The job's miner share (70% via reservoir.SPLIT_BPS); hard ceiling on all AGIS paid out for the job."""
    if not _int(job_fee): raise ValueError("non-negative int fee required")
    return job_fee * reservoir.SPLIT_BPS["miners"] // 10000

def voucher_message(v):
    core = {k: v.get(k) for k in VOUCHER_FIELDS}
    return DOMAIN + b"\n" + SCHEME.encode() + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

def _credit_ok(r, receipt_id):
    try:
        return (isinstance(r, dict) and r.get("receipt_id") == receipt_id and isinstance(r.get("client_id"), str)
                and r["client_id"] and _int(r.get("credits_awarded")) and r["credits_awarded"] > 0
                and r.get("digest") == token_bridge.receipt_digest(r))
    except Exception:
        return False

class Job:
    """One verification job (receipt_id). `credit_receipts` are the per-miner credit receipts earned on it (each
    digest-intact, receipt_id == this job, one per miner). `paid` False => reputation-only, zero AGIS."""
    def __init__(self, receipt_id, job_fee, paid, credit_receipts):
        if not isinstance(receipt_id, str) or not receipt_id: raise ValueError("receipt_id required")
        if not _int(job_fee) or not isinstance(paid, bool): raise ValueError("bad fee/paid")
        if not credit_receipts: raise ValueError("no credit receipts")
        self.credits = {}
        for r in credit_receipts:
            if not _credit_ok(r, receipt_id): raise ValueError("credit receipt missing, tampered or for another job")
            if r["client_id"] in self.credits: raise ValueError("duplicate miner on job")
            self.credits[r["client_id"]] = r["credits_awarded"]
        self.receipt_id, self.paid = receipt_id, paid
        self.job_fee = job_fee if paid else 0
        self.total = sum(self.credits.values())
        self.pool = miner_pool(self.job_fee)
        self.settled, self.paid_out = set(), 0

    def preview(self, miner_id):
        if miner_id not in self.credits: raise ValueError("miner earned no credits on this receipt")
        return self.pool * self.credits[miner_id] // self.total

def settle_credits(job, miner_id, seed_hex):
    """Consume miner's credits on this job, return a signed voucher. Raises ValueError (fail closed); nothing is
    consumed on failure. Unpaid job -> agis_out 0 (reputation only)."""
    if not isinstance(job, Job): raise ValueError("job required")
    if miner_id in job.settled: raise ValueError("credits already settled")
    agis_out = job.preview(miner_id)
    if job.paid_out + agis_out > job.pool: raise ValueError("would exceed job miner share")
    v = {"scheme": SCHEME, "miner_id": miner_id, "receipt_id": job.receipt_id, "job_fee": job.job_fee,
         "paid": job.paid, "credits_in": job.credits[miner_id], "job_credits_total": job.total, "agis_out": agis_out}
    ed, _ = ca._ed()
    if ed is None or not ca._hexn(seed_hex, 64): raise ValueError("bad signing key or ed25519 unavailable")
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(voucher_message(v)).hex()
    job.settled.add(miner_id); job.paid_out += agis_out
    return {**v, "pubkey": ca.pubkey_from_seed(seed_hex), "sig": sig}

def verify_voucher(v, trusted_pubkeys):
    """True iff trusted signature and agis_out <= this miner's pro-rata slice of the job's 70% share (0 if unpaid).
    Never raises."""
    try:
        if v.get("scheme") != SCHEME or v.get("pubkey") not in set(trusted_pubkeys): return False
        if not all(_int(v[k]) for k in ("job_fee", "credits_in", "job_credits_total", "agis_out")): return False
        if not isinstance(v["paid"], bool) or not v["receipt_id"] or v["credits_in"] > v["job_credits_total"] \
                or v["job_credits_total"] == 0: return False
        if not v["paid"] and (v["job_fee"] or v["agis_out"]): return False
        if v["agis_out"] > miner_pool(v["job_fee"]) * v["credits_in"] // v["job_credits_total"]: return False
        ed, _ = ca._ed()
        ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(v["pubkey"])).verify(bytes.fromhex(v["sig"]), voucher_message(v))
        return True
    except Exception:
        return False
