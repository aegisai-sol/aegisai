import json, itertools
import pytest
from aegis_miner import claim_merkle as cm, token_bridge

def _rec(n=5, rid="r1"):
    claims = [{"text": f"claim {i}", "vote": ["TRUE", "FALSE", "UNSURE"][i % 3], "evidence": f"ev-{i}-private"} for i in range(n)]
    claims.insert(1, {"text": "canary", "vote": "TRUE", "canary": True})
    r = {"receipt_id": rid, "client_id": "cid-secret", "ts": 1.0, "claims": claims, "credits_awarded": 1}
    r["digest"] = token_bridge.receipt_digest(r); return r

@pytest.mark.parametrize("n", [1, 2, 3, 5, 7, 8])
def test_all_subsets_verify(n):
    r = _rec(n); root = cm.claims_root(r)
    for k in range(1, n + 1):
        for sub in itertools.combinations(range(n), k):
            m = cm.disclose_multi(r, list(sub)); v = cm.verify_multi(m, root)
            assert v["ok"] and v["count"] == k and m["claims_root"] == root, (n, sub)

def test_compact_vs_separate_paths():
    r = _rec(16); idx = [0, 1, 2, 3, 8, 9]
    m = cm.disclose_multi(r, idx)
    separate = sum(len(cm.disclose(r, i)["path"]) for i in idx)
    assert len(m["proof"]) < separate and len(cm.disclose_multi(r, list(range(16)))["proof"]) == 0

def test_matches_single_disclosure_root_and_order_canonical():
    r = _rec(6); m = cm.disclose_multi(r, [4, 1])
    assert m["indices"] == [1, 4] and cm.verify_multi(m)["root"] == cm.disclose(r, 4)["claims_root"]

def test_privacy():
    blob = json.dumps(cm.disclose_multi(_rec(5), [0, 3]))
    for s in ("cid-secret", "ev-0-private", "canary", "claim 1", "claim 2", "claim 4"): assert s not in blob

def test_tamper_detected():
    r = _rec(7); root = cm.claims_root(r); m = cm.disclose_multi(r, [1, 4, 5])
    muts = [lambda x: x["claims"][1].update(vote="TRUE" if x["claims"][1]["vote"] != "TRUE" else "FALSE"),
            lambda x: x["claims"][0].update(text="forged"), lambda x: x.update(indices=[1, 4, 6]),
            lambda x: x.update(indices=[4, 1, 5]), lambda x: x.update(indices=[1, 1, 5]),
            lambda x: x["salts"].__setitem__(2, "0" * 64), lambda x: x["proof"].pop(),
            lambda x: x["proof"].append("a" * 64), lambda x: x["proof"].reverse() if len(set(x["proof"])) > 1 else x["proof"].pop(),
            lambda x: x.update(leaf_count=6), lambda x: x["claims"].pop(), lambda x: x.update(proof="nope")]
    for f in muts:
        x = json.loads(json.dumps(m)); f(x); assert not cm.verify_multi(x, root)["ok"]

def test_wrong_root_embedded_flag_and_malformed():
    r = _rec(4); m = cm.disclose_multi(r, [0, 2])
    assert not cm.verify_multi(m, cm.claims_root(_rec(4, rid="other")))["ok"]
    assert cm.verify_multi(m)["root_source"] == "embedded(untrusted)"
    for bad in (None, [], "x", {"leaf_count": True, "indices": [0]}, {**m, "indices": []}, {**m, "claims": "x"}):
        assert cm.verify_multi(bad)["ok"] is False

def test_prover_rejects_bad_indices():
    r = _rec(3)
    for bad, exc in (([], ValueError), ([0, 0], ValueError), ([3], IndexError), ([True], IndexError), ("0", ValueError)):
        with pytest.raises(exc): cm.disclose_multi(r, bad)

def test_leaf_count_binding():
    r = _rec(7); root = cm.claims_root(r); m = cm.disclose_multi(r, [1, 4, 5])
    x = {**m, "leaf_count": 8}  # same replay shape as 7 leaves -> root alone cannot pin N
    assert cm.verify_multi(x, root)["leaf_count_source"] == "embedded(untrusted)"
    assert cm.verify_multi(x, root, expected_leaf_count=7) == {"ok": False, "reason": "leaf_count mismatch"}
    v = cm.verify_multi(m, root, expected_leaf_count=7)
    assert v["ok"] and v["leaf_count"] == 7 and v["leaf_count_source"] == "expected"
