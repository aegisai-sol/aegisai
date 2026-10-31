# AegisAI (AGIS) — The Verification Layer for Trustworthy AI

**Proof-of-Verification (PoV)**: AI output is split into micro-claims, verified by a global network of phones, PCs and servers, agreed by stake × reputation consensus, and sealed on Solana as auditable receipts. Nodes earn AGIS for useful work; companies get AI they can trust.

- 📄 Protocol paper: [`docs/PROOF_OF_VERIFICATION.md`](docs/PROOF_OF_VERIFICATION.md) · BG: [`docs/POV-BG.md`](docs/POV-BG.md)
- 🏗 Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 🤝 Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)

> Status: **Phase 0 (mock)** — verification is simulated; token not minted; no contract address exists yet. Beware of fakes.

## 5-minute onboarding
1. Site + browser node: `cd ../aegisai-site && python3 -m http.server 8080` → http://localhost:8080 (Protocol, Dashboard, Mine in browser).
2. Python node: `cd ../aegisai-miner && python3 -m aegis_miner.coordinator &` then `AEGIS_COORDINATOR=http://localhost:8787 python3 main.py --seconds 30`.
3. Token (devnet only): `cd ../aegisai-token && npm install && npm run plan`.

## Hosting (static, no secrets)
`aegisai-site/` is pure static. Any of: `npx wrangler pages deploy aegisai-site` (Cloudflare Pages), `npx vercel aegisai-site --prod`, `netlify deploy --dir aegisai-site --prod`, or GitHub Pages from a repo. Dashboard falls back to mock data when no coordinator is reachable.

---
## Components

| Part | Path | Stack |
|---|---|---|
| Token | [`/workspace/aegisai-token`](../aegisai-token/README.md) | Node, @solana/web3.js, @solana/spl-token |
| Website + dashboard + browser miner | [`/workspace/aegisai-site`](../aegisai-site/README.md) | HTML, Tailwind CDN, Chart.js, Phantom, PWA |
| Python miner + mock coordinator | [`/workspace/aegisai-miner`](../aegisai-miner/README.md) | Python 3 stdlib (+ `solders` for real txs) |

## Token facts (locked)
1,000,000,000 AGIS · 9 decimals · mint authority revoked · freeze revoked · **developer 15% (150M) in vesting** (proposed: 3-mo cliff + 12-mo linear via Streamflow) · 85% public/liquidity. Launch path: **direct SPL mint** (pump.fun fair launch can't reserve a vested team share).

## Quick start
```bash
cd /workspace/aegisai-token && npm install && npm run plan && npm run keygen && npm run airdrop && AGIS_DEV_WALLET=<pubkey> npm run create
cd /workspace/aegisai-miner && python3 -m aegis_miner.coordinator &   # mock API :8787
AEGIS_COORDINATOR=http://localhost:8787 python3 main.py --seconds 30
cd /workspace/aegisai-site && python3 -m http.server 8080              # http://localhost:8080
```

## Status
- [x] Brand, logo, site (Tailwind) with Phantom connect
- [x] Tokenomics with 15% vested dev allocation
- [x] SPL create → mint 1B → dev 15% transfer → revoke mint/freeze script (devnet default, mainnet gated)
- [x] Python miner: simulation + coordinator + Solana Memo submit
- [x] Browser/PWA miner (Android/iOS/any OS) + live dashboard (mock data)
- [ ] Devnet run of create-token (needs devnet SOL)
- [ ] Metaplex metadata script (name/symbol/logo)
- [ ] Vesting stream for 15% (Streamflow) — published link
- [ ] Real coordinator, consensus, rewards; tiny model
- [ ] Hosting + domain, X account, community
- [ ] Mainnet mint, liquidity/LP (later, out of scope), CEX
- [ ] Native mobile apps

## Security
No private keys or seeds in any repo (`.keys/`, `.env` gitignored). Never share a seed phrase. Mainnet requires `MAINNET=1 --yes-mainnet`. Not financial advice.

### Receipt HMAC + claim normalizer v2
- `AEGIS_RECEIPT_HMAC=<secret>`: coordinator adds `mac` (HMAC-SHA256 over the receipt digest); `/v1/gate` and `/v1/gate/batch` return **DENY** for receipts with a missing or bad MAC. Unset = no MAC required. The secret is never logged or returned.
- Claims are normalized with versioned `claim_norm` v2 (NFKC, smart quotes/dashes → ASCII, zero-width stripped). The gate matches v1 and v2 digests for back-compat.
