// AegisAI RWA jobs client v1. Network API with local fallback. Miners get ciphertext + hash only.
export const RWA_API = 'https://agis-claim.onrender.com/api/rwa';
const j = async (u, o) => { const r = await fetch(u, o); const d = await r.json(); if (!r.ok || d.ok === false) throw new Error(d.error || r.status); return d; };
export const health = () => j(RWA_API + '/health', { signal: AbortSignal.timeout(8000) });
export const createJob = body => j(RWA_API + '/jobs', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
export const listJobs = (status = 'open') => j(RWA_API + '/jobs?status=' + status).then(d => d.jobs);
export const getJob = (id, full = false) => j(RWA_API + '/jobs/' + id + (full ? '?full=1' : '')).then(d => d.job);
// Recovery: public proof by fingerprint (no key). Falls back to list scan if server not yet redeployed.
export const byFingerprint = fp => j(RWA_API + '/by-fingerprint/' + fp).then(d => d.seals).catch(() => listJobs('all').then(a => a.filter(x => x.fingerprint === fp)));
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
if (typeof window !== 'undefined') window.agisRwa = { health, byFingerprint, wrapKey: (...a) => wrapKey(...a), unwrapKey: (...a) => unwrapKey(...a), createJob, listJobs, getJob, integrityCheck, vote };
// ── Wave A2: wallet-bound key wrap (recovery when phone AND agis1: key file are lost) ──
// wrapKey = HKDF-SHA256(ikm = Phantom ed25519 signature of `AEGIS/rwa-keywrap/v1|wallet|sealId|fp`,
//   salt = "AEGIS/rwa-keywrap/v1", info = sealId|fp) -> AES-GCM-256; blob = b64(iv12 || AESGCM(rawKey32)).
// Ed25519 signatures are deterministic, so the same wallet re-derives the same wrap key on any device.
// The derivation signature never leaves the browser; the server gets only the blob, via a separate attach signature.
// Only that wallet can unwrap; nobody can forge a wrap for another wallet. Seed lost too -> social recovery
// (2-of-3 guardians holding Shamir shares) is a TODO stub, not implemented.
const enc = s => new TextEncoder().encode(s);
const phantom = async () => { const p = window.phantom?.solana || window.solana; if (!p) throw new Error('Phantom not found'); const { publicKey } = await p.connect(); return { p, wallet: publicKey.toString() }; };
async function deriveWrapKey(p, wallet, id, fp) {
  const { signature } = await p.signMessage(enc(`AEGIS/rwa-keywrap/v1|${wallet}|${id}|${fp}`), 'utf8');
  const ikm = await crypto.subtle.importKey('raw', signature, 'HKDF', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'HKDF', hash: 'SHA-256', salt: enc('AEGIS/rwa-keywrap/v1'), info: enc(id + '|' + fp) }, ikm, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}
const unhex = h => new Uint8Array(h.match(/../g).map(x => parseInt(x, 16)));
export async function wrapKey(id, fp, agisKey) {
  const { p, wallet } = await phantom(), W = await deriveWrapKey(p, wallet, id, fp), iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, W, unhex(agisKey.replace(/^agis1:/, ''))));
  const blob = new Uint8Array(12 + ct.length); blob.set(iv); blob.set(ct, 12);
  const msg = `AEGIS/rwa-keywrap-attach/v1|${wallet}|${id}|${fp}|${Date.now()}`, { signature } = await p.signMessage(enc(msg), 'utf8');
  return j(RWA_API + '/jobs/' + id + '/keywrap', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ wallet, msg, sig: b64(signature), keyWrap: b64(blob) }) });
}
export async function unwrapKey(job) {
  if (!job.keyWrap) throw new Error('No wallet recovery on this seal');
  const { p, wallet } = await phantom(); if (wallet !== job.wrapWallet) throw new Error('Connect the wallet that sealed it: ' + job.wrapWallet);
  const W = await deriveWrapKey(p, wallet, job.id, job.fingerprint), blob = Uint8Array.from(atob(job.keyWrap), c => c.charCodeAt(0));
  const raw = new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: blob.slice(0, 12) }, W, blob.slice(12)));
  return 'agis1:' + [...raw].map(x => x.toString(16).padStart(2, '0')).join('');
}
