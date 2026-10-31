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

def consensus(url, claim_text, nodes, quorum=2, weights=None):
    """weights: optional {node_id: float>0}. When given, the verdict is picked by WEIGHTED tally
    (sum of voter weights) instead of raw count; quorum still requires >= quorum distinct agreeing nodes.
    Missing node ids default to weight 1.0. Hash agreement stays count-based (bytes are bytes)."""
    if len(nodes) < quorum: raise ValueError(f"need >= {quorum} nodes")
    def safe(n):
        try: return n(url, claim_text)
        except Exception as e: return {"node": getattr(n, "node_id", "?"), "vote": "UNSURE", "error": (str(e) or type(e).__name__)[:100]}
    with ThreadPoolExecutor(max_workers=len(nodes)) as ex: results = list(ex.map(safe, nodes))
    hashes = Counter(r["source_hash"] for r in results if r.get("source_hash"))
    votes = Counter(r.get("vote") for r in results if r.get("vote") and not r.get("error"))
    top_hash, hash_n = hashes.most_common(1)[0] if hashes else (None, 0)
    top_vote, vote_n = votes.most_common(1)[0] if votes else (None, 0)
    vote_weight = total_weight = None
    if weights is not None:
        import math
        for k, v in weights.items():  # reject poisoned weights (negative/NaN/inf/bool) before tallying
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"invalid weight for {k!r}")
        wt = Counter()
        for r in results:
            if r.get("vote") and not r.get("error"): wt[r["vote"]] += float(weights.get(r.get("node"), 1.0))
        total_weight = round(sum(wt.values()), 6)
        if wt:  # deterministic tie-break: higher weight, then higher count, then vote name
            top_vote = max(wt, key=lambda v: (wt[v], votes[v], str(v))); vote_n = votes[top_vote]
            vote_weight = round(wt[top_vote], 6)
    hash_ok, vote_ok = hash_n >= quorum, vote_n >= quorum and top_vote != "UNSURE"
    if hash_ok and vote_ok: status = "VALID"            # same bytes, same verdict
    elif vote_ok: status = "VALID_VERDICT"              # dynamic page (ads/timestamps) but verdicts agree
    elif hash_ok: status = "HASH_ONLY"                  # same content, verdict split -> needs more nodes
    else: status = "NO_CONSENSUS"
    rec = {"url": url, "claim": claim_text, "quorum": quorum, "nodes": len(nodes), "status": status,
           "valid": status in ("VALID", "VALID_VERDICT"), "consensus_hash": top_hash if hash_ok else None,
           "hash_agree": hash_n, "consensus_vote": top_vote if vote_ok else None, "vote_agree": vote_n,
           "per_node": [{k: r.get(k) for k in ("node", "vote", "source_hash", "error")} for r in results]}
    if weights is not None: rec.update(weighted=True, vote_weight=vote_weight, total_weight=total_weight)
    # quorum_strength = agreeing weight / total weight over non-errored votes (unweighted: counts).
    # In [0,1]; 0.0 when there are no usable votes or total weight is 0 (never divides by zero).
    num, den = (vote_weight or 0.0, total_weight or 0.0) if weights is not None else (vote_n, sum(votes.values()))
    rec["quorum_strength"] = round(num / den, 6) if den > 0 else 0.0
    # errored: count of nodes that failed to answer (excluded from tallies; ids in per_node)
    rec["errored"] = sum(1 for r in results if r.get("error"))
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

def peer_compat(h, expect):
    """Capability handshake: (ok, reason). Peer advertising a different protocol_version/claim_schema is refused;
    a peer advertising neither is treated as legacy-compatible."""
    if not expect or not isinstance(h, dict): return True, None
    pv, cs = expect
    if "protocol_version" in h and h["protocol_version"] != pv: return False, "protocol_mismatch"
    if "claim_schema" in h and h["claim_schema"] != cs: return False, "claim_schema_mismatch"
    return True, None

def ping_peers(endpoints, timeout=2.0, getter=None, now=_time.time, expect=None):
    getter = getter or _default_get
    def one(ie):
        i, e = ie; pid = f"peer{i}"; t0 = _time.monotonic()
        try:
            h = getter(e, timeout); ok = bool(h.get("ok")) if isinstance(h, dict) else False
            err = None if ok else "unhealthy"
            if ok:
                ok, err = peer_compat(h, expect)
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
    def __init__(self, fail_threshold=3, recover_threshold=2, half_life=0.0, clock=None, disagree_cap=4, weight_floor=0.0):
        import math as _m
        if isinstance(weight_floor, bool) or not isinstance(weight_floor, (int, float)) or not _m.isfinite(weight_floor) or not 0 <= weight_floor <= 1:
            raise ValueError("weight_floor must be a number in [0, 1]")
        self.weight_floor = float(weight_floor)  # 0 = off
        if isinstance(disagree_cap, bool) or not isinstance(disagree_cap, int) or disagree_cap < 0:
            raise ValueError("disagree_cap must be an int >= 0")
        self.disagree_cap = disagree_cap  # 0 disables disagreement decay
        if fail_threshold < 1 or recover_threshold < 1: raise ValueError("thresholds must be >= 1")
        self.n, self.m = int(fail_threshold), int(recover_threshold)
        import math, time as _t
        hl = float(half_life)
        if not math.isfinite(hl) or hl < 0: raise ValueError("half_life must be finite and >= 0")
        self.half_life, self._clock = hl, (clock or _t.monotonic)
        self._s = {}  # endpoint -> {"alive", "fails", "oks"}

    def observe(self, endpoint, ok):
        s = self._s.setdefault(endpoint, {"alive": True, "fails": 0, "oks": 0})
        if ok:
            s["oks"] += 1; s["fails"] = 0; s["last_ok"] = self._clock()
            if not s["alive"] and s["oks"] >= self.m: s["alive"] = True
        else:
            s["fails"] += 1; s["oks"] = 0
            if s["alive"] and s["fails"] >= self.n: s["alive"] = False
        return s["alive"]

    # Uptime weight formula (documented contract):
    #   weight(peer) = 0                                  if peer is dead
    #   weight(peer) = 1 + min(oks, cap) / cap            if alive   -> range [1.0, 2.0]
    # where oks = consecutive successful observations (ping or vote) and cap = weight_cap (default 10).
    # A fresh/unknown peer has weight 1.0; a peer with a >= cap success streak counts double.
    # Bounded so one long-lived peer can never outvote two fresh honest peers (2.0 == 1.0 + 1.0, ties
    # break on raw count). Any failure resets oks -> weight drops back to 1.0 immediately.
    # Idle fade (optional, half_life > 0, env AEGIS_WEIGHT_HALFLIFE seconds; 0 = off):
    #   bonus = min(oks, cap)/cap * 0.5 ** (idle / half_life),  idle = now - last successful observation
    #   weight = 1 + bonus   -> stale streaks decay toward 1.0 (never below 1.0 while alive).
    weight_cap = 10

    def breakdown(self, endpoint):
        """{bonus, fade, dissent, weight}: weight = 0 if dead else (1 + bonus*fade) * dissent."""
        s = self._s.get(endpoint)
        if s is None: return {"bonus": 0.0, "fade": 1.0, "dissent": 1.0, "weight": 1.0, "alive": True, "floored": False}
        bonus = min(s["oks"], self.weight_cap) / self.weight_cap
        fade = 1.0
        if self.half_life > 0 and bonus > 0 and "last_ok" in s:
            fade = 0.5 ** (max(0.0, self._clock() - s["last_ok"]) / self.half_life)
        dissent = self.disagree_factor(endpoint)
        raw = (1.0 + bonus * fade) * dissent
        # Weight floor (AEGIS_WEIGHT_FLOOR in [0,1], 0 = off): alive peers never weigh below floor.
        # Dead peers stay 0 (liveness decides exclusion, the floor never resurrects them).
        floored = s["alive"] and raw < self.weight_floor
        w = 0.0 if not s["alive"] else max(raw, self.weight_floor)
        return {"bonus": bonus, "fade": fade, "dissent": dissent, "weight": w, "alive": s["alive"], "floored": floored}

    def weight(self, endpoint): return self.breakdown(endpoint)["weight"]

    def breakdowns(self, endpoints):
        """{peerN: breakdown} — ids only."""
        return {f"peer{i}": self.breakdown(e) for i, e in enumerate(endpoints)}

    # Disagreement decay (documented contract):
    #   factor = 0.5 ** min(d, disagree_cap),  d = consecutive votes that disagreed with a reached consensus
    #   weight = (1 + bonus) * factor  -> a chronic dissenter fades toward (1+bonus)/2**cap (cap=4 -> >= 1/16),
    #   never 0 (liveness, not disagreement, decides exclusion). One agreeing vote resets d to 0.
    #   Votes when no consensus was reached (consensus_vote None) or errored votes don't count either way.
    # disagree_cap: per-instance (ctor / env AEGIS_DISAGREE_CAP, default 4, 0 = decay off)

    def observe_vote(self, endpoint, agreed):
        s = self._s.setdefault(endpoint, {"alive": True, "fails": 0, "oks": 0})
        s["disagree"] = 0 if agreed else s.get("disagree", 0) + 1
        return s["disagree"]

    def disagree_factor(self, endpoint):
        d = self._s.get(endpoint, {}).get("disagree", 0)
        return 0.5 ** min(d, self.disagree_cap)

    def disagreements(self, endpoints):
        """{peerN: consecutive disagreement streak} — ids only."""
        return {f"peer{i}": self._s.get(e, {}).get("disagree", 0) for i, e in enumerate(endpoints)}

    def weights(self, endpoints):
        """{peerN: weight} keyed by ids only (URLs never exposed)."""
        return {f"peer{i}": self.weight(e) for i, e in enumerate(endpoints)}

    def is_alive(self, endpoint): return self._s.get(endpoint, {"alive": True})["alive"]

    def observe_pings(self, endpoints, results):
        for e, r in zip(endpoints, results): r["alive"] = self.observe(e, r.get("ok"))
        return results

    def summary(self, endpoints):
        alive = [e for e in endpoints if self.is_alive(e)]
        return {"alive": len(alive), "dead": len(endpoints) - len(alive), "known": len(endpoints),
                "fail_threshold": self.n, "recover_threshold": self.m,
                "weights": self.weights(endpoints), "weight_cap": self.weight_cap, "weight_half_life": self.half_life,
                "disagree_streaks": self.disagreements(endpoints), "disagree_cap": self.disagree_cap, "weight_floor": self.weight_floor}

    def alive_endpoints(self, endpoints): return [e for e in endpoints if self.is_alive(e)]

def _env_int(name, default):
    import os
    try: return max(1, int(os.environ.get(name, default)))
    except ValueError: return default

def _env_float(name, default):
    import os, math
    try:
        v = float(os.environ.get(name, default))
        return v if math.isfinite(v) and v >= 0 else default
    except ValueError: return default

def _env_floor(name="AEGIS_WEIGHT_FLOOR", default=0.0, env=None):
    """Float in [0,1]; invalid/negative/non-finite -> default; above 1 -> 1."""
    import os, math
    env = os.environ if env is None else env
    try: v = float(str(env.get(name, default)).strip())
    except ValueError: return default
    if not math.isfinite(v) or v < 0: return default
    return min(v, 1.0)

def _env_cap(name, default, env=None, hi=16):
    """Int in [0, hi]; invalid/negative -> default; above hi -> hi (bounds the 1/2**cap floor)."""
    import os
    env = os.environ if env is None else env
    try: v = int(str(env.get(name, default)).strip())
    except ValueError: return default
    return default if v < 0 else min(v, hi)

_TRUTHY = {"1", "true", "yes", "on"}
def weighted_quorum_enabled(env=None):
    """AEGIS_WEIGHTED_QUORUM truthy (1/true/yes/on, case-insensitive) -> weighted voting."""
    import os
    env = os.environ if env is None else env
    return str(env.get("AEGIS_WEIGHTED_QUORUM", "")).strip().lower() in _TRUTHY

def resolve_weighted(body_value, env=None):
    """Per-request override: JSON bool wins; absent/None -> env flag; anything else -> ValueError."""
    if body_value is None: return weighted_quorum_enabled(env)
    if not isinstance(body_value, bool): raise ValueError("weighted must be a boolean")
    return body_value

PEER_HEALTH = PeerHealth(_env_int("AEGIS_PEER_FAILS", 3), _env_int("AEGIS_PEER_RECOVERS", 2),
                         half_life=_env_float("AEGIS_WEIGHT_HALFLIFE", 0.0),
                         disagree_cap=_env_cap("AEGIS_DISAGREE_CAP", 4),
                         weight_floor=_env_floor())


# --- quorum collection skips dead peers (hysteresis) ---
def build_nodes(peer_endpoints, health=None, quorum=2, node_factory=None):
    """Returns (nodes, info). No peers configured -> local 2-fetch demo.
    Peers configured -> self + ALIVE peers only (ids keep original index; URLs never in info)."""
    health = health or PEER_HEALTH; node_factory = node_factory or http_node
    peers = [p.strip() for p in peer_endpoints if p and p.strip()]
    if not peers:
        return [local_node("self"), local_node("self-b")], {"mode": "local_demo", "known": 0, "alive": 0, "skipped": []}
    alive = set(health.alive_endpoints(peers))
    nodes = [local_node("self")] + [node_factory(f"peer{i}", e) for i, e in enumerate(peers) if e in alive]
    skipped = [f"peer{i}" for i, e in enumerate(peers) if e not in alive]
    return nodes, {"mode": "peers", "known": len(peers), "alive": len(alive), "skipped": skipped}

def consensus_alive(url, claim_text, peer_endpoints, health=None, quorum=2, node_factory=None, weighted=False):
    """Consensus over alive peers; too few alive -> NO_CONSENSUS with reason (no exception).
    Passive health: a peer that errors during collection counts as a failed observation."""
    health = health or PEER_HEALTH
    nodes, info = build_nodes(peer_endpoints, health, quorum, node_factory)
    if len(nodes) < quorum:
        return {"url": url, "claim": claim_text, "quorum": quorum, "nodes": len(nodes), "status": "NO_CONSENSUS",
                "valid": False, "reason": "insufficient_alive_peers", "consensus_hash": None, "consensus_vote": None,
                "per_node": [], "peer_selection": info}
    _p = [p.strip() for p in peer_endpoints if p and p.strip()]
    w = None
    if weighted and _p:  # local self node = 1.0; peers by uptime streak (see PeerHealth.weight)
        w = dict(health.weights(_p)); w.setdefault("self", 1.0)
    rec = consensus(url, claim_text, nodes, quorum=quorum, weights=w)
    peers = [p.strip() for p in peer_endpoints if p and p.strip()]
    for r in rec["per_node"]:
        nid = r.get("node") or ""
        if nid.startswith("peer") and nid[4:].isdigit() and int(nid[4:]) < len(peers):
            health.observe(peers[int(nid[4:])], not r.get("error"))
            if rec.get("consensus_vote") is not None and r.get("vote") and not r.get("error"):
                health.observe_vote(peers[int(nid[4:])], r["vote"] == rec["consensus_vote"])
    rec["peer_selection"] = info
    if w is not None: rec["weights_used"] = w  # audit: ids-only weights snapshot taken BEFORE this round's observations
    return rec

def ping_flags(health=None, env=None):
    """Flags reported by /v1/peers/ping alongside per-peer breakdowns."""
    health = health or PEER_HEALTH
    return {"weighted_quorum": weighted_quorum_enabled(env), "disagree_cap": health.disagree_cap,
            "weight_floor": health.weight_floor}

def attach_breakdowns(health, endpoints, results):
    """Add ids-only weight breakdown to ping results (no URLs; keyed by position)."""
    for e, r in zip(endpoints, results): r["weight"] = health.breakdown(e)
    return results
