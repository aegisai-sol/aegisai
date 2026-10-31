"""Verify-then-Act gate (stub). An agent proposes an action on a claim; the gate answers
ALLOW / DENY / REQUIRE_RECEIPT from the local receipt store. Pure read-only: never signs, mints or posts.
  ALLOW            a non-flagged receipt with an intact digest has the claim voted TRUE
  DENY             a valid receipt has the claim voted FALSE (contradicted), or the receipt was tampered
  REQUIRE_RECEIPT  no valid receipt covers the claim (or only UNSURE / flagged ones) -> run /v1/verify first
"""
import hashlib, json, os, re
from aegis_miner import token_bridge
ACTIONS = ("publish", "post", "cite", "trade", "pay", "execute")

def claim_digest(text):
    """SHA-256 of the normalized claim (casefold, collapsed whitespace, trailing punctuation stripped)."""
    t = re.sub(r"\s+", " ", (text or "").casefold()).strip().rstrip(".!?;: ")
    return hashlib.sha256(t.encode()).hexdigest()

def _receipts(store):
    if not os.path.isdir(store): return
    for f in sorted(os.listdir(store)):
        if f.endswith(".json"):
            try: yield json.load(open(os.path.join(store, f)))
            except Exception: continue

def decide(action, store, claim=None, digest=None):
    act = str(action or "").split(" ", 1)[0].casefold()
    if act not in ACTIONS: raise ValueError(f"action must start with one of {ACTIONS}")
    d = digest or (claim_digest(claim) if claim else None)
    if not d or not re.fullmatch(r"[0-9a-f]{64}", d): raise ValueError("need claim text or 64-hex claim_digest")
    seen = []
    for r in _receipts(store):
        for c in r.get("claims", []):
            if c.get("canary") or claim_digest(c.get("text")) != d: continue
            intact = r.get("digest") == token_bridge.receipt_digest(r)
            seen.append({"receipt_id": r.get("receipt_id"), "vote": c.get("vote"), "flagged": bool(r.get("flagged")), "intact": intact})
    base = {"action": action, "claim_digest": d, "matches": seen[:10], "note": "Gate is advisory and read-only; no signing or on-chain action."}
    if any(not m["intact"] for m in seen): return dict(base, decision="DENY", reason="receipt digest mismatch (tampered)")
    good = [m for m in seen if not m["flagged"]]
    if any(m["vote"] == "FALSE" for m in good): return dict(base, decision="DENY", reason="claim contradicted by a valid receipt")
    hit = next((m for m in good if m["vote"] == "TRUE"), None)
    if hit: return dict(base, decision="ALLOW", reason="valid receipt supports claim", receipt_id=hit["receipt_id"])
    return dict(base, decision="REQUIRE_RECEIPT", reason="no valid supporting receipt; call POST /v1/verify first" if not seen else "only unsure/flagged receipts")
