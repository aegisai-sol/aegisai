import json
import pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, B, C, X = "11" * 32, "22" * 32, "33" * 32, "44" * 32
PA, PB, PC, PX = (ca.pubkey_from_seed(s) for s in (A, B, C, X))

def _rec(ts):
    r = {"receipt_id": "r1", "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(seed, ts): return ca.sign_card(token_bridge.receipt_proof(_rec(ts)), seed)

def test_roundtrip_and_order_independent():
    rots = [ca.make_rotation(A, B, 100), ca.make_rotation(B, C, 200)]
    b = ca.make_bundle(A, 1, 50, 500, rots)
    r = ca.check_bundle(b, [PA], now=60)
    assert r["ok"] and r["seq"] == 1 and r["signer"] == PA and len(r["rotations"]) == 2
    b2 = dict(b, rotations=list(reversed(b["rotations"])))
    assert ca.check_bundle(b2, [PA])["ok"]

def test_successor_key_can_sign_bundle_via_chain():
    b = ca.make_bundle(B, 2, 150, 500, [ca.make_rotation(A, B, 100)])
    assert ca.check_bundle(b, [PA])["ok"]
    assert ca.check_bundle(ca.make_bundle(B, 2, 150, 500), [PA])["reason"] == "signer not trusted"

def test_rotated_out_key_cannot_sign_later_bundle():
    b = ca.make_bundle(A, 3, 150, 500, [ca.make_rotation(A, B, 100)])
    assert ca.check_bundle(b, [PA])["reason"] == "signer not valid at issued_at"

def test_withheld_statement_detected_by_tamper():
    rev = ca.make_revocation(B, "compromised", 0)
    b = ca.make_bundle(A, 4, 50, 500, [ca.make_rotation(A, B, 100)], [rev])
    stripped = dict(b, revocations=[])  # attacker drops the revocation
    assert ca.check_bundle(stripped, [PA])["reason"] == "bad signature"

def test_rollback_and_expiry():
    b = ca.make_bundle(A, 5, 50, 500)
    assert ca.check_bundle(b, [PA], min_seq=5)["ok"]
    assert "rollback" in ca.check_bundle(b, [PA], min_seq=6)["reason"]
    assert ca.check_bundle(b, [PA], now=500)["reason"] == "bundle expired"
    assert ca.check_bundle(b, [PA], now=10)["reason"] == "bundle issued in the future"

def test_revoked_signer_rejected():
    assert ca.check_bundle(ca.make_bundle(A, 1, 50, 500, [], [ca.make_revocation(A, "compromised", 999)]), [PA])["reason"] == "bundle signer revoked"
    assert ca.check_bundle(ca.make_bundle(A, 1, 50, 500, [], [ca.make_revocation(A, "retired", 40)]), [PA])["reason"] == "bundle signer revoked"
    assert ca.check_bundle(ca.make_bundle(A, 1, 50, 500, [], [ca.make_revocation(A, "retired", 60)]), [PA])["ok"]

def test_forger_bundle_untrusted():
    assert ca.check_bundle(ca.make_bundle(X, 9, 50, 500), [PA])["reason"] == "signer not trusted"

@pytest.mark.parametrize("junk", [None, 1, {}, {"scheme": "x"}, {"scheme": ca.BUNDLE_SCHEME},
                                  {"scheme": ca.BUNDLE_SCHEME, "signer": "zz", "seq": -1}])
def test_malformed_never_raises(junk):
    assert not ca.check_bundle(junk, [PA])["ok"]

@pytest.mark.parametrize("args", [("zz", 1, 0, 1), (A, -1, 0, 1), (A, True, 0, 1), (A, 1, 5, 5), (A, 1, 0, 1, [{"scheme": ca.ROTATE_SCHEME}])])
def test_make_bundle_rejects_bad_input(args):
    with pytest.raises(ValueError): ca.make_bundle(*args)

def test_offline_cli_bundle(tmp_path):
    r = _rec(150); (tmp_path / "c.json").write_text(json.dumps(_card(B, 150))); (tmp_path / "d.json").write_text(json.dumps(cm.disclose(r, 0)))
    (tmp_path / "b.json").write_text(json.dumps(ca.make_bundle(B, 7, 120, 900, [ca.make_rotation(A, B, 100)])))
    base = [str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--pubkey", PA]
    assert ov.main(base) == 1
    assert ov.main(base + ["--bundle", str(tmp_path / "b.json"), "--now", "200"]) == 0
    assert ov.main(base + ["--bundle", str(tmp_path / "b.json"), "--min-seq", "8"]) == 1
    assert ov.main(base + ["--bundle", str(tmp_path / "b.json"), "--now", "900"]) == 1
    assert ov.main([str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--bundle", str(tmp_path / "b.json")]) == 1
