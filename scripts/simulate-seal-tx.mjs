// Dry-run the blockchain-only seal tx against public mainnet RPC WITHOUT signing (sigVerify:false). No funds move.
// Usage: npm i @solana/web3.js@1.95.3 (in a scratch dir) && node scripts/simulate-seal-tx.mjs [payerPubkeyWithSOL]
globalThis.localStorage = globalThis.localStorage || {};
const W = await import('@solana/web3.js');
const S = await import('../docs/js/seal-chain.js');
const payer = process.argv[2] || 'D96QgCXx93AMfKVLikbD8xbxQ6iB1bgrj9PWSiCVNgEg';
const fp = await S.sha256Hex(new TextEncoder().encode('simulate ' + Date.now()));
const p = await S.prepareSeal({ fingerprint: fp, wallet: payer, validHours: 24 });
const c = new W.Connection(process.env.RPC || 'https://solana-rpc.publicnode.com', 'confirmed');
const { blockhash, lastValidBlockHeight } = await c.getLatestBlockhash();
const tx = S.buildSealTx(W, { payer, memo: p.memo, indexAddress: p.indexAddress, blockhash, lastValidBlockHeight });
const msg = tx.compileMessage();
console.log('fee lamports', (await c.getFeeForMessage(msg)).value);
const r = await c.simulateTransaction(new W.VersionedTransaction(msg), { sigVerify: false, replaceRecentBlockhash: true });
console.log('err', JSON.stringify(r.value.err)); console.log(r.value.logs.join('\n'));
process.exit(r.value.err ? 1 : 0);
