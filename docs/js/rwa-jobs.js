// AegisAI RWA jobs client v1. Network API with local fallback. Miners get ciphertext + hash only.
export const RWA_API = 'https://agis-claim.onrender.com/api/rwa';
const j = async (u, o) => { const r = await fetch(u, o); const d = await r.json(); if (!r.ok || d.ok === false) throw new Error(d.error || r.status); return d; };
export const health = () => j(RWA_API + '/health', { signal: AbortSignal.timeout(8000) });
export const createJob = body => j(RWA_API + '/jobs', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
export const listJobs = (status = 'open') => j(RWA_API + '/jobs?status=' + status).then(d => d.jobs);
export const getJob = (id, full = false) => j(RWA_API + '/jobs/' + id + (full ? '?full=1' : '')).then(d => d.job);
export const b64 = buf => { let s = ''; const u = new Uint8Array(buf); for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000)); return btoa(s); };
// Integrity check without decrypting: fingerprint shape + ciphertext decodes + AES-GCM tag room.
export async function integrityCheck(id) {
  const job = await getJob(id, true), checks = [];
  const fpOk = /^[0-9a-f]{64}$/.test(job.fingerprint); checks.push('fingerprint:' + (fpOk ? 'ok' : 'bad'));
  let ctOk = true;
  if (job.ciphertextB64) { try { const n = atob(job.ciphertextB64).length; ctOk = n > 16; checks.push('ciphertext:' + n + 'B'); } catch { ctOk = false; checks.push('ciphertext:undecodable'); } }
  else checks.push('ciphertext:none');
  return { job, result: { ok: fpOk && ctOk, checks } };
}
// Sign + vote (Phantom). msg = AEGIS/rwa-vote/v1|wallet|jobId|fingerprint|ts
export async function vote(id, fingerprint, result) {
  const p = window.phantom?.solana || window.solana; if (!p) throw new Error('Phantom not found');
  const { publicKey } = await p.connect(), wallet = publicKey.toString();
  const msg = `AEGIS/rwa-vote/v1|${wallet}|${id}|${fingerprint}|${new Date().toISOString()}`;
  const { signature } = await p.signMessage(new TextEncoder().encode(msg), 'utf8');
  return j(RWA_API + '/jobs/' + id + '/vote', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ wallet, msg, sig: b64(signature), result }) });
}
if (typeof window !== 'undefined') window.agisRwa = { health, createJob, listJobs, getJob, integrityCheck, vote };
