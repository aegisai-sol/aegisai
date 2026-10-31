from aegis_miner.consensus import PeerHealth, consensus, consensus_alive

def node(nid, vote, h="h1", err=None):
    def run(u, c):
        if err: raise RuntimeError(err)
        return {"node": nid, "vote": vote, "source_hash": h}
    run.node_id = nid; return run

def test_weight_formula():
    ph = PeerHealth(2, 2)
    assert ph.weight("x") == 1.0
    for _ in range(5): ph.observe("x", True)
    assert ph.weight("x") == 1.5
    for _ in range(20): ph.observe("x", True)
    assert ph.weight("x") == 2.0
    ph.observe("x", False); assert ph.weight("x") == 1.0
    ph.observe("x", False); assert ph.weight("x") == 0.0

def test_weights_ids_only_and_summary():
    ph = PeerHealth(); ph.observe("http://secret", True)
    s = ph.summary(["http://secret"])
    assert s["weights"] == {"peer0": 1.1} and "secret" not in str(s)

def test_weighted_vote_picks_heavier_side():
    w = {"a": 2.0, "b": 2.0, "c": 1.0, "d": 1.0, "e": 1.0}
    nodes = [node("a", "SUPPORTED"), node("b", "SUPPORTED"), node("c", "REFUTED"), node("d", "REFUTED"), node("e", "REFUTED")]
    plain = consensus("u", "c", nodes); assert plain["consensus_vote"] == "REFUTED"
    r = consensus("u", "c", nodes, weights=w)
    assert r["consensus_vote"] == "SUPPORTED" and r["vote_weight"] == 4.0 and r["total_weight"] == 7.0 and r["weighted"]

def test_single_heavy_cannot_beat_quorum_count():
    r = consensus("u", "c", [node("a", "SUPPORTED"), node("b", "REFUTED")], quorum=2, weights={"a": 2.0})
    assert r["status"] in ("HASH_ONLY", "NO_CONSENSUS") and r["consensus_vote"] is None

def test_tie_breaks_on_count():
    nodes = [node("a", "SUPPORTED"), node("b", "REFUTED"), node("c", "REFUTED")]
    r = consensus("u", "c", nodes, weights={"a": 2.0}); assert r["consensus_vote"] == "REFUTED"

def test_errors_carry_no_weight():
    nodes = [node("a", "SUPPORTED", err="boom"), node("b", "REFUTED"), node("c", "REFUTED")]
    r = consensus("u", "c", nodes, weights={"a": 2.0}); assert r["total_weight"] == 2.0

def test_unweighted_receipt_unchanged():
    r = consensus("u", "c", [node("a", "SUPPORTED"), node("b", "SUPPORTED")]); assert "weighted" not in r

def test_consensus_alive_weighted():
    ph = PeerHealth(); peers = ["p0", "p1"]
    for _ in range(10): ph.observe("p0", True)
    fac = lambda nid, e: node(nid, "SUPPORTED")
    import aegis_miner.consensus as C
    orig = C.local_node; C.local_node = lambda nid, *a, **k: node(nid, "SUPPORTED")
    try: r = consensus_alive("u", "c", peers, health=ph, node_factory=fac, weighted=True)
    finally: C.local_node = orig
    assert r["weighted"] and r["total_weight"] == 2.0 + 1.0 + 1.0 and r["valid"]

import pytest
@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "2"])
def test_rejects_poisoned_weights(bad):
    with pytest.raises(ValueError):
        consensus("u", "c", [node("a", "SUPPORTED"), node("b", "SUPPORTED")], weights={"a": bad})
