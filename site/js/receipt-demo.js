// Client-side mirror of miner/aegis_miner/consensus.py status rules + reservoir.py split_fee (integer micro-units).
// Demo only: no token, no mint. Used by verify.html when no coordinator is reachable.
export const SPLIT_BPS = { miners: 7000, reservoir: 2000, treasury: 500, burn: 500 };
export function splitFee(fee, votes, flagged = false) {
  const parts = {}; for (const [k, b] of Object.entries(SPLIT_BPS)) parts[k] = Math.floor(fee * b / 10000);
  parts.reservoir += fee - Object.values(parts).reduce((a, b) => a + b, 0);
  const payouts = {}, w = Object.fromEntries(Object.entries(votes || {}).filter(([, x]) => x > 0));
  const tot = Object.values(w).reduce((a, b) => a + b, 0);
  if (flagged || !tot) parts.reservoir += parts.miners;
  else { let paid = 0; for (const n of Object.keys(w).sort()) { payouts[n] = Math.floor(parts.miners * w[n] / tot); paid += payouts[n]; } parts.reservoir += parts.miners - paid; }
  parts.miners = Object.values(payouts).reduce((a, b) => a + b, 0);
  return { fee_micro: fee, parts, payouts, flagged };
}
export function consensusStatus(perNode, quorum = 2) {
  const cnt = a => a.reduce((m, x) => (m[x] = (m[x] || 0) + 1, m), {}), top = m => Object.entries(m).sort((a, b) => b[1] - a[1])[0] || [null, 0];
  const [h, hn] = top(cnt(perNode.filter(r => r.source_hash && !r.error).map(r => r.source_hash)));
  const [v, vn] = top(cnt(perNode.filter(r => r.vote && !r.error).map(r => r.vote)));
  const hashOk = hn >= quorum, voteOk = vn >= quorum && v !== 'UNSURE';
  const status = hashOk && voteOk ? 'VALID' : voteOk ? 'VALID_VERDICT' : hashOk ? 'HASH_ONLY' : 'NO_CONSENSUS';
  return { status, quorum, nodes: perNode.length, valid: status.startsWith('VALID'), consensus_hash: hashOk ? h : null, consensus_vote: voteOk ? v : null, hash_agree: hn, vote_agree: vn, per_node: perNode };
}
export const SCENARIOS = {
  valid: [{ node: 'self', vote: 'TRUE', source_hash: '9f2c1a7be04d' }, { node: 'peer0', vote: 'TRUE', source_hash: '9f2c1a7be04d' }, { node: 'peer1', vote: 'TRUE', source_hash: '9f2c1a7be04d' }],
  dynamic: [{ node: 'self', vote: 'TRUE', source_hash: '9f2c1a7be04d' }, { node: 'peer0', vote: 'TRUE', source_hash: '41ab08c3d9e2' }, { node: 'peer1', vote: 'TRUE', source_hash: 'c07e55f1a2b8' }],
  split: [{ node: 'self', vote: 'TRUE', source_hash: '9f2c1a7be04d' }, { node: 'peer0', vote: 'FALSE', source_hash: '9f2c1a7be04d' }, { node: 'peer1', vote: 'UNSURE', error: 'timeout' }],
};
// Canonical JSON (sorted keys, compact) — mirrors aegis_miner.consensus.canonical_json / receipt_digest.
export function canonicalJson(x) {
  if (x === null || typeof x !== 'object') return JSON.stringify(x);
  if (Array.isArray(x)) return '[' + x.map(canonicalJson).join(',') + ']';
  return '{' + Object.keys(x).sort().map(k => JSON.stringify(k) + ':' + canonicalJson(x[k])).join(',') + '}';
}
export function receiptBody(c, f) {
  return { status: c.status, quorum: c.quorum, consensus_hash: c.consensus_hash, consensus_vote: c.consensus_vote,
    per_node: c.per_node.map(n => ({ node: n.node, vote: n.vote ?? null, source_hash: n.source_hash ?? null, error: n.error ?? null })),
    fee_micro: f.fee_micro, parts: f.parts, payouts: f.payouts, flagged: f.flagged };
}
export async function receiptDigest(body) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(body)));
  return 'sha256:' + [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}
