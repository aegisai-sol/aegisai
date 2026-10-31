import json
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, W1, W2, W3, X = "11" * 32, "55" * 32, "66" * 32, "77" * 32, "44" * 32
PA, P1, P2, P3, PX = (ca.pubkey_from_seed(s) for s in (A, W1, W2, W3, X))

def _rec(ts, rid="r1"):
    r = {"receipt_id": rid, "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(seed, ts=100, rid="r1"): return ca.sign_card(token_bridge.receipt_proof(_rec(ts, rid)), seed)
WK = [P1, P2, P3]

def test_two_of_three_quorum():
    c = _card(A)
    ws = [ca.make_witness(W1, c), ca.make_witness(W2, c)]
    r = ca.check_witnesses(c, ws, WK, 2)
    assert r["ok"] and r["count"] == 2 and r["signers"] == sorted([P1, P2])
    assert not ca.check_witnesses(c, ws[:1], WK, 2)["ok"]

def test_duplicates_and_strangers_do_not_pad():
    c = _card(A)
    ws = [ca.make_witness(W1, c)] * 3 + [ca.make_witness(X, c)]
    r = ca.check_witnesses(c, ws, WK, 2)
    assert not r["ok"] and r["count"] == 1

def test_coordinator_cannot_witness_itself():
    c = _card(A)
    ws = [ca.make_witness(A, c), ca.make_witness(W1, c)]
    assert ca.check_witnesses(c, ws, WK + [PA], 2)["count"] == 1
    assert ca.check_witnesses(c, ws, [PA, P1], 2)["reason"] == "threshold exceeds usable witness keys"

def test_witness_bound_to_card_and_coordinator():
    c, other = _card(A), _card(A, rid="r2")
    w = ca.make_witness(W1, other)
    assert ca.check_witnesses(c, [w], WK, 1)["count"] == 0
    assert ca.check_witnesses(c, [dict(w, receipt_id="r1", digest=c["digest"])], WK, 1)["count"] == 0
    resigned = ca.sign_card({k: v for k, v in c.items() if k != "attestation"}, X)  # same fields, forger coordinator
    assert ca.check_witnesses(resigned, [ca.make_witness(W1, c)], WK, 1)["count"] == 0
    tampered = dict(c, claim_count=99)
    assert ca.check_witnesses(tampered, [ca.make_witness(W1, c)], WK, 1)["count"] == 0

def test_witness_sig_not_replayable_as_attestation():
    c = _card(A); w = ca.make_witness(W1, c)
    fake = dict(c, attestation={"scheme": ca.SCHEME, "pubkey": P1, "sig": w["sig"]})
    assert not ca.verify_card(fake, [P1])["ok"]

def test_witness_revocations():
    c = _card(A, ts=100); ws = [ca.make_witness(W1, c), ca.make_witness(W2, c)]
    assert ca.check_witnesses(c, ws, WK, 2, [ca.make_revocation(W1, "compromised", 0)])["count"] == 1
    assert ca.check_witnesses(c, ws, WK, 2, [ca.make_revocation(W1, "retired", 500)])["ok"]
    assert ca.check_witnesses(c, ws, WK, 2, [ca.make_revocation(W1, "retired", 50)])["count"] == 1
    assert ca.check_witnesses(c, ws, WK, 2, [dict(ca.make_revocation(X, "compromised", 0), pubkey=P1)])["ok"]

def test_bad_inputs_fail_closed_never_raise():
    c = _card(A)
    for t in (0, -1, True, "2", None): assert not ca.check_witnesses(c, [], WK, t)["ok"]
    assert not ca.check_witnesses("x", [], WK, 1)["ok"]
    assert ca.check_witnesses(c, [None, 5, {"scheme": ca.WITNESS_SCHEME, "pubkey": "zz"}], WK, 1)["count"] == 0
    assert not ca.check_witnesses(c, [], ["nothex", 7], 1)["ok"]

def test_make_witness_rejects_unattested():
    import pytest
    with pytest.raises(ValueError): ca.make_witness(W1, token_bridge.receipt_proof(_rec(100)))
    with pytest.raises(ValueError): ca.make_witness("bad", _card(A))

def test_offline_cli_witness_quorum(tmp_path, capsys):
    rec = _rec(100); c = _card(A); d = cm.disclose(rec, 0)
    def w(name, obj): p = tmp_path / name; p.write_text(json.dumps(obj)); return str(p)
    base = [w("d.json", d), "--card", w("c.json", c), "--pubkey", PA] + sum((["--witness-key", k] for k in WK), [])
    w1, w2 = w("w1.json", ca.make_witness(W1, c)), w("w2.json", ca.make_witness(W2, c))
    assert ov.main(base + ["--witness", w1, "--witness", w2, "--witness-threshold", "2"]) == 0
    out = json.loads(capsys.readouterr().out); assert out["witnesses"]["count"] == 2
    assert ov.main(base + ["--witness", w1, "--witness-threshold", "2"]) == 1
    out = json.loads(capsys.readouterr().out); assert "witness quorum" in out["reason"] and not out["trusted"]
    assert ov.main([w("d2.json", d), "--card", w("c2.json", c), "--witness-threshold", "1"]) == 1
    assert ov.main(base + ["--witness", w1]) == 0  # no threshold -> legacy behaviour
