import json, os, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator as co

def _seed(tmp_path):
    rows = [("a", {"status": "VALID"}, 1000), ("b", {"verdict": "invalid"}, 1001), ("c", {"status": "VALID"}, 1002),
            ("d", {"status": "UNSURE"}, 1003), ("e", {"status": "VALID"}, 1004)]
    for rid, body, t in rows:
        p = tmp_path / f"{rid}.json"; p.write_text(json.dumps(body)); os.utime(p, (t, t))
    (tmp_path / "f.json").write_text("[1,2]"); os.utime(tmp_path / "f.json", (999, 999))

def test_filters_direct(tmp_path, monkeypatch):
    monkeypatch.setattr(co, "RECEIPTS", str(tmp_path)); _seed(tmp_path)
    r = co.list_receipts(2, 0, status="valid")
    assert r["total"] == 3 and [x["receipt_id"] for x in r["items"]] == ["e", "c"] and r["next_offset"] == 2
    assert r["filters"] == {"status": "VALID"}
    assert [x["receipt_id"] for x in co.list_receipts(2, 2, status="VALID")["items"]] == ["a"]
    assert [x["receipt_id"] for x in co.list_receipts(20, 0, status="INVALID")["items"]] == ["b"]
    s = co.list_receipts(20, 0, since=1003)
    assert s["total"] == 2 and [x["receipt_id"] for x in s["items"]] == ["e", "d"] and s["filters"] == {"since": 1003}
    both = co.list_receipts(20, 0, status="VALID", since=1002)
    assert [x["receipt_id"] for x in both["items"]] == ["e", "c"]
    assert "filters" not in co.list_receipts() and co.list_receipts()["total"] == 6
    assert co.list_receipts(20, 0, status="NOPE")["total"] == 0

def test_filters_http(tmp_path, monkeypatch):
    monkeypatch.setattr(co, "RECEIPTS", str(tmp_path)); _seed(tmp_path)
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_port}/v1/receipts"
    try:
        a = json.load(urllib.request.urlopen(base + "?status=VALID&since=1001&limit=1"))
        assert a["total"] == 2 and a["items"][0]["receipt_id"] == "e" and a["next_offset"] == 1
        for bad in ("?status=", "?status=a-b", "?status=" + "x" * 33, "?since=-1", "?since=1.5", "?since=abc"):
            try: urllib.request.urlopen(base + bad); assert False, bad
            except urllib.error.HTTPError as e: assert e.code == 400, bad
        assert "status" in json.load(urllib.request.urlopen(base.replace("/receipts", "/openapi.json")))["paths"]["/v1/receipts"]["get"]["summary"]
    finally: s.shutdown()
