"""Offline, server-free verifier for PoV-R claim disclosures.

A third party (journalist, auditor, reviewer) who received a proof card and a disclosure can check it with
no network and no trust in the coordinator:

    python -m aegis_miner.offline_verify disclosure.json --card proof_card.json

Accepts a single disclosure (pov-r/claim-merkle/1), a list of disclosures (set from one receipt) or a compact
multiproof (pov-r/claim-multiproof/1); the kind is auto-detected. The proof card pins claims_root, claim_count
(leaf count, so "k of N" is trustworthy) and receipt_id; any disagreement fails closed. Without a card the
embedded root is used and the result is marked untrusted (trusted=False). Exit 0 only when ok AND trusted
(or --allow-untrusted). Never raises on malformed input.
"""
import argparse, json, sys
from . import claim_merkle as cm, card_attest as ca

def _kind(obj):
    if isinstance(obj, list): return "set"
    if isinstance(obj, dict):
        if obj.get("scheme") == "pov-r/claim-multiproof/1" or "indices" in obj: return "multiproof"
        if isinstance(obj.get("disclosures"), list): return "set"
        if isinstance(obj.get("multiproof"), dict): return "multiproof"
        return "single"
    return None

def _unwrap(obj, kind):
    if isinstance(obj, dict) and kind == "set" and "disclosures" in obj: return obj["disclosures"]
    if isinstance(obj, dict) and kind == "multiproof" and isinstance(obj.get("multiproof"), dict): return obj["multiproof"]
    return obj

def _card_pins(card):
    if card is None: return None, None, None, None
    if not isinstance(card, dict): return None, None, None, "proof card must be an object"
    root, n, rid = card.get("claims_root"), card.get("claim_count"), card.get("receipt_id")
    if not cm._hex64(root): return None, None, None, "proof card has no valid claims_root"
    if not isinstance(n, int) or isinstance(n, bool) or n < 1: return None, None, None, "proof card has no valid claim_count"
    if not isinstance(rid, str) or not rid: return None, None, None, "proof card has no receipt_id"
    if isinstance(card.get("audit"), dict) and card["audit"].get("intact") is False:
        return None, None, None, "proof card self-audit not intact"
    return root, n, rid, None

def verify_offline(obj, card=None, root=None, leaf_count=None, pubkeys=None, revocations=None, rotations=None, retractions=None):
    """Verify any disclosure kind against trusted pins (card and/or explicit root/leaf_count).
    pubkeys: trusted coordinator card keys (hex). When given, the card MUST carry a valid Ed25519 attestation
    from one of them (pov-r/card-attest/1), so a forged card cannot vouch for a forged disclosure.
    Returns {ok, trusted, kind, reason, card_signed, ...}; never raises."""
    try:
        kind = _kind(obj)
        if kind is None: return {"ok": False, "trusted": False, "kind": None, "reason": "unrecognised input"}
        signer = None
        if pubkeys:
            if card is None: return {"ok": False, "trusted": False, "kind": kind, "reason": "--pubkey needs a proof card"}
            sv = ca.verify_card_chain(card, pubkeys, rotations, revocations)
            if not sv["ok"]: return {"ok": False, "trusted": False, "kind": kind, "reason": f"card attestation: {sv['reason']}", "card_signed": False}
            signer = sv["signer"]
            if retractions:
                rt = ca.check_card_retracted(card, retractions, pubkeys, rotations, revocations)
                if rt.get("retracted"):
                    return {"ok": False, "trusted": False, "kind": kind, "card_signed": True, "signer": signer, "retracted": True,
                            "reason": f"proof card retracted ({rt['reason']})", "retracted_at": rt["retracted_at"],
                            "superseded_by": rt["superseded_by"], "retracted_by": rt["signer"]}
        croot, cn, crid, err = _card_pins(card)
        if err: return {"ok": False, "trusted": False, "kind": kind, "reason": err}
        for a, b, what in ((root, croot, "root"), (leaf_count, cn, "leaf_count")):
            if a is not None and b is not None and a != b: return {"ok": False, "trusted": False, "kind": kind, "reason": f"explicit {what} disagrees with proof card"}
        if root is not None and not cm._hex64(root): return {"ok": False, "trusted": False, "kind": kind, "reason": "bad root"}
        if leaf_count is not None and (not isinstance(leaf_count, int) or isinstance(leaf_count, bool) or leaf_count < 1):
            return {"ok": False, "trusted": False, "kind": kind, "reason": "bad leaf_count"}
        R, N = root if root is not None else croot, leaf_count if leaf_count is not None else cn
        body = _unwrap(obj, kind)
        items = body if kind == "set" else [body]
        if crid is not None and any(not isinstance(d, dict) or d.get("receipt_id") != crid for d in items):
            return {"ok": False, "trusted": False, "kind": kind, "reason": "receipt_id does not match proof card"}
        if kind == "multiproof":
            r = cm.verify_multi(body, R, N)
        else:
            if N is not None and any(isinstance(d, dict) and d.get("leaf_count") != N for d in items):
                return {"ok": False, "trusted": False, "kind": kind, "reason": "leaf_count mismatch"}
            r = cm.verify_disclosure_set(items, R) if kind == "set" else cm.verify_disclosure(body, R)
        trusted = R is not None and N is not None
        out = {"ok": bool(r.get("ok")), "trusted": trusted, "kind": kind, "reason": r.get("reason"), "root": r.get("root"),
               "root_source": "pinned" if R is not None else "embedded(untrusted)",
               "leaf_count_source": "pinned" if N is not None else "embedded(untrusted)",
               "card_signed": True if signer else ("unchecked" if isinstance(card, dict) and card.get("attestation") else False),
               "signer": signer}
        if kind == "single" and isinstance(body, dict): out.update(count=1, indices=[body.get("index")], claims=[cm.public_claim(body.get("claim") or {})])
        elif kind == "set": out.update(count=r.get("count"), indices=r.get("indices"), claims=[cm.public_claim(d.get("claim") or {}) for d in items if isinstance(d, dict)])
        else: out.update(count=r.get("count"), indices=body.get("indices"), claims=[cm.public_claim(c) for c in body.get("claims") or [] if isinstance(c, dict)])
        if out["ok"]: out["leaf_count"] = N if N is not None else (items[0].get("leaf_count") if isinstance(items[0], dict) else None)
        return out
    except Exception as e:
        return {"ok": False, "trusted": False, "kind": None, "reason": f"malformed: {type(e).__name__}"}

def _load(path):
    with (sys.stdin if path == "-" else open(path)) as f: return json.load(f)

def main(argv=None):
    p = argparse.ArgumentParser(prog="aegis_miner.offline_verify", description="Verify a PoV-R claim disclosure offline")
    p.add_argument("disclosure", help="disclosure / set / multiproof JSON file, or - for stdin")
    p.add_argument("--card", help="proof card JSON (GET /v1/receipts/{id}/proof) - pins root, claim_count, receipt_id")
    p.add_argument("--root"); p.add_argument("--leaf-count", type=int)
    p.add_argument("--pubkey", action="append", help="trusted coordinator card key (hex, GET /v1/card-key); repeatable; card must be signed by one")
    p.add_argument("--revocation", action="append", help="self-signed key revocation JSON (pov-r/key-revoke/1); repeatable")
    p.add_argument("--rotation", action="append", help="dual-signed key rotation JSON (pov-r/key-rotate/1); repeatable, followed from --pubkey")
    p.add_argument("--bundle", help="signed trust bundle JSON (pov-r/trust-bundle/1); its rotations/revocations/retractions are used, needs --pubkey")
    p.add_argument("--equivocation", action="append", help="equivocation proof JSON (pov-r/equivocation/1); repeatable; a proven-equivocating bundle signer is rejected")
    p.add_argument("--retraction", action="append", help="signed card retraction JSON (pov-r/card-retract/1); repeatable; needs --pubkey")
    p.add_argument("--now", type=float, help="unix time for bundle expiry check")
    p.add_argument("--min-seq", type=int, help="last accepted bundle seq (rollback protection)")
    p.add_argument("--allow-untrusted", action="store_true", help="exit 0 on ok even without pinned root/leaf_count")
    a = p.parse_args(argv)
    try:
        obj = _load(a.disclosure); card = _load(a.card) if a.card else None
        revs = [_load(x) for x in a.revocation or []]
        rots = [_load(x) for x in a.rotation or []]
        bundle = _load(a.bundle) if a.bundle else None
        eqs = [_load(x) for x in a.equivocation or []]
        rets = [_load(x) for x in a.retraction or []]
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False, "trusted": False, "reason": f"cannot read input: {e}"})); return 2
    if bundle is not None:
        if not a.pubkey:
            print(json.dumps({"ok": False, "trusted": False, "reason": "--bundle needs --pubkey"})); return 1
        b = ca.check_bundle(bundle, a.pubkey, a.now, a.min_seq, eqs)
        if not b["ok"]:
            print(json.dumps({"ok": False, "trusted": False, "reason": f"trust bundle: {b['reason']}"})); return 1
        rots, revs, rets = rots + b["rotations"], revs + b["revocations"], rets + b["retractions"]
    if rets and not a.pubkey:
        print(json.dumps({"ok": False, "trusted": False, "reason": "--retraction needs --pubkey"})); return 1
    r = verify_offline(obj, card, a.root, a.leaf_count, a.pubkey, revs, rots, rets)
    if bundle is not None: r["bundle_seq"] = b["seq"]
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0 if r["ok"] and (r["trusted"] or a.allow_untrusted) else 1

if __name__ == "__main__":
    sys.exit(main())
