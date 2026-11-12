// Verify chain-proof: finalized AEGIS/rwa/v1 Memo accepted from firm or sealer signer.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

if (typeof globalThis.localStorage === 'undefined') globalThis.localStorage = {};

const C = await import('../docs/js/chain-proof.js');
const { DICT } = await import('../docs/js/i18n.js');

const FIRM = C.SEAL_SIGNER;
const SEALER = '6gXafzpPUShAf5Voy7NvQHDw6uGEQ7K9UhF96eG5mhFQ';
const ID = 'abcdef123456';
const FP = 'ab'.repeat(32);
const MEMO = `AEGIS/rwa/v1|${ID}|${FP}|verified|2026-11-01T00:00:00.000Z|forever`;
const TX = '4'.repeat(80);

function parsed({ signer = FIRM, memo = MEMO, err = null, confirmationStatus = 'finalized', blockTime = 1761955200, noSigner = false } = {}) {
  return {
    confirmationStatus,
    blockTime,
    meta: { err, logMessages: [`Program log: Memo (len ${memo.length}): "${memo}"`] },
    transaction: {
      message: {
        accountKeys: noSigner ? [{ pubkey: signer, signer: false, writable: true }] : [{ pubkey: signer, signer: true, writable: true }],
        instructions: [{ programId: 'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr', parsed: memo }]
      }
    }
  };
}

test('parseMemo reads AEGIS/rwa/v1 fields', () => {
  const p = C.parseMemo(MEMO);
  assert.equal(p.id, ID);
  assert.equal(p.fingerprint, FP);
  assert.equal(p.status, 'verified');
  assert.equal(p.created, '2026-11-01T00:00:00.000Z');
  assert.equal(p.validUntil, null);
  assert.equal(p.expired, false);
  assert.equal(C.parseMemo('nope'), null);
});

test('firm-signed finalized memo is accepted and firm-attested', () => {
  const p = C.proofFromParsedTx(TX, parsed({ signer: FIRM }));
  assert.ok(p);
  assert.equal(p.id, ID);
  assert.equal(p.fingerprint, FP);
  assert.equal(p.receiptTx, TX);
  assert.equal(p._chainSource, true);
  assert.equal(p.firmAttested, true);
  assert.equal(p.signerKind, 'firm');
  assert.equal(p.signer, FIRM);
  assert.match(C.signerText(p), /AGIS firm key/);
  assert.ok(C.signerText(p).includes(FIRM));
  assert.doesNotMatch(C.signerText(p), /not a firm attestation/);
});

test('sealer-signed finalized memo is accepted and is not firm-attested', () => {
  const p = C.proofFromParsedTx(TX, parsed({ signer: SEALER }));
  assert.ok(p, 'sealer-paid memo must be accepted when the user supplies the tx');
  assert.equal(p.id, ID);
  assert.equal(p.fingerprint, FP);
  assert.equal(p.firmAttested, false);
  assert.equal(p.signerKind, 'sealer');
  assert.equal(p.signer, SEALER);
  assert.ok(!p.signers.includes(FIRM));
  const line = C.signerText(p);
  assert.match(line, /sealer wallet/);
  assert.ok(line.includes(SEALER));
  assert.match(line, /not a firm attestation/);
  assert.doesNotMatch(line, /firm key/);
});

test('rejects unfinalized, failed, unsigned, or memo-less transactions', () => {
  assert.equal(C.proofFromParsedTx(TX, parsed({ confirmationStatus: 'confirmed' })), null);
  assert.equal(C.proofFromParsedTx(TX, parsed({ confirmationStatus: 'processed' })), null);
  assert.equal(C.proofFromParsedTx(TX, parsed({ err: { InstructionError: [0, 'Custom'] } })), null);
  assert.equal(C.proofFromParsedTx(TX, null), null);
  assert.equal(C.proofFromParsedTx(TX, parsed({ noSigner: true })), null);
  assert.equal(C.proofFromParsedTx(TX, parsed({ memo: 'hello world' })), null);
});

test('expect fingerprint/id must match the memo (sealer and firm)', () => {
  const ok = { id: ID, fingerprint: FP };
  assert.ok(C.proofFromParsedTx(TX, parsed({ signer: SEALER }), ok));
  assert.equal(C.proofFromParsedTx(TX, parsed({ signer: SEALER }), { id: ID, fingerprint: 'cd'.repeat(32) }), null);
  assert.equal(C.proofFromParsedTx(TX, parsed({ signer: FIRM }), { id: 'ffffffffffff', fingerprint: FP }), null);
  assert.ok(C.memoMatches(C.parseMemo(MEMO), { hash: FP }));
  assert.equal(C.memoMatches(C.parseMemo(MEMO), { hash: '00'.repeat(32) }), false);
});

test('EN+BG signer strings; keys present in both dictionaries', () => {
  const p = C.proofFromParsedTx(TX, parsed({ signer: SEALER }));
  const firm = C.proofFromParsedTx(TX, parsed({ signer: FIRM }));
  const t = lang => (k, fb) => (DICT[lang] && DICT[lang][k]) || fb;
  assert.equal(C.signerText(firm, t('en')), 'Signed by the AGIS firm key (' + FIRM + ')');
  assert.equal(C.signerText(firm, t('bg')), 'Подписано с фирмения ключ на AGIS (' + FIRM + ')');
  assert.equal(C.signerText(p, t('en')), 'Signed by sealer wallet ' + SEALER + ' — not a firm attestation');
  assert.equal(C.signerText(p, t('bg')), 'Подписано от портфейла на печатащия ' + SEALER + ' — не е фирмено потвърждение');
  const keys = ['verify.signer.firm', 'verify.signer.sealer', 'verify.record', 'verify.chain.firm', 'verify.chain.sealer'];
  for (const k of keys) {
    assert.ok(DICT.en[k], 'missing en ' + k);
    assert.ok(DICT.bg[k], 'missing bg ' + k);
    assert.notEqual(DICT.en[k], DICT.bg[k], k + ' untranslated');
  }
});

test('D96 history scan path is unchanged; docs/site chain-proof mirrors; fromTx uses finalized', () => {
  const src = fs.readFileSync(new URL('../docs/js/chain-proof.js', import.meta.url), 'utf8');
  const site = fs.readFileSync(new URL('../site/js/chain-proof.js', import.meta.url), 'utf8');
  assert.equal(src, site);
  assert.match(src, /getSignaturesForAddress',\s*\[SEAL_SIGNER/);
  assert.match(src, /commitment:'finalized'/);
  assert.equal(C.SEAL_SIGNER, 'D96QgCXx93AMfKVLikbD8xbxQ6iB1bgrj9PWSiCVNgEg');
  // scan must not walk an arbitrary sealer address
  assert.doesNotMatch(src, /getSignaturesForAddress',\s*\[(?!SEAL_SIGNER)/);
});
