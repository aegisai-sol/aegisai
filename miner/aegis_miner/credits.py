"""Proof Credits ledger (append-only jsonl). Stub.
PoV-R Reservoir rules (not enforced here, Option A: no mint until audit + LP):
credits are non-transferable; conversion to AGIS only against real paid verification fees,
capped per period at <=70% of fees and <=0.5% of the 40% Reservoir."""
import json, os, time

def eligible(result): return result.get("confidence", 0) >= 0.7 and result.get("vote") != "UNSURE"

def award(path, client_id, receipt_id, results):
    n = sum(1 for r in results if eligible(r))
    if n:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps({"ts": time.time(), "client_id": client_id, "receipt_id": receipt_id, "credits": n}) + "\n")
    return n

def balance(path, client_id):
    if not os.path.exists(path): return 0
    return sum(e["credits"] for e in map(json.loads, open(path)) if e["client_id"] == client_id)
