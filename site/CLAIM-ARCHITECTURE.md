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

## RWA jobs API v1 (live path)

RWA here = **document verification** (not tokenization). The file is SHA-256 fingerprinted and AES-256-GCM encrypted in the browser; the key never leaves the user. The claim server (`agis-claim.onrender.com`) stores jobs under `./deployments/rwa-jobs/` (`index.json` + `<id>.b64` ciphertext).

| Method | Path | Notes |
|---|---|---|
| POST | `/api/rwa/jobs` | `{fingerprint, meta:{type,pages,name?,iv?,bytes?}, ciphertextB64?, rewardEstimate?}` → `{ok,id,created}`; body max 4 MB |
| GET | `/api/rwa/jobs?status=open\|verified\|failed\|all` | list, no ciphertext |
| GET | `/api/rwa/jobs/:id[?full=1]` | detail; `full=1` adds ciphertext for miners |
| POST | `/api/rwa/jobs/:id/vote` | `{wallet,msg,sig,result:{ok,checks[]}}`, msg = `AEGIS/rwa-vote/v1|wallet|jobId|fingerprint|ts`, ed25519 verified; threshold `RWA_VOTES` (default 1) → `verified`/`failed` |
| GET | `/api/rwa/health` | `{rwa:true,jobs,open}` (also in `/api/health`) |

Rate limits per IP: 120 GET / 20 POST per minute. Client: `site/js/rwa-jobs.js` (`window.agisRwa.listJobs / integrityCheck / vote`) — the miner can call it in the next patch. `rwa.html` uses the network when it's reachable and falls back to the local queue. Not built yet: Solana memo receipt, fee burn, CDN storage. Note: Render disk is ephemeral unless a persistent disk is attached.

## RWA seal receipt on Solana (v1)
"Seal a file" = notarize a real file (invoice, receipt, deed scan, PDF, photo, video, Excel). Not tokenization.
When a job reaches `verified`/`failed`, the claim server sends one **Solana Memo** tx from the payer (mint-auth) key:
`AEGIS/rwa/v1|<jobId>|<sha256>|<status>` (program `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`).
- Job JSON gets `receiptTx` (signature → Solscan), `receiptAt`, `receiptError`.
- No keypair or payer SOL < 0.003 → `receiptTx:null` + `receiptError`; the vote still succeeds. Disable with `RWA_MEMO=0`.
- Only hash + status + time go on chain; file content never does. Private mode sends an AES-GCM ciphertext to miners; public anchor sends the hash only.
- Cost ≈ 5,000 lamports per seal (base fee).

## RWA seal privacy (v1.1)
- File is hashed (SHA-256) and, in Private mode (default), encrypted with AES-256-GCM **in the browser** before it leaves the device. Filename and MIME are inside the encrypted envelope.
- Server/miners store and see only: ciphertext, fingerprint, IV, coarse type, size. Miners vote without decrypting.
- Server rejects any key/secret/password/plaintext field. We never hold the key; lost key = unrecoverable.
- On-chain: permanent Solana Memo `AEGIS/rwa/v1|sealId|fingerprint|status` — no expiry, no personal data.
- Retrieve: user enters Seal ID + key → page GETs `/api/rwa/jobs/:id?full=1` (ciphertext) → decrypts locally → re-checks fingerprint → preview via blob URL. The key is never sent.
- localStorage keeps seal IDs; keys only if the user ticks "save key on this device". Sharing = user gives key off-platform.
- GDPR: uploader is controller; only ciphertext off-chain (deletable), hash on-chain.

## RWA recovery (Wave A + A2)
- **A · Same file:** `GET /api/rwa/by-fingerprint/:sha256` (or `?fp=`) → public fields only (id, status, receiptTx, created, minimal meta, `walletRecovery` flag). Lost phone but have the file → re-hash → proof, no key. `proof.html?id=` / `?fp=` = status + Solscan.
- **A2 · Wallet-bound key wrap (lost phone AND lost `agis1:` key):** on Private seal (checkbox, default ON when Phantom connected) the browser signs `AEGIS/rwa-keywrap/v1|wallet|sealId|fp` in Phantom; wrap key = HKDF-SHA256(ikm=signature, salt="AEGIS/rwa-keywrap/v1", info=`sealId|fp`) → AES-GCM-256; blob = b64(iv12‖AESGCM(rawKey)). Ed25519 is deterministic → same wallet re-derives on any device. The derivation signature never leaves the browser. Blob attached via `POST /api/rwa/jobs/:id/keywrap` authorised by a *separate* signature `AEGIS/rwa-keywrap-attach/v1|wallet|id|fp|ts`; write-once. Job fields: `keyWrap`, `wrapWallet`, `wrapAlg`. Retrieve → "Unlock with wallet" → sign → unwrap → decrypt locally.
- Honesty: we never custody keys; only that wallet can unwrap; nobody can forge a wrap for another wallet's seal (attach requires that wallet's signature, write-once). Caveat: a wallet that signs the exact keywrap message on a phishing site leaks that seal's wrap key — only sign on aegisai-sol.github.io.
- **Seed also lost:** social recovery 2-of-3 guardians (Shamir shares of the AES key, each wrapped to a guardian wallet) — stub/TODO, not implemented.
