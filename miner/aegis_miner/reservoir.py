"""Reservoir fee accounting stub (off-chain ledger; no token, no mint).
Each verify fee (in Proof Credits / future AGIS units) splits: miners / reservoir / treasury / burn.
Miner share is pro-rata to confident, non-flagged claim votes. Integer math (micro-units) so totals always reconcile."""
SPLIT_BPS = {"miners": 7000, "reservoir": 2000, "treasury": 500, "burn": 500}
assert sum(SPLIT_BPS.values()) == 10000

def split_fee(fee_micro, votes, flagged=False):
    """votes: {node_id: weight}. Flagged receipt -> miners' share goes to reservoir."""
    if fee_micro < 0: raise ValueError("negative fee")
    parts = {k: fee_micro * b // 10000 for k, b in SPLIT_BPS.items()}
    parts["reservoir"] += fee_micro - sum(parts.values())  # rounding dust -> reservoir
    payouts = {}
    w = {n: x for n, x in (votes or {}).items() if x > 0}
    if flagged or not w:
        parts["reservoir"] += parts["miners"]
    else:
        tot, pool, paid = sum(w.values()), parts["miners"], 0
        for n in sorted(w): payouts[n] = pool * w[n] // tot; paid += payouts[n]
        parts["reservoir"] += pool - paid
    parts["miners"] = sum(payouts.values())
    assert sum(parts.values()) == fee_micro
    return {"fee_micro": fee_micro, "parts": parts, "payouts": payouts, "flagged": flagged}

class Ledger:
    def __init__(self): self.balances, self.totals, self.receipts = {}, dict.fromkeys(SPLIT_BPS, 0), []
    def settle(self, receipt_id, fee_micro, votes, flagged=False):
        if receipt_id in self.receipts: raise ValueError("double settle")
        r = split_fee(fee_micro, votes, flagged)
        for k, v in r["parts"].items(): self.totals[k] += v
        for n, v in r["payouts"].items(): self.balances[n] = self.balances.get(n, 0) + v
        self.receipts.append(receipt_id); return r
