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
