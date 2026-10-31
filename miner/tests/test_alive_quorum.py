import json
from aegis_miner import consensus as c

def fake(results):
    def factory(nid, ep):
        def run(url, claim):
            r = results[ep]
            if isinstance(r, Exception): raise r
            return dict(r, node=nid)
        run.node_id = nid; return run
    return factory

GOOD = {"vote": "TRUE", "source_hash": "h1"}

def _patch_local(monkeypatch):
    monkeypatch.setattr(c, "local_node", lambda nid, **k: (lambda u, cl: dict(GOOD, node=nid)))

def test_only_alive_peers_used(monkeypatch):
    _patch_local(monkeypatch)
    eps = ["http://a:1", "http://b:1", "http://c:1"]; h = c.PeerHealth(1, 1); h.observe(eps[1], False)
    called = []
    def factory(nid, ep):
        called.append(ep); return fake({e: GOOD for e in eps})(nid, ep)
    rec = c.consensus_alive("https://x", "y", eps, health=h, node_factory=factory)
    assert called == [eps[0], eps[2]] and rec["nodes"] == 3 and rec["status"] == "VALID"
    assert rec["peer_selection"]["skipped"] == ["peer1"] and "http" not in json.dumps(rec["peer_selection"])

def test_too_few_alive_no_consensus(monkeypatch):
    _patch_local(monkeypatch)
    eps = ["http://a:1", "http://b:1"]; h = c.PeerHealth(1, 1)
    for e in eps: h.observe(e, False)
    rec = c.consensus_alive("https://x", "y", eps, health=h, node_factory=fake({}))
    assert rec["status"] == "NO_CONSENSUS" and rec["reason"] == "insufficient_alive_peers" and not rec["valid"]

def test_no_peers_local_demo_unchanged(monkeypatch):
    _patch_local(monkeypatch)
    rec = c.consensus_alive("https://x", "y", ["", " "], health=c.PeerHealth())
    assert rec["peer_selection"]["mode"] == "local_demo" and rec["nodes"] == 2 and rec["valid"]

def test_passive_health_marks_erroring_peer_dead(monkeypatch):
    _patch_local(monkeypatch)
    eps = ["http://a:1", "http://bad:1"]; h = c.PeerHealth(1, 1)
    rec = c.consensus_alive("https://x", "y", eps, health=h, node_factory=fake({eps[0]: GOOD, eps[1]: ConnectionError()}))
    assert rec["valid"] and h.is_alive(eps[0]) and not h.is_alive(eps[1])
    rec2 = c.consensus_alive("https://x", "y", eps, health=h, node_factory=fake({eps[0]: GOOD}))
    assert rec2["peer_selection"]["skipped"] == ["peer1"] and rec2["nodes"] == 2
