import json, os, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator as co

def test_receipt_pagination(tmp_path, monkeypatch):
    monkeypatch.setattr(co, "RECEIPTS", str(tmp_path))
    for i in range(5):
        p = tmp_path / f"r{i}.json"; p.write_text(json.dumps({"status": "VALID"})); os.utime(p, (1000 + i, 1000 + i))
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_port}/v1/receipts"
    try:
        a = json.load(urllib.request.urlopen(base + "?limit=2"))
        assert a["total"] == 5 and [x["receipt_id"] for x in a["items"]] == ["r4", "r3"] and a["next_offset"] == 2
        b = json.load(urllib.request.urlopen(base + "?limit=2&offset=4"))
        assert [x["receipt_id"] for x in b["items"]] == ["r0"] and b["next_offset"] is None
        assert json.load(urllib.request.urlopen(base))["limit"] == 20
        for bad in ("?limit=0", "?limit=101", "?offset=-1", "?limit=x"):
            try: urllib.request.urlopen(base + bad); assert False, bad
            except urllib.error.HTTPError as e: assert e.code == 400
    finally: s.shutdown()
