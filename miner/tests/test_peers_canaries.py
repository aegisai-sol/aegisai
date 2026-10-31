import json, threading, urllib.request
from http.server import ThreadingHTTPServer
from aegis_miner import consensus as c, verify as v, coordinator as co

def fake(e, timeout):
    if "dead" in e: raise TimeoutError()
    if "sick" in e: return {"ok": False}
    return {"ok": True}

def test_ping_peers_fake():
    c._LAST_OK.clear()
    r = c.ping_peers(["http://up:1", "http://dead:1", "http://sick:1"], getter=fake, now=lambda: 1000.0)
    assert [x["ok"] for x in r] == [True, False, False]
    assert r[0]["last_ok"] == 1000.0 and r[1]["error"] == "TimeoutError" and r[2]["error"] == "unhealthy"
    assert "up" not in json.dumps(r) and "dead" not in json.dumps(r)
    assert c.peer_liveness(["http://up:1", "http://dead:1"], now=lambda: 1100.0)["live"] == 1
    assert c.peer_liveness(["http://up:1"], now=lambda: 2000.0)["live"] == 0  # stale

def test_peers_ping_endpoint(monkeypatch):
    monkeypatch.setenv("AEGIS_PEERS", "http://127.0.0.1:1")  # closed port -> fails fast
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        r = json.load(urllib.request.urlopen(f"http://127.0.0.1:{s.server_port}/v1/peers/ping"))
        assert r["peers"][0]["id"] == "peer0" and not r["peers"][0]["ok"] and "127.0.0.1:1" not in json.dumps(r)
    finally: s.shutdown()

def test_canaries_v2_answers():
    for t, exp in v.CANARY_POOL_V2: assert v.check_claim({"text": t})["vote"] == exp, t

def test_yes_miner_caught():
    cs = [dict(x, **v.check_claim(x)) for x in v.make_canaries("r1", 2)]
    assert any(x["expected"] == "FALSE" for x in cs) and v.canary_ok(cs)[0]
    assert not v.canary_ok(cs, {x["claim_id"]: "TRUE" for x in cs})[0]
