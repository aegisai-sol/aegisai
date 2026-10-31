import json, threading, urllib.request
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator as co

def test_health(monkeypatch):
    monkeypatch.setenv("AEGIS_PEERS", "http://p1:8787,http://p2:8787,"); monkeypatch.delenv("AEGIS_ALLOW_HTTP", raising=False)
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        h = json.load(urllib.request.urlopen(f"http://127.0.0.1:{s.server_port}/v1/health"))
        assert h["ok"] and h["peers"] == 2 and h["citation_policy"] == "https-only" and h["anchor"] == "off"
        assert "p1" not in json.dumps(h)
    finally: s.shutdown()
