# Storage & token integration (PoV-R) — working hooks

Status: Option A — **no AGIS mint**. Everything below runs today in off-chain mode; the on-chain parts are interfaces waiting for mint + LP + audit.

## Flow: receipt → Proof Credits → AGIS claim
1. `POST /v1/verify` (coordinator) → claims checked (`verify.py`: arithmetic, Proof-of-Source support check, canaries).
2. Receipt saved to `data/receipts/<id>.json` with `digest` = `token_bridge.receipt_digest()` (canonical SHA-256; this is what gets anchored via SPL Memo on devnet — `solana_submit.py`, opt-in `AEGIS_SOLANA_SUBMIT=1`).
3. Confident, canary-passing votes → `credits.award()` → append-only `data/credits.jsonl` (non-transferable).
4. `GET /v1/claim-quote/<client_id>` → `token_bridge.claim_quote()`: pro-rata share of the period pool,
   `pool = min(0.70 × period fees / AGIS price, 0.5% × Reservoir remaining)`. Returns 0 + reason while no mint.
5. `token_bridge.claim_intent()` → **unsigned** intent JSON. The operator reviews and signs in Phantom; the coordinator never holds keys.

## Where state lives
| State | Today | After mint |
|---|---|---|
| Receipts | `data/receipts/*.json` (coordinator disk) | same + digest memo on Solana |
| Proof Credits | `data/credits.jsonl` | same (off-chain; burned on claim) |
| AGIS mint | none | SPL mint, address in `AEGIS_MINT` |
| Reservoir (40% = 400M) | constant in `token_bridge.py` | token account in `AEGIS_RESERVOIR_ATA`, read via `getTokenAccountBalance` (`SplState`) |
| Fees / price | `OffchainState(fees_usd, price_usd)` | fee ledger + LP price oracle (NotImplemented hooks) |
| Firm keys | **Phantom / vault / Drive only — never in repo, chat, or coordinator env** | multisig for Reservoir |

`GET /v1/token-state` reports which mode is active (`state_from_env()` switches to `SplState` when both env vars are set).

## Next hooks to fill
- Fee ledger (paid verify API calls) → `period_fees_usd()`.
- LP price oracle → `agis_price_usd()`.
- Credit burn entry on claim (negative ledger line) + claim program / multisig transfer from Reservoir.
- Multi-node fetch consensus for Proof-of-Source receipts.

## Devnet receipt anchoring (toggle, default OFF)
The coordinator can anchor each `/v1/verify` receipt digest as an SPL Memo on **devnet**:
`AEGIS_ANCHOR_RECEIPTS=1 SOLANA_KEYPAIR=/path/devnet.json python3 -m aegis_miner.coordinator` (needs `pip install solders` + devnet SOL).
Memo: `AGIS|PoV-R|<receipt_id>|<digest>`; tx sig stored in `rec.onchain.memo_tx`. Ignored when `MAINNET=1`. Never put keys in chat/repo.

## Devnet anchoring — tested path (Oct 31)
- Default **OFF**. `MAINNET=1` or any mainnet RPC is **refused** in code (phase 1 = devnet only).
- `AEGIS_ANCHOR_DRYRUN=1` builds + signs the SPL Memo tx locally and never sends (returns `DRYRUN:<sig>`).
- CI: `miner/tests/test_anchor.py` mocks RPC and uses an **ephemeral TEST-ONLY keypair** created in a pytest tmp dir (never on disk in repo).
- Real devnet TX (manual, not yet done — box could not reach api.devnet.solana.com):
  1. `solana-keygen new -o ~/aegis-devnet-TEST-ONLY.json` (throwaway, never the firm Phantom wallet)
  2. `solana airdrop 1 <pubkey> -u devnet` or https://faucet.solana.com
  3. `AEGIS_ANCHOR_RECEIPTS=1 SOLANA_KEYPAIR=~/aegis-devnet-TEST-ONLY.json python3 -m aegis_miner.coordinator`
  4. POST /v1/verify → receipt `onchain.memo_tx` → check on explorer.solana.com/?cluster=devnet
