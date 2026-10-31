from aegis_miner import consensus as c
def node(i, vote, h="h", err=None):
    def f(u, t):
        if err: raise RuntimeError(err)
        return {"node": i, "vote": vote, "source_hash": h}
    f.node_id = i; return f
def test_unweighted_strength():
    r = c.consensus("u", "t", [node("a","TRUE"), node("b","TRUE"), node("c","FALSE")])
    assert r["quorum_strength"] == round(2/3, 6) and r["errored"] == 0
def test_weighted_strength():
    r = c.consensus("u", "t", [node("a","TRUE"), node("b","TRUE"), node("c","FALSE")], weights={"a":1,"b":1,"c":2})
    assert r["quorum_strength"] == 0.5
def test_zero_total_and_errors():
    r = c.consensus("u", "t", [node("a","TRUE"), node("b","TRUE")], weights={"a":0,"b":0})
    assert r["quorum_strength"] == 0.0
    r = c.consensus("u", "t", [node("a",None,err="x"), node("b",None,err="y")])
    assert r["quorum_strength"] == 0.0 and r["errored"] == 2
def test_ping_flags_floor():
    f = c.ping_flags(c.PeerHealth(weight_floor=0.25), env={})
    assert f == {"weighted_quorum": False, "disagree_cap": 4, "weight_floor": 0.25}
