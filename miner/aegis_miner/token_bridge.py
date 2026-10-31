"""Receipt -> Proof Credit ledger -> (later) AGIS claim path. Working hooks, Option A safe.
Token state lives behind TokenState. Today: OffchainState (jsonl, no token). Later: SplState reading the
SPL mint + Reservoir token account on Solana. No private keys are ever read here: signing is done by the
operator's Phantom / vault-held keypair outside this process; we only emit unsigned claim intents."""
import os
import hashlib, json, os, time
from aegis_miner import credits
from aegis_miner import claim_merkle as _cm

RESERVOIR_SUPPLY = 400_000_000          # 40% of 1B AGIS (whitepaper); not minted (Option A)
FEE_SHARE_CAP, RESERVOIR_PERIOD_CAP = 0.70, 0.005

def receipt_digest(rec):
    """Canonical SHA-256 of a receipt (what gets anchored via devnet memo later)."""
    core = {k: rec[k] for k in ("receipt_id", "client_id", "claims", "credits_awarded") if k in rec}
    if "nonce" in rec:  # nonce-bound receipts (replay protection) also bind ts, so TTL can't be dodged by editing ts
        core.update(nonce=rec["nonce"], ts=rec.get("ts"))
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

def audit_receipt(rec, secret=None, store_dir=None):
    """Third-party integrity audit of a presented receipt body (no side effects, secret never returned).
    digest_ok: rec['digest'] recomputes; mac: absent|valid|invalid|unchecked(no key here);
    known: stored copy with same id has the same digest (None if no store / not found);
    intact: digest_ok and mac not invalid/required-missing and known is not False."""
    if not isinstance(rec, dict) or not isinstance(rec.get("receipt_id"), str):
        raise ValueError("receipt object with receipt_id required")
    want = receipt_digest(rec)
    digest_ok = rec.get("digest") == want
    k = secret if secret is not None else hmac_secret()
    if not k: mac = "unchecked" if "mac" in rec else "absent"
    elif "mac" not in rec: mac = "missing"
    else: mac = "valid" if mac_ok(rec, k) else "invalid"
    known = None
    rid = rec["receipt_id"]
    if store_dir and rid.isalnum():
        f = os.path.join(store_dir, rid + ".json")
        if os.path.exists(f):
            try: known = json.load(open(f)).get("digest") == rec.get("digest")
            except Exception: known = False
    intact = digest_ok and mac not in ("invalid", "missing") and known is not False
    return {"receipt_id": rid, "intact": intact, "digest_ok": digest_ok, "mac": mac, "known": known,
            "protocol_version": rec.get("protocol_version")}

def receipt_proof(rec, secret=None, store_dir=None):
    """Compact shareable proof card for a stored receipt: digest/nonce/schema + vote tally + self-audit.
    Privacy: no claim texts, evidence, client_id, or MAC value are included (only mac_present)."""
    if not isinstance(rec, dict) or not isinstance(rec.get("receipt_id"), str):
        raise ValueError("receipt object with receipt_id required")
    claims = [c for c in (rec.get("claims") or []) if isinstance(c, dict) and not c.get("canary")]
    tally = {}
    for c in claims:
        v = str(c.get("vote") or "UNSURE").upper(); tally[v] = tally.get(v, 0) + 1
    cal = rec.get("calibration") if isinstance(rec.get("calibration"), dict) else {}
    a = audit_receipt(rec, secret=secret, store_dir=store_dir)
    return {"receipt_id": rec["receipt_id"], "digest": rec.get("digest"), "nonce": rec.get("nonce"),
            "protocol_version": rec.get("protocol_version"), "claim_schema": rec.get("claim_schema"),
            "ts": rec.get("ts"), "claim_count": len(claims), "votes": dict(sorted(tally.items())),
            "calibration_ok": cal.get("ok"), "flagged": bool(rec.get("flagged")), "mac_present": "mac" in rec,
            "onchain": rec.get("onchain") if isinstance(rec.get("onchain"), dict) else None,
            "audit": {k: a[k] for k in ("intact", "digest_ok", "mac")}, "claims_root": _cm.claims_root(rec)}

AUDIT_BATCH_MAX = 50

def audit_batch(recs, secret=None, store_dir=None, max_items=AUDIT_BATCH_MAX):
    """Audit up to max_items receipts in one call. Malformed items get an error entry (batch never 400s on one bad item).
    In-batch replay: a receipt_id or nonce seen twice marks every later copy duplicate and not intact.
    all_intact is True only if every item audited intact and the batch is non-empty."""
    if not isinstance(recs, list) or not recs: raise ValueError("receipts must be a non-empty list")
    if len(recs) > max_items: raise ValueError(f"at most {max_items} receipts per batch")
    k = secret if secret is not None else hmac_secret()
    seen_ids, seen_nonces, out, dup_ids, dup_nonces = set(), set(), [], [], []
    for i, r in enumerate(recs):
        try: a = audit_receipt(r, secret=k, store_dir=store_dir)
        except ValueError as e:
            out.append({"index": i, "intact": False, "error": str(e)[:120]}); continue
        a["index"] = i; a["duplicate"] = False
        rid, n = a["receipt_id"], r.get("nonce")
        if rid in seen_ids: a["duplicate"] = True; dup_ids.append(rid)
        if isinstance(n, str) and n in seen_nonces: a["duplicate"] = True; dup_nonces.append(n)
        seen_ids.add(rid)
        if isinstance(n, str): seen_nonces.add(n)
        if a["duplicate"]: a["intact"] = False
        out.append(a)
    ok = sum(1 for a in out if a["intact"])
    return {"count": len(out), "intact_count": ok, "all_intact": ok == len(out),
            "duplicate_ids": sorted(set(dup_ids)), "duplicate_nonces_count": len(set(dup_nonces)), "results": out}

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
