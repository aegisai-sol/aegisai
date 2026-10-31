// Data layer. MODE=mock now. Swap fetchStats() for Solana RPC / Helius indexer / DexScreener when CA exists.
export const CONFIG = { MODE: 'mock', COORDINATOR: localStorage.agisCoordinator || 'http://localhost:8787', MINT: null /* TBD */ };
let s = null;
export async function fetchStats() {
  if (CONFIG.MODE === 'live' && CONFIG.MINT) {
    const r = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${CONFIG.MINT}`).then(r => r.json());
    const p = r.pairs?.[0]; return { ...(s || {}), price: +p?.priceUsd || 0 };
  }
  try { const r = await fetch(CONFIG.COORDINATOR + '/api/stats', { signal: AbortSignal.timeout(1500) }); if (r.ok) return r.json(); } catch {}
  if (!s) s = await fetch('api/mock-stats.json').then(r => r.json());
  // drift mock so the dashboard feels live
  const last = s.priceHistory.at(-1); s.priceHistory.push(+(last * (1 + (Math.random() - 0.48) * 0.03)).toFixed(6)); s.priceHistory.shift();
  s.price = s.priceHistory.at(-1); s.holders += Math.random() < .4 ? 1 : 0; s.txCount += Math.floor(Math.random() * 9);
  s.activeNodes = Math.max(20, s.activeNodes + Math.round((Math.random() - .5) * 3));
  s.votesPerHour.push(Math.round(s.votesPerHour.at(-1) * (0.9 + Math.random() * .2))); s.votesPerHour.shift();
  return s;
}
export async function postVote(v) {
  try { const r = await fetch(CONFIG.COORDINATOR + '/api/vote', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(v), signal: AbortSignal.timeout(1500) }); return r.ok ? 'coordinator' : 'offline'; }
  catch { const q = JSON.parse(localStorage.agisVotes || '[]'); q.push(v); localStorage.agisVotes = JSON.stringify(q.slice(-500)); return 'local'; }
}
