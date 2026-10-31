# AGIS — Exchange Listing Path (no promises)

**Order:** DEX liquidity → trackers → small CEX → mid/large CEX. No listing is guaranteed; prices below are approximate and change.

1. **DEX pool (first)** — Raydium CPMM (pool creation fee ≈0.15–0.2 SOL + rent) or Meteora DLMM/DAMM (≈0.05–0.1 SOL rent). Real cost is the liquidity itself (both AGIS and SOL/USDC). Consider locking/burning LP tokens for trust.
2. **Trackers** — DexScreener (auto; paid profile ≈$299), Jupiter strict/verified list, Birdeye, then CoinGecko & CoinMarketCap applications (free; need live trading, website, explorer, socials).
3. **Before CEX** — third-party smart-contract/token audit, decide on mint authority (revoke or multisig + published emission schedule), transparent team/eco wallets, steady volume & holders.
4. **Small/mid CEX** — MEXC, Gate, BitMart, LBank: application via their listing forms; typically ask for listing/marketing fees (often tens of thousands USD), market-maker, KYC of team.
5. **Larger CEX** — Bitget, BloFin (futures-focused; usually lists after strong spot volume elsewhere), KuCoin, OKX: require audit, legal opinion, significant volume/community. Apply only after steps 1–4.

Never pay "listing agents" who promise guaranteed listings — common scam.

## Status — 2026-10-31 13:25 (Europe/Sofia)
- **Claim API:** server is ready (rate limits 10/min per IP, 5/min per wallet, 100 AGIS/day per wallet cap, `/api/health`). Public HTTPS host pending (Railway: `token/Dockerfile`, secret `MINT_AUTH_JSON`, `MAINNET=1`, volume on `/app/deployments` for the ledger). Miner `agis-claim-url` stays empty → Claim mint OFF until set.
- **LP:** payout wallet holds ~0.135 SOL. Raydium CPMM needs ~0.15–0.2 SOL in fees/rent **plus** SOL to seed the pool. Minimum sensible: **~0.5–1 SOL extra** (≈0.4–0.9 SOL short). Team/eco wallets are not touched.
- **DexScreener:** listed automatically once a Raydium/Meteora pool exists. After that, "Enhanced Token Info" (logo, socials) costs ~$299 at marketplace.dexscreener.com.
- **Jupiter:** routes to the pool automatically after it's indexed. Verification at catdetlist.jup.ag (needs metadata, socials, liquidity/volume).
- **Checklist:** ✅ Metaplex metadata/logo · ✅ website/whitepaper · ⏳ X/Telegram links in metadata · ⏳ LP + lock/burn LP tokens · ⏳ DexScreener info · ⏳ Jupiter verify · ❌ audit.


## Status — 2026-10-31 13:41 Europe/Sofia
- **Claim API LIVE:** https://agis-claim.onrender.com (`/api/health` OK). Miner `agis-claim-url` → `/api/claim`.
- **LP / DexScreener / Jupiter:** still blocked on ~0.5–1 SOL for pool (wallet ~0.13 SOL).
