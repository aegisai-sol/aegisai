import pytest, unittest.mock as m
from aegis_miner import consensus as c, coordinator as co
from tests.test_quorum_strength import node

@pytest.mark.parametrize("raw,want", [(None, 2), ("", 2), ("3", 3), (" 4 ", 4), ("1", 2), ("0", 2), ("-3", 2),
                                      ("x", 2), ("2.5", 2), ("99", 16), ("16", 16)])
def test_env_quorum(raw, want):
    env = {} if raw is None else {"AEGIS_QUORUM": raw}
    assert c.env_quorum(env) == want

def test_resolve_quorum_valid_and_tighten_only():
    f = c.resolve_quorum
    assert f(None, env={}) is None and f(2, env={}) == 2 and f(5, env={}) == 5 and f(16, env={}) == 16
    assert f(3, env={"AEGIS_QUORUM": "3"}) == 3
    with pytest.raises(ValueError, match="below"): f(2, env={"AEGIS_QUORUM": "3"})  # request may only tighten

@pytest.mark.parametrize("v", [True, False, 1, 0, -2, 17, 2.0, 2.5, "3", [3], float("nan")])
def test_resolve_quorum_invalid(v):
    with pytest.raises(ValueError): c.resolve_quorum(v, env={})

def _run(**kw):
    h = c.PeerHealth()
    fac = lambda nid, e: node(nid, "TRUE")
    with m.patch.object(c, "local_node", lambda nid: node(nid, "TRUE")):
        return c.consensus_alive("u", "t", ["e0", "e1"], health=h, node_factory=fac, **kw)

def test_consensus_alive_records_quorum_applied():
    with m.patch.dict("os.environ", {"AEGIS_QUORUM": "2"}):
        r = _run()  # self + 2 peers = 3 nodes, env quorum 2
        assert r["quorum"] == 2 and r["valid"] and r["quorum_applied"] == {"value": 2, "source": "env"}
        r = _run(quorum=3)
        assert r["quorum"] == 3 and r["valid"] and r["quorum_applied"] == {"value": 3, "source": "request"}
        r = _run(quorum=4)  # only 3 nodes -> graceful NO_CONSENSUS, still audited
        assert r["status"] == "NO_CONSENSUS" and r["reason"] == "insufficient_alive_peers"
        assert r["quorum_applied"] == {"value": 4, "source": "request"}
    with m.patch.dict("os.environ", {"AEGIS_QUORUM": "3"}):
        r = _run()
        assert r["quorum"] == 3 and r["quorum_applied"] == {"value": 3, "source": "env"}

def test_health_reports_env_quorum():
    with m.patch.dict("os.environ", {"AEGIS_QUORUM": "3"}):
        assert co.health()["quorum"] == 3
    with m.patch.dict("os.environ", {"AEGIS_QUORUM": "junk"}):
        assert co.health()["quorum"] == 2
