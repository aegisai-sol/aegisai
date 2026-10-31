# Proof-of-Verification (PoV) — AegisAI Protocol Paper (lite) v0.1

*Status: draft for review · October 2026 · MVP is simulated; numbers are design targets, not measurements.*

## Abstract
AegisAI introduces **Proof-of-Verification (PoV)**: a consensus-for-useful-work primitive in which heterogeneous, low-power nodes (phones, laptops, servers) verify atomic AI-generated **micro-claims**, reach stake- and reputation-weighted agreement, and anchor the verified result on Solana. Rewards flow to work that reduces AI error, not to hash grinding or idle capital.

## 1. Problem
1. **Hallucinations.** LLMs state false facts with confidence. Enterprises need checked outputs, but verification by a second large model or human review is slow and costly.
2. **Verification cost is mis-shaped.** Most checks (a date, a sum, a citation, a unit, a named entity) are tiny. Routing each through a frontier model wastes compute.
3. **Idle weak devices.** Billions of phones and old PCs sit idle; PoW excludes them, PoS rewards capital rather than work.

## 2. The primitive
**Micro-claim**: an atomic, checkable statement extracted from AI output, e.g. `"Bulgaria joined the EU in 2007"` or `"17 × 23 = 391"`, with a context bundle (source snippet, rule set, model hint).

**PoV round**
1. *Decompose* — a requester (or the coordinator) splits an AI answer into micro-claims.
2. *Assign* — each claim goes to *k* randomly selected nodes (k = 5–15), drawn by VRF-style randomness weighted by stake × reputation, across device classes.
3. *Verify* — nodes run deterministic rules + a small local model (target < 1 GB, ONNX/quantized) and output `{TRUE, FALSE, UNSURE}` + confidence.
4. *Commit–reveal* — node first submits `H(vote ‖ salt ‖ node_id ‖ task_id)`, then reveals after the commit window closes.
5. *Aggregate* — weighted supermajority (default ≥ 2/3 of weight) finalizes the verdict; otherwise escalates to a larger quorum or a heavier verifier.
6. *Attest* — a batch Merkle root of verdicts is written to Solana (Memo now, dedicated program later). Each claim gets a verifiable receipt.
7. *Reward / penalize* — agreeing nodes earn AGIS from the reward pool and reputation; deviating or non-revealing nodes lose reputation and (later) stake.

## 3. Why this is new
| Approach | What it rewards | Gap PoV fills |
|---|---|---|
| Proof-of-Work | Hash waste | PoV work has external value (fewer AI errors) |
| Proof-of-Stake | Locked capital | PoV requires work; stake only weights and secures it |
| Centralized fact-check APIs | One vendor's judgment | PoV is open, auditable, receipt on-chain |
| Federated learning | Training updates | PoV targets *inference-time verification*, not training |
| Generic compute/inference markets | Raw GPU time | PoV runs on CPUs and phones, produces verdicts + attestations |

The novelty is the **combination**: micro-inference on weak heterogeneous hardware + commit-reveal consensus + on-chain attestation + rewards for useful verification. We do not claim each ingredient is new; we claim the primitive and its market are.

## 4. Threat model and mitigations
| Threat | Mitigation |
|---|---|
| **Copy-voting / lazy nodes** | Commit–reveal; per-node salted task variants; vote timing analysis |
| **Collusion** | Random, unpredictable assignment; cross-device-class quorums; collusion-detection on correlated votes; slash on proven collusion |
| **Sybil** | Minimum stake per node, reputation warm-up, per-wallet rate limits, optional device attestation (Play Integrity / App Attest) later |
| **Free-riding (always TRUE)** | **Gold/challenge tasks** with known answers injected at random; failure = reputation hit |
| **Poisoned tasks** | Requester deposits, task templates, coordinator sanity filters |
| **Coordinator trust** | Phase 1 centralized but publishes all commitments; later multiple coordinators + on-chain program for settlement |
| **Majority wrong (honest error)** | UNSURE option, escalation to heavier verifier, confidence-weighted scoring |

*Stake slashing is a stub in the MVP (reputation only); real slashing ships with the on-chain program after audit.*

## 5. Economics (summary)
- Supply 1,000,000,000 AGIS fixed, mint & freeze authority revoked.
- **Developer 15% (150M) vested** — 3-month cliff + 12-month linear, public stream link at launch.
- 85% public: node reward pool, liquidity, ecosystem/grants (split published before mainnet).
- Demand side: companies pay for verification (AGIS or stable → buy-back to pool). Emissions decay over time; fee share grows.

## 6. Phases
| Phase | What runs | Real? |
|---|---|---|
| 0 · Mock | Simulated tasks, local coordinator, browser + Python node, mock dashboard | **Now** |
| 1 · Devnet | SPL token on devnet, Memo attestations of vote batches, commit-reveal live | Next |
| 2 · Small models | ONNX models < 1 GB (NLI / fact classifiers) on PC; WebGPU/WASM in browser | |
| 3 · Mainnet rewards | Mainnet token, vested 15%, reward pool distribution, reputation | |
| 4 · Verification API | Paid API for companies: submit AI output → verdict + on-chain receipt | |
| 5 · Decentralize | Multiple coordinators, on-chain settlement program, staking & slashing (audited) | |

## 7. Honest limitations
- The MVP **simulates** verification; it does not yet check real-world facts.
- Small models are weaker than frontier models; PoV relies on decomposition, rules, quorum and escalation, not on any single node being smart.
- Phones mine only while the PWA is open (browser background limits).
- Phase 1 coordinator is centralized. No audit yet. Not financial advice.

## Canaries v2 & peer liveness
- Each `/v1/verify` request hides 2 canaries; at least one is a **FALSE trap** (e.g. a wrong product), so an "always TRUE" miner fails calibration and earns 0 credits. Pool also covers large-number and division checks. Patterns live in `verify.CANARY_POOL_V2`.
- `GET /v1/peers/ping` probes each `AEGIS_PEERS` entry's `/v1/health` (2s timeout) and returns `peer0..N` with `ok`, `latency_ms`, `last_ok` — never URLs or keys. `/v1/health.peer_liveness` gives a cached live/known count (stale after 300s).
