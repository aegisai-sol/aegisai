import json, threading, urllib.request, pytest
from http.server import ThreadingHTTPServer
from aegis_miner import consensus as c, coordinator as co

def test_dead_only_after_n_consecutive_fails():
    h = c.PeerHealth(3, 2)
    assert h.observe("a", False) and h.observe("a", False)
    assert h.observe("a", True)            # ok resets fail streak
    assert h.observe("a", False) and h.observe("a", False)
    assert h.observe("a", False) is False  # 3rd consecutive -> dead

def test_recover_after_m_oks_and_fail_resets_recovery():
    h = c.PeerHealth(1, 3)
    assert h.observe("a", False) is False
    h.observe("a", True); h.observe("a", True); assert not h.is_alive("a")
    h.observe("a", False); h.observe("a", True); h.observe("a", True); assert not h.is_alive("a")
    assert h.observe("a", True) is True

def test_fake_peers_ping_flapping_and_summary_no_urls():
    eps = ["http://good:1", "http://flaky:1", "http://down:1"]; tick = {"n": 0}
    def getter(e, t):
        if "down" in e: raise ConnectionError()
        if "flaky" in e and tick["n"] % 2: raise TimeoutError()
        return {"ok": True}
    h = c.PeerHealth(2, 2)
    for i in range(4):
        tick["n"] = i; res = h.observe_pings(eps, c.ping_peers(eps, getter=getter))
    assert [r["alive"] for r in res] == [True, True, False]
    s = h.summary(eps); assert s["alive"] == 2 and s["dead"] == 1
    assert h.alive_endpoints(eps) == eps[:2]
    assert "http" not in json.dumps(s) and "good" not in json.dumps(res)

def test_bad_thresholds():
    with pytest.raises(ValueError): c.PeerHealth(0, 1)

def test_protocol_version_in_health_and_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(co, "RECEIPTS", str(tmp_path)); monkeypatch.setenv("AEGIS_PEERS", "")
    monkeypatch.setattr(co.verify, "check_claim", lambda cl: {"verdict": "UNVERIFIED"})
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{s.server_port}"
        h = json.load(urllib.request.urlopen(base + "/v1/health"))
        assert h["protocol_version"] == "pov-r/1" and h["peer_health"]["known"] == 0
        r = urllib.request.Request(base + "/v1/verify", json.dumps({"text": "Python was released in 1991."}).encode(), {"Content-Type": "application/json"})
        rec = json.load(urllib.request.urlopen(r))
        assert rec["protocol_version"] == "pov-r/1" and rec["claim_schema"] == 1
        body = {k: v for k, v in rec.items() if k not in ("digest", "mac", "onchain")}
    finally: s.shutdown()
