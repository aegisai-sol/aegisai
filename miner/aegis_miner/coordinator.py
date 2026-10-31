"""Mock coordinator API (stdlib). GET /api/stats, POST /api/vote, GET /api/votes. CORS open for local dev.
Run: python3 -m aegis_miner.coordinator [port=8787]. Replace with a real service + Solana indexer later."""
import json, os, random, sys, time, uuid
from aegis_miner import verify, credits
DATA = os.environ.get("AEGIS_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
RECEIPTS, CREDITS = os.path.join(DATA, "receipts"), os.path.join(DATA, "credits.jsonl")
RESERVOIR_NOTE = "Proof Credits are non-transferable; AGIS conversion only vs paid fees, capped <=70% fees / <=0.5% Reservoir per period. No mint yet (Option A)."
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
VOTES, NODES = [], {}
PRICE = [0.00042]
for _ in range(47): PRICE.append(round(PRICE[-1] * (1 + random.uniform(-.03, .032)), 6))
class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code)
        for k, v in (("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Headers", "Content-Type")): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self): self._send(204, {})
    def do_GET(self):
        if self.path == "/api/stats":
            now = time.time(); PRICE.append(round(PRICE[-1] * (1 + random.uniform(-.02, .021)), 6)); PRICE.pop(0)
            hour = [v for v in VOTES if now - v["_t"] < 3600]
            self._send(200, {"mock": True, "price": PRICE[-1], "priceHistory": PRICE, "holders": 1287 + len(NODES),
                             "txCount": 48211 + len(VOTES), "activeNodes": len([n for n, t in NODES.items() if now - t < 300]),
                             "votesPerHour": [random.randint(900, 1600) for _ in range(23)] + [len(hour)],
                             "recentVotes": [{k: v for k, v in x.items() if k != "_t"} for x in VOTES[-20:]]})
        elif self.path.startswith("/v1/receipts/"):
            rid = os.path.basename(self.path); f = os.path.join(RECEIPTS, rid + ".json")
            if rid.isalnum() and os.path.exists(f): self._send(200, json.load(open(f)))
            else: self._send(404, {"error": "receipt not found"})
        elif self.path.startswith("/v1/credits/"):
            cid = self.path.split("/v1/credits/", 1)[1]
            self._send(200, {"client_id": cid, "credits": credits.balance(CREDITS, cid)})
        elif self.path == "/api/votes": self._send(200, VOTES[-100:])
        else: self._send(404, {"error": "not found"})
    def do_POST(self):
        if self.path == "/v1/verify": return self._verify()
        if self.path != "/api/vote": return self._send(404, {"error": "not found"})
        try: v = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception: return self._send(400, {"error": "bad json"})
        v["_t"] = time.time(); VOTES.append(v); del VOTES[:-5000]; NODES[v.get("node_id", "?")] = v["_t"]
        self._send(200, {"ok": True, "accepted": v.get("digest")})
    def _verify(self):
        try: body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except Exception: return self._send(400, {"error": "bad json"})
        text = (body.get("text") or "").strip()
        if not text or len(text) > 20000: return self._send(400, {"error": "text required (<=20000 chars)"})
        cid = str(body.get("client_id") or "anon")[:64]
        rid = uuid.uuid4().hex[:16]
        claims = [dict(c, **verify.check_claim(c)) for c in verify.decompose(text)[:50]]
        can = verify.make_canary(rid); claims.append(dict(can, **verify.check_claim(can)))
        ok, bad = verify.canary_ok(claims, body.get("client_votes"))
        n = credits.award(CREDITS, cid, rid, [c for c in claims if not c.get("canary")]) if ok else 0
        rec = {"receipt_id": rid, "client_id": cid, "ts": time.time(), "claims": claims,
               "credits_awarded": n, "calibration": {"ok": ok, "failed": bad},
               "flagged": not ok, "reservoir_note": RESERVOIR_NOTE, "onchain": "PENDING (devnet memo later)"}
        os.makedirs(RECEIPTS, exist_ok=True); json.dump(rec, open(os.path.join(RECEIPTS, rid + ".json"), "w"))
        self._send(200, rec)
    def log_message(self, *a): pass
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"AegisAI mock coordinator on http://localhost:{port}"); ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
