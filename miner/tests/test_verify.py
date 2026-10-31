import json, os, threading, urllib.request
from aegis_miner import verify, credits

def test_arith():
    assert verify.check_claim({"text": "2 + 2 = 5"})["vote"] == "FALSE"
    r = verify.check_claim({"text": "10 * 3 = 30"}); assert r["vote"] == "TRUE" and r["method"] == "arithmetic"

def test_split_and_url_quote():
    cs = verify.decompose('The sky is blue. Docs say "Solana uses proof of history" https://solana.com/docs. 2 + 2 = 4')
    assert len(cs) == 3
    assert cs[1]["url"] == "https://solana.com/docs" and cs[1]["quote"] == "Solana uses proof of history"

def test_source_votes():
    c = {"text": "x", "url": "http://e", "quote": "Hello  World"}
    assert verify.check_claim(c, fetcher=lambda u: "say hello world now")["vote"] == "TRUE"
    r = verify.check_claim(c, fetcher=lambda u: "nothing here"); assert r["vote"] == "FALSE" and len(r["source_hash"]) == 64
    def boom(u): raise OSError("down")
    assert verify.check_claim(c, fetcher=boom)["vote"] == "UNSURE"

def test_credits(tmp_path):
    p = str(tmp_path / "c.jsonl")
    n = credits.award(p, "a", "r1", [{"vote": "TRUE", "confidence": .99}, {"vote": "UNSURE", "confidence": .9}, {"vote": "TRUE", "confidence": .65}])
    assert n == 1 and credits.balance(p, "a") == 1 and credits.balance(p, "b") == 0

def test_coordinator_roundtrip(tmp_path, monkeypatch):
    from aegis_miner import coordinator as co
    from http.server import ThreadingHTTPServer
    monkeypatch.setattr(co, "RECEIPTS", str(tmp_path / "r")); monkeypatch.setattr(co, "CREDITS", str(tmp_path / "c.jsonl"))
    s = ThreadingHTTPServer(("127.0.0.1", 0), co.H); threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_port}"
    r = json.load(urllib.request.urlopen(urllib.request.Request(base + "/v1/verify", json.dumps({"text": "2 + 2 = 4. 3 * 3 = 10", "client_id": "t"}).encode(), {"Content-Type": "application/json"})))
    assert r["credits_awarded"] == 2
    assert json.load(urllib.request.urlopen(base + "/v1/receipts/" + r["receipt_id"]))["receipt_id"] == r["receipt_id"]
    assert json.load(urllib.request.urlopen(base + "/v1/credits/t"))["credits"] == 2
    assert "price" in json.load(urllib.request.urlopen(base + "/api/stats"))
    s.shutdown()


def test_list_split_and_url_dots():
    cs = verify.decompose("1. 2 + 2 = 4\n2) Paris is in France.\n- See https://example.com/a.b for more. Next line")
    assert [c["text"] for c in cs][:2] == ["2 + 2 = 4", "Paris is in France."]
    assert cs[2]["url"] == "https://example.com/a.b" and len(cs) == 4

def test_url_only():
    r = verify.check_claim({"text": "see", "url": "http://e"}, page_fetcher=lambda u: ("Example Domain", "body"))
    assert r["vote"] == "UNSURE" and r["note"] == "no quote to match" and r["page_title"] == "Example Domain" and len(r["source_hash"]) == 64
    def boom(u): raise OSError("dns")
    assert verify.check_claim({"text": "see", "url": "http://e"}, page_fetcher=boom)["vote"] == "FALSE"

def test_canary():
    c = verify.make_canary("x"); c.update(verify.check_claim(c))
    assert c["vote"] == "TRUE" and verify.canary_ok([c])[0]
    assert not verify.canary_ok([c], {c["claim_id"]: "FALSE"})[0]
