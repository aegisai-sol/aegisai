// PoV-R verify client. Tries coordinator POST /v1/verify; falls back to local mirror of aegis_miner/verify.py.
const FALSE_MARKERS = ["flat", "sun orbits", "always", "never", "100% guaranteed", "cure"];
const URL_RE = /https?:\/\/[^\s<>"')\]]+/;
const QUOTE_RE = /["\u201c\u201e]([^"\u201c\u201d\u201e]{4,})["\u201d\u201c]/;
const ARITH_RE = /(-?\d+(?:\.\d+)?)\s*([+\-*/x×])\s*(-?\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)/;
export const COORDINATOR = window.AEGIS_COORDINATOR || new URLSearchParams(location.search).get('coordinator') || localStorage.agisCoordinator || (location.hostname === 'localhost' ? 'http://localhost:8787' : '');
async function sha(s) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join(''); }
const LIST_RE = /^\s*(?:[-*\u2022\u2013]|\d{1,3}[.)]|\(\d{1,3}\)|[a-zA-Z][.)])\s+/;
const URL_GUARD = /https?:\/\/\S+?(?=[.,;:!?)\]]*(?:\s|$))/g;
export function splitSentences(t) {
  const out = [];
  for (let line of t.trim().split(/\n/)) {
    line = line.replace(LIST_RE, '').trim(); if (!line) continue;
    const urls = []; const g = line.replace(URL_GUARD, m => `\u0000${urls.push(m) - 1}\u0000`);
    for (let p of g.split(/(?<=[.!?])\s+(?=[A-Z0-9"\u201c\u201eА-Я])/)) { p = p.replace(/\u0000(\d+)\u0000/g, (_, i) => urls[+i]).trim(); if (p) out.push(p); }
  }
  return out;
}
export function tinyCheck(text) {
  const m = text.match(ARITH_RE);
  if (m) { const a = +m[1], b = +m[3], r = +m[4]; const v = { '+': a + b, '-': a - b, '*': a * b, 'x': a * b, '×': a * b, '/': b ? a / b : null }[m[2]]; if (v != null) return [Math.abs(v - r) < 1e-9, 0.99]; }
  const bad = FALSE_MARKERS.some(k => text.toLowerCase().includes(k)); return [!bad, bad ? 0.8 : 0.65];
}
export function checkClaim(c) {
  if (c.url) return { vote: 'UNSURE', confidence: 0, method: 'source', note: c.quote ? 'quote match needs coordinator (browser CORS blocks cross-site fetch)' : 'no quote to match; page fetch needs coordinator (CORS)' };
  const [ok, conf] = tinyCheck(c.text);
  if (ARITH_RE.test(c.text)) return { vote: ok ? 'TRUE' : 'FALSE', confidence: conf, method: 'arithmetic' };
  if (conf < 0.7) return { vote: 'UNSURE', confidence: conf, method: 'heuristic' };
  return { vote: ok ? 'TRUE' : 'FALSE', confidence: conf, method: 'heuristic' };
}
export async function verifyLocal(text, clientId) {
  const claims = [];
  for (const s of splitSentences(text).slice(0, 50)) {
    const c = { claim_id: (await sha(s)).slice(0, 12), text: s };
    const u = s.match(URL_RE); if (u) c.url = u[0].replace(/[.,;:]+$/, '');
    const q = s.match(QUOTE_RE); if (q) c.quote = q[1].trim();
    claims.push({ ...c, ...checkClaim(c) });
  }
  { const t = ['7 + 5 = 12','9 * 8 = 72','15 + 27 = 42'][Date.now() % 3]; const c = { claim_id: 'canary-local', text: t, canary: true, expected: 'TRUE' }; claims.push({ ...c, ...checkClaim(c) }); }
  const calOk = claims.filter(c => c.canary).every(c => c.vote === c.expected);
  const credits = !calOk ? 0 : claims.filter(r => !r.canary && r.confidence >= 0.7 && r.vote !== 'UNSURE').length;
  const rid = 'local-' + (await sha(text + Date.now())).slice(0, 16);
  const bal = (+(localStorage['agisCredits:' + clientId] || 0)) + credits; localStorage['agisCredits:' + clientId] = bal;
  return { receipt_id: rid, client_id: clientId, ts: Date.now() / 1000, claims, credits_awarded: credits, calibration: { ok: calOk }, flagged: !calOk, credits_balance: bal, onchain: 'PENDING (devnet memo later)', reservoir_note: 'Proof Credits are non-transferable; local demo receipt (coordinator offline).', source: 'local' };
}
export async function verify(text, clientId = 'web-demo') {
  if (COORDINATOR) {
    try {
      const r = await fetch(COORDINATOR.replace(/\/$/, '') + '/v1/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, client_id: clientId }), signal: AbortSignal.timeout(15000) });
      if (r.ok) return { ...(await r.json()), source: 'coordinator' };
    } catch {}
  }
  return verifyLocal(text, clientId);
}
