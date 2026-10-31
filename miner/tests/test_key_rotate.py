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

def test_rotation_roundtrip():
    r = ca.make_rotation(A, B, 100)
    assert ca.check_rotation(r) == (PA, PB, 100) and r["scheme"] == ca.ROTATE_SCHEME

def test_successor_trusted_from_pinned_old_key():
    rot = [ca.make_rotation(A, B, 100)]
    assert ca.verify_card_chain(_card(B, 150), [PA], rot)["ok"]
    assert not ca.verify_card(_card(B, 150), [PA])["ok"]  # without the chain, B is unknown

def test_windows_enforced_both_sides():
    rot = [ca.make_rotation(A, B, 100)]
    assert ca.verify_card_chain(_card(A, 50), [PA], rot)["ok"]
    assert "rotated out" in ca.verify_card_chain(_card(A, 100), [PA], rot)["reason"]
    assert "predates" in ca.verify_card_chain(_card(B, 50), [PA], rot)["reason"]

def test_multi_hop_chain():
    rot = [ca.make_rotation(B, C, 200), ca.make_rotation(A, B, 100)]  # order independent
    assert ca.verify_card_chain(_card(C, 250), [PA], rot)["ok"]
    assert not ca.verify_card_chain(_card(B, 250), [PA], rot)["ok"]
    assert ca.verify_card_chain(_card(B, 150), [PA], rot)["ok"]

def test_needs_new_key_countersignature():
    r = ca.make_rotation(A, X, 100); r["new_pubkey"] = PB  # endorse a key you can't prove you hold
    assert ca.check_rotation(r) is None
    assert not ca.verify_card_chain(_card(B, 150), [PA], [r])["ok"]

def test_third_party_cannot_insert_rotation():
    r = ca.make_rotation(X, B, 100)  # signed by an untrusted key
    assert not ca.verify_card_chain(_card(B, 150), [PA], [r])["ok"]
    assert ca.verify_card_chain(_card(A, 150), [PA], [r])["ok"]

def test_compromised_key_endorses_nothing():
    rot = [ca.make_rotation(A, X, 100)]; rev = [ca.make_revocation(A, "compromised", 0)]
    assert not ca.verify_card_chain(_card(X, 150), [PA], rot, rev)["ok"]

def test_fork_cannot_widen_trust():
    rot = [ca.make_rotation(A, C, 200), ca.make_rotation(A, B, 100)]
    assert ca.verify_card_chain(_card(B, 250), [PA], rot)["ok"]
    assert not ca.verify_card_chain(_card(C, 250), [PA], rot)["ok"]

def test_cycle_safe():
    rot = [ca.make_rotation(A, B, 100), ca.make_rotation(B, A, 200)]
    w = ca.resolve_trust([PA], rot)
    assert set(w) == {PA, PB} and ca.verify_card_chain(_card(B, 150), [PA], rot)["ok"]

@pytest.mark.parametrize("field,val", [("effective_at", 1), ("old_pubkey", PX), ("scheme", "x"), ("old_sig", "zz"), ("effective_at", True)])
def test_tampered_rotation_ignored(field, val):
    r = ca.make_rotation(A, B, 100); r[field] = val
    assert ca.check_rotation(r) is None

@pytest.mark.parametrize("args", [(A, A, 1), (A, B, -1), (A, B, "1"), ("zz", B, 1)])
def test_make_rotation_rejects_bad_input(args):
    with pytest.raises(ValueError): ca.make_rotation(*args)

def test_no_rotation_behaviour_unchanged():
    assert ca.verify_card_chain(_card(A, 100), [PA])["ok"] and not ca.verify_card_chain(_card(A, 100), [PB])["ok"]
    for junk in (None, [None, "x", {}], [{"scheme": ca.ROTATE_SCHEME}]):
        assert ca.verify_card_chain(_card(A, 100), [PA], junk)["ok"]

def test_offline_cli_rotation(tmp_path):
    r = _rec(150); (tmp_path / "c.json").write_text(json.dumps(_card(B, 150))); (tmp_path / "d.json").write_text(json.dumps(cm.disclose(r, 0)))
    (tmp_path / "rot.json").write_text(json.dumps(ca.make_rotation(A, B, 100)))
    base = [str(tmp_path / "d.json"), "--card", str(tmp_path / "c.json"), "--pubkey", PA]
    assert ov.main(base) == 1
    assert ov.main(base + ["--rotation", str(tmp_path / "rot.json")]) == 0
