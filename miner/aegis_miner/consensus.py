"""Multi-node fetch consensus (PoV-R).
Independent nodes each re-fetch the cited URL and run the Proof-of-Source check.
A receipt is VALID when >= quorum nodes agree on the content hash AND/OR the verdict.
Nodes are callables (url, claim_text) -> result dict; remote miners plug in the same way."""
import hashlib, json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from . import verify

def local_node(node_id, page_fetcher=verify.fetch_page):
    def run(url, claim_text):
        r = verify.check_url_only(url, page_fetcher=page_fetcher, claim_text=claim_text)
        return dict(r, node=node_id)
    run.node_id = node_id
    return run

def http_node(node_id, endpoint, timeout=15):
    """Remote miner: POST {url, claim} to endpoint/v1/fetch-check."""
    import urllib.request
    def run(url, claim_text):
        req = urllib.request.Request(endpoint.rstrip("/") + "/v1/fetch-check",
            data=json.dumps({"url": url, "claim": claim_text}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r: return dict(json.loads(r.read()), node=node_id)
    run.node_id = node_id
    return run

def consensus(url, claim_text, nodes, quorum=2):
    if len(nodes) < quorum: raise ValueError(f"need >= {quorum} nodes")
    def safe(n):
        try: return n(url, claim_text)
        except Exception as e: return {"node": getattr(n, "node_id", "?"), "vote": "UNSURE", "error": str(e)[:100]}
    with ThreadPoolExecutor(max_workers=len(nodes)) as ex: results = list(ex.map(safe, nodes))
    hashes = Counter(r["source_hash"] for r in results if r.get("source_hash"))
    votes = Counter(r.get("vote") for r in results if r.get("vote") and not r.get("error"))
    top_hash, hash_n = hashes.most_common(1)[0] if hashes else (None, 0)
    top_vote, vote_n = votes.most_common(1)[0] if votes else (None, 0)
    hash_ok, vote_ok = hash_n >= quorum, vote_n >= quorum and top_vote != "UNSURE"
    if hash_ok and vote_ok: status = "VALID"            # same bytes, same verdict
    elif vote_ok: status = "VALID_VERDICT"              # dynamic page (ads/timestamps) but verdicts agree
    elif hash_ok: status = "HASH_ONLY"                  # same content, verdict split -> needs more nodes
    else: status = "NO_CONSENSUS"
    rec = {"url": url, "claim": claim_text, "quorum": quorum, "nodes": len(nodes), "status": status,
           "valid": status in ("VALID", "VALID_VERDICT"), "consensus_hash": top_hash if hash_ok else None,
           "hash_agree": hash_n, "consensus_vote": top_vote if vote_ok else None, "vote_agree": vote_n,
           "per_node": [{k: r.get(k) for k in ("node", "vote", "source_hash", "error")} for r in results]}
    rec["receipt_digest"] = hashlib.sha256(json.dumps({k: rec[k] for k in ("url", "claim", "status", "consensus_hash", "consensus_vote")}, sort_keys=True).encode()).hexdigest()
    return rec


def canonical_json(x) -> str:
    """Sorted keys, compact separators; mirrors site/js/receipt-demo.js canonicalJson."""
    import json as _j
    return _j.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def receipt_digest(body) -> str:
    import hashlib as _h
    return "sha256:" + _h.sha256(canonical_json(body).encode()).hexdigest()


# --- peer liveness: ids peer0..N only; URLs/keys never returned ---
import time as _time
_LAST_OK = {}

def _default_get(endpoint, timeout):
    import urllib.request
    with urllib.request.urlopen(endpoint.rstrip("/") + "/v1/health", timeout=timeout) as r:
        return json.loads(r.read())

def ping_peers(endpoints, timeout=2.0, getter=None, now=_time.time):
    getter = getter or _default_get
    def one(ie):
        i, e = ie; pid = f"peer{i}"; t0 = _time.monotonic()
        try:
            h = getter(e, timeout); ok = bool(h.get("ok")) if isinstance(h, dict) else False
            err = None if ok else "unhealthy"
        except Exception as ex: ok, err = False, type(ex).__name__
        if ok: _LAST_OK[e] = now()
        return {"id": pid, "ok": ok, "latency_ms": int((_time.monotonic() - t0) * 1000),
                "last_ok": _LAST_OK.get(e), **({"error": err} if err else {})}
    if not endpoints: return []
    with ThreadPoolExecutor(max_workers=len(endpoints)) as ex: return list(ex.map(one, enumerate(endpoints)))

def peer_liveness(endpoints, now=_time.time, stale_s=300):
    """Cached summary for /v1/health (no network call)."""
    t = now(); live = sum(1 for e in endpoints if e in _LAST_OK and t - _LAST_OK[e] <= stale_s)
    return {"live": live, "known": len(endpoints), "stale_after_s": stale_s}


# --- peer health hysteresis: dead after N consecutive fails, alive again after M consecutive oks ---
class PeerHealth:
    """Flap-resistant peer state. Starts 'alive'. Ids only (peer0..N); URLs never exposed."""
    def __init__(self, fail_threshold=3, recover_threshold=2):
        if fail_threshold < 1 or recover_threshold < 1: raise ValueError("thresholds must be >= 1")
        self.n, self.m = int(fail_threshold), int(recover_threshold)
        self._s = {}  # endpoint -> {"alive", "fails", "oks"}

    def observe(self, endpoint, ok):
        s = self._s.setdefault(endpoint, {"alive": True, "fails": 0, "oks": 0})
        if ok:
            s["oks"] += 1; s["fails"] = 0
            if not s["alive"] and s["oks"] >= self.m: s["alive"] = True
        else:
            s["fails"] += 1; s["oks"] = 0
            if s["alive"] and s["fails"] >= self.n: s["alive"] = False
        return s["alive"]

    def is_alive(self, endpoint): return self._s.get(endpoint, {"alive": True})["alive"]

    def observe_pings(self, endpoints, results):
        for e, r in zip(endpoints, results): r["alive"] = self.observe(e, r.get("ok"))
        return results

    def summary(self, endpoints):
        alive = [e for e in endpoints if self.is_alive(e)]
        return {"alive": len(alive), "dead": len(endpoints) - len(alive), "known": len(endpoints),
                "fail_threshold": self.n, "recover_threshold": self.m}

    def alive_endpoints(self, endpoints): return [e for e in endpoints if self.is_alive(e)]

def _env_int(name, default):
    import os
    try: return max(1, int(os.environ.get(name, default)))
    except ValueError: return default

PEER_HEALTH = PeerHealth(_env_int("AEGIS_PEER_FAILS", 3), _env_int("AEGIS_PEER_RECOVERS", 2))
