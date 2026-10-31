"""Publicly verifiable proof-card attestation (Ed25519) for PoV-R.

The receipt MAC (HMAC) proves integrity only to the coordinator, and an offline proof card is just JSON: anyone
could forge one with their own claims_root and claim_count. A card attestation is an Ed25519 signature by the
coordinator's card key over the card's pinned fields, so a third party holding only the coordinator's public key
can trust the card offline and therefore every disclosure checked against it.

Signed message (domain separated, canonical JSON): b"pov-r/card-attest/1\\n" + canon(pinned fields). Unsigned
extras (e.g. onchain) are deliberately not covered; anything a verifier relies on is in PINNED.
Ed25519 keys are the same curve as Solana accounts, so the pubkey can later be published on-chain.
Requires the optional 'cryptography' package; without it signing is skipped and verification fails closed.
"""
import json

SCHEME = "pov-r/card-attest/1"
PINNED = ("receipt_id", "digest", "nonce", "claims_root", "claim_count", "votes", "protocol_version",
          "claim_schema", "ts", "flagged", "calibration_ok", "mac_present")

def _hexn(s, n):
    return isinstance(s, str) and len(s) == n and all(ch in "0123456789abcdef" for ch in s)

def card_message(card):
    core = {k: card.get(k) for k in PINNED}
    a = card.get("audit")
    core["audit_intact"] = a.get("intact") if isinstance(a, dict) else None
    return SCHEME.encode() + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

def _ed():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        return ed25519, serialization
    except Exception:
        return None, None

def pubkey_from_seed(seed_hex):
    ed, ser = _ed()
    if ed is None or not _hexn(seed_hex, 64): return None
    pk = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).public_key()
    return pk.public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()

def sign_card(card, seed_hex):
    """Return a copy of card with an 'attestation' {scheme, pubkey, sig}. Raises ValueError on a bad seed or when
    Ed25519 is unavailable (caller decides whether to serve unsigned)."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("card signing key must be 64 lowercase hex chars (32-byte seed)")
    body = {k: v for k, v in card.items() if k != "attestation"}
    sk = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))
    return {**body, "attestation": {"scheme": SCHEME, "pubkey": pubkey_from_seed(seed_hex), "sig": sk.sign(card_message(body)).hex()}}

REVOKE_SCHEME = "pov-r/key-revoke/1"
REVOKE_REASONS = ("compromised", "retired")

def revoke_message(pubkey, reason, revoked_at):
    core = {"pubkey": pubkey, "reason": reason, "revoked_at": revoked_at}
    return REVOKE_SCHEME.encode() + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

def make_revocation(seed_hex, reason, revoked_at):
    """Self-signed key revocation (like an OpenPGP revocation cert): only the key holder can revoke, so a third party
    cannot DoS a coordinator by 'revoking' its key, and the statement verifies offline with no registry.
    reason 'compromised' kills every card from that key (an attacker can backdate ts); 'retired' (planned rotation)
    keeps cards with ts < revoked_at valid. Raises ValueError on bad input."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("bad seed")
    if reason not in REVOKE_REASONS: raise ValueError("reason must be compromised|retired")
    if isinstance(revoked_at, bool) or not isinstance(revoked_at, (int, float)) or revoked_at < 0: raise ValueError("bad revoked_at")
    pk = pubkey_from_seed(seed_hex)
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(revoke_message(pk, reason, revoked_at)).hex()
    return {"scheme": REVOKE_SCHEME, "pubkey": pk, "reason": reason, "revoked_at": revoked_at, "sig": sig}

def check_revocation(rev):
    """Return (pubkey, reason, revoked_at) for a valid self-signed revocation, else None. Never raises."""
    try:
        if not isinstance(rev, dict) or rev.get("scheme") != REVOKE_SCHEME: return None
        pk, reason, at, sig = rev.get("pubkey"), rev.get("reason"), rev.get("revoked_at"), rev.get("sig")
        if not _hexn(pk, 64) or not _hexn(sig, 128) or reason not in REVOKE_REASONS: return None
        if isinstance(at, bool) or not isinstance(at, (int, float)) or at < 0: return None
        ed, _ = _ed()
        if ed is None: return None
        ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), revoke_message(pk, reason, at))
        return pk, reason, at
    except Exception:
        return None

def verify_card(card, trusted_pubkeys, revocations=None):
    """Check a card's attestation against a set of trusted pubkeys (hex). Returns {ok, reason, signer}; never raises.
    A card signed by a key not in trusted_pubkeys fails: a forger can always sign with their own key.
    revocations: self-signed pov-r/key-revoke/1 statements; invalid ones are ignored (cannot revoke what you don't hold)."""
    try:
        if not isinstance(card, dict): return {"ok": False, "reason": "proof card must be an object"}
        keys = {k.lower() for k in (trusted_pubkeys or []) if isinstance(k, str)}
        if not keys or any(not _hexn(k, 64) for k in keys): return {"ok": False, "reason": "no valid trusted pubkey"}
        at = card.get("attestation")
        if not isinstance(at, dict): return {"ok": False, "reason": "proof card not attested"}
        if at.get("scheme") != SCHEME: return {"ok": False, "reason": "unknown attestation scheme"}
        pk, sig = at.get("pubkey"), at.get("sig")
        if not _hexn(pk, 64) or not _hexn(sig, 128): return {"ok": False, "reason": "bad attestation fields"}
        if pk not in keys: return {"ok": False, "reason": "signer not trusted"}
        ed, _ = _ed()
        if ed is None: return {"ok": False, "reason": "ed25519 unavailable"}
        try: ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), card_message(card))
        except Exception: return {"ok": False, "reason": "bad signature"}
        for rv in revocations or []:
            c = check_revocation(rv)
            if c is None or c[0] != pk: continue
            ts = card.get("ts")
            if c[1] == "compromised": return {"ok": False, "reason": "signer key revoked (compromised)", "signer": pk}
            if isinstance(ts, bool) or not isinstance(ts, (int, float)) or ts >= c[2]:
                return {"ok": False, "reason": "signer key retired before card ts", "signer": pk}
        return {"ok": True, "reason": None, "signer": pk}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}

ROTATE_SCHEME = "pov-r/key-rotate/1"
MAX_ROTATION_DEPTH = 16

def rotate_message(old_pubkey, new_pubkey, effective_at):
    core = {"old_pubkey": old_pubkey, "new_pubkey": new_pubkey, "effective_at": effective_at}
    return ROTATE_SCHEME.encode() + b"\n" + json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

def _num(x): return not isinstance(x, bool) and isinstance(x, (int, float)) and x >= 0

def make_rotation(old_seed_hex, new_seed_hex, effective_at):
    """Planned key rotation with dual signatures: the OLD key endorses the successor (so a verifier that only pinned
    the old key can follow the chain offline, no re-distribution of trust), and the NEW key countersigns (proof of
    possession, so nobody can 'rotate' onto a key they don't hold). From effective_at the old key may no longer sign
    cards (implicit retirement) and the new key is trusted only for cards with ts >= effective_at. Raises ValueError."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(old_seed_hex, 64) or not _hexn(new_seed_hex, 64): raise ValueError("bad seed")
    if old_seed_hex == new_seed_hex: raise ValueError("new key must differ from old key")
    if not _num(effective_at): raise ValueError("bad effective_at")
    op, np_ = pubkey_from_seed(old_seed_hex), pubkey_from_seed(new_seed_hex)
    msg = rotate_message(op, np_, effective_at)
    sign = lambda s: ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(s)).sign(msg).hex()
    return {"scheme": ROTATE_SCHEME, "old_pubkey": op, "new_pubkey": np_, "effective_at": effective_at,
            "old_sig": sign(old_seed_hex), "new_sig": sign(new_seed_hex)}

def check_rotation(rot):
    """Return (old_pubkey, new_pubkey, effective_at) for a valid dual-signed rotation, else None. Never raises."""
    try:
        if not isinstance(rot, dict) or rot.get("scheme") != ROTATE_SCHEME: return None
        op, np_, at = rot.get("old_pubkey"), rot.get("new_pubkey"), rot.get("effective_at")
        if not _hexn(op, 64) or not _hexn(np_, 64) or op == np_ or not _num(at): return None
        if not _hexn(rot.get("old_sig"), 128) or not _hexn(rot.get("new_sig"), 128): return None
        ed, _ = _ed()
        if ed is None: return None
        msg = rotate_message(op, np_, at)
        for pk, sig in ((op, rot["old_sig"]), (np_, rot["new_sig"])):
            ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), msg)
        return op, np_, at
    except Exception:
        return None

def resolve_trust(trusted_pubkeys, rotations=None, revocations=None):
    """Expand pinned root keys along valid rotations. Returns {pubkey: (not_before, not_after)} validity windows
    (None = open). Rules: invalid rotations ignored; a key revoked as 'compromised' endorses nothing (an attacker
    holding it could mint successors); first valid rotation per old key wins deterministically (earliest
    effective_at, then new_pubkey) so a forked chain can't widen trust; depth capped; cycles ignored. Never raises."""
    try:
        win = {k.lower(): (None, None) for k in (trusted_pubkeys or []) if isinstance(k, str) and _hexn(k.lower(), 64)}
        bad = {c[0] for c in (check_revocation(r) for r in revocations or []) if c and c[1] == "compromised"}
        edges = {}
        for r in rotations or []:
            c = check_rotation(r)
            if c and c[0] not in bad:
                cur = edges.get(c[0])
                if cur is None or (c[2], c[1]) < (cur[1], cur[0]): edges[c[0]] = (c[1], c[2])
        frontier = list(win)
        for _ in range(MAX_ROTATION_DEPTH):
            nxt = []
            for old in frontier:
                if old not in edges: continue
                new, at = edges[old]
                nb, na = win[old]
                if na is not None and at >= na: continue  # old key already expired before it could rotate
                win[old] = (nb, at)
                if new not in win: win[new] = (at, None); nxt.append(new)
            frontier = nxt
            if not frontier: break
        return win
    except Exception:
        return {}

def verify_card_chain(card, trusted_pubkeys, rotations=None, revocations=None):
    """verify_card that follows pov-r/key-rotate/1 chains from the pinned keys and enforces each key's
    validity window on the card ts. Returns {ok, reason, signer, chain_depth}; never raises."""
    try:
        win = resolve_trust(trusted_pubkeys, rotations, revocations)
        if not win: return {"ok": False, "reason": "no valid trusted pubkey"}
        v = verify_card(card, list(win), revocations)
        if not v.get("ok"): return v
        nb, na = win[v["signer"]]
        if nb is not None or na is not None:
            ts = card.get("ts")
            if not _num(ts): return {"ok": False, "reason": "card ts required for rotated key", "signer": v["signer"]}
            if nb is not None and ts < nb: return {"ok": False, "reason": "card predates signer key", "signer": v["signer"]}
            if na is not None and ts >= na: return {"ok": False, "reason": "signer key rotated out before card ts", "signer": v["signer"]}
        return {**v, "rotated": nb is not None}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}

BUNDLE_SCHEME = "pov-r/trust-bundle/1"
MAX_BUNDLE_STATEMENTS = 256

def _canon(x): return json.dumps(x, sort_keys=True, separators=(",", ":"))

def bundle_message(signer, seq, issued_at, expires_at, rotations, revocations, retractions=None):
    core = {"signer": signer, "seq": seq, "issued_at": issued_at, "expires_at": expires_at,
            "rotations": sorted(_canon(r) for r in rotations), "revocations": sorted(_canon(r) for r in revocations)}
    # Retractions are committed only when present, so pre-retraction bundles keep their exact signed bytes.
    if retractions: core["retractions"] = sorted(_canon(r) for r in retractions)
    return BUNDLE_SCHEME.encode() + b"\n" + _canon(core).encode()

def _int(x): return not isinstance(x, bool) and isinstance(x, int) and x >= 0

def make_bundle(seed_hex, seq, issued_at, expires_at, rotations=(), revocations=(), retractions=()):
    """Signed, sequenced snapshot of every key-rotation and revocation statement the coordinator knows. Individual
    statements are self-authenticating, but a verifier can't tell whether one is being WITHHELD (e.g. a
    'compromised' revocation). A bundle closes that gap: a monotonic seq lets a verifier refuse rollback to an older
    snapshot, and expires_at bounds how stale a replayed one can be. retractions (pov-r/card-retract/1) ride the same
    anti-withholding channel: a coordinator can't quietly keep a retracted card vouching for one audience without
    signing a bundle that omits it (and a conflicting same-seq bundle is an equivocation proof). Statement order does
    not matter. Raises ValueError."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("bad seed")
    if not _int(seq): raise ValueError("seq must be a non-negative int")
    if not _num(issued_at) or not _num(expires_at) or expires_at <= issued_at: raise ValueError("need 0 <= issued_at < expires_at")
    rots, revs, rets = list(rotations), list(revocations), list(retractions)
    if len(rots) + len(revs) + len(rets) > MAX_BUNDLE_STATEMENTS: raise ValueError("too many statements")
    if any(check_rotation(r) is None for r in rots) or any(check_revocation(r) is None for r in revs) \
            or any(check_retraction(r) is None for r in rets):
        raise ValueError("bundle may only carry valid statements")
    pk = pubkey_from_seed(seed_hex)
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(
        bundle_message(pk, seq, issued_at, expires_at, rots, revs, rets)).hex()
    out = {"scheme": BUNDLE_SCHEME, "signer": pk, "seq": seq, "issued_at": issued_at, "expires_at": expires_at,
           "rotations": rots, "revocations": revs, "sig": sig}
    if rets: out["retractions"] = rets
    return out

def check_bundle(bundle, trusted_pubkeys, now=None, min_seq=None, equivocations=None):
    """Verify a pov-r/trust-bundle/1 against pinned root keys. The signer must be a key reachable from the pins via
    the bundle's own rotations, valid at issued_at, and not revoked (compromised at all, or retired at/before
    issued_at). now: reject if expired or issued in the future; min_seq: last seq this verifier accepted (rollback
    -> reject; equal seq is a re-fetch and OK). equivocations: pov-r/equivocation/1 proofs; a bundle whose signer is
    proven to have equivocated is rejected (its snapshots can no longer be trusted to be the one global view). Returns {ok, reason, seq, signer, rotations, revocations, retractions}; never raises.
    Carried retractions are only signature-checked here; who may retract which card is still decided by
    check_card_retracted against the pins."""
    try:
        if not isinstance(bundle, dict) or bundle.get("scheme") != BUNDLE_SCHEME: return {"ok": False, "reason": "not a trust bundle"}
        pk, seq, ia, ea, sig = (bundle.get(k) for k in ("signer", "seq", "issued_at", "expires_at", "sig"))
        rots, revs, rets = bundle.get("rotations"), bundle.get("revocations"), bundle.get("retractions", [])
        if not _hexn(pk, 64) or not _hexn(sig, 128) or not _int(seq) or not _num(ia) or not _num(ea) or ea <= ia:
            return {"ok": False, "reason": "bad bundle fields"}
        if not isinstance(rots, list) or not isinstance(revs, list) or not isinstance(rets, list) \
                or len(rots) + len(revs) + len(rets) > MAX_BUNDLE_STATEMENTS:
            return {"ok": False, "reason": "bad bundle statements"}
        ed, _ = _ed()
        if ed is None: return {"ok": False, "reason": "ed25519 unavailable"}
        try: ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), bundle_message(pk, seq, ia, ea, rots, revs, rets))
        except Exception: return {"ok": False, "reason": "bad signature"}
        win = resolve_trust(trusted_pubkeys, rots, revs)
        if not win: return {"ok": False, "reason": "no valid trusted pubkey"}
        if pk not in win: return {"ok": False, "reason": "signer not trusted"}
        nb, na = win[pk]
        if (nb is not None and ia < nb) or (na is not None and ia >= na): return {"ok": False, "reason": "signer not valid at issued_at"}
        for c in (check_revocation(r) for r in revs):
            if c and c[0] == pk and (c[1] == "compromised" or ia >= c[2]): return {"ok": False, "reason": "bundle signer revoked"}
        if now is not None:
            if not _num(now): return {"ok": False, "reason": "bad now"}
            if now >= ea: return {"ok": False, "reason": "bundle expired"}
            if ia > now: return {"ok": False, "reason": "bundle issued in the future"}
        if min_seq is not None and (not _int(min_seq) or seq < min_seq): return {"ok": False, "reason": "bundle rollback (seq < last seen)"}
        if equivocations:
            for e in list(equivocations)[:MAX_BUNDLE_STATEMENTS]:
                ev = check_equivocation(e, trusted_pubkeys)
                if ev.get("ok") and ev.get("signer") == pk: return {"ok": False, "reason": "bundle signer equivocated", "signer": pk}
        return {"ok": True, "reason": None, "seq": seq, "signer": pk,
                "rotations": [r for r in rots if check_rotation(r)], "revocations": [r for r in revs if check_revocation(r)],
                "retractions": [r for r in rets if check_retraction(r)]}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}

EQUIVOCATION_SCHEME = "pov-r/equivocation/1"

def make_equivocation(bundle_a, bundle_b):
    """Package two conflicting signed bundles as a portable fraud proof (gossip it; anyone re-verifies offline)."""
    return {"scheme": EQUIVOCATION_SCHEME, "a": bundle_a, "b": bundle_b}

def check_equivocation(proof, trusted_pubkeys):
    """Prove a coordinator showed different verifiers different trust snapshots (split view, e.g. hiding a
    'compromised' revocation from one audience). check_bundle's rollback guard accepts an equal seq as a re-fetch,
    so a split view is only visible by comparing bundles across verifiers. Proven iff both bundles verify against
    the pins (expiry ignored: old evidence stays evidence), share a signer, and either carry the same seq with
    different signed content ('same-seq fork') or order seq and issued_at oppositely ('non-monotonic seq').
    Returns {ok, reason, signer, seq, kind}; ok=True means equivocation PROVEN. Never raises."""
    try:
        if not isinstance(proof, dict) or proof.get("scheme") != EQUIVOCATION_SCHEME: return {"ok": False, "reason": "not an equivocation proof"}
        a, b = proof.get("a"), proof.get("b")
        ra, rb = check_bundle(a, trusted_pubkeys), check_bundle(b, trusted_pubkeys)
        if not ra.get("ok") or not rb.get("ok"): return {"ok": False, "reason": "bundle invalid: " + str(ra.get("reason") or rb.get("reason"))}
        if ra["signer"] != rb["signer"]: return {"ok": False, "reason": "different signers"}
        ma = bundle_message(a["signer"], a["seq"], a["issued_at"], a["expires_at"], a["rotations"], a["revocations"], a.get("retractions"))
        mb = bundle_message(b["signer"], b["seq"], b["issued_at"], b["expires_at"], b["rotations"], b["revocations"], b.get("retractions"))
        base = {"signer": ra["signer"]}
        if a["seq"] == b["seq"]:
            if ma == mb: return {"ok": False, "reason": "same bundle (re-fetch)", **base, "seq": a["seq"]}
            return {"ok": True, "reason": None, **base, "seq": a["seq"], "kind": "same-seq fork"}
        if (a["seq"] - b["seq"]) * (a["issued_at"] - b["issued_at"]) < 0:
            return {"ok": True, "reason": None, **base, "seq": min(a["seq"], b["seq"]), "kind": "non-monotonic seq"}
        return {"ok": False, "reason": "consistent history", **base}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}

RETRACT_SCHEME = "pov-r/card-retract/1"
RETRACT_REASONS = ("source_withdrawn", "error", "superseded")

def retract_message(signer, receipt_id, digest, reason, retracted_at, superseded_by):
    core = {"signer": signer, "receipt_id": receipt_id, "digest": digest, "reason": reason,
            "retracted_at": retracted_at, "superseded_by": superseded_by}
    return RETRACT_SCHEME.encode() + b"\n" + _canon(core).encode()

def make_retraction(seed_hex, card, reason, retracted_at, superseded_by=None):
    """Signed retraction of ONE issued proof card (e.g. a cited source was later withdrawn, or the verdict was wrong).
    Cards are offline artifacts that live forever in screenshots and PDFs; without retraction a correct-at-issue but
    later-invalidated card keeps vouching. Bound to the card's receipt_id AND digest, so it can't be replayed against
    another card. 'superseded' must name the replacement receipt_id. Raises ValueError."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("bad seed")
    if not isinstance(card, dict): raise ValueError("card must be an object")
    rid, dg = card.get("receipt_id"), card.get("digest")
    if not isinstance(rid, str) or not rid or not isinstance(dg, str) or not dg: raise ValueError("card needs receipt_id and digest")
    if reason not in RETRACT_REASONS: raise ValueError("reason must be source_withdrawn|error|superseded")
    if not _num(retracted_at): raise ValueError("bad retracted_at")
    if reason == "superseded":
        if not isinstance(superseded_by, str) or not superseded_by or superseded_by == rid: raise ValueError("superseded needs a different superseded_by receipt_id")
    elif superseded_by is not None: raise ValueError("superseded_by only allowed with reason superseded")
    pk = pubkey_from_seed(seed_hex)
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(
        retract_message(pk, rid, dg, reason, retracted_at, superseded_by)).hex()
    return {"scheme": RETRACT_SCHEME, "signer": pk, "receipt_id": rid, "digest": dg, "reason": reason,
            "retracted_at": retracted_at, "superseded_by": superseded_by, "sig": sig}

def check_retraction(ret):
    """Return (signer, receipt_id, digest, reason, retracted_at, superseded_by) for a well-signed retraction, else None.
    Signature only; who may retract is decided by check_card_retracted. Never raises."""
    try:
        if not isinstance(ret, dict) or ret.get("scheme") != RETRACT_SCHEME: return None
        f = tuple(ret.get(k) for k in ("signer", "receipt_id", "digest", "reason", "retracted_at", "superseded_by"))
        pk, rid, dg, reason, at, sb = f
        if not _hexn(pk, 64) or not _hexn(ret.get("sig"), 128) or reason not in RETRACT_REASONS or not _num(at): return None
        if not isinstance(rid, str) or not rid or not isinstance(dg, str) or not dg: return None
        if reason == "superseded":
            if not isinstance(sb, str) or not sb or sb == rid: return None
        elif sb is not None: return None
        ed, _ = _ed()
        if ed is None: return None
        ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(ret["sig"]), retract_message(*f))
        return f
    except Exception:
        return None

def check_card_retracted(card, retractions, trusted_pubkeys, rotations=None, revocations=None):
    """Is this card retracted by an authorised key? Authorised = reachable from the pins (same trust graph as
    verify_card_chain, so a successor key can retract its predecessor's cards) and not revoked as 'compromised'.
    A retraction only ever REMOVES trust, so a retired/rotated-out key may still retract (fail-safe), but strangers,
    forgers, compromised keys and retractions for a different receipt_id/digest are ignored (no third-party DoS).
    Earliest valid retraction wins deterministically. Returns {retracted, reason, retracted_at, superseded_by, signer};
    never raises (malformed input -> retracted False)."""
    try:
        if not isinstance(card, dict) or not retractions: return {"retracted": False}
        win = resolve_trust(trusted_pubkeys, rotations, revocations)
        bad = {c[0] for c in (check_revocation(r) for r in revocations or []) if c and c[1] == "compromised"}
        best = None
        for r in list(retractions)[:MAX_BUNDLE_STATEMENTS]:
            c = check_retraction(r)
            if c is None or c[0] not in win or c[0] in bad: continue
            if c[1] != card.get("receipt_id") or c[2] != card.get("digest"): continue
            if best is None or (c[4], c[3], c[0]) < (best[4], best[3], best[0]): best = c
        if best is None: return {"retracted": False}
        return {"retracted": True, "reason": best[3], "retracted_at": best[4], "superseded_by": best[5], "signer": best[0]}
    except Exception:
        return {"retracted": False}

MAX_SUPERSESSION_DEPTH = 16

def resolve_current_card(card, successors, retractions, trusted_pubkeys, rotations=None, revocations=None):
    """Follow pov-r/card-retract/1 'superseded' links from an old card to the card that currently vouches.
    A reader holding a screenshot of a superseded card learns not just "stale" but WHICH card replaced it, and can
    verify the replacement offline. Every hop must be a trusted card (verify_card_chain), the retraction must be
    authorised (check_card_retracted), the successor must carry the named receipt_id and must not predate its
    predecessor (no backdated replacement). Fail-closed: two different trusted successors for one receipt_id
    ('ambiguous', a split view), a cycle, or depth > MAX_SUPERSESSION_DEPTH. Returns
    {status, reason, current, path}; status: current | retracted | successor_missing | invalid. path lists the
    receipt_ids walked (start first). Never raises."""
    try:
        v = verify_card_chain(card, trusted_pubkeys, rotations, revocations)
        if not v.get("ok"): return {"status": "invalid", "reason": f"start card: {v.get('reason')}", "current": None, "path": []}
        pool = {}
        for s in list(successors or [])[:MAX_BUNDLE_STATEMENTS]:
            if not isinstance(s, dict) or not verify_card_chain(s, trusted_pubkeys, rotations, revocations).get("ok"): continue
            pool.setdefault(s.get("receipt_id"), {})[s.get("digest")] = s
        cur, path, seen = card, [card.get("receipt_id")], {(card.get("receipt_id"), card.get("digest"))}
        for _ in range(MAX_SUPERSESSION_DEPTH + 1):
            rt = check_card_retracted(cur, retractions, trusted_pubkeys, rotations, revocations)
            if not rt.get("retracted"): return {"status": "current", "reason": None, "current": cur, "path": path}
            if rt["reason"] != "superseded":
                return {"status": "retracted", "reason": rt["reason"], "current": None, "path": path}
            nxt = pool.get(rt["superseded_by"], {})
            if not nxt: return {"status": "successor_missing", "reason": f"superseded by {rt['superseded_by']}", "current": None,
                                "path": path + [rt["superseded_by"]]}
            if len(nxt) > 1: return {"status": "invalid", "reason": "ambiguous successor (conflicting cards)", "current": None, "path": path}
            s = next(iter(nxt.values()))
            if not _num(s.get("ts")) or not _num(cur.get("ts")) or s["ts"] < cur["ts"]:
                return {"status": "invalid", "reason": "successor predates superseded card", "current": None, "path": path}
            key = (s.get("receipt_id"), s.get("digest"))
            if key in seen: return {"status": "invalid", "reason": "supersession cycle", "current": None, "path": path}
            seen.add(key); path.append(s.get("receipt_id")); cur = s
        return {"status": "invalid", "reason": "supersession chain too deep", "current": None, "path": path}
    except Exception as e:
        return {"status": "invalid", "reason": f"malformed: {type(e).__name__}", "current": None, "path": []}

WITNESS_SCHEME = "pov-r/card-witness/1"
MAX_WITNESSES = 64

def witness_message(card, witness_pubkey):
    """Bytes a witness signs: the card's pinned core (same as card-attest) plus the coordinator's attestation pubkey
    and the witness's own pubkey, under a distinct domain so a witness sig can never be replayed as a card attestation."""
    core = card_message(card)[len(SCHEME) + 1:].decode()
    at = card.get("attestation") if isinstance(card.get("attestation"), dict) else {}
    meta = {"coordinator": at.get("pubkey"), "witness": witness_pubkey}
    return WITNESS_SCHEME.encode() + b"\n" + core.encode() + b"\n" + _canon(meta).encode()

def make_witness(seed_hex, card):
    """Independent witness co-signature over an ATTESTED card. A witness is a validator that re-checked the receipt
    (e.g. replayed the consensus votes / re-fetched sources) and vouches for the same pinned fields. Collecting k of n
    witness co-signatures means a single compromised coordinator key can no longer mint a card a k-of-n verifier
    accepts. Raises ValueError on bad input."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("bad seed")
    if not isinstance(card, dict) or not isinstance(card.get("attestation"), dict): raise ValueError("card must be attested")
    pk = pubkey_from_seed(seed_hex)
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(witness_message(card, pk)).hex()
    return {"scheme": WITNESS_SCHEME, "pubkey": pk, "receipt_id": card.get("receipt_id"), "digest": card.get("digest"), "sig": sig}

def check_witnesses(card, witnesses, witness_pubkeys, threshold, revocations=None, dissents=None, max_dissent=0):
    """Count distinct trusted witnesses that validly co-signed this card. Returns {ok, count, threshold, signers,
    reason}; never raises. Rules: only keys in witness_pubkeys count (strangers can't pad the count); each key counts
    once (duplicates ignored); the card's own coordinator key never counts as a witness (independence); a witness key
    with a valid self-signed 'compromised' revocation doesn't count, a 'retired' one counts only for cards with
    ts < revoked_at; a sig over a different card (other receipt_id/digest/coordinator) fails. threshold < 1 or greater
    than the number of distinct usable witness keys fails closed."""
    try:
        if not isinstance(card, dict): return {"ok": False, "count": 0, "threshold": threshold, "signers": [], "reason": "proof card must be an object"}
        if not _int(threshold) or threshold < 1: return {"ok": False, "count": 0, "threshold": threshold, "signers": [], "reason": "bad threshold"}
        at = card.get("attestation") if isinstance(card.get("attestation"), dict) else {}
        coord = at.get("pubkey")
        keys = {k.lower() for k in (witness_pubkeys or []) if isinstance(k, str) and _hexn(k.lower(), 64)} - {coord}
        if threshold > len(keys): return {"ok": False, "count": 0, "threshold": threshold, "signers": [], "reason": "threshold exceeds usable witness keys"}
        ed, _ = _ed()
        if ed is None: return {"ok": False, "count": 0, "threshold": threshold, "signers": [], "reason": "ed25519 unavailable"}
        dead, retired = set(), {}
        for rv in revocations or []:
            c = check_revocation(rv)
            if c is None: continue
            if c[1] == "compromised": dead.add(c[0])
            else: retired[c[0]] = min(c[2], retired.get(c[0], c[2]))
        ts = card.get("ts")
        good = set()
        for w in list(witnesses or [])[:MAX_WITNESSES]:
            if not isinstance(w, dict) or w.get("scheme") != WITNESS_SCHEME: continue
            pk, sig = w.get("pubkey"), w.get("sig")
            if not _hexn(pk, 64) or not _hexn(sig, 128) or pk not in keys or pk in good or pk in dead: continue
            if pk in retired and (isinstance(ts, bool) or not isinstance(ts, (int, float)) or ts >= retired[pk]): continue
            if w.get("receipt_id") != card.get("receipt_id") or w.get("digest") != card.get("digest"): continue
            try: ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), witness_message(card, pk))
            except Exception: continue
            good.add(pk)
        d = check_dissents(card, dissents, witness_pubkeys, revocations) if dissents else {"dissenters": [], "reasons": {}}
        dis = set(d["dissenters"])
        good -= dis  # a witness that both co-signed and dissented has equivocated: its approval is void
        n = len(good)
        out = {"ok": n >= threshold, "count": n, "threshold": threshold, "signers": sorted(good),
               "reason": None if n >= threshold else f"only {n} of {threshold} required witnesses",
               "dissenters": sorted(dis), "dissent_reasons": d["reasons"]}
        if not _int(max_dissent): max_dissent = 0
        if len(dis) > max_dissent:
            out.update(ok=False, reason=f"disputed: {len(dis)} trusted witness dissent(s) > max_dissent {max_dissent}")
        return out
    except Exception as e:
        return {"ok": False, "count": 0, "threshold": threshold, "signers": [], "reason": f"malformed: {type(e).__name__}",
                "dissenters": [], "dissent_reasons": {}}

DISSENT_SCHEME = "pov-r/card-dissent/1"
DISSENT_REASONS = ("source_mismatch", "claim_unsupported", "replay_mismatch", "calibration_failed")
MAX_DISSENTS = 64

def dissent_message(card, witness_pubkey, reason):
    """Bytes a dissenting witness signs: same binding as a co-signature (pinned core + coordinator + witness) plus the
    reason, under its own domain so a dissent can never be replayed as an approval or an attestation (and vice versa)."""
    core = card_message(card)[len(SCHEME) + 1:].decode()
    at = card.get("attestation") if isinstance(card.get("attestation"), dict) else {}
    meta = {"coordinator": at.get("pubkey"), "witness": witness_pubkey, "reason": reason}
    return DISSENT_SCHEME.encode() + b"\n" + core.encode() + b"\n" + _canon(meta).encode()

def make_dissent(seed_hex, card, reason):
    """Signed witness dissent: a validator that re-checked the receipt and got a DIFFERENT result says so, verifiably.
    Without it a k-of-n quorum only ever shows approvals, so a coordinator can quietly collect k friendly witnesses
    while the others' objections vanish. A dissent travels with the card and turns the verdict into 'disputed'.
    Raises ValueError on bad input."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("bad seed")
    if not isinstance(card, dict) or not isinstance(card.get("attestation"), dict): raise ValueError("card must be attested")
    if reason not in DISSENT_REASONS: raise ValueError("reason must be one of " + "|".join(DISSENT_REASONS))
    pk = pubkey_from_seed(seed_hex)
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(dissent_message(card, pk, reason)).hex()
    return {"scheme": DISSENT_SCHEME, "pubkey": pk, "receipt_id": card.get("receipt_id"), "digest": card.get("digest"),
            "reason": reason, "sig": sig}

def check_dissents(card, dissents, witness_pubkeys, revocations=None):
    """Return {dissenters, reasons} for distinct trusted witnesses that validly dissented on this card; never raises.
    Same trust rules as check_witnesses: strangers and the coordinator itself don't count, duplicates count once,
    a 'compromised' witness key is ignored (an attacker can't smear a card with a stolen key), a 'retired' key only
    for cards with ts < revoked_at, and a dissent bound to another card/coordinator/reason fails."""
    try:
        if not isinstance(card, dict): return {"dissenters": [], "reasons": {}}
        at = card.get("attestation") if isinstance(card.get("attestation"), dict) else {}
        coord = at.get("pubkey")
        keys = {k.lower() for k in (witness_pubkeys or []) if isinstance(k, str) and _hexn(k.lower(), 64)} - {coord}
        ed, _ = _ed()
        if ed is None or not keys: return {"dissenters": [], "reasons": {}}
        dead, retired = set(), {}
        for rv in revocations or []:
            c = check_revocation(rv)
            if c is None: continue
            if c[1] == "compromised": dead.add(c[0])
            else: retired[c[0]] = min(c[2], retired.get(c[0], c[2]))
        ts = card.get("ts")
        found = {}
        for w in list(dissents or [])[:MAX_DISSENTS]:
            if not isinstance(w, dict) or w.get("scheme") != DISSENT_SCHEME: continue
            pk, sig, reason = w.get("pubkey"), w.get("sig"), w.get("reason")
            if not _hexn(pk, 64) or not _hexn(sig, 128) or pk not in keys or pk in found or pk in dead: continue
            if reason not in DISSENT_REASONS: continue
            if pk in retired and (isinstance(ts, bool) or not isinstance(ts, (int, float)) or ts >= retired[pk]): continue
            if w.get("receipt_id") != card.get("receipt_id") or w.get("digest") != card.get("digest"): continue
            try: ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), dissent_message(card, pk, reason))
            except Exception: continue
            found[pk] = reason
        return {"dissenters": sorted(found), "reasons": dict(sorted(found.items()))}
    except Exception:
        return {"dissenters": [], "reasons": {}}

ROSTER_SCHEME = "pov-r/witness-roster/1"

def roster_message(signer, seq, issued_at, expires_at, witnesses, threshold):
    core = {"signer": signer, "seq": seq, "issued_at": issued_at, "expires_at": expires_at,
            "witnesses": sorted(witnesses), "threshold": threshold}
    return ROSTER_SCHEME.encode() + b"\n" + _canon(core).encode()

def make_roster(seed_hex, seq, issued_at, expires_at, witnesses, threshold):
    """Signed witness roster: a governance key publishes WHICH validators count as independent witnesses and the
    k-of-n threshold, sequenced and expiring. Without it every verifier hand-pins witness keys and picks its own k,
    so the network can't add/remove validators and a sloppy verifier can silently accept k=1. Witness order doesn't
    matter. Raises ValueError."""
    ed, _ = _ed()
    if ed is None: raise ValueError("ed25519 unavailable (install cryptography)")
    if not _hexn(seed_hex, 64): raise ValueError("bad seed")
    if not _int(seq): raise ValueError("seq must be a non-negative int")
    if not _num(issued_at) or not _num(expires_at) or expires_at <= issued_at: raise ValueError("need 0 <= issued_at < expires_at")
    ws = sorted({w.lower() for w in witnesses if isinstance(w, str)})
    if not ws or len(ws) > MAX_WITNESSES or any(not _hexn(w, 64) for w in ws) or len(ws) != len(list(witnesses)):
        raise ValueError("witnesses must be 1..64 distinct 64-hex pubkeys")
    if not _int(threshold) or not 1 <= threshold <= len(ws): raise ValueError("need 1 <= threshold <= len(witnesses)")
    pk = pubkey_from_seed(seed_hex)
    if pk in ws: raise ValueError("governance key cannot list itself as a witness")
    sig = ed.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(
        roster_message(pk, seq, issued_at, expires_at, ws, threshold)).hex()
    return {"scheme": ROSTER_SCHEME, "signer": pk, "seq": seq, "issued_at": issued_at, "expires_at": expires_at,
            "witnesses": ws, "threshold": threshold, "sig": sig}

def check_roster(roster, governance_pubkeys, now=None, min_seq=None, card_ts=None, revocations=None):
    """Verify a pov-r/witness-roster/1 against pinned governance keys. Returns {ok, reason, seq, signer, witnesses,
    threshold}; never raises. Fails closed on: unpinned/compromised signer (retired only if issued_at >= retired_at),
    bad/duplicate witness keys, threshold outside 1..n, expired or future-issued roster (now), rollback below
    min_seq, and - with card_ts - a card outside the roster's [issued_at, expires_at) window, so an old card can't be
    judged by a later, friendlier roster and a new card can't hide behind a stale one."""
    try:
        if not isinstance(roster, dict) or roster.get("scheme") != ROSTER_SCHEME: return {"ok": False, "reason": "not a witness roster"}
        pk, seq, ia, ea, ws, k, sig = (roster.get(x) for x in ("signer", "seq", "issued_at", "expires_at", "witnesses", "threshold", "sig"))
        if not _hexn(pk, 64) or not _hexn(sig, 128) or not _int(seq) or not _num(ia) or not _num(ea) or ea <= ia:
            return {"ok": False, "reason": "bad roster fields"}
        if not isinstance(ws, list) or not ws or len(ws) > MAX_WITNESSES or any(not _hexn(w, 64) for w in ws) \
                or len(set(ws)) != len(ws) or pk in ws:
            return {"ok": False, "reason": "bad roster witnesses"}
        if not _int(k) or not 1 <= k <= len(ws): return {"ok": False, "reason": "bad roster threshold"}
        gov = {g.lower() for g in (governance_pubkeys or []) if isinstance(g, str)}
        if not gov or any(not _hexn(g, 64) for g in gov): return {"ok": False, "reason": "no valid governance pubkey"}
        if pk not in gov: return {"ok": False, "reason": "roster signer not trusted"}
        ed, _ = _ed()
        if ed is None: return {"ok": False, "reason": "ed25519 unavailable"}
        try: ed.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)).verify(bytes.fromhex(sig), roster_message(pk, seq, ia, ea, ws, k))
        except Exception: return {"ok": False, "reason": "bad signature"}
        for c in (check_revocation(r) for r in revocations or []):
            if c and c[0] == pk and (c[1] == "compromised" or ia >= c[2]): return {"ok": False, "reason": "roster signer revoked"}
        if now is not None:
            if not _num(now): return {"ok": False, "reason": "bad now"}
            if now >= ea: return {"ok": False, "reason": "roster expired"}
            if ia > now: return {"ok": False, "reason": "roster issued in the future"}
        if min_seq is not None and (not _int(min_seq) or seq < min_seq): return {"ok": False, "reason": "roster rollback (seq < last seen)"}
        if card_ts is not None and (not _num(card_ts) or not ia <= card_ts < ea):
            return {"ok": False, "reason": "card ts outside roster validity window"}
        return {"ok": True, "reason": None, "seq": seq, "signer": pk, "witnesses": list(ws), "threshold": k}
    except Exception as e:
        return {"ok": False, "reason": f"malformed: {type(e).__name__}"}

def check_witnesses_rostered(card, witnesses, roster, governance_pubkeys, now=None, min_seq=None, revocations=None,
                             dissents=None, max_dissent=0, min_threshold=None):
    """k-of-n witness check where the witness set and k come from a governance-signed roster valid at the card's ts.
    min_threshold lets a cautious verifier demand MORE than the roster's k (never less). Never raises."""
    try:
        ts = card.get("ts") if isinstance(card, dict) else None
        r = check_roster(roster, governance_pubkeys, now, min_seq, ts if _num(ts) else -1, revocations)
        if not r["ok"]:
            return {"ok": False, "count": 0, "threshold": None, "signers": [], "reason": f"roster: {r['reason']}",
                    "dissenters": [], "dissent_reasons": {}, "roster_seq": None}
        k = r["threshold"]
        if min_threshold is not None:
            if not _int(min_threshold) or min_threshold < 1:
                return {"ok": False, "count": 0, "threshold": k, "signers": [], "reason": "bad min_threshold",
                        "dissenters": [], "dissent_reasons": {}, "roster_seq": r["seq"]}
            k = max(k, min_threshold)
        out = check_witnesses(card, witnesses, r["witnesses"], k, revocations, dissents, max_dissent)
        out.setdefault("dissenters", []); out.setdefault("dissent_reasons", {})
        out["roster_seq"] = r["seq"]
        return out
    except Exception as e:
        return {"ok": False, "count": 0, "threshold": None, "signers": [], "reason": f"malformed: {type(e).__name__}",
                "dissenters": [], "dissent_reasons": {}, "roster_seq": None}
