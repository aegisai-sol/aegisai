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
