// Mine page schedule panel (docs/js/mine-schedule.js): parse/format + honest fallback with mocked fetch.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as M from '../docs/js/mine-schedule.js';
import * as R from '../token/scripts/mine-rules.mjs';
import { DICT } from '../docs/js/i18n.js';

const GEN = Date.parse('2026-10-31T00:00:00Z') / 1000;
// Build a body exactly the way claim-server.mjs GET /api/mine/schedule does (repo source of truth).
function serverBody(nowSec, chainSupply) {
  const era = R.eraOf(nowSec, GEN), allowed = R.emittedUntil(nowSec, GEN), ledgerMined = 0n;
  const base = { ok: true, mint: 'GhSiU95vtKwn7FBAW1u5krxYP2PnpFPotb1LJFZkbzhW', genesis: new Date(GEN * 1000).toISOString(), era, eraSeconds: R.ERA,
    ratePerSecBase: String(R.RATE0 >> BigInt(era)), minePoolBase: String(R.MINE_POOL_BASE), maxSupplyBase: String(R.MAX_SUPPLY_BASE),
    launchBase: String(R.LAUNCH_BASE), emittedUntilBase: String(allowed), ledgerMinedBase: '0' };
  if (chainSupply === null) return { ...base, chainSupplyBase: null, chainMinedBase: null, minedTotalBase: null, headroomBase: null, withinSchedule: null, note: 'RPC unavailable' };
  const g = R.scheduleGate({ amount: 1n, ledgerMined, chainSupply, nowSec, genesisSec: GEN });
  return { ...base, chainSupplyBase: String(chainSupply), chainMinedBase: String(g.chainMined), minedTotalBase: String(g.minedTotal), headroomBase: String(g.headroom), withinSchedule: g.minedTotal <= allowed };
}
const tr = lang => k => DICT[lang][k] ?? DICT.en[k] ?? k;
const res = (status, body, { badJson = false } = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => { if (badJson) throw new SyntaxError('x'); return body; } });
const NOW = Date.parse('2026-11-07T10:00:00Z');
const mined = 1_500_000_000n * R.BASE + 12_345n * R.BASE; // chain supply = launch + 12,345 AGIS mined

test('parses a real server-shaped body and derives epoch, per-unit, next halving', () => {
  const s = M.parseSchedule(serverBody(NOW / 1000, mined));
  assert.equal(s.era, 0);
  assert.equal(s.minedTotalBase, 12_345n * R.BASE);
  assert.equal(M.perUnitBase(s), R.RATE0 / 10000n);            // UNIT_BPS=1 mirrors computeClaim
  assert.equal(M.isoDay(M.nextHalvingMs(s)), '2028-10-30');      // genesis + 730 days
  assert.equal(M.pctBps(s.minedTotalBase, s.minePoolBase), 0.01); // 12k of 8.5B → tiny but non-zero
  assert.equal(M.formatPct(M.pctBps(s.minedTotalBase, s.minePoolBase)), '<0.01%');
});

test('formatting: compact EN/BG, floors, percent edges', () => {
  assert.equal(M.formatAgis(8_500_000_000n * M.BASE, 'en'), '8.5B');
  assert.equal(M.formatAgis(8_500_000_000n * M.BASE, 'bg'), '8,5 млрд');
  assert.equal(M.formatAgis(1_239_999n * M.BASE, 'en'), '1.23M');   // floor, never round up
  assert.equal(M.formatAgis(12_345n * M.BASE, 'en'), '12.34K');
  assert.equal(M.formatAgis(0n, 'en'), '0');
  assert.equal(M.formatAgis(5n * M.BASE / 2n, 'bg'), '2,5');
  assert.equal(M.formatPerUnit(6_738_330n, 'en'), '0.006738');
  assert.equal(M.formatPerUnit(6_738_330n, 'bg'), '0,006738');
  assert.equal(M.formatPct(0), '0%');
  assert.equal(M.formatPct(0.5), '<0.01%');
  assert.equal(M.formatPct(1234, 'bg'), '12,34%');
  assert.equal(M.pctBps(20n, 10n), 10000);
  assert.equal(M.pctBps(1234n, 10000n), 1234);
  assert.equal(M.pctBps(0n, 10n), 0);                       // clamped
  assert.equal(M.pctBps(null, 10n), null);
});

test('parseSchedule rejects off-spec bodies (fail closed, no fake numbers)', () => {
  const good = serverBody(NOW / 1000, mined);
  for (const bad of [null, {}, { ...good, ok: false }, { ...good, era: -1 }, { ...good, era: 1.5 }, { ...good, eraSeconds: 0 },
    { ...good, genesis: 'nope' }, { ...good, minePoolBase: '-5' }, { ...good, ratePerSecBase: '1e9' }, { ...good, emittedUntilBase: undefined },
    { ...good, emittedUntilBase: String(R.MINE_POOL_BASE + 1n) }, { ...good, minePoolBase: String(R.MAX_SUPPLY_BASE + 1n) }, { ...good, minedTotalBase: 'abc' }])
    assert.throws(() => M.parseSchedule(bad));
});

test('fetchSchedule: ok path hits /api/mine/schedule, no-store', async () => {
  let url, opt;
  const r = await M.fetchSchedule('https://x.test/', { fetchImpl: async (u, o) => { url = u; opt = o; return res(200, serverBody(NOW / 1000, mined)); } });
  assert.equal(url, 'https://x.test/api/mine/schedule');
  assert.equal(opt.cache, 'no-store');
  assert.equal(r.state, 'ok');
});

test('fetchSchedule fallbacks: 404 pending, network/5xx unreachable, bad JSON/body invalid, no API', async () => {
  assert.equal((await M.fetchSchedule('https://x', { fetchImpl: async () => res(404, { ok: false, error: 'not found' }) })).state, 'pending');
  assert.equal((await M.fetchSchedule('https://x', { fetchImpl: async () => { throw new TypeError('Failed to fetch'); } })).state, 'unreachable');
  assert.equal((await M.fetchSchedule('https://x', { fetchImpl: async () => res(502, {}) })).state, 'unreachable');
  assert.equal((await M.fetchSchedule('https://x', { fetchImpl: async () => res(200, null, { badJson: true }) })).state, 'invalid');
  assert.equal((await M.fetchSchedule('https://x', { fetchImpl: async () => res(200, { ok: true, era: 'x' }) })).state, 'invalid');
  assert.equal((await M.fetchSchedule('', { fetchImpl: async () => res(200, {}) })).state, 'unreachable');
});

test('fallback HTML shows the localized message and zero digits (never fake numbers)', () => {
  for (const lang of ['en', 'bg']) for (const state of ['pending', 'unreachable', 'invalid', 'loading']) {
    const v = M.describe({ state }, tr(lang), lang, NOW), h = M.scheduleHtml(v, tr(lang));
    assert.ok(!/progressbar/.test(h));
    const key = state === 'loading' ? 'sched.loading' : 'sched.' + state;
    assert.ok(h.includes(DICT[lang][key].replace(/"/g, '&quot;')), lang + ' ' + state);
    if (state !== 'loading') assert.ok(!/\d/.test(h.replace(/class="[^"]*"/g, '')), 'no digits in ' + lang + ' ' + state);
  }
  assert.match(DICT.en['sched.pending'], /Schedule unavailable — server update pending/);
});

test('ok HTML: EN + BG panels carry epoch, reward, progress bar, next halving, plain line', () => {
  const r = { state: 'ok', s: M.parseSchedule(serverBody(NOW / 1000, mined)) };
  const en = M.scheduleHtml(M.describe(r, tr('en'), 'en', NOW), tr('en'));
  assert.ok(en.includes('Halving epoch') && en.includes('0.006738 AGIS') && en.includes('12.34K</b> / 8.5B AGIS') && en.includes('&lt;0.01%'));
  assert.ok(en.includes('2028-10-30 · 723d') && en.includes('role="progressbar"') && en.includes(DICT.en['sched.plain']));
  const bg = M.scheduleHtml(M.describe(r, tr('bg'), 'bg', NOW), tr('bg'));
  assert.ok(bg.includes('Епоха (халвинг)') && bg.includes('0,006738 AGIS') && bg.includes('8,5 млрд AGIS') && bg.includes('723 дни'));
});

test('RPC-down body: shows "mined unavailable", no progress bar, but schedule still parses', () => {
  const r = { state: 'ok', s: M.parseSchedule(serverBody(NOW / 1000, null)) };
  const h = M.scheduleHtml(M.describe(r, tr('en'), 'en', NOW), tr('en'));
  assert.ok(h.includes(DICT.en['sched.minedNA']) && !h.includes('progressbar'));
});

test('every sched.* key exists in EN and BG; docs/site mirrors identical', () => {
  const en = Object.keys(DICT.en).filter(k => k.startsWith('sched.')), bg = Object.keys(DICT.bg).filter(k => k.startsWith('sched.'));
  assert.ok(en.length >= 14);
  assert.deepEqual([...en].sort(), [...bg].sort());
  for (const k of en) assert.notEqual(DICT.bg[k], DICT.en[k] === ' дни' ? '' : DICT.en[k], k + ' untranslated');
  for (const f of ['js/mine-schedule.js', 'js/i18n.js', 'miner.html', 'sw.js'])
    assert.equal(fs.readFileSync(new URL('../site/' + f, import.meta.url), 'utf8'), fs.readFileSync(new URL('../docs/' + f, import.meta.url), 'utf8'), f);
  const html = fs.readFileSync(new URL('../docs/miner.html', import.meta.url), 'utf8');
  assert.ok(html.includes('id="schedBody"') && html.includes('./js/mine-schedule.js'));
  assert.match(fs.readFileSync(new URL('../docs/sw.js', import.meta.url), 'utf8'), /agis-v44/);
});

test('every inline <script type=module> on Mine/Token/RWA pages is valid JS (regression: 2a5ef64 broke miner.html with a missing brace)', async () => {
  const { execFileSync } = await import('node:child_process');
  const os = await import('node:os'), path = await import('node:path');
  for (const tree of ['docs', 'site']) for (const page of ['miner.html', 'token.html', 'rwa.html', 'index.html']) {
    const f = new URL(`../${tree}/${page}`, import.meta.url);
    if (!fs.existsSync(f)) continue;
    const html = fs.readFileSync(f, 'utf8');
    [...html.matchAll(/<script type="module">([\s\S]*?)<\/script>/g)].forEach((m, i) => {
      const tmp = path.join(os.tmpdir(), `agis-inline-${tree}-${page}-${i}.mjs`);
      fs.writeFileSync(tmp, m[1]);
      try { execFileSync(process.execPath, ['--check', tmp], { stdio: 'pipe' }); }
      catch (e) { assert.fail(`${tree}/${page} inline module #${i}: ${String(e.stderr).split('\n').slice(0, 4).join(' ')}`); }
    });
  }
});
