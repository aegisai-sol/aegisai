import pytest, unittest.mock as m
from aegis_miner import consensus as c
from tests.test_quorum_strength import node

def low_peer():
    h = c.PeerHealth(disagree_cap=0, agreement_min_votes=2)  # instance threshold 0 = off
    for _ in range(4): h.observe_vote("e1", False)
    for _ in range(4): h.observe_vote("e0", True)
    return h

def test_override_applies_and_marks_cut():
    h = low_peer()
    assert h.agreement_cut_ids(["e0", "e1"]) == []
    assert h.agreement_cut_ids(["e0", "e1"], 0.5) == ["peer1"]
    b = h.breakdown("e1", 0.5); assert b["agreement_cut"] and b["agreement"] == 0.25
    assert not h.breakdown("e1")["agreement_cut"] and not h.breakdown("unknown")["agreement_cut"]

def test_consensus_alive_records_override_and_cut_ids():
    h = low_peer(); votes = {"peer0": "TRUE", "peer1": "TRUE"}
    fac = lambda nid, e: node(nid, votes[nid])
    with m.patch.object(c, "local_node", lambda nid: node(nid, "TRUE")):
        r = c.consensus_alive("u", "t", ["e0", "e1"], health=h, node_factory=fac, weighted=True, agreement_threshold=0.5)
        assert r["agreement_threshold_applied"] == {"value": 0.5, "source": "request"}
        assert r["agreement_cut"] == ["peer1"] and r["weights_used"]["peer1"] < r["weights_used"]["peer0"]
        r2 = c.consensus_alive("u", "t", ["e0", "e1"], health=h, node_factory=fac, weighted=True)
        assert r2["agreement_threshold_applied"]["source"] == "env" and r2["agreement_cut"] == []
        r3 = c.consensus_alive("u", "t", ["e0", "e1"], health=h, node_factory=fac)
        assert "agreement_cut" not in r3  # unweighted round: no weights snapshot
    assert h.agreement_threshold == 0.0  # override never mutates instance

@pytest.mark.parametrize("v", [True, -0.1, 1.5, "0.5", float("nan"), float("inf"), [0.5]])
def test_resolve_invalid(v):
    with pytest.raises(ValueError): c.resolve_agreement_threshold(v)

def test_resolve_valid():
    f = c.resolve_agreement_threshold
    assert f(None) is None and f(0) == 0.0 and f(1) == 1.0 and f(0.7) == 0.7

def test_summary_lists_cut_ids():
    h = c.PeerHealth(disagree_cap=0, agreement_threshold=0.5, agreement_min_votes=2)
    for _ in range(3): h.observe_vote("e1", False)
    assert h.summary(["e0", "e1"])["agreement_cut"] == ["peer1"]
