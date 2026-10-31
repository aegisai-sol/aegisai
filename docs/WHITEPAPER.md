# AegisAI Whitepaper — Proof-of-Verification Reservoir (PoV-R)

*Version 0.2 · 31 October 2026 · Status: MVP / pre-TGE (Option A — no token mint until audit + LP capital). Numbers are design targets, not measurements. Not financial advice.*

## Abstract
AegisAI is a verification network for AI output. Instead of building another large language model, AegisAI splits AI answers into small, checkable **micro-claims**, has many low-power nodes verify them, aggregates the votes with commit–reveal consensus, and issues a **receipt** that can be anchored on Solana. The economic layer, the **Reservoir**, rewards correct verification with **Proof Credits** that convert to AGIS only against real, paid verification fees.

## 1. Problem
1. **AI hallucinations.** LLMs state wrong facts, sums and fake citations with confidence. Businesses using AI need checked output.
2. **Verification is mis-priced.** Most checks (a date, a sum, a quote, a URL) are tiny. Sending each one to a frontier model or a human is slow and costly.
3. **No portable proof.** When an answer *was* checked, there is usually no receipt a third party can audit.

## 2. Solution overview
**PoV-R = Proof-of-Verification + Reservoir.**
- **PoV** is the protocol: decompose → assign → verify → commit–reveal → aggregate → attest.
- **Reservoir** is the economics: hard-capped supply, Proof Credits for correct votes, conversion capped by real fee revenue.

## 3. The Proof-of-Verification round
1. **Decompose** — AI text is split into micro-claims (e.g. "17 × 23 = 391", "Source X says Y").
2. **Assign** — each claim goes to *k* random nodes (k = 5–15), weighted by reputation (and stake later), across device classes.
3. **Verify** — nodes run deterministic methods: arithmetic/rules, **Proof-of-Source**, small local models later. Output: TRUE / FALSE / UNSURE + confidence.
4. **Commit–reveal** — nodes commit `H(vote‖salt‖node‖task)` then reveal, preventing copy-voting.
5. **Aggregate** — weighted ≥ 2/3 supermajority finalizes; otherwise escalate.
6. **Attest** — batch Merkle root of verdicts to Solana (Memo first, dedicated program later). Each claim gets a receipt ID.

## 4. Verification methods
- **Arithmetic & rules** — deterministic checks of numbers, units, dates.
- **Proof-of-Source** — fetch the cited URL and check whether the quoted text actually exists on the page (normalized fingerprint). Catches fabricated citations — one of the most common AI failures.
- **Calibration canaries** — known-answer tasks injected at random to detect lazy or dishonest nodes.
- **Small models (planned)** — quantized NLI/fact classifiers (< 1 GB, ONNX/WebGPU) for claims rules can't settle.

## 5. Reservoir & Proof Credits
- Hard cap: **1,000,000,000 AGIS**; mint authority revoked after genesis.
- Nodes earn **Proof Credits** (off-chain ledger first, Solana later) for votes that match the final verdict and pass canaries.
- Credits convert to AGIS **only against paid verification fees**: at most **70% of fees** per epoch and at most **0.5% of Reservoir** per epoch. No fees → no emission.
- This ties token issuance to real usage rather than inflation.

## 6. Role of the AGIS token
AGIS is integral to PoV-R: it pays verifiers (via Reservoir conversion), can be used for verification fees, and later for node stake/slashing. **Option A:** no mint and no trading until an external audit and LP capital from a raise exist. Product first, token second.

## 7. AI — but not another LLM
AegisAI does not compete with OpenAI, xAI or others. Any model's output (theirs, or a future AegisAI helper) can pass through PoV. AegisAI is the trust layer: AI produces, PoV verifies, receipts prove.

## 8. Architecture
Requesters → **Coordinator API** (decomposer, task queue, assigner, commit/reveal store, aggregator, credits ledger) → nodes (browser PWA, Python, Docker later) → batched attestation on Solana.
Key endpoints: `POST /v1/verify`, `GET /v1/receipts/{id}`, `POST /v1/nodes/register`, `GET /v1/tasks/next`, commit/reveal.
Nodes sign with their wallet (ed25519); private keys never leave the device.

## 9. Security model
| Threat | Mitigation |
|---|---|
| Copy-voting | Commit–reveal, salted task variants |
| Collusion | Random assignment, cross-device quorums, correlation detection |
| Sybil | Reputation warm-up, rate limits, stake later, optional device attestation |
| Always-TRUE free-riding | Calibration canaries |
| Coordinator trust | Phase 1 centralized but publishes commitments; later multi-coordinator + on-chain settlement |

## 10. Future vertical: RWA Doc Check
Tokenized real-world assets rely on documents (NAV reports, filings, insurance, audits). AI summaries of these are increasingly used — and can be wrong. **RWA Doc Check** applies Proof-of-Source to them: "NAV is X" or "the asset is insured" is checked against the actual public filing, with a receipt. AegisAI will not tokenize assets or act as a price oracle; it verifies claims about them. Planned after the core Verify product (6–12 months).

## 11. Current status (honest)
- **Live:** Verify web app (arithmetic, Proof-of-Source, calibration canaries, receipts, in-browser Proof Credits) at bold-thistle-3z5f.here.now/verify.html.
- **Code:** github.com/aegisai-sol/aegisai — tests passing for the verify engine.
- **Simulated:** multi-node network, browser miner, dashboard stats.
- **Not yet:** token mint, on-chain program, audit, paying customers.

## 12. Roadmap
| Stage | Deliverable |
|---|---|
| NOW | Verify app + Proof-of-Source + receipts |
| NEAR | Public Verify API, Solana Memo attestations, Proof Credits on devnet |
| NEXT | Small on-device models, multi-node network, audit, raise → LP → AGIS TGE |
| LATER | RWA Doc Check pilot, mobile app, decentralized coordinators, staking/slashing |

## 13. Risks & limitations
Small models are weaker than frontier models; PoV relies on decomposition, rules, quorum and escalation. Phase 1 is centralized. No audit yet. Regulatory treatment of tokens varies by jurisdiction. Nothing here is an offer to sell securities or financial advice.

*Contact: aibot.universe@gmail.com · X @AegisAI_Sol · Telegram @AegisAI_Sol*
