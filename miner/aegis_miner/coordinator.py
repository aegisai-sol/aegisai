"""Mock coordinator API (stdlib). GET /api/stats, POST /api/vote, GET /api/votes. CORS open for local dev.
Run: python3 -m aegis_miner.coordinator [port=8787]. Replace with a real service + Solana indexer later."""
import json, os, random, sys, time, uuid
from aegis_miner import verify, credits, token_bridge
DATA = os.environ.get("AEGIS_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
RECEIPTS, CREDITS = os.path.join(DATA, "receipts"), os.path.join(DATA, "credits.jsonl")
RESERVOIR_NOTE = "Proof Credits are non-transferable; AGIS conversion only vs paid fees, capped <=70% fees / <=0.5% Reservoir per period. No mint yet (Option A)."
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
VOTES, NODES = [], {}
PRICE = [0.00042]
for _ in range(47): PRICE.append(round(PRICE[-1] * (1 + random.uniform(-.03, .032)), 6))
def fee_preview(b, reservoir):
    fee = int(b.get("fee_micro", 1000000))
    if not 0 <= fee <= 10**15: raise ValueError("fee_micro out of range")
    votes = b.get("votes")
    c = b.get("consensus")
    if votes is None and c:
        votes = {n["node"]: 1 for n in c.get("per_node", []) if c.get("valid") and n.get("vote") == c.get("consensus_vote")}
    votes = {str(k): int(v) for k, v in (votes or {}).items()}
    r = reservoir.split_fee(fee, votes, bool(b.get("flagged")))
    r.update(split_bps=reservoir.SPLIT_BPS, source="coordinator", note="Off-chain preview only; no token minted, no payouts live.")
    return r
START = time.time()
def health():
    """Liveness + config summary. Never exposes peer URLs or keys, only counts."""
    peers = [p for p in os.environ.get("AEGIS_PEERS", "").split(",") if p.strip()]
    return {"ok": True, "uptime_s": int(time.time() - START), "peers": len(peers), "quorum": 2,
            "citation_policy": "https-only" if os.environ.get("AEGIS_ALLOW_HTTP") != "1" else "http-allowed(dev)",
            "max_redirects": verify.MAX_REDIRECTS, "anchor": "devnet" if os.environ.get("AEGIS_ANCHOR_RECEIPTS") == "1" else "off",
            "token_mode": token_bridge.state_from_env().mode}
def list_receipts(limit=20, offset=0):
    """Newest-first page of receipt summaries (id, mtime, status). No bodies, so pages stay small."""
    ids = sorted((f for f in (os.listdir(RECEIPTS) if os.path.isdir(RECEIPTS) else []) if f.endswith(".json")),
                 key=lambda f: (-os.path.getmtime(os.path.join(RECEIPTS, f)), f))
    items = []
    for f in ids[offset:offset + limit]:
        try: r = json.load(open(os.path.join(RECEIPTS, f)))
        except Exception: r = {}
        items.append({"receipt_id": f[:-5], "status": r.get("status") or r.get("verdict"), "mtime": int(os.path.getmtime(os.path.join(RECEIPTS, f)))})
    nxt = offset + limit if offset + limit < len(ids) else None
    return {"total": len(ids), "limit": limit, "offset": offset, "next_offset": nxt, "items": items}
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
        elif self.path == "/v1/receipts" or self.path.startswith("/v1/receipts?"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            try: limit, offset = int(q.get("limit", ["20"])[0]), int(q.get("offset", ["0"])[0])
            except ValueError: return self._send(400, {"error": "limit/offset must be integers"})
            if not (1 <= limit <= 100 and offset >= 0): return self._send(400, {"error": "limit 1..100, offset >= 0"})
            self._send(200, list_receipts(limit, offset))
        elif self.path.startswith("/v1/receipts/"):
            rid = os.path.basename(self.path); f = os.path.join(RECEIPTS, rid + ".json")
            if rid.isalnum() and os.path.exists(f): self._send(200, json.load(open(f)))
            else: self._send(404, {"error": "receipt not found"})
        elif self.path.startswith("/v1/credits/"):
            cid = self.path.split("/v1/credits/", 1)[1]
            self._send(200, {"client_id": cid, "credits": credits.balance(CREDITS, cid)})
        elif self.path.startswith("/v1/claim-quote/"):
            cid = self.path.split("/v1/claim-quote/", 1)[1]
            tot = sum(e["credits"] for e in map(json.loads, open(CREDITS))) if os.path.exists(CREDITS) else 0
            self._send(200, token_bridge.claim_quote(CREDITS, cid, tot, token_bridge.state_from_env()))
        elif self.path == "/v1/token-state":
            st = token_bridge.state_from_env(); self._send(200, {"mode": st.mode, "mint": st.mint()})
        elif self.path == "/v1/health": self._send(200, health())
        elif self.path == "/api/votes": self._send(200, VOTES[-100:])
        else: self._send(404, {"error": "not found"})
    def do_POST(self):
        if self.path == "/v1/verify": return self._verify()
        if self.path == "/v1/fee-preview": return self._fee_preview()
        if self.path in ("/v1/fetch-check", "/v1/consensus"):
            from . import verify as _v, consensus as _c
            try: b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))); url, claim = b["url"], b.get("claim", "")
            except Exception: return self._send(400, {"error": "need {url, claim}"})
            try:
                if self.path == "/v1/fetch-check": return self._send(200, _v.check_url_only(url, claim_text=claim))
                peers = [_c.http_node(f"peer{i}", e) for i, e in enumerate(filter(None, os.environ.get("AEGIS_PEERS", "").split(",")))]
                nodes = [_c.local_node("self")] + peers
                if len(nodes) < 2: nodes.append(_c.local_node("self-b"))  # demo mode: 2 local independent fetches
                return self._send(200, _c.consensus(url, claim, nodes, quorum=2))
            except Exception as e: return self._send(400, {"error": str(e)[:200]})
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
        rec["digest"] = token_bridge.receipt_digest(rec)
        if os.environ.get("AEGIS_ANCHOR_RECEIPTS") == "1" and os.environ.get("MAINNET") != "1":  # default OFF; devnet only
            try:
                from aegis_miner.solana_submit import SolanaSubmitter
                rec["onchain"] = {"cluster": "devnet", "memo_tx": SolanaSubmitter().submit(f"AGIS|PoV-R|{rid}|{rec['digest']}")}
            except Exception as e: rec["onchain"] = f"ANCHOR_FAILED: {type(e).__name__}"
        os.makedirs(RECEIPTS, exist_ok=True); json.dump(rec, open(os.path.join(RECEIPTS, rid + ".json"), "w"))
        self._send(200, rec)
    def _fee_preview(self):
        """Fee-split preview (mirrors reservoir.split_fee). Body: {fee_micro, votes:{node:weight}, flagged} or {fee_micro, consensus:{valid, consensus_vote, per_node:[...]}, flagged}."""
        from . import reservoir
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            return self._send(200, fee_preview(b, reservoir))
        except Exception as e: return self._send(400, {"error": str(e)[:200]})
    def log_message(self, *a): pass
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"AegisAI mock coordinator on http://localhost:{port}"); ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
