import json, pytest
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, G, G2, W1, W2, W3, X = "11" * 32, "22" * 32, "33" * 32, "55" * 32, "66" * 32, "77" * 32, "44" * 32
PA, PG, PG2, P1, P2, P3, PX = (ca.pubkey_from_seed(s) for s in (A, G, G2, W1, W2, W3, X))
WK = [P1, P2, P3]

def _rec(ts, rid="r1"):
    r = {"receipt_id": rid, "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(ts=100, rid="r1"): return ca.sign_card(token_bridge.receipt_proof(_rec(ts, rid)), A)
def _ros(seq=1, ia=0, ea=1000, ws=WK, k=2, seed=G): return ca.make_roster(seed, seq, ia, ea, ws, k)

def test_roster_roundtrip_and_order_independent():
    r = ca.check_roster(_ros(), [PG])
    assert r["ok"] and r["threshold"] == 2 and r["witnesses"] == sorted(WK) and r["seq"] == 1
    assert ca.make_roster(G, 1, 0, 1000, list(reversed(WK)), 2)["sig"] == _ros()["sig"]

def test_roster_rejects_untrusted_tampered_or_bad():
    ro = _ros()
    assert ca.check_roster(ro, [PG2])["reason"] == "roster signer not trusted"
    assert not ca.check_roster(ca.make_roster(X, 1, 0, 1000, WK, 2), [PG])["ok"]
    assert ca.check_roster(dict(ro, threshold=1), [PG])["reason"] == "bad signature"  # can't lower k
    assert ca.check_roster(dict(ro, witnesses=sorted(WK + [PX])), [PG])["reason"] == "bad signature"  # can't pad
    assert ca.check_roster(dict(ro, witnesses=[P1, P1, P2]), [PG])["reason"] == "bad roster witnesses"
    assert ca.check_roster(dict(ro, threshold=4), [PG])["reason"] == "bad roster threshold"
    assert ca.check_roster(dict(ro, scheme=ca.BUNDLE_SCHEME), [PG])["reason"] == "not a witness roster"
    for bad in (None, 3, "x", {}, dict(ro, seq=True), dict(ro, sig="zz")): assert not ca.check_roster(bad, [PG])["ok"]
    assert not ca.check_roster(ro, ["bad"])["ok"] and not ca.check_roster(ro, [])["ok"]

def test_make_roster_validation():
    for args in ((G, 1, 0, 1000, [], 1), (G, 1, 0, 1000, WK, 0), (G, 1, 0, 1000, WK, 4), (G, 1, 5, 5, WK, 1),
                 (G, -1, 0, 1000, WK, 1), (G, 1, 0, 1000, [P1, P1], 1), (G, 1, 0, 1000, ["zz"], 1),
                 (G, 1, 0, 1000, [PG, P1], 1), ("bad", 1, 0, 1000, WK, 1)):
        with pytest.raises(ValueError): ca.make_roster(*args)

def test_roster_freshness_rollback_window_and_revocation():
    ro = _ros(seq=5, ia=50, ea=500)
    assert ca.check_roster(ro, [PG], now=100)["ok"]
    assert ca.check_roster(ro, [PG], now=500)["reason"] == "roster expired"
    assert ca.check_roster(ro, [PG], now=10)["reason"] == "roster issued in the future"
    assert ca.check_roster(ro, [PG], min_seq=6)["reason"].startswith("roster rollback")
    assert ca.check_roster(ro, [PG], min_seq=5)["ok"]
    assert ca.check_roster(ro, [PG], card_ts=49)["reason"] == "card ts outside roster validity window"
    assert ca.check_roster(ro, [PG], card_ts=500)["reason"] == "card ts outside roster validity window"
    assert ca.check_roster(ro, [PG], card_ts=50)["ok"]
    assert ca.check_roster(ro, [PG], revocations=[ca.make_revocation(G, "compromised", 999)])["reason"] == "roster signer revoked"
    assert ca.check_roster(ro, [PG], revocations=[ca.make_revocation(G, "retired", 40)])["reason"] == "roster signer revoked"
    assert ca.check_roster(ro, [PG], revocations=[ca.make_revocation(G, "retired", 60)])["ok"]
    assert ca.check_roster(ro, [PG], revocations=[ca.make_revocation(X, "compromised", 0)])["ok"]

def test_rostered_quorum_uses_roster_keys_and_k():
    c = _card(); ws = [ca.make_witness(W1, c), ca.make_witness(W2, c)]
    r = ca.check_witnesses_rostered(c, ws, _ros(), [PG])
    assert r["ok"] and r["count"] == 2 and r["threshold"] == 2 and r["roster_seq"] == 1
    assert not ca.check_witnesses_rostered(c, ws[:1], _ros(), [PG])["ok"]
    # a witness the roster dropped no longer counts
    assert not ca.check_witnesses_rostered(c, ws, _ros(ws=[P1, P3], k=2), [PG])["ok"]
    # verifier can demand more than k, never less
    assert not ca.check_witnesses_rostered(c, ws, _ros(), [PG], min_threshold=3)["ok"]
    assert ca.check_witnesses_rostered(c, ws, _ros(), [PG], min_threshold=1)["threshold"] == 2
    assert ca.check_witnesses_rostered(c, ws, _ros(), [PG], min_threshold=0)["reason"] == "bad min_threshold"
    # card outside roster window, untrusted roster, dissent
    assert "roster:" in ca.check_witnesses_rostered(_card(ts=2000), ws, _ros(), [PG])["reason"]
    assert "roster:" in ca.check_witnesses_rostered(c, ws, _ros(seed=X), [PG])["reason"]
    d = ca.check_witnesses_rostered(c, ws, _ros(), [PG], dissents=[ca.make_dissent(W3, c, "source_mismatch")])
    assert not d["ok"] and d["dissenters"] == [P3]

def test_rostered_coordinator_listed_fails_closed_and_never_raises():
    c = _card(); ws = [ca.make_witness(W1, c)]
    r = ca.check_witnesses_rostered(c, ws, _ros(ws=[PA, P1], k=2), [PG])
    assert not r["ok"] and "threshold exceeds" in r["reason"]
    for bad in (None, "x", 7): assert not ca.check_witnesses_rostered(bad, ws, _ros(), [PG])["ok"]
    assert not ca.check_witnesses_rostered(c, [None, 3], {"scheme": ca.ROSTER_SCHEME}, [PG])["ok"]

def test_offline_cli_roster(tmp_path, capsys):
    rec = _rec(100); c = _card(); d = cm.disclose(rec, 0)
    def w(name, obj): p = tmp_path / name; p.write_text(json.dumps(obj)); return str(p)
    base = [w("d.json", d), "--card", w("c.json", c), "--pubkey", PA]
    q = ["--witness", w("w1.json", ca.make_witness(W1, c)), "--witness", w("w2.json", ca.make_witness(W2, c))]
    ro = ["--roster", w("ro.json", _ros(seq=3)), "--governance-key", PG]
    assert ov.main(base + q + ro) == 0
    out = json.loads(capsys.readouterr().out); assert out["witnesses"]["roster_seq"] == 3 and out["witnesses"]["threshold"] == 2
    assert ov.main(base + q[:2] + ro) == 1; capsys.readouterr()
    assert ov.main(base + q + ro + ["--roster-min-seq", "4"]) == 1
    assert "rollback" in json.loads(capsys.readouterr().out)["reason"]
    assert ov.main(base + q + ro + ["--witness-threshold", "3"]) == 1; capsys.readouterr()
    assert ov.main(base + q + ["--roster", w("ro2.json", _ros())]) == 1
    assert "--governance-key" in json.loads(capsys.readouterr().out)["reason"]
