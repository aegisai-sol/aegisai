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
