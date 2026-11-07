// AGIS PoV-R v2 browser solver. Real work, no shortcuts: every task is checked by actually
// multiplying, hashing (SHA-256) or testing primality. Same rules as the claim server
// (agis-claim pov-tasks.mjs). Works in browsers and Node 18+ (globalThis.crypto.subtle).
export const CLAIM_DOMAIN = 'AEGIS/mine-claim/v2';
const enc = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
export function isPrime(x) { if (!Number.isInteger(x) || x < 2) return false; for (let d = 2; d * d <= x; d++) if (x % d === 0) return false; return true; }
export async function sha256Hex(s) { return hex(await crypto.subtle.digest('SHA-256', enc.encode(s))); }

// Returns true/false verdict for one task string. Throws on an unknown task (never guesses).
export async function solveTask(text) {
  let m;
  if ((m = /^(\d+)\*(\d+)=(-?\d+)$/.exec(text))) return Number(m[1]) * Number(m[2]) === Number(m[3]);
  if ((m = /^sha256\((agis:[0-9a-f]+)\)\^([0-9a-f]{2})$/.exec(text))) return (await sha256Hex(m[1])).startsWith(m[2]);
  if ((m = /^prime\((\d+)\)$/.exec(text))) return isPrime(Number(m[1]));
  throw new Error('unknown task: ' + String(text).slice(0, 40));
}
export const taskKind = t => t[0] === 's' ? 'hash' : t[0] === 'p' ? 'prime' : 'multiply';

// Answer bits MSB-first, hex, length = ceil(n/8)*2 (exactly what the server grades).
export function encodeAnswers(bools) {
  const bytes = new Uint8Array(Math.ceil(bools.length / 8));
  bools.forEach((b, i) => { if (b) bytes[i >> 3] |= 0x80 >> (i & 7); });
  return hex(bytes);
}

// AEGIS/mine-claim/v2|wallet|batchId|answersHex|from|to|uuid|tier|cores|benchMs
export function buildClaimMsg({ wallet, batchId, answersHex, from, to, uuid, tier, cores, benchMs }) {
  const f = [wallet, batchId, answersHex, from, to, uuid, tier, cores, benchMs];
  if (f.some(x => x === undefined || x === null || String(x).includes('|'))) throw new Error('bad claim field');
  return [CLAIM_DOMAIN, ...f].join('|');
}

// Server clock is the reference for the work window: from = batch issuedAt (server time),
// to = issuedAt + locally measured elapsed time. Immune to a wrong phone clock.
export function workWindow(issuedAtIso, elapsedMs) {
  const t0 = Date.parse(issuedAtIso); if (!Number.isFinite(t0)) throw new Error('bad issuedAt');
  return { from: new Date(t0).toISOString(), to: new Date(t0 + Math.max(1000, Math.round(elapsedMs))).toISOString() };
}

// Fetch a wallet-bound batch. Render free tier may cold-start (~50 s), so allow a long timeout.
export async function fetchBatch(base, wallet, n = 120, timeoutMs = 75000) {
  const r = await fetch(`${base}/api/mine/tasks?wallet=${encodeURIComponent(wallet)}&n=${n}`, { signal: AbortSignal.timeout(timeoutMs), cache: 'no-store' });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.ok) throw new Error(j.error || 'claim server error ' + r.status);
  if (j.domain !== CLAIM_DOMAIN || !j.batchId || !Array.isArray(j.tasks) || !j.tasks.length) throw new Error('unexpected task batch format');
  return j;
}
export async function postClaim(base, body, timeoutMs = 90000) {
  const r = await fetch(`${base}/api/claim`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(timeoutMs) });
  const j = await r.json().catch(() => ({ ok: false, error: 'bad response ' + r.status }));
  return { status: r.status, ...j };
}

// Parse desktop --pov-wallet unsigned claim JSON for browser paste→sign.
// Accepts full prepare_claim output or a minimal {wallet,msg}. Returns {wallet,msg}.
export function parseDeskClaim(raw, connectedWallet) {
  let j = raw;
  if (typeof raw === 'string') {
    const t = raw.trim();
    if (!t) throw new Error('paste the desk claim JSON first');
    try { j = JSON.parse(t); } catch { throw new Error('not valid JSON'); }
  }
  if (!j || typeof j !== 'object' || Array.isArray(j)) throw new Error('claim must be a JSON object');
  const wallet = String(j.wallet || j.postBody?.wallet || '').trim();
  const msg = String(j.msg || j.postBody?.msg || '').trim();
  if (!wallet) throw new Error('missing wallet');
  if (!msg) throw new Error('missing msg');
  if (wallet.includes('|')) throw new Error('bad wallet');
  if (!msg.startsWith(CLAIM_DOMAIN + '|')) throw new Error('msg must start with ' + CLAIM_DOMAIN + '|');
  const parts = msg.split('|');
  if (parts.length !== 10) throw new Error('msg has wrong field count');
  if (parts[1] !== wallet) throw new Error('msg wallet does not match wallet field');
  if (connectedWallet != null && String(connectedWallet).trim() !== '') {
    if (String(connectedWallet).trim() !== wallet) throw new Error('connected wallet does not match desk claim wallet');
  }
  return { wallet, msg };
}

// Pure guard: auto-offer Phantom claim once when a paid browser batch finishes.
// Never for desk paste; never while a claim is in flight; wallet must match batch.
export function shouldAutoOfferClaim({ batch, walletId, claiming, deskClaiming }) {
  if (claiming || deskClaiming) return false;
  if (!walletId || !batch) return false;
  if (batch.wallet !== walletId) return false;
  if (!Array.isArray(batch.tasks) || !Array.isArray(batch.answers)) return false;
  if (batch.tasks.length === 0 || batch.answers.length !== batch.tasks.length) return false;
  if (batch.autoClaimOffered) return false;
  return true;
}
