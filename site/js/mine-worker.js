/* PRACTICE ONLY — local synthetic tasks. Does NOT earn AGIS and must never POST /api/claim.
   Paid mining uses miner.html → miner-worker.js (solve/solveBatch) → wallet sign → /api/claim. */
importScripts('./pov-worker-core.js');

let timer = null;
let wallet = null;
let n = 0, ok = 0, score = 0;

self.onmessage = (e) => {
  const msg = e.data || {};
  if (msg.type === 'start') {
    wallet = msg.wallet || null;
    if (timer) clearInterval(timer);
    timer = setInterval(tick, msg.intervalMs || 1000);
    self.postMessage({ type: 'status', running: true, practice: true });
  } else if (msg.type === 'stop') {
    if (timer) clearInterval(timer);
    timer = null;
    self.postMessage({ type: 'status', running: false, practice: true });
  } else if (msg.type === 'wallet') {
    wallet = msg.wallet || null;
  } else if (msg.type === 'ping') {
    self.postMessage({ type: 'pong', n, ok, score, running: !!timer, practice: true });
  }
};

async function tick() {
  try {
    const rec = await self.__agisMineStep(wallet);
    n++;
    ok += rec.hit ? 1 : 0;
    score = +(score + rec.confidence * (rec.hit ? 1 : -1)).toFixed(2);
    self.postMessage({ type: 'tick', rec, n, ok, score, practice: true });
  } catch (err) {
    self.postMessage({ type: 'error', error: String(err && err.message || err), practice: true });
  }
}
