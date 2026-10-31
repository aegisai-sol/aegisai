# AegisAI Miner / Validator (Python — PC & servers)

Lightweight Proof-of-Verification node. Pure stdlib in simulation; runs on Raspberry Pi / old laptops. **No model downloads** (mock TinyLM = arithmetic + heuristics; real version: <1 GB quantized model, later).

| Mode | How | What happens |
|---|---|---|
| Simulation (default) | `python3 main.py --seconds 30` | Mock micro-tasks, votes + SHA-256 digest to `data/votes.jsonl`. No network, no keys. |
| + Coordinator | `python3 -m aegis_miner.coordinator` then `AEGIS_COORDINATOR=http://localhost:8787 python3 main.py` | Votes POSTed to the mock API; site dashboard reads `/api/stats`. |
| Solana submit (real txs) | `pip install -r requirements.txt` then `AEGIS_SOLANA_SUBMIT=1 SOLANA_KEYPAIR=../aegisai-token/.keys/devnet.json python3 main.py --seconds 10 --interval 3` | One **SPL Memo** tx per vote: `AGIS|PoV|<node>|<claim>|<vote>|<digest>`, signed by your keypair. **Devnet** by default; `SOLANA_RPC` overrides; `MAINNET=1` for mainnet (costs ~0.000005 SOL/vote). |

Memo program: `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr` (official SPL Memo). Fund the devnet key with `npm run airdrop` in `../aegisai-token`. Tx signatures are printed and saved in `votes.jsonl` (`tx` field); view at `https://explorer.solana.com/tx/<sig>?cluster=devnet`.

Mobile/any OS: use the browser/PWA miner (`../aegisai-site/miner.html`). Native Android/iOS apps are planned later.

Simulated scores have **no monetary value**; rewards/consensus are not live.

## Public coordinator for the web Verify demo
`verify.html` (site) calls `POST {coordinator}/v1/verify` if a coordinator is set via `?coordinator=URL`, `window.AEGIS_COORDINATOR` or `localStorage.agisCoordinator`; otherwise it runs an in-browser mirror of `verify.py` (arithmetic + heuristic; source checks return UNSURE). To expose a local coordinator without deploying (no minting, no keys): `python3 -m aegis_miner.coordinator` then `cloudflared tunnel --url http://localhost:8787` (or `ngrok http 8787`) and open `https://bold-thistle-3z5f.here.now/verify.html?coordinator=https://<tunnel-host>`. CORS `*` is already sent. Tunnel URLs are ephemeral — fine for a mid-check demo.

## Public verify demo (PoV-R)
`scripts/run_public_demo.sh` starts the stdlib coordinator on :8787 (`POST /v1/verify`, `GET /v1/receipts/<id>`, `GET /v1/credits/<id>`) and prints a cloudflared/ngrok hint. Point the site at it: `verify.html?coordinator=https://<tunnel>`.
Checks: numbered/bullet list splitting · arithmetic (exact) · source quote match (fetch + sha256) · URL-only → page title + hash + UNSURE "no quote to match", unreachable → FALSE · one calibration canary per batch (wrong canary vote ⇒ receipt flagged, 0 credits).

## Peer node (Docker) — multi-node quorum
`miner/Dockerfile` runs the stdlib coordinator as a node; `miner/docker-compose.yml` starts two (`node-a`, `node-b`). `AEGIS_PEERS` is a comma-separated list of peer base URLs; `POST /v1/consensus` on a node fetches locally and asks each peer (`/v1/fetch-check`) independently, then returns `status` = `VALID` / `VALID_VERDICT` / `HASH_ONLY` / `NO_CONSENSUS` with `quorum=2`.

```bash
cd miner && docker compose up --build
curl -XPOST localhost:8787/v1/consensus -d '{"url":"https://example.com/","claim":"example domain"}'
# a second machine: docker build -t aegis-node . && docker run -p 8787:8787 -e AEGIS_PEERS=http://<other-host>:8787 aegis-node
```
No secrets, no keypairs, no Solana submit in the image. Data lives in the `/data` volume.

**Coordinator ops:** `AEGIS_RATE_LIMIT=N/SEC` (e.g. `30/60`, per-IP on `/v1/verify` + `/v1/fee-preview`, off by default) · `AEGIS_CORS_ORIGINS=https://a,https://b` (default `*`) · spec at `GET /v1/openapi.json` · counters at `GET /v1/metrics`.

**Verify-then-Act:** `POST /v1/gate {"action":"publish","claim":"..."}` (or `claim_digest`) → `ALLOW` / `DENY` / `REQUIRE_RECEIPT` from the local receipt store (non-flagged, digest-intact receipts only). Read-only, no signing.
