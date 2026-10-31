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
