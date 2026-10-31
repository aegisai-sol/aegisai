import json
from aegis_miner import card_attest as ca, claim_merkle as cm, token_bridge, offline_verify as ov

A, B, X = "11" * 32, "22" * 32, "44" * 32
PA, PB, PX = (ca.pubkey_from_seed(s) for s in (A, B, X))

def _rec(ts, rid="r1", tag=""):
    r = {"receipt_id": rid, "client_id": "c", "ts": ts, "nonce": "nonce-1234", "credits_awarded": 1,
         "claims": [{"text": f"claim {i}{tag}", "vote": "TRUE", "evidence": "e"} for i in range(3)],
         "calibration": {"ok": True, "failed": []}, "flagged": False, "protocol_version": "pov-r/1", "claim_schema": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(seed, ts, rid="r1", tag=""): return ca.sign_card(token_bridge.receipt_proof(_rec(ts, rid, tag)), seed)

def _sup(seed, card, to, at=500): return ca.make_retraction(seed, card, "superseded", at, superseded_by=to)

def test_unretracted_card_is_current():
    c = _card(A, 100)
    r = ca.resolve_current_card(c, [], [], [PA])
    assert r["status"] == "current" and r["current"] is c and r["path"] == ["r1"]

def test_follows_two_hop_chain():
    c1, c2, c3 = _card(A, 100, "r1"), _card(A, 200, "r2"), _card(A, 300, "r3")
    rets = [_sup(A, c1, "r2"), _sup(A, c2, "r3")]
    r = ca.resolve_current_card(c1, [c3, c2], rets, [PA])
    assert r["status"] == "current" and r["current"]["receipt_id"] == "r3" and r["path"] == ["r1", "r2", "r3"]

def test_terminal_retraction_and_missing_successor():
    c1, c2 = _card(A, 100, "r1"), _card(A, 200, "r2")
    r = ca.resolve_current_card(c1, [c2], [_sup(A, c1, "r2"), ca.make_retraction(A, c2, "error", 600)], [PA])
    assert r["status"] == "retracted" and r["reason"] == "error" and r["current"] is None
    m = ca.resolve_current_card(c1, [], [_sup(A, c1, "r2")], [PA])
    assert m["status"] == "successor_missing" and m["path"] == ["r1", "r2"]

def test_forged_successor_ignored():
    c1, fake = _card(A, 100, "r1"), _card(X, 200, "r2")
    r = ca.resolve_current_card(c1, [fake], [_sup(A, c1, "r2")], [PA])
    assert r["status"] == "successor_missing"

def test_stranger_supersession_ignored():
    c1, c2 = _card(A, 100, "r1"), _card(X, 200, "r2")
    r = ca.resolve_current_card(c1, [c2], [_sup(X, c1, "r2")], [PA])
    assert r["status"] == "current" and r["current"] is c1

def test_ambiguous_successor_fails_closed():
    c1, a2, b2 = _card(A, 100, "r1"), _card(A, 200, "r2", "a"), _card(A, 200, "r2", "b")
    assert a2["digest"] != b2["digest"]
    r = ca.resolve_current_card(c1, [a2, b2], [_sup(A, c1, "r2")], [PA])
    assert r["status"] == "invalid" and "ambiguous" in r["reason"]

def test_backdated_successor_rejected():
    c1, c2 = _card(A, 300, "r1"), _card(A, 100, "r2")
    r = ca.resolve_current_card(c1, [c2], [_sup(A, c1, "r2")], [PA])
    assert r["status"] == "invalid" and "predates" in r["reason"]

def test_cycle_detected():
    c1, c2 = _card(A, 100, "r1"), _card(A, 100, "r2")
    r = ca.resolve_current_card(c1, [c1, c2], [_sup(A, c1, "r2"), _sup(A, c2, "r1")], [PA])
    assert r["status"] == "invalid" and "cycle" in r["reason"]

def test_successor_signed_by_rotated_key():
    c1, c2 = _card(A, 100, "r1"), _card(B, 300, "r2")
    rot = ca.make_rotation(A, B, 200)
    r = ca.resolve_current_card(c1, [c2], [_sup(B, c1, "r2")], [PA], [rot])
    assert r["status"] == "current" and r["current"]["receipt_id"] == "r2"
    assert ca.resolve_current_card(c1, [c2], [_sup(B, c1, "r2")], [PA])["status"] == "current"  # no rotation: B untrusted
    assert ca.resolve_current_card(c1, [c2], [_sup(B, c1, "r2")], [PA])["current"] is c1

def test_untrusted_start_and_malformed_never_raise():
    assert ca.resolve_current_card(_card(X, 1), [], [], [PA])["status"] == "invalid"
    assert ca.resolve_current_card(None, None, None, None)["status"] == "invalid"
    assert ca.resolve_current_card(_card(A, 1), ["junk", 5, None], [{"x": 1}], [PA])["status"] == "current"

def test_cli_reports_current_card(tmp_path, capsys):
    c1, c2 = _card(A, 100, "r1"), _card(A, 200, "r2")
    files = {"d": cm.disclose(_rec(100, "r1"), 0), "c1": c1, "c2": c2, "rt": _sup(A, c1, "r2")}
    for k, v in files.items(): (tmp_path / f"{k}.json").write_text(json.dumps(v))
    p = lambda k: str(tmp_path / f"{k}.json")
    rc = ov.main([p("d"), "--card", p("c1"), "--pubkey", PA, "--retraction", p("rt"), "--successor", p("c2")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["retracted"] and out["supersession"]["status"] == "current"
    assert out["supersession"]["current_receipt_id"] == "r2" and out["supersession"]["current_digest"] == c2["digest"]
    rc = ov.main([p("d"), "--card", p("c1"), "--pubkey", PA, "--retraction", p("rt")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["supersession"]["status"] == "successor_missing"
