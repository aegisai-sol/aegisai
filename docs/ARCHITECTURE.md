# AegisAI Architecture (scale path)

```
 Requesters (AI apps, enterprises)          Solana
        │ POST /v1/verify                      ▲ batch Merkle root (Memo → PoV program)
        ▼                                      │
 ┌──────────────── Coordinator API ────────────┴──┐
 │ decomposer · task queue · assigner (VRF-ish)   │
 │ commit/reveal store · aggregator · rewards ledger│
 └──────┬───────────────┬───────────────┬─────────┘
        │ WSS/HTTPS     │               │
  Browser PWA node  Python node   Docker node (future)
  (phones, any OS)  (PC/RPi/server) (servers, GPU optional)
```

## Coordinator API (v1 draft)
| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/nodes/register` | wallet pubkey + signed nonce, device class, capabilities |
| GET | `/v1/tasks/next` | lease a micro-claim (TTL ~30 s) |
| POST | `/v1/tasks/{id}/commit` | `H(vote‖salt‖node‖task)` |
| POST | `/v1/tasks/{id}/reveal` | vote, salt, confidence |
| GET | `/v1/stats` | network KPIs for dashboard (already mocked by `aegis_miner.coordinator`) |
| POST | `/v1/verify` | (Phase 4, paid) submit AI output → claims → verdicts + receipt |
| GET | `/v1/receipts/{id}` | verdict + Solana tx signature + Merkle proof |

Auth: nodes sign requests with their wallet (ed25519); no private keys leave the device. Stateless API behind a load balancer; Postgres for ledger, Redis for task leases; batch attestation worker posts one Solana tx per N verdicts (cost-bounded).

## Node types
| Type | Runs on | Verifier | Status |
|---|---|---|---|
| Browser PWA (`aegisai-site/miner.html`) | Android, iOS, desktop browsers | JS rules → WASM/WebGPU ONNX | MVP (simulated) |
| Python (`aegisai-miner`) | Windows/macOS/Linux/RPi/servers | rules → onnxruntime CPU | MVP (simulated) |
| Docker | servers, cloud | same as Python, higher quota | planned |

### How phones mine
Open the site → "Add to Home Screen" (PWA) → connect Phantom (mobile in-app browser or deep link) → node leases tasks while the app is open, verifies locally in a Web Worker, commits/reveals, shows earned points. Rewards accrue to the wallet off-chain and are claimed in batches (low fees). Battery guard: pauses on low battery / not charging (configurable).

## Reward pool (from the 85%)
- Pool allocation published before mainnet; emitted per epoch (e.g. daily) with decaying schedule.
- `reward_i = epoch_emission × (score_i / Σscore)`, `score = correct_weighted_votes × reputation × device_fairness_factor` (keeps phones competitive vs servers).
- Claims via Merkle distributor (one root per epoch on Solana).
- Developer 15% is **separate and vested**; never used for rewards.

## Scaling notes
Horizontal coordinators sharded by task id; attestation batched; read-heavy dashboard served from cached `/v1/stats` + Solana RPC/indexer (Helius) for holders and txs.

### Weighted quorum env knobs
- `AEGIS_WEIGHTED_QUORUM` — enable uptime-weighted voting (per-request `weighted` bool overrides).
- `AEGIS_WEIGHT_HALFLIFE` — idle-fade of uptime bonus, seconds (0 = off).
- `AEGIS_DISAGREE_CAP` — max halvings for consecutive dissent (default 4, 0 = off, clamp 16).
- `AEGIS_AGREEMENT_WINDOW` — sliding window of last W counted votes for per-peer `window_rate` (default 20, max 1000); older votes drop out.
- `AEGIS_AGREEMENT_THRESHOLD` — opt-in low-agreement penalty t in [0,1] (default 0 = off): if `window_rate < t`, weight *= `max(0.25, window_rate / t)`.
- `AEGIS_AGREEMENT_MIN_VOTES` — sample-size guard; penalty only applies once the window holds >= N votes (default 5).
- `AEGIS_WEIGHT_FLOOR` — minimum weight for an *alive* peer, float in [0,1] (default 0 = off; >1 clamps to 1; invalid → 0). Dead peers stay 0. Breakdown reports `floored: true` when applied.
- `AEGIS_MIN_STRENGTH` — float in [0,1] (default 0 = off; >1 clamps to 1; invalid → 0). A VALID/VALID_VERDICT round with `quorum_strength` below it is downgraded to `NO_CONSENSUS` (`reason: low_strength`, `downgraded_from`), and the receipt digest reflects the downgrade.
- `AEGIS_QUORUM` — min distinct agreeing nodes for `/v1/consensus` (default 2, clamp 2..16; invalid/<2 → 2); reported in `/v1/health` and `/v1/peers/ping`. Per-request JSON int `quorum` may only *tighten* it (int in [2,16] and >= `AEGIS_QUORUM`; bool/float/lower → 400). Records carry `quorum_applied` {value, source: env|request}, also on `insufficient_alive_peers`.
- `AEGIS_STRENGTH_WINDOW` — rolling window of recent rounds for `/v1/health.quorum_strength` {latest, avg, min, samples, window, rounds, downgraded, min_strength} (default 20, clamp 1..1000; strengths only, no URLs/claims).

`/v1/health` exposes `peer_weights` ({peerN: {bonus, fade, dissent, weight, alive, floored}}, ids only, same shape as `/v1/peers/ping`). Weighted `/v1/consensus` records include `weights_used` (ids-only snapshot before the round's health updates) for audit.
