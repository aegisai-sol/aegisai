import pytest
from aegis_miner import consensus as c, coordinator as co

def test_decay_formula_and_reset():
    h = c.PeerHealth()
    for _ in range(10): h.observe("a", True)
    assert h.weight("a") == 2.0
    h.observe_vote("a", False); assert h.weight("a") == 1.0
    h.observe_vote("a", False); assert h.weight("a") == 0.5
    for _ in range(10): h.observe_vote("a", False)
    assert h.weight("a") == pytest.approx(2.0 / 16) and h.weight("a") > 0
    h.observe_vote("a", True); assert h.weight("a") == 2.0

def test_consensus_alive_tracks_dissent():
    h = c.PeerHealth()
    def fac(nid, e):
        def run(url, claim): return {"node": nid, "vote": "FALSE" if e == "bad" else "TRUE", "source_hash": "x"}
        run.node_id = nid; return run
    import aegis_miner.consensus as m
    orig = m.local_node
    m.local_node = lambda nid, **k: fac(nid, "good")
    try:
        for _ in range(3): rec = c.consensus_alive("https://e", "c", ["good", "bad"], health=h, node_factory=fac)
    finally: m.local_node = orig
    assert rec["consensus_vote"] == "TRUE"
    s = h.summary(["good", "bad"])
    assert s["disagree_streaks"] == {"peer0": 0, "peer1": 3} and s["weights"]["peer1"] < 1.0
    assert "bad" not in str(s)

def test_health_weighting(monkeypatch):
    monkeypatch.setenv("AEGIS_WEIGHTED_QUORUM", "1")
    monkeypatch.setattr(c.PEER_HEALTH, "half_life", 0.0)
    assert co.health()["weighting"] == {"weighted_quorum": True}
    monkeypatch.setattr(c.PEER_HEALTH, "half_life", 60.0)
    monkeypatch.delenv("AEGIS_WEIGHTED_QUORUM")
    assert co.health()["weighting"] == {"weighted_quorum": False, "half_life": 60.0}
