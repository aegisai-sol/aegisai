import json, pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, W1, W2, W3, X = "11" * 32, "55" * 32, "66" * 32, "77" * 32, "44" * 32
PA, P1, P2, P3, PX = (ca.pubkey_from_seed(s) for s in (A, W1, W2, W3, X))
WK = [P1, P2, P3]

def _rec(ts, rid="r1"):
    r = {"receipt_id": rid, "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(seed, ts=100, rid="r1"): return ca.sign_card(token_bridge.receipt_proof(_rec(ts, rid)), seed)

def test_trusted_dissent_disputes_quorum():
    c = _card(A); ws = [ca.make_witness(W1, c), ca.make_witness(W2, c)]
    d = ca.make_dissent(W3, c, "source_mismatch")
    r = ca.check_witnesses(c, ws, WK, 2, dissents=[d])
    assert not r["ok"] and r["count"] == 2 and r["dissenters"] == [P3] and "disputed" in r["reason"]
    assert r["dissent_reasons"] == {P3: "source_mismatch"}
    assert ca.check_witnesses(c, ws, WK, 2, dissents=[d], max_dissent=1)["ok"]
    assert ca.check_witnesses(c, ws, WK, 2)["dissenters"] == []

def test_cosign_and_dissent_voids_approval():
    c = _card(A); ws = [ca.make_witness(W1, c), ca.make_witness(W2, c)]
    r = ca.check_witnesses(c, ws, WK, 2, dissents=[ca.make_dissent(W1, c, "replay_mismatch")], max_dissent=1)
    assert not r["ok"] and r["count"] == 1 and r["signers"] == [P2]

def test_strangers_coordinator_dupes_and_compromised_cannot_dispute():
    c = _card(A); ws = [ca.make_witness(W1, c), ca.make_witness(W2, c)]
    assert ca.check_witnesses(c, ws, WK, 2, dissents=[ca.make_dissent(X, c, "source_mismatch")])["ok"]
    assert ca.check_witnesses(c, ws, WK + [PA], 2, dissents=[ca.make_dissent(A, c, "source_mismatch")])["ok"]
    d = ca.make_dissent(W3, c, "claim_unsupported")
    assert ca.check_dissents(c, [d, d, d], WK)["dissenters"] == [P3]
    assert ca.check_witnesses(c, ws, WK, 2, [ca.make_revocation(W3, "compromised", 0)], dissents=[d])["ok"]
    assert not ca.check_witnesses(c, ws, WK, 2, [ca.make_revocation(W3, "retired", 500)], dissents=[d])["ok"]
    assert ca.check_witnesses(c, ws, WK, 2, [ca.make_revocation(W3, "retired", 50)], dissents=[d])["ok"]

def test_dissent_bound_to_card_reason_and_domain():
    c, other = _card(A), _card(A, rid="r2")
    d = ca.make_dissent(W3, other, "source_mismatch")
    assert ca.check_dissents(c, [d], WK)["dissenters"] == []
    assert ca.check_dissents(c, [dict(d, receipt_id="r1", digest=c["digest"])], WK)["dissenters"] == []
    good = ca.make_dissent(W3, c, "source_mismatch")
    assert ca.check_dissents(c, [dict(good, reason="claim_unsupported")], WK)["dissenters"] == []
    assert ca.check_dissents(dict(c, claim_count=99), [good], WK)["dissenters"] == []
    # a co-signature can't be replayed as a dissent nor a dissent as a co-signature
    w = ca.make_witness(W3, c)
    assert ca.check_dissents(c, [dict(w, scheme=ca.DISSENT_SCHEME, reason="source_mismatch")], WK)["dissenters"] == []
    assert ca.check_witnesses(c, [dict(good, scheme=ca.WITNESS_SCHEME)], WK, 1)["count"] == 0

def test_bad_inputs_never_raise():
    c = _card(A)
    assert ca.check_dissents("x", [], WK) == {"dissenters": [], "reasons": {}}
    assert ca.check_dissents(c, [None, 3, {"scheme": ca.DISSENT_SCHEME, "pubkey": "zz"}], WK)["dissenters"] == []
    assert ca.check_dissents(c, [ca.make_dissent(W3, c, "source_mismatch")], ["bad", 7])["dissenters"] == []
    with pytest.raises(ValueError): ca.make_dissent(W3, c, "because")
    with pytest.raises(ValueError): ca.make_dissent(W3, token_bridge.receipt_proof(_rec(100)), "source_mismatch")
    with pytest.raises(ValueError): ca.make_dissent("bad", c, "source_mismatch")

def test_offline_cli_dissent(tmp_path, capsys):
    rec = _rec(100); c = _card(A); d = cm.disclose(rec, 0)
    def w(name, obj): p = tmp_path / name; p.write_text(json.dumps(obj)); return str(p)
    base = [w("d.json", d), "--card", w("c.json", c), "--pubkey", PA] + sum((["--witness-key", k] for k in WK), [])
    w1, w2 = w("w1.json", ca.make_witness(W1, c)), w("w2.json", ca.make_witness(W2, c))
    ds = w("ds.json", ca.make_dissent(W3, c, "source_mismatch"))
    q = ["--witness", w1, "--witness", w2, "--witness-threshold", "2"]
    assert ov.main(base + q) == 0; capsys.readouterr()
    assert ov.main(base + q + ["--dissent", ds]) == 1
    out = json.loads(capsys.readouterr().out)
    assert "disputed" in out["reason"] and out["witnesses"]["dissenters"] == [P3] and not out["trusted"]
    assert ov.main(base + q + ["--dissent", ds, "--max-dissent", "1"]) == 0; capsys.readouterr()
    assert ov.main(base + ["--dissent", ds]) == 1  # no threshold: a trusted dissent still disputes
    out = json.loads(capsys.readouterr().out); assert out["dissent"]["dissenters"] == [P3]
    assert ov.main(base + ["--dissent", w("x.json", ca.make_dissent(X, c, "source_mismatch"))]) == 0
