import json, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator
from aegis_miner.ratelimit import RateLimiter

class Clock:
    t = 100.0
    def __call__(self): return self.t

def test_limiter_fake_clock_per_ip():
    c = Clock(); r = RateLimiter.from_env("2/10", clock=c)
    assert r.check("1.1.1.1") == (True, 0) and r.check("1.1.1.1") == (True, 0)
    ok, ra = r.check("1.1.1.1"); assert not ok and ra == 10
    assert r.check("2.2.2.2")[0]  # other IP unaffected
    c.t += 4; assert r.check("1.1.1.1") == (False, 6)
    c.t += 6; assert r.check("1.1.1.1") == (True, 0)

def test_limiter_off_by_default():
    r = RateLimiter.from_env("")
    assert all(r.check("x")[0] for _ in range(1000))

def test_http_429_retry_after_and_openapi():
    old = coordinator.LIMITER; coordinator.LIMITER = RateLimiter(1, 30, clock=Clock())
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_port}"
    try:
        req = lambda: urllib.request.Request(base + "/v1/fee-preview", json.dumps({"fee_micro": 1000}).encode(), {"Content-Type": "application/json"})
        assert urllib.request.urlopen(req()).status == 200
        try: urllib.request.urlopen(req()); assert False
        except urllib.error.HTTPError as e:
            assert e.code == 429 and e.headers["Retry-After"] == "30"
        spec = json.load(urllib.request.urlopen(base + "/v1/openapi.json"))
        assert spec["openapi"].startswith("3.") and "429" in spec["paths"]["/v1/verify"]["post"]["responses"]
        assert urllib.request.urlopen(base + "/v1/health").status == 200  # GET not limited
    finally:
        coordinator.LIMITER = old; s.shutdown()
