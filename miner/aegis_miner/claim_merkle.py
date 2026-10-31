"""Selective claim disclosure for PoV-R receipts (Merkle commitment over non-canary claims).

A receipt holder can prove ONE verified claim (text + vote) belonged to a receipt without revealing
the other claims, evidence, client_id or MAC. The proof card publishes claims_root; a disclosure carries
the claim, its salt, index, leaf count and sibling path. Anyone can check it offline with verify_disclosure.

Hashing (domain separated, RFC 6962 style): leaf = H(0x00 || salt || canon({text, vote})),
node = H(0x01 || left || right); an odd last node is promoted unchanged. Salts are derived from the
full stored claim (incl. private evidence) + receipt_id + index, so sibling leaves of short or
guessable claims ("TRUE"/"FALSE") cannot be brute-forced from the path. Canaries are excluded.
"""
import hashlib, json

MAX_PATH = 64

def _h(*parts):
    return hashlib.sha256(b"".join(parts)).hexdigest()

def _canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":")).encode()

def public_claim(c):
    return {"text": str(c.get("text") or ""), "vote": str(c.get("vote") or "UNSURE").upper()}

def leaf_salt(rid, index, claim):
    return _h(b"pov-r/leaf-salt|", str(rid).encode(), b"|", str(index).encode(), b"|", _canon(claim))

def leaf_hash(salt, pub):
    return _h(b"\x00", bytes.fromhex(salt), _canon(pub))

def real_claims(rec):
    return [c for c in (rec.get("claims") or []) if isinstance(c, dict) and not c.get("canary")]

def _levels(leaves):
    lv = [leaves]
    while len(lv[-1]) > 1:
        cur, nxt = lv[-1], []
        for i in range(0, len(cur), 2):
            nxt.append(_h(b"\x01", bytes.fromhex(cur[i]), bytes.fromhex(cur[i + 1])) if i + 1 < len(cur) else cur[i])
        lv.append(nxt)
    return lv

def _leaves(rec):
    rid = rec.get("receipt_id")
    return [leaf_hash(leaf_salt(rid, i, c), public_claim(c)) for i, c in enumerate(real_claims(rec))]

def claims_root(rec):
    """Merkle root over non-canary claims, or None if the receipt has no real claims."""
    lv = _leaves(rec)
    return _levels(lv)[-1][0] if lv else None

def disclose(rec, index):
    """Disclosure for claim #index (0-based among non-canary claims). Raises IndexError when out of range."""
    claims = real_claims(rec)
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(claims): raise IndexError("claim index out of range")
    levels, path, i = _levels(_leaves(rec)), [], index
    for lvl in levels[:-1]:
        sib = i ^ 1
        if sib < len(lvl): path.append({"side": "L" if sib < i else "R", "hash": lvl[sib]})
        i //= 2
    c = claims[index]
    return {"receipt_id": rec.get("receipt_id"), "digest": rec.get("digest"), "index": index, "leaf_count": len(claims),
            "claim": public_claim(c), "salt": leaf_salt(rec.get("receipt_id"), index, c), "path": path,
            "claims_root": levels[-1][0], "scheme": "pov-r/claim-merkle/1"}

def _hex64(s):
    return isinstance(s, str) and len(s) == 64 and all(ch in "0123456789abcdef" for ch in s)

def verify_disclosure(d, expected_root=None):
    """Check a disclosure. expected_root should come from the receipt's proof card (trusted channel).
    Returns {ok, reason, root}; never raises on malformed input."""
    try:
        if not isinstance(d, dict): return {"ok": False, "reason": "disclosure must be an object"}
        idx, n, path, salt = d.get("index"), d.get("leaf_count"), d.get("path"), d.get("salt")
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in (idx, n)) or not 0 <= idx < n:
            return {"ok": False, "reason": "bad index/leaf_count"}
        if not _hex64(salt): return {"ok": False, "reason": "bad salt"}
        if not isinstance(path, list) or len(path) > MAX_PATH: return {"ok": False, "reason": "bad path"}
        cl = d.get("claim")
        if not isinstance(cl, dict): return {"ok": False, "reason": "claim required"}
        h, i, width, used = leaf_hash(salt, public_claim(cl)), idx, n, 0
        while width > 1:  # replay tree shape so the path length/sides must match index + leaf_count exactly
            sib = i ^ 1
            if sib < width:
                if used >= len(path): return {"ok": False, "reason": "path too short"}
                p = path[used]; used += 1
                if not isinstance(p, dict) or not _hex64(p.get("hash")) or p.get("side") != ("L" if sib < i else "R"):
                    return {"ok": False, "reason": "bad path step"}
                a, b = (p["hash"], h) if p["side"] == "L" else (h, p["hash"])
                h = _h(b"\x01", bytes.fromhex(a), bytes.fromhex(b))
            i //= 2; width = (width + 1) // 2
        if used != len(path): return {"ok": False, "reason": "path too long"}
        root = expected_root if expected_root is not None else d.get("claims_root")
        if not _hex64(root): return {"ok": False, "reason": "bad root"}
        return {"ok": h == root, "reason": None if h == root else "root mismatch", "root": h,
                "root_source": "expected" if expected_root is not None else "embedded(untrusted)"}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}

MAX_SET = 32

def verify_disclosure_set(ds, expected_root=None):
    """Verify several disclosures from ONE receipt as a consistent set (e.g. "claims 0 and 3 were both verified").
    Every item must verify against the same root, share receipt_id + leaf_count, and use distinct indices,
    so a holder cannot splice claims from two different receipts or repeat one claim to inflate a count.
    Returns {ok, reason, count, indices, root, items}; never raises."""
    if not isinstance(ds, list) or not ds: return {"ok": False, "reason": "disclosures must be a non-empty list", "count": 0}
    if len(ds) > MAX_SET: return {"ok": False, "reason": f"too many disclosures (max {MAX_SET})", "count": len(ds)}
    items = [verify_disclosure(d, expected_root) for d in ds]
    out = {"count": len(ds), "items": items, "indices": [d.get("index") if isinstance(d, dict) else None for d in ds]}
    bad = [i for i, v in enumerate(items) if not v.get("ok")]
    if bad: return {**out, "ok": False, "reason": f"item {bad[0]} failed: {items[bad[0]].get('reason')}"}
    if len({d.get("receipt_id") for d in ds}) != 1: return {**out, "ok": False, "reason": "mixed receipt_id"}
    if len({d.get("leaf_count") for d in ds}) != 1: return {**out, "ok": False, "reason": "mixed leaf_count"}
    if len({v.get("root") for v in items}) != 1: return {**out, "ok": False, "reason": "mixed roots"}
    if len(set(out["indices"])) != len(ds): return {**out, "ok": False, "reason": "duplicate index"}
    return {**out, "ok": True, "reason": None, "root": items[0]["root"], "receipt_id": ds[0].get("receipt_id"),
            "leaf_count": ds[0].get("leaf_count"), "root_source": items[0].get("root_source")}

MAX_MULTI = 256

def _multi_walk(n, known, sibling):
    """Shared prover/verifier replay of the tree for a set of known leaves. sibling(level, idx) returns the
    hash of a needed sibling that is not derivable from the known set. Returns the root."""
    width, level = n, 0
    while width > 1:
        nxt = {}
        for i in sorted(known):
            p = i // 2
            if p in nxt: continue
            sib = i ^ 1
            if sib >= width: nxt[p] = known[i]; continue
            sh = known[sib] if sib in known else sibling(level, sib)
            a, b = (known[i], sh) if i % 2 == 0 else (sh, known[i])
            nxt[p] = _h(b"\x01", bytes.fromhex(a), bytes.fromhex(b))
        known, width, level = nxt, (width + 1) // 2, level + 1
    return known[0]

def disclose_multi(rec, indices):
    """Compact multiproof for several claims of one receipt: siblings shared between paths (or derivable from
    other disclosed leaves) are sent once, so k claims cost far fewer hashes than k separate paths.
    Raises IndexError / ValueError on bad indices."""
    claims = real_claims(rec)
    if not isinstance(indices, list) or not indices or len(indices) > MAX_MULTI: raise ValueError("indices must be a non-empty list")
    if any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(claims) for i in indices): raise IndexError("claim index out of range")
    if len(set(indices)) != len(indices): raise ValueError("duplicate index")
    idx = sorted(indices); rid = rec.get("receipt_id"); lv = _levels(_leaves(rec)); proof = []
    def sib(level, j):
        proof.append(lv[level][j]); return lv[level][j]
    root = _multi_walk(len(claims), {i: lv[0][i] for i in idx}, sib)
    return {"receipt_id": rid, "digest": rec.get("digest"), "leaf_count": len(claims), "indices": idx,
            "claims": [public_claim(claims[i]) for i in idx], "salts": [leaf_salt(rid, i, claims[i]) for i in idx],
            "proof": proof, "claims_root": root, "scheme": "pov-r/claim-multiproof/1"}

def verify_multi(m, expected_root=None, expected_leaf_count=None):
    """Verify a multiproof. Indices must be strictly ascending (canonical, no duplicates), every proof hash is
    consumed exactly once in replay order, and the recomputed root must equal expected_root (trusted, from the
    proof card) or the embedded root (flagged untrusted). The tree shape does not always pin leaf_count (e.g. 7 vs
    8 leaves can replay identically), so pass expected_leaf_count from the proof card's tally to make a
    "k of N claims" statement trustworthy; otherwise it is flagged embedded(untrusted).
    Returns {ok, reason, root, count, leaf_count, leaf_count_source}; never raises."""
    try:
        if not isinstance(m, dict): return {"ok": False, "reason": "multiproof must be an object"}
        n, idx, cls, salts, proof = m.get("leaf_count"), m.get("indices"), m.get("claims"), m.get("salts"), m.get("proof")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1: return {"ok": False, "reason": "bad leaf_count"}
        if expected_leaf_count is not None and n != expected_leaf_count: return {"ok": False, "reason": "leaf_count mismatch"}
        if not isinstance(idx, list) or not idx or len(idx) > MAX_MULTI: return {"ok": False, "reason": "bad indices"}
        if any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < n for i in idx): return {"ok": False, "reason": "bad indices"}
        if any(b <= a for a, b in zip(idx, idx[1:])): return {"ok": False, "reason": "indices must be strictly ascending"}
        if not isinstance(cls, list) or not isinstance(salts, list) or not len(cls) == len(salts) == len(idx):
            return {"ok": False, "reason": "claims/salts must match indices"}
        if any(not isinstance(c, dict) for c in cls) or any(not _hex64(s) for s in salts): return {"ok": False, "reason": "bad claim or salt"}
        if not isinstance(proof, list) or len(proof) > MAX_PATH * len(idx) or any(not _hex64(p) for p in proof):
            return {"ok": False, "reason": "bad proof"}
        it = iter(proof); short = []
        def sib(level, j):
            v = next(it, None)
            if v is None: short.append(1); return "0" * 64
            return v
        h = _multi_walk(n, {i: leaf_hash(s, public_claim(c)) for i, s, c in zip(idx, salts, cls)}, sib)
        if short: return {"ok": False, "reason": "proof too short"}
        if next(it, None) is not None: return {"ok": False, "reason": "proof too long"}
        root = expected_root if expected_root is not None else m.get("claims_root")
        if not _hex64(root): return {"ok": False, "reason": "bad root"}
        ok = h == root
        return {"ok": ok, "reason": None if ok else "root mismatch", "root": h, "count": len(idx), "leaf_count": n,
                "leaf_count_source": "expected" if expected_leaf_count is not None else "embedded(untrusted)",
                "root_source": "expected" if expected_root is not None else "embedded(untrusted)"}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}
