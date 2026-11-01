// Proves the browser miner solver (docs/js/pov-solver.js) matches the claim server grader.
// Uses the real pov-tasks.mjs from the agis-claim repo when present (CLAIM_REPO env or ../agis-claim-push).
// Optional LIVE=1: also fetch a real batch from prod and check the answer format.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as S from '../docs/js/pov-solver.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = process.env.CLAIM_REPO || path.resolve(here, '../../agis-claim-push');
const povPath = path.join(repo, 'pov-tasks.mjs');
const hasPov = fs.existsSync(povPath);
const W = '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin';

test('site and docs solver copies are identical', () => {
  assert.equal(fs.readFileSync(path.join(here, '../site/js/pov-solver.js'), 'utf8'), fs.readFileSync(path.join(here, '../docs/js/pov-solver.js'), 'utf8'));
});

test('encodeAnswers matches server bit layout (MSB-first)', () => {
  assert.equal(S.encodeAnswers([true]), '80');
  assert.equal(S.encodeAnswers([false, true, false, false, false, false, false, true, true]), '4180');
  assert.equal(S.encodeAnswers(Array(120).fill(false)).length, 30);
});

test('claim message has the exact v2 field order', () => {
  const m = S.buildClaimMsg({ wallet: W, batchId: '1800000000.0123456789abcdef.3.' + 'a'.repeat(32), answersHex: 'a0', from: 'F', to: 'T', uuid: 'U', tier: 'phone', cores: 4, benchMs: 30 });
  const p = m.split('|');
  assert.equal(p.length, 10);
  assert.deepEqual([p[0], p[1], p[3], p[4], p[5], p[6], p[7], p[8], p[9]], ['AEGIS/mine-claim/v2', W, 'a0', 'F', 'T', 'U', 'phone', '4', '30']);
  assert.throws(() => S.buildClaimMsg({ wallet: 'a|b', batchId: 'x', answersHex: '', from: 1, to: 1, uuid: 1, tier: 1, cores: 1, benchMs: 1 }));
});

test('work window uses server issuedAt and measured elapsed', () => {
  const w = S.workWindow('2026-11-01T00:00:00.000Z', 125000);
  assert.equal(w.from, '2026-11-01T00:00:00.000Z'); assert.equal(w.to, '2026-11-01T00:02:05.000Z');
});

test('unknown task is refused, never guessed', async () => {
  await assert.rejects(() => S.solveTask('rm -rf /'), /unknown task/);
});

test('browser solver scores >=90% (in fact 100%) on real server tasks', { skip: !hasPov && 'pov-tasks.mjs not found' }, async () => {
  const P = await import(pathToFileURL(povPath).href);
  const secret = Buffer.from('test-secret-' + Date.now());
  const kinds = new Set(); let total = 0, right = 0;
  for (let k = 0; k < 25; k++) {
    const { batchId, tasks } = P.issueBatch(secret, W, P.MAX_TASKS, 1_800_000_000 + k, '0123456789abcdef');
    const answers = [];
    for (const t of tasks) { answers.push(await S.solveTask(t)); kinds.add(S.taskKind(t)); }
    const g = P.gradeAnswers(secret, batchId, S.encodeAnswers(answers));
    assert.equal(g.pass, true); total += g.n; right += g.correct;
  }
  assert.equal(kinds.size, 3);
  assert.ok(right / total >= 0.9);
  assert.equal(right, total, `solver disagreed on ${total - right}/${total}`);
  console.log(`# graded ${right}/${total} correct (${(100 * right / total).toFixed(1)}%) across 25 batches`);
});

test('LIVE: prod batch parses and solves', { skip: process.env.LIVE !== '1' && 'set LIVE=1' }, async () => {
  const j = await S.fetchBatch('https://agis-claim.onrender.com', W, 30);
  assert.equal(j.tasks.length, 30);
  for (const t of j.tasks) assert.equal(typeof await S.solveTask(t), 'boolean');
});
