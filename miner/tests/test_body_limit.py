import json, socket, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator

def test_max_body_env():
    assert coordinator.max_body({}) == 262144
    assert coordinator.max_body({"AEGIS_MAX_BODY": "abc"}) == 262144
    assert coordinator.max_body({"AEGIS_MAX_BODY": "10"}) == 1024
    assert coordinator.max_body({"AEGIS_MAX_BODY": str(10**9)}) == 4194304
    assert coordinator.max_body({"AEGIS_MAX_BODY": " 5000 "}) == 5000

def test_body_check_logic():
    assert coordinator.body_check(None, 100) is None
    assert coordinator.body_check("", 100) is None
    assert coordinator.body_check("100", 100) is None
    assert coordinator.body_check("101", 100)[0] == 413
    assert coordinator.body_check("-5", 100)[0] == 400
    assert coordinator.body_check("1e3", 100)[0] == 400

def _srv():
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}"

def _raw(port, cl):
    c = socket.create_connection(("127.0.0.1", port), timeout=5)
    c.sendall(f"POST /v1/fee-preview HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: {cl}\r\n\r\n".encode())
    data = b""
    while True:
        chunk = c.recv(4096)
        if not chunk: break
        data += chunk
    c.close(); return data.decode(errors="replace")

def test_http_413_and_400_without_reading_body(monkeypatch):
    monkeypatch.setenv("AEGIS_MAX_BODY", "2048")
    s, base = _srv()
    try:
        before = coordinator.METRICS["body_rejected"]; hits = coordinator.METRICS["rate_limit_hits"]
        r = _raw(s.server_port, 10**9)  # claims 1 GB, sends nothing: must answer immediately, not hang
        assert " 413 " in r.split("\r\n")[0] and '"max_body": 2048' in r
        r = _raw(s.server_port, "-1")
        assert " 400 " in r.split("\r\n")[0]
        assert coordinator.METRICS["body_rejected"] == before + 2
        assert coordinator.METRICS["rate_limit_hits"] == hits  # rejected before limiter
        ok = urllib.request.urlopen(urllib.request.Request(base + "/v1/fee-preview", json.dumps({"fee_micro": 1000}).encode(), {"Content-Type": "application/json"}))
        assert ok.status == 200
        assert json.load(urllib.request.urlopen(base + "/v1/health"))["max_body"] == 2048
        spec = json.load(urllib.request.urlopen(base + "/v1/openapi.json"))
        assert "413" in spec["paths"]["/v1/verify"]["post"]["responses"]
        assert "413" not in spec["paths"]["/v1/health"]["get"]["responses"]
    finally: s.shutdown()
