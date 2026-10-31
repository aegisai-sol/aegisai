"""Receipt -> Proof Credit ledger -> (later) AGIS claim path. Working hooks, Option A safe.
Token state lives behind TokenState. Today: OffchainState (jsonl, no token). Later: SplState reading the
SPL mint + Reservoir token account on Solana. No private keys are ever read here: signing is done by the
operator's Phantom / vault-held keypair outside this process; we only emit unsigned claim intents."""
import os
import hashlib, json, os, time
from aegis_miner import credits

RESERVOIR_SUPPLY = 400_000_000          # 40% of 1B AGIS (whitepaper); not minted (Option A)
FEE_SHARE_CAP, RESERVOIR_PERIOD_CAP = 0.70, 0.005

def receipt_digest(rec):
    """Canonical SHA-256 of a receipt (what gets anchored via devnet memo later)."""
    core = {k: rec[k] for k in ("receipt_id", "client_id", "claims", "credits_awarded") if k in rec}
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def hmac_secret():
    """AEGIS_RECEIPT_HMAC secret bytes or None. Never logged or returned."""
    v = os.environ.get("AEGIS_RECEIPT_HMAC", "")
    return v.encode() if v else None

def receipt_mac(rec, secret=None):
    """HMAC-SHA256 over the receipt digest. Returns None when no secret configured."""
    import hmac as _hm
    k = secret if secret is not None else hmac_secret()
    if not k: return None
    return "hmac-sha256:" + _hm.new(k, receipt_digest(rec).encode(), hashlib.sha256).hexdigest()

def mac_ok(rec, secret=None):
    """True if no secret configured, else constant-time check of rec['mac']."""
    import hmac as _hm
    want = receipt_mac(rec, secret)
    if want is None: return True
    got = rec.get("mac")
    return isinstance(got, str) and _hm.compare_digest(got, want)

class TokenState:
    mode = "abstract"
    def mint(self): return None
    def reservoir_remaining(self): raise NotImplementedError
    def period_fees_usd(self): raise NotImplementedError
    def agis_price_usd(self): raise NotImplementedError

class OffchainState(TokenState):
    """Pre-mint: no token exists, so the claimable amount is always 0 but the math runs end to end."""
    mode = "offchain (Option A: no mint)"
    def __init__(self, fees_usd=0.0, price_usd=None): self.fees, self.price = fees_usd, price_usd
    def reservoir_remaining(self): return RESERVOIR_SUPPLY
    def period_fees_usd(self): return self.fees
    def agis_price_usd(self): return self.price

class SplState(TokenState):
    """Post-mint hook. Fill AEGIS_MINT + AEGIS_RESERVOIR_ATA; reads balances via public RPC only."""
    mode = "spl"
    def __init__(self, mint, reservoir_ata, rpc="https://api.devnet.solana.com"):
        self.mint_addr, self.ata, self.rpc = mint, reservoir_ata, rpc
    def mint(self): return self.mint_addr
    def reservoir_remaining(self):
        from aegis_miner.solana_submit import _rpc
        return float(_rpc(self.rpc, "getTokenAccountBalance", [self.ata])["value"]["uiAmount"] or 0)
    def period_fees_usd(self): raise NotImplementedError("fee ledger not wired yet")
    def agis_price_usd(self): raise NotImplementedError("price oracle (LP) not wired yet")

def state_from_env():
    m, a = os.environ.get("AEGIS_MINT"), os.environ.get("AEGIS_RESERVOIR_ATA")
    return SplState(m, a, os.environ.get("AEGIS_RPC", "https://api.devnet.solana.com")) if m and a else OffchainState()

def claim_quote(ledger_path, client_id, total_period_credits, state):
    """Pro-rata AGIS this client could claim this period, under both caps. 0 while no mint/price."""
    mine = credits.balance(ledger_path, client_id)
    q = {"client_id": client_id, "credits": mine, "token_mode": state.mode, "mint": state.mint(), "claimable_agis": 0.0}
    price = state.agis_price_usd()
    if not state.mint() or not price or not total_period_credits:
        q["reason"] = "no AGIS mint / price yet (Option A) — credits accrue, claim opens after mint+LP+audit"; return q
    pool = min(FEE_SHARE_CAP * state.period_fees_usd() / price, RESERVOIR_PERIOD_CAP * state.reservoir_remaining())
    q["period_pool_agis"], q["claimable_agis"] = pool, pool * mine / total_period_credits
    return q

def claim_intent(quote, wallet_pubkey):
    """Unsigned claim intent for the operator to review+sign in Phantom. Never signs, never sends."""
    if quote["claimable_agis"] <= 0: return None
    return {"type": "agis_claim_intent", "to": wallet_pubkey, "amount": quote["claimable_agis"],
            "mint": quote["mint"], "credits_burned": quote["credits"], "created_at": int(time.time()), "signed": False}
