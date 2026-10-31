from aegis_miner import consensus as c, coordinator
from tests.test_quorum_strength import node
def three(): return [node("a","TRUE"), node("b","TRUE"), node("c","FALSE")]
def test_downgrade_below_threshold():
    r = c.consensus("u","t",three(), min_strength=0.7)
    assert r["status"]=="NO_CONSENSUS" and not r["valid"] and r["reason"]=="low_strength"
    assert r["downgraded_from"]=="VALID" and r["consensus_vote"] is None
    assert r["receipt_digest"] != c.consensus("u","t",three())["receipt_digest"]
def test_no_downgrade_at_or_above():
    assert c.consensus("u","t",three(), min_strength=round(2/3,6))["status"]=="VALID"
    assert c.consensus("u","t",three(), min_strength=0)["status"]=="VALID"
def test_env_parse():
    f=c.env_min_strength
    assert f({})==0.0 and f({"AEGIS_MIN_STRENGTH":"0.6"})==0.6 and f({"AEGIS_MIN_STRENGTH":"x"})==0.0
    assert f({"AEGIS_MIN_STRENGTH":"-1"})==0.0 and f({"AEGIS_MIN_STRENGTH":"5"})==1.0 and f({"AEGIS_MIN_STRENGTH":"nan"})==0.0
def test_tracker_rolling():
    t=c.StrengthTracker(window=2)
    assert t.summary()["latest"] is None
    for v in (1.0,0.5,0.0): t.record(v)
    s=t.summary(); assert s["latest"]==0.0 and s["avg"]==0.25 and s["samples"]==2 and s["rounds"]==3 and s["min"]==0.0
def test_window_env():
    w=c._env_window
    assert w({})==20 and w({"AEGIS_STRENGTH_WINDOW":"5"})==5 and w({"AEGIS_STRENGTH_WINDOW":"0"})==20
    assert w({"AEGIS_STRENGTH_WINDOW":"9999"})==1000 and w({"AEGIS_STRENGTH_WINDOW":"z"})==20
def test_alive_records_and_counts_downgrade():
    t=c.StrengthTracker(); h=c.PeerHealth()
    votes={"peer0":"TRUE","peer1":"FALSE"}
    fac=lambda nid,e: node(nid, votes[nid])
    import unittest.mock as m
    with m.patch.object(c,"local_node",lambda nid: node(nid,"TRUE")):
        r=c.consensus_alive("u","t",["e0","e1"],health=h,node_factory=fac,min_strength=0.9,tracker=t)
    assert r["reason"]=="low_strength" and t.summary()["downgraded"]==1 and t.summary()["samples"]==1
def test_health_exposes_strength():
    q=coordinator.health()["quorum_strength"]
    assert set(q)>={"latest","avg","samples","window","downgraded","min_strength"}
    assert "http" not in str(q)
