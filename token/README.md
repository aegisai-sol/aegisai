# AegisAI (AGIS) — SPL Token

Fixed-supply SPL token: **1,000,000,000 AGIS**, **9 decimals**, **mint authority revoked**, **freeze authority revoked** (default).

> Default cluster is **devnet**. Mainnet requires `MAINNET=1` **and** `--yes-mainnet`. No keys are ever committed (`.keys/`, `.env` are gitignored). Never share a seed phrase with anyone, including bots.

## Developer allocation (required)
**LOCKED: 15% = 150,000,000 AGIS** (`AGIS_DEV_PCT=15`, the script default).
- Set `AGIS_DEV_WALLET=<pubkey>` — ideally a **vesting contract** escrow (Streamflow / Bonfida Token Vesting), not a hot wallet.
- Recommended vesting: **12-month linear unlock, optional 3-month cliff** (min 6 months). Create the stream right after mint; publish the stream link on the site.
- Order: create mint → mint 1B → transfer 15% dev → revoke mint (+freeze) → liquidity later (out of scope).
- **pump.fun cannot do this**: its fair launch has no reserved team allocation on the curve; the only way there is a disclosed creator first buy. A reserved, vested 15% requires **this direct SPL path** + own liquidity (Raydium/Meteora) later.

## Requirements
Node 18+ (tested on Node 24). `npm install`

## Steps (devnet)
```bash
npm install
npm run plan                 # dry run: prints exact steps + cost, no network
npm run keygen               # writes ./.keys/devnet.json (gitignored)
npm run airdrop              # 1 devnet SOL (or https://faucet.solana.com)
AGIS_DEV_WALLET=<pubkey> npm run create   # mint 1B, 15% to dev, revoke, verify
```
Result is written to `deployments/devnet.json` with an Explorer link. The script exits non-zero if mint authority is still set.

Options: `--keep-freeze` (skip freeze revoke; later `AGIS_MINT=<mint> npm run revoke-freeze`), `AGIS_MINT_KEYPAIR=./.keys/vanity.json` (vanity mint address from `solana-keygen grind`), `SOLANA_RPC=<url>` (Helius/QuickNode etc.), `AGIS_DECIMALS=6`.

## Mainnet
```bash
SOLANA_KEYPAIR=/secure/path/mainnet.json MAINNET=1 node scripts/create-token.mjs --yes-mainnet
```
Use a dedicated hot wallet holding only ~0.05 SOL. Phantom export path works if saved as a JSON byte array; prefer `solana-keygen new` on an offline machine.

## Cost
Mint rent ≈ 0.00146 SOL, ATA ≈ 0.00204 SOL, ~5 tx fees ≈ 0.000025 SOL → **< 0.01 SOL** total. Metadata (Metaplex) adds ≈ 0.01–0.02 SOL.

## Equivalent with solana-cli
```bash
spl-token create-token --decimals 9            # -> <MINT>
spl-token create-account <MINT>
spl-token mint <MINT> 1000000000
spl-token authorize <MINT> mint --disable
spl-token authorize <MINT> freeze --disable
spl-token display <MINT>                       # Mint authority: (not set)
```

## Metadata (name, symbol, logo)
Wallets show "Unknown token" until metadata exists. Add **before** launch with Metaplex Token Metadata (`@metaplex-foundation/mpl-token-metadata` `createMetadataAccountV3`, URI → JSON on Arweave/IPFS with `../aegisai-site/assets/agis-logo.png`), or use Token-2022 with the metadata extension. Metadata update authority can be kept for fixes then revoked (`isMutable=false`). Planned as a follow-up script.

## pump.fun alternative (NOT compatible with reserved dev %)
pump.fun creates its own mint (1B supply, 6 decimals, mint/freeze revoked, bonding curve → Raydium/PumpSwap migration). If launching there, **do not** run this script on mainnet — the pump mint becomes the official CA. Creator first buy is visible on-chain; disclose it. This repo then serves as devnet testing + documentation.

## Out of scope
Liquidity pools / LP, CEX listings — handled later.

## RPC
Probed 2026-10-31 00:58 (Europe/Sofia) from the box (JSON-RPC getHealth / getBalance):
| Endpoint | Result |
|---|---|
| https://api.devnet.solana.com | timeout (10s) |
| https://devnet.helius-rpc.com/?api-key=demo | Unauthorized |
| https://solana-devnet.gateway.tatum.io | getHealth ok, but getBalance = paid plan only → unusable |
| https://devnet.sonic.game | timeout |
| https://rpc.ankr.com/solana_devnet | API key required |
| https://solana-devnet.drpc.org | devnet not on free plan |
| https://devnet.solana.com | timeout |
| https://solana-devnet.api.onfinality.io/public | **works** (getVersion/getBalance; airdrop unsupported) |
No keyless devnet RPC works from the box; default stays `clusterApiUrl('devnet')`. Use a free-keyed RPC (Helius/Alchemy/QuickNode free tier): `SOLANA_RPC=<url> npm run create`, or run from another network.

## Metadata
`metadata/agis.json` must be hosted at `https://bold-thistle-3z5f.here.now/metadata/agis.json` (or set `AGIS_METADATA_URI`). `npm run create` now writes metadata (step 3c) before revoking mint authority. Standalone: `AGIS_MINT=<mint> npm run metadata` (only while mint authority is still held). Dry run: `npm run metadata:plan`.
