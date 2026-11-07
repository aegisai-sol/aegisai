import test from 'node:test';
import assert from 'node:assert/strict';
import { eraOf, difficultyBps, computeClaim, RATE0, ERA } from '../scripts/mine-rules.mjs';
const G = 1_800_000_000, CAP = 100n * 10n ** 9n, GCAP = 100000n * 10n ** 9n;
const base = (o = {}) => computeClaim({ tasks: 10, fromSec: G + 5, genesisSec: G, unitBps: 1, wallet: 'W', day: 'D', ledgerDay: {}, dayWallets: [], dailyCap: CAP, globalCap: GCAP, ...o });

test('era halves every ~2y and never negative', () => {
  assert.equal(eraOf(G - 10, G), 0);
  assert.equal(eraOf(G + ERA - 1, G), 0);
  assert.equal(eraOf(G + ERA, G), 1);
  const a = base(), b = base({ fromSec: G + ERA + 5 });
  assert.equal(b.amount * 2n <= a.amount && a.amount - b.amount * 2n <= 10n, true);
});
test('full reward up to 100 wallets, then shared', () => {
  assert.equal(difficultyBps(0), 10000n);
  assert.equal(difficultyBps(100), 10000n);
  assert.equal(difficultyBps(200), 5000n);
  assert.throws(() => difficultyBps(-1));
  const many = Array.from({ length: 199 }, (_, i) => 'x' + i);
  const r = base({ dayWallets: many });
  assert.equal(r.active, 200); assert.equal(r.difficultyBps, 5000);
  assert.equal(r.amount, (RATE0 * 10n / 10000n) * 5000n / 10000n);
});
test('same wallet again does not raise difficulty', () => {
  const r = base({ dayWallets: Array.from({ length: 100 }, (_, i) => i ? 'x' + i : 'W') });
  assert.equal(r.active, 100); assert.equal(r.difficultyBps, 10000);
});
test('per-wallet cap clips then fails closed', () => {
  const r = base({ tasks: 100_000_000, ledgerDay: { 'D|W': String(CAP - 5n) } });
  assert.equal(r.ok, true); assert.equal(r.amount, 5n);
  const f = base({ ledgerDay: { 'D|W': String(CAP) } });
  assert.equal(f.ok, false); assert.equal(f.error, 'daily cap reached');
});
test('global cap clips', () => {
  const r = base({ tasks: 100_000_000, ledgerDay: { 'D|*': String(GCAP - 7n) } });
  assert.equal(r.amount, 7n);
});
test('era far future mints nothing', () => {
  assert.equal(base({ fromSec: G + ERA * 300 }).ok, false);
});

// ---- schedule ceiling (85% pool + halving + 10B max, chain-floored) ----
import fs from 'node:fs';
import { emittedUntil, minedFromLedger, scheduleGate, MINE_POOL_BASE, MAX_SUPPLY_BASE, LAUNCH_BASE } from '../scripts/mine-rules.mjs';
const V = JSON.parse(fs.readFileSync(new URL('../../miner/tests/emission_schedule_vectors.json', import.meta.url), 'utf8'));
const gate = (o = {}) => scheduleGate({ amount: 5n * 10n ** 9n, ledgerMined: 0n, chainSupply: LAUNCH_BASE, nowSec: G + 3600, genesisSec: G, ...o });

test('emittedUntil: shared vectors (Python mine_emit agrees), monotonic, < 85% pool forever', () => {
  for (const c of V.cases) assert.equal(String(emittedUntil(V.genesis + c.offset, V.genesis)), c.emittedUntil);
  let prev = -1n;
  for (const c of V.cases) { const x = BigInt(c.emittedUntil); assert.ok(x >= prev); prev = x; }
  assert.ok(emittedUntil(G + ERA * 1000, G) < MINE_POOL_BASE);
  assert.equal(emittedUntil(G - 50, G), 0n);
  assert.equal(emittedUntil(G + 10, G), RATE0 * 10n);
  assert.equal(emittedUntil(G + ERA, G), RATE0 * BigInt(ERA));
  assert.equal(MINE_POOL_BASE + LAUNCH_BASE, MAX_SUPPLY_BASE);
});
test('minedFromLedger sums only network-day keys', () => {
  assert.equal(minedFromLedger({ 'D1|*': '7', 'D1|W': '7', 'D2|*': '5', 'D2|X': '5' }), 12n);
  assert.equal(minedFromLedger({}), 0n);
  assert.equal(minedFromLedger(undefined), 0n);
});
test('gate passes normal claim inside schedule', () => {
  const r = gate();
  assert.equal(r.ok, true); assert.equal(r.allowed, RATE0 * 3600n); assert.equal(r.minedTotal, 0n);
});
test('gate fails closed past schedule (ledger total)', () => {
  const allowed = emittedUntil(G + 3600, G);
  assert.equal(gate({ amount: 1n, ledgerMined: allowed }).error, 'exceeds emission schedule');
  assert.equal(gate({ amount: 1n, ledgerMined: allowed - 1n }).ok, true);
});
test('wiped ledger cannot reset ceiling: on-chain supply floors mined total', () => {
  const allowed = emittedUntil(G + 3600, G);
  const r = gate({ amount: 1n, ledgerMined: 0n, chainSupply: LAUNCH_BASE + allowed });
  assert.equal(r.ok, false); assert.equal(r.error, 'exceeds emission schedule'); assert.equal(r.chainMined, allowed);
  // burns lower supply: ledger term still counts what was mined
  const b = gate({ amount: 1n, ledgerMined: allowed, chainSupply: LAUNCH_BASE });
  assert.equal(b.ok, false); assert.equal(b.minedTotal, allowed);
});
test('hard 10B max supply even if schedule would allow', () => {
  const r = gate({ amount: 2n, chainSupply: MAX_SUPPLY_BASE - 1n, ledgerMined: 0n, nowSec: G + ERA * 50, launch: MAX_SUPPLY_BASE });
  assert.equal(r.error, 'exceeds max supply');
  assert.equal(gate({ amount: 1n, chainSupply: MAX_SUPPLY_BASE - 1n, nowSec: G + ERA * 50, launch: MAX_SUPPLY_BASE }).ok, true);
});
test('gate rejects garbage inputs (fail closed, no silent pass)', () => {
  assert.throws(() => gate({ amount: 0n }));
  assert.throws(() => gate({ amount: 5 }));
  assert.throws(() => gate({ chainSupply: undefined }));
  assert.throws(() => gate({ chainSupply: -1n }));
  assert.throws(() => gate({ ledgerMined: -1n }));
  assert.throws(() => gate({ nowSec: NaN }));
});
