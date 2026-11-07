// E2E: real claim-server.mjs process against a fake Solana JSON-RPC (no keys, no network, no mainnet).
// Proves the mine-pool schedule ceiling runs in the live request path, fails closed, and is chain-floored.
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import bs58 from 'bs58';
import { Keypair } from '@solana/web3.js';
import { LAUNCH_BASE, MAX_SUPPLY_BASE, RATE0 } from '../scripts/mine-rules.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'agis-claim-e2e-'));
const GENESIS = Math.floor(Date.now() / 1000) - 100; // allowed ~= RATE0 * 100
let supply = LAUNCH_BASE, supplyDown = false, rpcCalls = [];

const rpc = http.createServer((req, res) => {
  let b = ''; req.on('data', d => b += d); req.on('end', () => {
    const one = j => {
      rpcCalls.push(j.method);
      const ctx = { slot: 1 };
      if (j.method === 'getTokenSupply' && !supplyDown) return { jsonrpc: '2.0', id: j.id, result: { context: ctx, value: { amount: String(supply), decimals: 9, uiAmount: null, uiAmountString: String(supply / 10n ** 9n) } } };
      if (j.method === 'getBalance') return { jsonrpc: '2.0', id: j.id, result: { context: ctx, value: 1_000_000_000 } };
      return { jsonrpc: '2.0', id: j.id, error: { code: -32000, message: 'fake rpc: ' + j.method + ' disabled' } };
    };
    const j = JSON.parse(b); res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(Array.isArray(j) ? j.map(one) : one(j)));
  });
});
let srv, port;
const freePort = () => new Promise(r => { const s = http.createServer().listen(0, () => { const p = s.address().port; s.close(() => r(p)); }); });

test.before(async () => {
  await new Promise(r => rpc.listen(0, '127.0.0.1', r));
  const kp = path.join(tmp, 'throwaway.json');
  fs.writeFileSync(kp, JSON.stringify(Array.from(Keypair.generate().secretKey)));
  port = await freePort();
  srv = spawn(process.execPath, [path.join(here, '../scripts/claim-server.mjs')], {
    cwd: tmp, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, MAINNET: '', SOLANA_RPC: `http://127.0.0.1:${rpc.address().port}`, SOLANA_KEYPAIR: kp, PORT: String(port),
      LEDGER: path.join(tmp, 'ledger.json'), RWA_DIR: path.join(tmp, 'rwa'), AGIS_GENESIS: String(GENESIS) } });
  await new Promise((ok, bad) => { let o = ''; srv.stdout.on('data', d => { o += d; if (o.includes('claim server on')) ok(); }); srv.on('exit', c => bad(new Error('server exited ' + c))); setTimeout(() => bad(new Error('boot timeout')), 10000); });
});
test.after(() => { srv?.kill(); rpc.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

function signedClaim() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ed25519');
  const wallet = bs58.encode(publicKey.export({ format: 'der', type: 'spki' }).subarray(12));
  const to = new Date(Date.now() - 1000), from = new Date(to.getTime() - 60e3);
  const msg = `AEGIS/mine-claim/v1|${wallet}|30|${from.toISOString()}|${to.toISOString()}|${crypto.randomUUID()}`;
  return { wallet, msg, sig: crypto.sign(null, Buffer.from(msg), privateKey).toString('base64') };
}
const post = async c => (await fetch(`http://127.0.0.1:${port}/api/claim`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(c) })).json();
const schedule = async () => (await fetch(`http://127.0.0.1:${port}/api/mine/schedule`)).json();

test('inside schedule: gate passes and request reaches the mint step (fake RPC refuses mint)', async () => {
  supply = LAUNCH_BASE; supplyDown = false; rpcCalls = [];
  const r = await post(signedClaim());
  assert.equal(r.ok, false); assert.match(r.error, /^mint failed/);
  assert.ok(rpcCalls.includes('getTokenSupply'), 'supply must be read before mint');
});
test('wiped ledger, chain already at schedule: fails closed "exceeds emission schedule"', async () => {
  supply = LAUNCH_BASE + RATE0 * 100_000n; supplyDown = false;
  const r = await post(signedClaim());
  assert.deepEqual(r, { ok: false, error: 'exceeds emission schedule' });
});
test('chain at 10B max: fails closed "exceeds max supply"', async () => {
  supply = MAX_SUPPLY_BASE; supplyDown = false;
  assert.deepEqual(await post(signedClaim()), { ok: false, error: 'exceeds max supply' });
});
test('RPC cannot read supply: fails closed, no mint attempt', async () => {
  supplyDown = true; rpcCalls = [];
  assert.deepEqual(await post(signedClaim()), { ok: false, error: 'supply check unavailable, try later' });
  assert.ok(!rpcCalls.includes('getAccountInfo') && !rpcCalls.includes('sendTransaction'));
  supplyDown = false;
});
test('GET /api/mine/schedule: public audit numbers + withinSchedule flag', async () => {
  supply = LAUNCH_BASE + RATE0 * 10n;
  let s = await schedule();
  assert.equal(s.ok, true); assert.equal(s.era, 0); assert.equal(s.ratePerSecBase, String(RATE0));
  assert.equal(s.launchBase, String(LAUNCH_BASE)); assert.equal(s.chainMinedBase, String(RATE0 * 10n));
  assert.equal(s.withinSchedule, true); assert.ok(BigInt(s.headroomBase) > 0n);
  assert.ok(BigInt(s.emittedUntilBase) >= RATE0 * 100n);
  supply = LAUNCH_BASE + RATE0 * 100_000n;
  s = await schedule(); assert.equal(s.withinSchedule, false); assert.equal(s.headroomBase, '0');
  supplyDown = true; s = await schedule(); assert.equal(s.chainSupplyBase, null); assert.equal(s.withinSchedule, null); supplyDown = false;
});
test('failed claims leave no ledger debit or replay marker', () => {
  const l = fs.existsSync(path.join(tmp, 'ledger.json')) ? JSON.parse(fs.readFileSync(path.join(tmp, 'ledger.json'), 'utf8')) : { seen: {}, day: {} };
  assert.deepEqual(l.day, {}); assert.deepEqual(Object.values(l.seen).filter(v => v !== undefined), []);
});
