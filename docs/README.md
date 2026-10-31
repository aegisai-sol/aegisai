# AegisAI Site (Tailwind CDN, static)

Pages: `index.html` (pitch, PoV, utility, tokenomics 1B / 15% dev vested / mint+freeze revoked, roadmap, NFA), `dashboard.html` (Chart.js live stats), `miner.html` (browser/PWA miner), `manifest.webmanifest` + `sw.js` (installable, offline).

Run: `python3 -m http.server 8080` → http://localhost:8080 . Optional live data: `cd ../aegisai-miner && python3 -m aegis_miner.coordinator`.

- **Wallet** (`js/wallet.js`): Phantom via `window.phantom.solana`; connect / disconnect, truncated pubkey, auto-reconnect if trusted, shows "Install Phantom" when absent. Read-only identity — never requests keys or signatures for funds.
- **Data layer** (`js/api.js`): `MODE='mock'` → coordinator `/api/stats` → fallback `api/mock-stats.json` with drift. Set `MINT` + `MODE='live'` to pull price from DexScreener; add Helius/RPC `getTokenLargestAccounts`/indexer for holders/txs.
- **PoV logic** (`js/pov.js`) mirrors the Python `tiny_check`.
- Mobile: open `miner.html` in Chrome (Android) or Safari (iOS) → Add to Home Screen. Background mining on iOS is limited by the OS (runs while open).
- CA shows **TBD** until the token exists. `index.v1.html` = previous version.
