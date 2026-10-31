"""Verify-then-Act gate (stub). An agent proposes an action on a claim; the gate answers
ALLOW / DENY / REQUIRE_RECEIPT from the local receipt store. Pure read-only: never signs, mints or posts.
  ALLOW            a non-flagged receipt with an intact digest has the claim voted TRUE
  DENY             a valid receipt has the claim voted FALSE (contradicted), or the receipt was tampered
  REQUIRE_RECEIPT  no valid receipt covers the claim (or only UNSURE / flagged ones) -> run /v1/verify first
"""
import hashlib, json, os, re, time, unicodedata
from aegis_miner import token_bridge
MAX_BATCH = 50

def ttl_s():
    """AEGIS_RECEIPT_TTL seconds; 0/unset = receipts never expire."""
    try: return max(0, int(os.environ.get("AEGIS_RECEIPT_TTL", "0")))
    except ValueError: return 0

ACTIONS = ("publish", "post", "cite", "trade", "pay", "execute")

NORM_VERSION = 2  # current claim normalizer; receipts record it as "claim_norm"
NORM_VERSIONS = (1, 2)
_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"})

def normalize_claim(text, version=NORM_VERSION):
    """v1: casefold, collapse whitespace, strip trailing punctuation.
    v2: v1 + Unicode NFKC, smart quotes/dashes -> ASCII, zero-width chars removed."""
    t = text or ""
    if version >= 2:
        t = unicodedata.normalize("NFKC", t).translate(_QUOTES)
        t = re.sub(r"[\u200b-\u200d\ufeff]", "", t)
    elif version != 1: raise ValueError("unknown norm version")
    return re.sub(r"\s+", " ", t.casefold()).strip().rstrip(".!?;: ")

def claim_digest(text, version=NORM_VERSION):
    """SHA-256 of the normalized claim (versioned normalizer)."""
    return hashlib.sha256(normalize_claim(text, version).encode()).hexdigest()

def _claim_matches(text, d):
    """Match a query digest against any known normalizer version (back-compat with v1 receipts)."""
    return any(claim_digest(text, v) == d for v in NORM_VERSIONS)

def _receipts(store):
    if not os.path.isdir(store): return
    for f in sorted(os.listdir(store)):
        if f.endswith(".json"):
            try: yield json.load(open(os.path.join(store, f)))
            except Exception: continue

def decide(action, store, claim=None, digest=None, now=None):
    act = str(action or "").split(" ", 1)[0].casefold()
    if act not in ACTIONS: raise ValueError(f"action must start with one of {ACTIONS}")
    d = digest or (claim_digest(claim) if claim else None)
    if not d or not re.fullmatch(r"[0-9a-f]{64}", d): raise ValueError("need claim text or 64-hex claim_digest")
    seen, ttl, now = [], ttl_s(), now if now is not None else time.time()
    for r in _receipts(store):
        for c in r.get("claims", []):
            if c.get("canary") or not _claim_matches(c.get("text"), d): continue
            intact = r.get("digest") == token_bridge.receipt_digest(r) and token_bridge.mac_ok(r)
            seen.append({"receipt_id": r.get("receipt_id"), "vote": c.get("vote"), "flagged": bool(r.get("flagged")), "intact": intact,
                         "expired": bool(ttl) and (now - float(r.get("ts") or 0)) > ttl})
    base = {"action": action, "claim_digest": d, "matches": seen[:10], "note": "Gate is advisory and read-only; no signing or on-chain action."}
    if any(not m["intact"] for m in seen): return dict(base, decision="DENY", reason="receipt digest/MAC mismatch (tampered or unsigned)")
    good = [m for m in seen if not m["flagged"] and not m["expired"]]
    base["ttl_s"] = ttl
    if any(m["vote"] == "FALSE" for m in good): return dict(base, decision="DENY", reason="claim contradicted by a valid receipt")
    hit = next((m for m in good if m["vote"] == "TRUE"), None)
    if hit: return dict(base, decision="ALLOW", reason="valid receipt supports claim", receipt_id=hit["receipt_id"])
    return dict(base, decision="REQUIRE_RECEIPT", reason="no valid supporting receipt; call POST /v1/verify first" if not seen else "only unsure/flagged/expired receipts")

def decide_batch(action, store, claims):
    """Gate many claims for one action. Overall: DENY if any DENY, else REQUIRE_RECEIPT if any, else ALLOW."""
    if not isinstance(claims, list) or not claims: raise ValueError("claims must be a non-empty list")
    if len(claims) > MAX_BATCH: raise ValueError(f"max {MAX_BATCH} claims per batch")
    now = time.time(); res = []
    for c in claims:
        r = decide(action, store, digest=c[7:]) if isinstance(c, str) and c.startswith("digest:") else decide(action, store, claim=c, now=now)
        res.append({k: r[k] for k in ("claim_digest", "decision", "reason")} | ({"receipt_id": r["receipt_id"]} if "receipt_id" in r else {}))
    ds = {r["decision"] for r in res}
    overall = "DENY" if "DENY" in ds else "REQUIRE_RECEIPT" if "REQUIRE_RECEIPT" in ds else "ALLOW"
    return {"action": action, "decision": overall, "count": len(res), "results": res, "ttl_s": ttl_s(),
            "note": "Gate is advisory and read-only; no signing or on-chain action."}
