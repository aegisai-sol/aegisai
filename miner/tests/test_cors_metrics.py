import json, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator
from aegis_miner.ratelimit import RateLimiter

def test_cors_origin_logic():
    assert coordinator.cors_origin("https://x.io", "") == "*"
    assert coordinator.cors_origin(None, "*") == "*"
    spec = "https://a.io, https://b.io/"
    assert coordinator.cors_origin("https://b.io", spec) == "https://b.io"
    assert coordinator.cors_origin("https://evil.io", spec) is None
    assert coordinator.cors_origin(None, spec) is None

def _srv():
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}"

def test_cors_http_allowlist(monkeypatch):
    monkeypatch.setenv("AEGIS_CORS_ORIGINS", "https://ok.io")
    s, base = _srv()
    try:
        r = urllib.request.urlopen(urllib.request.Request(base + "/v1/health", headers={"Origin": "https://ok.io"}))
        assert r.headers["Access-Control-Allow-Origin"] == "https://ok.io"
        r = urllib.request.urlopen(urllib.request.Request(base + "/v1/health", headers={"Origin": "https://bad.io"}))
        assert r.headers["Access-Control-Allow-Origin"] is None
    finally: s.shutdown()

def test_metrics_counts():
    old = coordinator.LIMITER; coordinator.LIMITER = RateLimiter(1, 30)
    s, base = _srv()
    try:
        m0 = json.load(urllib.request.urlopen(base + "/v1/metrics"))
        assert set(m0) == {"verify_count", "fee_preview_count", "rate_limit_hits", "body_rejected"}
        req = lambda: urllib.request.Request(base + "/v1/fee-preview", json.dumps({"fee_micro": 1000}).encode(), {"Content-Type": "application/json"})
        urllib.request.urlopen(req())
        try: urllib.request.urlopen(req())
        except urllib.error.HTTPError as e: assert e.code == 429
        m = json.load(urllib.request.urlopen(base + "/v1/metrics"))
        assert m["fee_preview_count"] == m0["fee_preview_count"] + 1 and m["rate_limit_hits"] == m0["rate_limit_hits"] + 1
    finally: coordinator.LIMITER = old; s.shutdown()
