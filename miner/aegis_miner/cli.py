"""AegisAI (AGIS) miner/validator. Default: simulation. --pov-wallet: real PoV-R batches."""
import argparse, hashlib, json, os, random, re, time, uuid
from datetime import datetime, timezone

CLAIMS = [
    ("Water boils at 100 C at sea level.", True),
    ("The Earth is flat.", False),
    ("Python is a programming language.", True),
    ("2 + 2 = 5", False),
    ("Solana uses proof of history.", True),
    ("The sun orbits the Earth.", False),
    ("10 * 3 = 30", True),
]
from aegis_miner.verify import tiny_check, FALSE_MARKERS  # noqa: F401


def load_config(path="config.yaml"):
    cfg = {"node_id": "agis-node-local-001", "mock_mode": True,
           "dry_run_submit": True, "votes_path": "./data/votes.jsonl", "coordinator": ""}
    if os.path.exists(path):
        for line in open(path):
            if ":" in line and not line.strip().startswith("#"):
                k, v = line.split(":", 1); v = v.strip()
                cfg[k.strip()] = {"true": True, "false": False}.get(v.lower(), v)
    for k in cfg:
        ev = os.environ.get("AEGIS_" + k.upper())
        if ev is not None:
            cfg[k] = {"true": True, "false": False}.get(ev.lower(), ev)
    return cfg


def fake_claim():
    text, truth = random.choice(CLAIMS)
    return {"claim_id": str(uuid.uuid4())[:8], "text": text, "_truth": truth}


def run(cfg, seconds, interval, submitter=None):
    end = time.time() + seconds; n = correct = 0
    os.makedirs(os.path.dirname(cfg["votes_path"]) or ".", exist_ok=True)
    while time.time() < end:
        c = fake_claim(); t0 = time.perf_counter()
        vote, conf = tiny_check(c["text"])
        ms = (time.perf_counter() - t0) * 1000
        hit = vote == c["_truth"]; n += 1; correct += hit
        score = round(conf * (1 if hit else -1), 3)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "node_id": cfg["node_id"],
               "claim_id": c["claim_id"], "claim": c["text"], "vote": "TRUE" if vote else "FALSE",
               "confidence": conf, "score": score, "latency_ms": round(ms, 3),
               "mock": cfg["mock_mode"], "tx": "DRY-RUN"}
        rec["digest"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:16]
        if submitter:
            try:
                memo = f"AGIS|PoV|{cfg['node_id']}|{c['claim_id']}|{rec['vote']}|{rec['digest']}"
                rec["tx"] = submitter.submit(memo); print(f"   tx {rec['tx']}")
            except Exception as e:
                rec["tx"] = f"ERROR:{e}"; print(f"   submit failed: {e}")
        print(f"[{c['claim_id']}] {rec['vote']:5} conf={conf} score={score:+} | {c['text']}")
        if cfg.get("coordinator"):
            try:
                import urllib.request
                urllib.request.urlopen(urllib.request.Request(cfg["coordinator"] + "/api/vote", json.dumps(rec).encode(), {"Content-Type": "application/json"}), timeout=2)
            except Exception as e: print(f"   coordinator offline: {e}")
        if cfg["dry_run_submit"]:
            with open(cfg["votes_path"], "a") as f: f.write(json.dumps(rec) + "\n")
        time.sleep(interval)
    print(f"\nDone: {n} tasks, accuracy {correct}/{n}, votes -> {cfg['votes_path'] if cfg['dry_run_submit'] else 'not saved'}")


def run_pov(wallet: str, *, base: str, n: int, local: bool, tier: str, cores: int):
    from aegis_miner import pov_mine as pm

    if not wallet or not wallet.strip():
        raise SystemExit("wallet required for PoV-R mine (Phantom pubkey)")
    if local:
        secret = (os.environ.get("AEGIS_POV_SECRET") or "test-secret").encode()
        out = pm.local_demo(secret, wallet.strip(), n=n)
        print(json.dumps({k: out[k] for k in ("wallet", "batchId", "n", "answersHex", "grade", "msg", "local", "elapsedMs")}, indent=2))
        if not out["grade"]["pass"]:
            raise SystemExit("local grade failed accuracy gate")
        print(f"\nOK local PoV: {out['grade']['correct']}/{out['grade']['n']} · sign msg then POST /api/claim")
        return
    out = pm.run_once(wallet.strip(), base=base, n=n, tier=tier, cores=cores)
    print(json.dumps({k: out[k] for k in ("wallet", "batchId", "n", "answersHex", "msg", "issuedAt", "elapsedMs", "tier", "note")}, indent=2))
    print(f"\nOK live PoV: solved {out['n']} wallet-bound tasks in {out['elapsedMs']} ms — approve msg in wallet, then claim")


def main():
    p = argparse.ArgumentParser(prog="aegis_miner", description="AegisAI PoV miner (simulation or wallet-bound PoV-R)")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--pov-wallet", default="", help="Solana wallet pubkey → fetch+solve real PoV-R batch (no keys)")
    p.add_argument("--pov-n", type=int, default=12, help="tasks per batch (1..120); live default often 120")
    p.add_argument("--pov-base", default=os.environ.get("AEGIS_CLAIM_BASE", "https://agis-claim.onrender.com"))
    p.add_argument("--pov-local", action="store_true", help="offline HMAC demo (no network); AEGIS_POV_SECRET optional")
    p.add_argument("--tier", default="laptop")
    p.add_argument("--cores", type=int, default=4)
    a = p.parse_args()
    if a.pov_wallet or a.pov_local:
        run_pov(a.pov_wallet or "LocalDemo1111111111111111111111111111111", base=a.pov_base, n=a.pov_n, local=a.pov_local or not a.pov_wallet, tier=a.tier, cores=a.cores)
        return
    cfg = load_config(a.config)
    sub = None
    if os.environ.get("AEGIS_SOLANA_SUBMIT") == "1":
        from aegis_miner.solana_submit import SolanaSubmitter
        sub = SolanaSubmitter()
        print(f"AegisAI miner | node={cfg['node_id']} | SOLANA SUBMIT ON | {sub.cluster} | {sub.kp.pubkey()}\n")
    else:
        print(f"AegisAI miner | node={cfg['node_id']} mock={cfg['mock_mode']} | SIMULATION (no txs)\n")
    run(cfg, a.seconds, a.interval, sub)
