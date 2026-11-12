// Blockchain-only Seal: client tx builder + on-chain verify path (mock RPC, no network, no signing).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';

if (typeof globalThis.localStorage === 'undefined') globalThis.localStorage = {};
const S = await import('../docs/js/seal-chain.js');
const C = await import('../docs/js/chain-proof.js');
const { DICT } = await import('../docs/js/i18n.js');

const WALLET = '6gXafzpPUShAf5Voy7NvQHDw6uGEQ7K9UhF96eG5mhFQ';
const FILE = new TextEncoder().encode('invoice #42 — total 100 EUR');
const FP = crypto.createHash('sha256').update(FILE).digest('hex');
const NOW = new Date('2026-11-12T10:00:00.000Z');
const TX = '5'.repeat(88);

// Minimal @solana/web3.js stand-in: enough surface for buildSealTx.
class PK { constructor(s) { this.s = String(s); } toBase58() { return this.s; } toString() { return this.s; } equals(o) { return o.s === this.s; } }
const MockW = {
  PublicKey: PK,
  Transaction: class { constructor(o) { Object.assign(this, o); this.instructions = []; } add(i) { this.instructions.push(i); return this; } },
  TransactionInstruction: class { constructor(o) { Object.assign(this, o); } },
  SystemProgram: { transfer: ({ fromPubkey, toPubkey, lamports }) => ({ programId: new PK(S.SYSTEM_PROGRAM), lamports, keys: [{ pubkey: fromPubkey, isSigner: true, isWritable: true }, { pubkey: toPubkey, isSigner: false, isWritable: true }] }) },
};

function parsedTx({ memo, signer = WALLET, err = null, blockTime = 1762941600 }) {
  return { blockTime, meta: { err, logMessages: [`Program log: Memo (len ${memo.length}): "${memo}"`] },
    transaction: { message: { accountKeys: [{ pubkey: signer, signer: true, writable: true }], instructions: [{ programId: S.MEMO_PROGRAM, parsed: memo }] } } };
}
function mockRpc(db) {
  // db: { sigsByAddr: {addr: [sig]}, txs: {sig: parsed}, firmSigs: [{signature, memo}] }
  const calls = [];
  const rpc = async (method, params) => {
    calls.push(method);
    if (method === 'getSignaturesForAddress') {
      const a = params[0];
      if (a === C.SEAL_SIGNER) return { res: db.firmSigs || [] };
      return { res: (db.sigsByAddr?.[a] || []).map(signature => ({ signature, err: null })) };
    }
    if (method === 'getTransaction') return { res: db.txs?.[params[0]] || null };
    throw new Error('unexpected ' + method);
  };
  rpc.calls = calls; return rpc;
}

test('base58 round-trip and leading zeros', () => {
  for (const bytes of [new Uint8Array(32).fill(7), Uint8Array.from([0, 0, 1, 2, 255]), crypto.randomBytes(32)]) {
    assert.deepEqual([...S.b58decode(S.b58encode(bytes))], [...bytes]);
  }
  assert.equal(S.b58encode(new Uint8Array(32)), '1'.repeat(32));
  assert.equal(S.b58encode(S.b58decode(C.SEAL_SIGNER)), C.SEAL_SIGNER);
});

test('fingerprint index key is deterministic sha256("AEGIS/rwa/v1/fp|"+fp), 32 bytes, distinct per file', async () => {
  const want = crypto.createHash('sha256').update('AEGIS/rwa/v1/fp|' + FP).digest();
  const a = await S.fpIndexAddress(FP);
  assert.deepEqual([...S.b58decode(a)], [...want]);
  assert.equal(a, await S.fpIndexAddress(FP));
  assert.notEqual(a, await S.fpIndexAddress('00'.repeat(32)));
  await assert.rejects(S.fpIndexAddress('xyz'));
});

test('memo is AEGIS/rwa/v1 and parses with the existing verifier (chain-proof.js)', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, validHours: 24, now: NOW });
  assert.match(p.id, /^[0-9a-f]{12}$/);
  assert.equal(p.created, NOW.toISOString());
  assert.equal(p.validUntil, '2026-11-13T10:00:00.000Z');
  assert.equal(p.memo, `AEGIS/rwa/v1|${p.id}|${FP}|sealed|${p.created}|${p.validUntil}`);
  const m = C.parseMemo(p.memo);
  assert.equal(m.id, p.id); assert.equal(m.fingerprint, FP); assert.equal(m.status, 'sealed'); assert.equal(m.validUntil, p.validUntil);
  const forever = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  assert.ok(forever.memo.endsWith('|forever'));
  assert.equal(C.parseMemo(forever.memo).validUntil, null);
  assert.ok(new TextEncoder().encode(p.memo).length < 200, 'memo stays small');
  // same file+wallet+time → same id; different time → different id
  assert.equal((await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW })).id, forever.id);
  assert.notEqual((await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: new Date(+NOW + 1) })).id, forever.id);
});

test('prepareSeal / buildMemo reject bad input (no wallet, bad hash)', async () => {
  await assert.rejects(S.prepareSeal({ fingerprint: FP, wallet: null }), /wallet/);
  await assert.rejects(S.prepareSeal({ fingerprint: 'nothex', wallet: WALLET }), /fingerprint/);
  assert.throws(() => S.buildMemo({ id: 'XYZ', fingerprint: FP, created: NOW.toISOString() }), /seal id/);
});

test('buildSealTx: user is fee payer + only signer; memo + 0-lamport self-transfer with read-only index key', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  const tx = S.buildSealTx(MockW, { payer: WALLET, memo: p.memo, indexAddress: p.indexAddress, blockhash: 'BH', lastValidBlockHeight: 1 });
  assert.equal(tx.feePayer.toBase58(), WALLET);
  assert.equal(tx.instructions.length, 2);
  const [memo, xfer] = tx.instructions;
  assert.equal(memo.programId.toBase58(), S.MEMO_PROGRAM);
  assert.equal(new TextDecoder().decode(memo.data), p.memo);
  assert.deepEqual(memo.keys.map(k => [k.pubkey.toBase58(), k.isSigner]), [[WALLET, true]]);
  assert.equal(xfer.programId.toBase58(), S.SYSTEM_PROGRAM);
  assert.equal(xfer.lamports, 0);
  assert.equal(xfer.keys[0].pubkey.toBase58(), WALLET);
  assert.equal(xfer.keys[1].pubkey.toBase58(), WALLET, 'self-transfer: no funds move to anyone');
  const idx = xfer.keys[2];
  assert.equal(idx.pubkey.toBase58(), p.indexAddress);
  assert.equal(idx.isSigner, false); assert.equal(idx.isWritable, false);
  const signers = tx.instructions.flatMap(i => i.keys).filter(k => k.isSigner).map(k => k.pubkey.toBase58());
  assert.deepEqual([...new Set(signers)], [WALLET], 'no firm key, no server co-signer');
});

test('verify: file only → found via on-chain fingerprint index → match, signed by sealer wallet', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  const rpc = mockRpc({ sigsByAddr: { [p.indexAddress]: [TX] }, txs: { [TX]: parsedTx({ memo: p.memo }) } });
  const r = await S.verifyOnChain({ fileFp: FP }, { rpc });
  assert.equal(r.status, 'match');
  assert.equal(r.proofs.length, 1);
  assert.equal(r.proofs[0].receiptTx, TX);
  assert.equal(r.proofs[0].signerKind, 'sealer');
  assert.equal(r.proofs[0].firmAttested, false);
  assert.equal(r.proofs[0].signer, WALLET);
  assert.ok(!rpc.calls.includes('fetch'), 'only RPC calls');
});

test('verify: tx + wrong file → mismatch (never a false pass)', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  const rpc = mockRpc({ txs: { [TX]: parsedTx({ memo: p.memo }) } });
  const other = crypto.createHash('sha256').update('tampered').digest('hex');
  assert.equal((await S.verifyOnChain({ tx: TX, fileFp: other }, { rpc })).status, 'mismatch');
  assert.equal((await S.verifyOnChain({ tx: TX, fileFp: FP }, { rpc })).status, 'match');
  assert.equal((await S.verifyOnChain({ tx: TX }, { rpc })).status, 'found');
});

test('verify: index memo for another fingerprint is ignored; unknown file → no-seal', async () => {
  const other = crypto.createHash('sha256').update('other').digest('hex');
  const p = await S.prepareSeal({ fingerprint: other, wallet: WALLET, now: NOW });
  const idx = await S.fpIndexAddress(FP);
  const rpc = mockRpc({ sigsByAddr: { [idx]: [TX] }, txs: { [TX]: parsedTx({ memo: p.memo }) } });
  assert.equal((await S.verifyOnChain({ fileFp: FP }, { rpc })).status, 'no-seal');
  assert.equal((await S.verifyOnChain({ fileFp: FP }, { rpc: mockRpc({}) })).status, 'no-seal');
});

test('verify: failed or unfinalized tx never passes; missing tx → no-seal', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  const bad = parsedTx({ memo: p.memo, err: { InstructionError: [0, 'x'] } });
  assert.equal((await S.verifyOnChain({ tx: TX, fileFp: FP }, { rpc: mockRpc({ txs: { [TX]: bad } }) })).status, 'no-seal');
  const pend = { ...parsedTx({ memo: p.memo }), confirmationStatus: 'confirmed' };
  assert.equal((await S.verifyOnChain({ tx: TX, fileFp: FP }, { rpc: mockRpc({ txs: { [TX]: pend } }) })).status, 'no-seal');
  assert.equal((await S.verifyOnChain({ tx: TX, fileFp: FP }, { rpc: mockRpc({}) })).status, 'no-seal');
});

test('verify: expired validUntil is reported as expired', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, validHours: 1, now: new Date('2020-01-01T00:00:00Z') });
  const r = await S.verifyOnChain({ tx: TX, fileFp: FP }, { rpc: mockRpc({ txs: { [TX]: parsedTx({ memo: p.memo }) } }) });
  assert.equal(r.status, 'match');
  assert.equal(r.proofs[0].expired, true);
});

test('verify: older firm-key seals (no index key) still found via legacy scan', async () => {
  const memo = `AEGIS/rwa/v1|abcdef123456|${FP}|verified|2026-10-31T00:00:00.000Z|forever`;
  const rpc = mockRpc({ firmSigs: [{ signature: TX, err: null, memo: `[147] ${memo}` }], txs: { [TX]: parsedTx({ memo, signer: C.SEAL_SIGNER }) } });
  const r = await S.verifyOnChain({ fileFp: FP }, { rpc });
  assert.equal(r.status, 'match');
  assert.equal(r.proofs[0].firmAttested, true);
  const byId = await S.verifyOnChain({ id: 'abcdef123456' }, { rpc });
  assert.equal(byId.status, 'found');
  assert.equal((await S.verifyOnChain({ id: '000000000000' }, { rpc })).status, 'need-tx');
});

test('parseVerifyInput accepts tx, proof URL, explorer URL, receipt JSON, fingerprint, id; rejects junk', async () => {
  assert.deepEqual(S.parseVerifyInput(TX), { tx: TX });
  assert.equal(S.parseVerifyInput(`https://aegisai-sol.github.io/aegisai/proof.html?id=abcdef123456&tx=${TX}`).tx, TX);
  assert.equal(S.parseVerifyInput(`https://solscan.io/tx/${TX}`).tx, TX);
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  const rc = S.receiptObject({ ...p, tx: TX, name: 'invoice.pdf' });
  const parsed = S.parseVerifyInput(JSON.stringify(rc));
  assert.equal(parsed.tx, TX); assert.equal(parsed.fingerprint, FP); assert.equal(parsed.id, p.id);
  assert.deepEqual(S.parseVerifyInput(FP.toUpperCase()), { fingerprint: FP });
  assert.deepEqual(S.parseVerifyInput('ABCDEF123456'), { id: 'abcdef123456' });
  assert.equal(S.parseVerifyInput('hello world').bad, true);
  assert.deepEqual(S.parseVerifyInput(''), {});
});

test('receipt carries everything needed to verify without us', async () => {
  const p = await S.prepareSeal({ fingerprint: FP, wallet: WALLET, now: NOW });
  const rc = S.receiptObject({ ...p, tx: TX });
  assert.equal(rc.fingerprintSha256, FP); assert.equal(rc.tx, TX); assert.equal(rc.signer, WALLET); assert.equal(rc.memo, p.memo);
  assert.equal(rc.solscan, 'https://solscan.io/tx/' + TX);
  assert.match(rc.proof, /proof\.html\?id=[0-9a-f]{12}&tx=/);
  assert.equal(rc.validUntil, 'forever');
});

test('fee helpers: base fee 5000 lamports = 0.000005 SOL', () => {
  assert.equal(S.feeSol(5000), 0.000005);
  assert.equal(S.feeSol(), 0.000005);
});

test('Seal page is blockchain-only: no claim server, no job API, no upload', () => {
  for (const f of ['docs/rwa.html', 'docs/js/seal-page.js', 'docs/js/seal-chain.js']) {
    const s = fs.readFileSync(f, 'utf8');
    assert.doesNotMatch(s, /onrender\.com|rwa-jobs|createJob|CLAIM_API|ciphertextB64|\/api\/(rwa|mine|claim|supply)/, f);
  }
  const page = fs.readFileSync('docs/js/seal-page.js', 'utf8');
  const urls = [...page.matchAll(/https:\/\/[a-z0-9.-]+/g)].map(m => m[0]);
  for (const u of urls) assert.ok(['https://esm.sh', 'https://api.coingecko.com', 'https://aegisai-sol.github.io'].includes(u), 'unexpected host ' + u);
  const proof = fs.readFileSync('docs/proof.html', 'utf8');
  assert.doesNotMatch(proof, /rwa-jobs|getJob|byFingerprint\(/);
});

test('i18n: EN and BG have identical keys; every data-i18n key on Seal/Home/Roadmap/How-to exists in both', () => {
  const en = Object.keys(DICT.en).sort(), bg = Object.keys(DICT.bg).sort();
  assert.deepEqual(en, bg);
  for (const k of en) assert.ok(String(DICT.bg[k]).trim(), 'empty bg ' + k);
  for (const f of ['docs/rwa.html', 'docs/index.html', 'docs/roadmap.html', 'docs/howto.html', 'docs/miner.html', 'docs/token.html']) {
    const s = fs.readFileSync(f, 'utf8');
    for (const m of s.matchAll(/data-i18n(?:-html|-placeholder)?="([^"]+)"/g)) {
      assert.ok(DICT.en[m[1]], `${f}: missing en ${m[1]}`); assert.ok(DICT.bg[m[1]], `${f}: missing bg ${m[1]}`);
    }
  }
  const page = fs.readFileSync('docs/js/seal-page.js', 'utf8');
  for (const m of page.matchAll(/(?<![\w.])t\('([a-z0-9.]+)'\)/g)) { assert.ok(DICT.en[m[1]] && DICT.bg[m[1]], 'seal-page key ' + m[1]); }
});

test('UI honesty: Stake button is disabled (coming on-chain); miner shows beta-server banner; Burn stays live', () => {
  const tok = fs.readFileSync('docs/token.html', 'utf8');
  assert.match(tok, /<button id="sb"[^>]*disabled/);
  assert.match(tok, /<button id="bb" class="b">Burn AGIS<\/button>/);
  assert.match(fs.readFileSync('docs/miner.html', 'utf8'), /data-i18n="m2.banner"/);
  const rm = fs.readFileSync('docs/roadmap.html', 'utf8');
  for (const k of ['rm2.arweave.t', 'rm2.program.t', 'rm2.payagis.t', 'rm2.sponsored.t', 'rm2.credits.t']) assert.ok(rm.includes(k), k);
});

test('all inline + module scripts on changed pages parse (node --check)', async () => {
  const { execFileSync } = await import('node:child_process');
  const os = await import('node:os'); const path = await import('node:path');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'agis-inline-'));
  let n = 0;
  for (const f of ['docs/rwa.html', 'docs/index.html', 'docs/proof.html', 'docs/roadmap.html', 'docs/token.html', 'docs/miner.html', 'docs/howto.html', 'docs/rwa-legacy.html']) {
    const s = fs.readFileSync(f, 'utf8');
    for (const m of s.matchAll(/<script(?![^>]*src=)([^>]*)>([\s\S]*?)<\/script>/g)) {
      if (!m[2].trim()) continue;
      const file = path.join(dir, `s${n++}.${/type="module"/.test(m[1]) ? 'mjs' : 'cjs'}`);
      fs.writeFileSync(file, m[2]);
      assert.doesNotThrow(() => execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' }), `${f} script #${n}`);
    }
  }
  assert.ok(n > 8);
});
