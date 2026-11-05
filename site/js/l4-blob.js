// L4 prep: client-side encrypted blob package for decentralized storage (IPFS/Arweave).
// Honest status: encrypt + hash + download package are LIVE; public pin / CID-on-Memo are SCAFFOLD.
// Memo design (not auto-written yet — keeps AEGIS/rwa/v1 parsers intact):
//   AEGIS/rwa-blob/v1|<sealId12>|<blobHash64>|<cidOr->
// Proof JSON may carry blobHash / blobCid alongside the seal. Server never gets decrypt keys.
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');

export async function sha256Hex(buf) {
  return hex(await crypto.subtle.digest('SHA-256', buf instanceof ArrayBuffer ? buf : new Uint8Array(buf)));
}

/** Build an L4 package from already-encrypted ciphertext (never plaintext). */
export async function buildL4Package({ sealId, fingerprint, ivHex, enc = 'aes-gcm-env1', ciphertext, passphraseWrap = null, meta = {} }) {
  const ct = ciphertext instanceof Uint8Array ? ciphertext : new Uint8Array(ciphertext);
  const blobHash = await sha256Hex(ct);
  let s = '';
  for (let i = 0; i < ct.length; i += 0x8000) s += String.fromCharCode(...ct.subarray(i, i + 0x8000));
  const pkg = {
    v: 'AEGIS/l4/v1',
    sealId: sealId || null,
    fingerprint,
    enc,
    iv: ivHex,
    blobHash,
    blobCid: null, // filled when a pin provider returns a CID
    ciphertextB64: btoa(s),
    passphraseWrap: passphraseWrap || undefined,
    meta: { ...meta, created: new Date().toISOString(), pinStatus: 'local-only' },
    memoHint: sealId ? `AEGIS/rwa-blob/v1|${sealId}|${blobHash}|-` : null,
    note: 'Encrypted on your device. Pin this file to IPFS/Arweave yourself (or wait for built-in pin). Put memoHint on Solana when ready. We never hold the key.',
  };
  return pkg;
}

export function downloadL4Package(pkg, filename) {
  const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || `agis-l4-${pkg.sealId || 'local'}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** Scaffold only — never claim success. Returns null until a pin JWT exists. */
export async function tryPinL4(_pkg) {
  // No Pinata / web3.storage / nft.storage keys on this box. Bring-your-own pin next.
  return { ok: false, reason: 'No pin provider configured. Download the L4 package and pin it yourself (IPFS desktop, Pinata, web3.storage).' };
}

export function l4StatusCopy() {
  return {
    live: ['Client AES-256-GCM encrypt', 'SHA-256 of ciphertext (blobHash)', 'Downloadable AEGIS/l4/v1 package', 'Memo field design AEGIS/rwa-blob/v1'],
    scaffold: ['Optional blobCid on proof JSON', 'UI storage choice'],
    blocked: ['Automatic IPFS/Arweave pin (no provider key)', 'Auto second Memo with CID', 'Gateway retrieve by CID'],
  };
}
