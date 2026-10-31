import json, copy
import pytest
from aegis_miner import claim_merkle as cm, token_bridge, offline_verify as ov

def _rec(n=6, rid="r1"):
    claims = [{"text": f"claim {i}", "vote": ["TRUE", "FALSE"][i % 2], "evidence": f"ev{i}"} for i in range(n)]
    claims.insert(2, {"text": "canary", "vote": "TRUE", "canary": True})
    r = {"receipt_id": rid, "client_id": "c", "ts": 1.0, "claims": claims, "credits_awarded": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

def _card(r): return token_bridge.receipt_proof(r)

def test_single_set_multi_trusted():
    r = _rec(); card = _card(r)
    for obj, kind, k in ((cm.disclose(r, 3), "single", 1), ([cm.disclose(r, 0), cm.disclose(r, 4)], "set", 2),
                         ({"disclosures": [cm.disclose(r, 1)]}, "set", 1), (cm.disclose_multi(r, [5, 0, 2]), "multiproof", 3),
                         ({"multiproof": cm.disclose_multi(r, [1])}, "multiproof", 1)):
        v = ov.verify_offline(obj, card)
        assert v["ok"] and v["trusted"] and v["kind"] == kind and v["count"] == k and v["leaf_count"] == 6, (kind, v)

def test_untrusted_without_pins():
    r = _rec(); v = ov.verify_offline(cm.disclose(r, 0))
    assert v["ok"] and not v["trusted"] and v["root_source"] == "embedded(untrusted)"
    v = ov.verify_offline(cm.disclose(r, 0), root=cm.claims_root(r), leaf_count=6)
    assert v["ok"] and v["trusted"]

def test_card_from_other_receipt_rejected():
    a, b = _rec(rid="a"), _rec(rid="b")
    v = ov.verify_offline(cm.disclose(a, 0), _card(b)); assert not v["ok"] and "receipt_id" in v["reason"]
    forged = dict(_card(b), receipt_id="a")
    assert not ov.verify_offline(cm.disclose(a, 0), forged)["ok"]

def test_leaf_count_inflation_rejected():
    r = _rec(7); card = _card(r); m = cm.disclose_multi(r, [0, 1])
    lie = dict(card, claim_count=8)
    assert not ov.verify_offline(m, lie)["ok"]
    d = cm.disclose(r, 0); assert not ov.verify_offline(d, lie)["ok"]
    assert not ov.verify_offline(d, card, leaf_count=8)["ok"]

def test_bad_cards_and_conflicts():
    r = _rec(); card = _card(r); d = cm.disclose(r, 0)
    for bad in ("x", {}, dict(card, claims_root="zz"), dict(card, claim_count=0), dict(card, claim_count=True),
                dict(card, receipt_id=""), dict(card, audit={"intact": False})):
        assert not ov.verify_offline(d, bad)["ok"], bad
    assert not ov.verify_offline(d, card, root="a" * 64)["ok"]
    assert not ov.verify_offline(d, None, root="nothex")["ok"]

def test_tamper_and_garbage_never_raise():
    r = _rec(); card = _card(r); d = cm.disclose(r, 2); d["claim"]["vote"] = "TRUE" if d["claim"]["vote"] != "TRUE" else "FALSE"
    assert not ov.verify_offline(d, card)["ok"]
    for junk in (None, 5, "s", [], [1], {"indices": "x"}, {"disclosures": [None]}, [{"receipt_id": "r1"}]):
        assert ov.verify_offline(junk, card)["ok"] is False

def test_cli_exit_codes(tmp_path, capsys):
    r = _rec(); dp, cp = tmp_path / "d.json", tmp_path / "c.json"
    dp.write_text(json.dumps(cm.disclose_multi(r, [0, 3]))); cp.write_text(json.dumps(_card(r)))
    assert ov.main([str(dp), "--card", str(cp)]) == 0 and json.loads(capsys.readouterr().out)["count"] == 2
    assert ov.main([str(dp)]) == 1 and ov.main([str(dp), "--allow-untrusted"]) == 0
    capsys.readouterr(); assert ov.main([str(tmp_path / "missing.json")]) == 2
    bad = json.loads(dp.read_text()); bad["claims"][0]["text"] = "forged"; dp.write_text(json.dumps(bad))
    assert ov.main([str(dp), "--card", str(cp)]) == 1

def test_privacy_of_output():
    r = _rec(); blob = json.dumps(ov.verify_offline(cm.disclose_multi(r, [1]), _card(r)))
    for s in ("ev0", "ev1", "canary", "claim 0", "claim 2"): assert s not in blob
