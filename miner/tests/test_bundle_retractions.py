import json
import pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, B, X = "11" * 32, "22" * 32, "44" * 32
PA, PB, PX = (ca.pubkey_from_seed(s) for s in (A, B, X))

def _rec(ts, rid="r1"):
    r = {"receipt_id": rid, "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(seed, ts, rid="r1"): return ca.sign_card(token_bridge.receipt_proof(_rec(ts, rid)), seed)

def test_bundle_without_retractions_keeps_legacy_bytes():
    b = ca.make_bundle(A, 1, 10, 100)
    assert "retractions" not in b
    legacy = ca.BUNDLE_SCHEME.encode() + b"\n" + ca._canon({"signer": PA, "seq": 1, "issued_at": 10, "expires_at": 100,
                                                             "rotations": [], "revocations": []}).encode()
    assert ca.bundle_message(PA, 1, 10, 100, [], []) == legacy
    r = ca.check_bundle(b, [PA]); assert r["ok"] and r["retractions"] == []

def test_bundle_carries_retraction_signed():
    card = _card(A, 5); rt = ca.make_retraction(A, card, "source_withdrawn", 50)
    b = ca.make_bundle(A, 2, 60, 600, retractions=[rt])
    r = ca.check_bundle(b, [PA], now=100)
    assert r["ok"] and r["retractions"] == [rt]
    assert ca.check_card_retracted(card, r["retractions"], [PA])["retracted"]

def test_stripping_retraction_breaks_signature():
    card = _card(A, 5); rt = ca.make_retraction(A, card, "error", 50)
    b = ca.make_bundle(A, 2, 60, 600, retractions=[rt])
    stripped = {k: v for k, v in b.items() if k != "retractions"}
    assert ca.check_bundle(stripped, [PA])["reason"] == "bad signature"
    assert ca.check_bundle(dict(b, retractions=[]), [PA])["reason"] == "bad signature"

def test_hidden_retraction_split_view_is_equivocation():
    card = _card(A, 5); rt = ca.make_retraction(A, card, "error", 50)
    full = ca.make_bundle(A, 3, 60, 600, retractions=[rt]); hidden = ca.make_bundle(A, 3, 60, 600)
    e = ca.check_equivocation(ca.make_equivocation(full, hidden), [PA])
    assert e["ok"] and e["kind"] == "same-seq fork"
    assert not ca.check_equivocation(ca.make_equivocation(full, json.loads(json.dumps(full))), [PA])["ok"]

def test_make_rejects_invalid_retraction_and_overflow():
    card = _card(A, 5); rt = ca.make_retraction(A, card, "error", 50)
    with pytest.raises(ValueError): ca.make_bundle(A, 1, 10, 100, retractions=[dict(rt, reason="superseded")])
    with pytest.raises(ValueError): ca.make_bundle(A, 1, 10, 100, retractions=[rt] * (ca.MAX_BUNDLE_STATEMENTS + 1))

def test_bundle_cannot_authorise_stranger_retraction():
    card = _card(A, 5); rx = ca.make_retraction(X, card, "error", 50)
    r = ca.check_bundle(ca.make_bundle(A, 1, 60, 600, retractions=[rx]), [PA])
    assert r["ok"] and not ca.check_card_retracted(card, r["retractions"], [PA])["retracted"]

@pytest.mark.parametrize("junk", [None, 1, "x", {}])
def test_malformed_retractions_field_never_raises(junk):
    b = ca.make_bundle(A, 1, 10, 100); b["retractions"] = junk
    assert ca.check_bundle(b, [PA])["ok"] is False

def test_offline_cli_applies_bundle_retraction(tmp_path):
    rec = _rec(5); card = ca.sign_card(token_bridge.receipt_proof(rec), A)
    d = cm.disclose(rec, 0); rt = ca.make_retraction(A, card, "source_withdrawn", 50)
    files = {"d": d, "c": card, "b": ca.make_bundle(A, 1, 60, 600, retractions=[rt]), "b0": ca.make_bundle(A, 1, 60, 600)}
    for k, v in files.items(): (tmp_path / f"{k}.json").write_text(json.dumps(v))
    base = [str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--pubkey", PA, "--now", "100"]
    assert ov.main(base + ["--bundle", str(tmp_path / "b0.json")]) == 0
    assert ov.main(base + ["--bundle", str(tmp_path / "b.json")]) == 1
