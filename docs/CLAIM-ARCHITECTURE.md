# AGIS Claim Architecture (light · scalable · secure)

## 1. Split
- **Static site** (GitHub Pages / CDN): UI, miner, RWA client-side encryption. No secrets.
- **Claim API** (separate VPS/Railway, later): verifies claims and mints AGIS. **Only place the mint authority key lives** (env/HSM, never in git).
- Browser never holds, sees, or requests the mint key.

## 2. Device load
- Mining tick runs in a Web Worker; **≤1 task/sec** enforced in code (guard + single task per tick).
- Tiny CPU checks only, **no GPU**; phone tier ×1, reward weight capped ×2.
- When the tab is hidden, charts/UI redraw pause; Wake Lock is optional (only while visible).
- RWA jobs are size-capped; for always-on mining use the desktop miner.

## 3. Site load
- Static files served from CDN — no server to overload.
- Claims are tiny JSON POSTs (`{wallet,msg,sig}` < 1 KB), batched by the user (one Claim, not per task).
- Claim API: rate limit per IP and per wallet (e.g. 5/min/IP, 1 claim/10 min/wallet).
- No large uploads on the claim path; RWA content is encrypted client-side and stored separately — miners never read content.

## 4. Security
- Ed25519 wallet signature over `AEGIS/mine-claim/v1|wallet|units|from|to|uuid`.
- Replay protection: uuid stored server-side, timestamps must be recent and non-overlapping.
- Caps: 25 AGIS/job, 100 AGIS/wallet/day, global daily emission cap.
- CORS allowlist (site origin only), HTTPS only, no public admin UI, logs + alerting on mint.

## 5. Rollout
1. ✅ Miner protections live (≤1/s, worker, hidden-pause, light-load badge).
2. ⏳ Deploy claim API on a host (not yet) with the rules above.
3. ⏳ Set `<meta name="agis-claim-url" content="https://…/claim">` in `miner.html`. Until then, **Claim mint is OFF** — signed claims are saved locally only.


## Live Claim (2026-10-31)
- Public API: `https://agis-claim.onrender.com`
- Health: `GET /api/health`
- Miner meta `agis-claim-url`: `https://agis-claim.onrender.com/api/claim`
- Host: Render free (cold start ~50s after idle)
