import json, threading, urllib.request
from http.server import ThreadingHTTPServer
from aegis_miner import coordinator, reservoir

def test_fee_preview_func_matches_reservoir():
    r = coordinator.fee_preview({"fee_micro": 1000001, "votes": {"a": 1, "b": 2}}, reservoir)
    assert r["parts"] == reservoir.split_fee(1000001, {"a": 1, "b": 2})["parts"]
    assert sum(r["parts"].values()) == 1000001

def test_fee_preview_from_consensus_and_flagged():
    c = {"valid": True, "consensus_vote": "supported", "per_node": [{"node": "x", "vote": "supported"}, {"node": "y", "vote": "contradicted"}]}
    r = coordinator.fee_preview({"consensus": c}, reservoir)
    assert list(r["payouts"]) == ["x"]
    f = coordinator.fee_preview({"consensus": c, "flagged": True}, reservoir)
    assert f["payouts"] == {} and f["parts"]["reservoir"] == 900000

def test_fee_preview_http_and_bad_input():
    s = ThreadingHTTPServer(("127.0.0.1", 0), coordinator.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    u = f"http://127.0.0.1:{s.server_port}/v1/fee-preview"
    def post(body):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, json.dumps(body).encode(), {"Content-Type": "application/json"})))
        except urllib.error.HTTPError as e: return e.code
    r = post({"fee_micro": 1000000, "votes": {"n1": 1}})
    assert r["source"] == "coordinator" and r["parts"]["miners"] == 700000
    assert post({"fee_micro": -5}) == 400
    s.shutdown()
