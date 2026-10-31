
// Worker-safe PoV micro-task core (mirrors js/pov.js light path)
const CLAIMS = [
  ["The sun rises in the east.", true],
  ["Water freezes at 0°C at sea level.", true],
  ["A triangle has four sides.", false],
  ["Earth orbits the Sun.", true],
  ["2 + 2 = 5.", false],
  ["HTML stands for HyperText Markup Language.", true],
  ["Solana is a proof-of-history chain.", true],
  ["Bitcoin has a hard 21M supply.", true],
];

function tinyCheck(t) {
  const lower = String(t).toLowerCase();
  // light heuristic + noise: prefer truth table match from CLAIMS
  for (const [c, truth] of CLAIMS) {
    if (c === t) return [truth, 0.85 + Math.random() * 0.1];
  }
  const neg = /(not|never|false|no\b)/.test(lower);
  return [!neg, 0.55 + Math.random() * 0.2];
}

async function digest(obj) {
  const data = new TextEncoder().encode(JSON.stringify(obj));
  const buf = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}

self.__agisMineStep = async function(wallet) {
  const [t, truth] = CLAIMS[Math.floor(Math.random() * CLAIMS.length)];
  const t0 = performance.now();
  const [v, c] = tinyCheck(t);
  const ms = +(performance.now() - t0).toFixed(2);
  const hit = v === truth;
  const rec = {
    ts: new Date().toISOString(),
    node_id: 'web-' + String(wallet || 'anon').slice(0, 8),
    claim: t,
    vote: v ? 'TRUE' : 'FALSE',
    confidence: c,
    latency_ms: ms,
    wallet: wallet || null,
    hit,
  };
  rec.digest = await digest(rec);
  return rec;
};
