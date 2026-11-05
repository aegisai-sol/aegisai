// Passphrase wrap for seal AES keys (device theft hardening).
// PBKDF2-SHA-256 @ 600k iters + AES-256-GCM (native Web Crypto — no Argon2 wasm dep).
// Never send passphrase or raw agis1 key to the claim API.
const TEX = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
const unhex = h => new Uint8Array(String(h).match(/../g).map(x => parseInt(x, 16)));
export const WRAP_ALG = 'pbkdf2-sha256-aes-gcm';
export const WRAP_ITERS = 600000;

async function derive(pass, salt, usages) {
  const base = await crypto.subtle.importKey('raw', TEX.encode(pass), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations: WRAP_ITERS },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    usages
  );
}

/** @param {string} agisKey  agis1: + 64 hex */
export async function wrapWithPassphrase(agisKey, passphrase, sealId) {
  if (!passphrase || passphrase.length < 8) throw new Error('Passphrase must be at least 8 characters');
  const rawHex = String(agisKey).replace(/^agis1:/i, '').toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(rawHex)) throw new Error('Bad seal key');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const K = await derive(passphrase, salt, ['encrypt']);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, K, unhex(rawHex)));
  return {
    v: 1,
    alg: WRAP_ALG,
    iter: WRAP_ITERS,
    salt: hex(salt),
    iv: hex(iv),
    wrap: hex(ct),
    sealId: sealId || undefined,
  };
}

/** @returns {string} agis1:hex */
export async function unwrapWithPassphrase(blob, passphrase) {
  if (!blob || blob.alg !== WRAP_ALG) throw new Error('Unsupported wrap format');
  const iters = blob.iter || WRAP_ITERS;
  const salt = unhex(blob.salt), iv = unhex(blob.iv);
  const base = await crypto.subtle.importKey('raw', TEX.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  const K = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations: iters },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt']
  );
  let raw;
  try {
    raw = new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, K, unhex(blob.wrap)));
  } catch {
    throw new Error('Wrong passphrase — cannot unlock key');
  }
  return 'agis1:' + hex(raw);
}

export function loadWraps() {
  try { return JSON.parse(localStorage.agisSealKeyWraps || '{}'); } catch { return {}; }
}
export function saveWrap(sealId, blob) {
  const all = loadWraps();
  all[sealId] = blob;
  localStorage.agisSealKeyWraps = JSON.stringify(all);
}
export function getWrap(sealId) {
  return loadWraps()[sealId] || null;
}
