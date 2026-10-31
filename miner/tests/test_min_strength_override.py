import pytest, unittest.mock as m
from aegis_miner import consensus as c, coordinator
from tests.test_quorum_strength import node
def test_resolve():
    r=c.resolve_min_strength
    assert r(None) is None and r(0)==0.0 and r(0.5)==0.5 and r(1)==1.0
    for bad in (True,"0.5",-0.1,1.5,float("nan"),float("inf"),[0.5]):
        with pytest.raises(ValueError): r(bad)
def _run(ms, env=None):
    votes={"peer0":"TRUE","peer1":"FALSE"}
    with m.patch.object(c,"local_node",lambda nid: node(nid,"TRUE")), m.patch.dict("os.environ", env or {}, clear=False):
        return c.consensus_alive("u","t",["e0","e1"],health=c.PeerHealth(),node_factory=lambda n,e: node(n,votes[n]),
                                 min_strength=ms,tracker=c.StrengthTracker())
def test_request_overrides_env():
    r=_run(0.0, {"AEGIS_MIN_STRENGTH":"0.9"})
    assert r["status"]!="NO_CONSENSUS" or r.get("reason")!="low_strength"
    assert r["min_strength_applied"]=={"value":0.0,"source":"request"}
def test_env_source():
    r=_run(None, {"AEGIS_MIN_STRENGTH":"0.9"})
    assert r["min_strength_applied"]=={"value":0.9,"source":"env"} and r["reason"]=="low_strength"
def test_agreement_rates():
    h=c.PeerHealth(); h.observe_vote("a",True); h.observe_vote("a",False); h.observe_vote("a",True)
    r=h.agreement_rates(["a","b"])
    assert r["peer0"]=={"agreed":2,"votes":3,"rate":round(2/3,6)} and r["peer1"]=={"agreed":0,"votes":0,"rate":None}
def test_health_peer_agreement_ids_only(monkeypatch):
    monkeypatch.setenv("AEGIS_PEERS","http://x:1,http://y:2")
    a=coordinator.health()["peer_agreement"]
    assert set(a)=={"peer0","peer1"} and "http" not in str(a)
