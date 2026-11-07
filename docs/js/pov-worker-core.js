// Worker-safe PoV-R micro-solver (same kinds as claim-server / pov-solver.js).
// No trivia table. Wallet required — anonymous mining is not a thing.
const enc = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
function isPrime(x) { if (!Number.isInteger(x) || x < 2) return false; for (let d = 2; d * d <= x; d++) if (x % d === 0) return false; return true; }
async function sha256Hex(s) { return hex(await crypto.subtle.digest('SHA-256', enc.encode(s))); }
async function solveTask(text) {
  let m;
  if ((m = /^(\d+)\*(\d+)=(-?\d+)$/.exec(text))) return Number(m[1]) * Number(m[2]) === Number(m[3]);
  if ((m = /^sha256\((agis:[0-9a-f]+)\)\^([0-9a-f]{2})$/.exec(text))) return (await sha256Hex(m[1])).startsWith(m[2]);
  if ((m = /^prime\((\d+)\)$/.exec(text))) return isPrime(Number(m[1]));
  throw new Error('unknown task');
}
// PRACTICE ONLY — deterministic local tasks. Never paid. Paid claims: miner.html → miner-worker solve → /api/claim.
function practiceTask(seed) {
  const kind = seed % 3;
  if (kind === 0) { const a = 100 + (seed % 900), b = 100 + ((seed * 7) % 900); return `${a}*${b}=${a * b}`; }
  if (kind === 1) { const s = 'agis:' + (seed * 7919).toString(16).slice(0, 12).padStart(12, '0'); return `sha256(${s})^00`; }
  return `prime(${1001 + (seed % 60000)})`;
}
self.__agisMineStep = async function(wallet) {
  if (!wallet) throw new Error('wallet required');
  const seed = (Date.now() ^ (wallet.charCodeAt(0) << 8)) >>> 0;
  const text = practiceTask(seed);
  const t0 = performance.now();
  const vote = await solveTask(text);
  const ms = +(performance.now() - t0).toFixed(2);
  const data = new TextEncoder().encode(JSON.stringify({ text, vote, wallet }));
  const buf = await crypto.subtle.digest('SHA-256', data);
  return {
    ts: new Date().toISOString(),
    node_id: 'web-' + String(wallet).slice(0, 8),
    claim: text,
    vote: vote ? 'TRUE' : 'FALSE',
    confidence: 0.99,
    latency_ms: ms,
    wallet,
    hit: true,
    digest: hex(buf).slice(0, 16),
    practice: true,
  };
};
self.__agisSolveTask = solveTask;
