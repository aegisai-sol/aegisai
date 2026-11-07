// Mine page: public "Mining rewards schedule" panel fed by claim server GET /api/mine/schedule.
// Pure parse/format helpers (unit-tested in tests/mine-schedule.test.mjs) + fetch with honest fallback.
// Never invents numbers: anything other than a valid 200 JSON from the server renders an "unavailable" state.
export const BASE = 10n ** 9n;              // AGIS decimals = 9
export const UNIT_BPS = 1n;                  // claim-server default (UNIT_BPS=1): per-unit = rate/sec * 1/10000
const DIGITS = /^\d{1,40}$/;

function big(v, name, nullable = false) {
  if (v === null || v === undefined) { if (nullable) return null; throw new Error('missing ' + name); }
  const s = String(v);
  if (!DIGITS.test(s)) throw new Error('bad ' + name);
  return BigInt(s);
}

/** Validate a /api/mine/schedule body. Throws on anything off-spec (caller shows "unavailable"). */
export function parseSchedule(j) {
  if (!j || typeof j !== 'object' || j.ok !== true) throw new Error('not ok');
  const era = j.era, eraSeconds = j.eraSeconds, genesisMs = Date.parse(j.genesis);
  if (!Number.isInteger(era) || era < 0 || era > 255) throw new Error('bad era');
  if (!Number.isInteger(eraSeconds) || eraSeconds <= 0) throw new Error('bad eraSeconds');
  if (!Number.isFinite(genesisMs)) throw new Error('bad genesis');
  const s = {
    era, eraSeconds, genesisMs,
    ratePerSecBase: big(j.ratePerSecBase, 'ratePerSecBase'),
    minePoolBase: big(j.minePoolBase, 'minePoolBase'),
    maxSupplyBase: big(j.maxSupplyBase, 'maxSupplyBase'),
    emittedUntilBase: big(j.emittedUntilBase, 'emittedUntilBase'),
    minedTotalBase: big(j.minedTotalBase, 'minedTotalBase', true),   // null when server could not read Solana supply
    headroomBase: big(j.headroomBase, 'headroomBase', true),
    withinSchedule: typeof j.withinSchedule === 'boolean' ? j.withinSchedule : null,
  };
  if (s.minePoolBase <= 0n || s.minePoolBase > s.maxSupplyBase) throw new Error('bad pool');
  if (s.emittedUntilBase > s.minePoolBase) throw new Error('bad emittedUntil');
  return s;
}

export const nextHalvingMs = s => s.genesisMs + (s.era + 1) * s.eraSeconds * 1000;
/** AGIS per verified unit at 1x difficulty, phone tier (×1), from the server's live rate. */
export const perUnitBase = s => s.ratePerSecBase * UNIT_BPS / 10000n;
/** part/whole in basis points (0..10000, floored to 0.01 bps), BigInt math, clamped. */
export function pctBps(part, whole) {
  if (part === null || whole <= 0n) return null;
  const b = part * 1000000n / whole;
  return Number(b > 1000000n ? 1000000n : b) / 100;
}

const SEP = { en: { dec: '.', u: ['', 'K', 'M', 'B'] }, bg: { dec: ',', u: ['', ' хил.', ' млн', ' млрд'] } };
/** Compact AGIS amount from base units, e.g. 1.23B / 1,23 млрд. Floors (never rounds up). */
export function formatAgis(base, lang = 'en') {
  const L = SEP[lang] || SEP.en;
  const whole = base / BASE;
  let i = 0, div = 1n;
  while (i < 3 && whole >= div * 1000n) { div *= 1000n; i++; }
  if (i === 0) {
    const n = Number(base) / 1e9;
    if (n === 0) return '0';
    const s = (n < 0.01 ? n.toFixed(6) : n.toFixed(2)).replace(/0+$/, '').replace(/\.$/, '');
    return s.replace('.', L.dec);
  }
  const hundredths = whole * 100n / div;           // floor to 2 decimals
  const s = (hundredths / 100n) + '.' + String(hundredths % 100n).padStart(2, '0');
  return s.replace(/\.?0+$/, '').replace('.', L.dec) + L.u[i];
}
export function formatPerUnit(base, lang = 'en') {
  const s = (Number(base) / 1e9).toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
  return lang === 'bg' ? s.replace('.', ',') : s;
}
export function formatPct(bps, lang = 'en') {
  if (bps === null) return null;
  const s = bps === 0 ? '0' : bps < 1 ? '<0.01' : (bps / 100).toFixed(2);
  return (lang === 'bg' ? s.replace('.', ',') : s) + '%';
}
export const isoDay = ms => new Date(ms).toISOString().slice(0, 10);

/**
 * Fetch schedule. Returns {state:'ok', s} | {state:'pending'} (route not deployed / 404)
 * | {state:'unreachable'} (network/timeout/5xx) | {state:'invalid'} (bad body). Never throws.
 */
export async function fetchSchedule(api, { fetchImpl = globalThis.fetch, timeoutMs = 75000 } = {}) {
  if (!api || typeof fetchImpl !== 'function') return { state: 'unreachable' };
  let r;
  try {
    const opt = { cache: 'no-store' };
    if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) opt.signal = AbortSignal.timeout(timeoutMs);
    r = await fetchImpl(api.replace(/\/$/, '') + '/api/mine/schedule', opt);
  } catch { return { state: 'unreachable' }; }
  if (!r || r.status === 404 || r.status === 405) return { state: 'pending' };
  if (!r.ok) return { state: 'unreachable' };
  let j;
  try { j = await r.json(); } catch { return { state: 'invalid' }; }
  try { return { state: 'ok', s: parseSchedule(j) }; } catch { return { state: 'invalid' }; }
}

/** View model of display strings. tr(key) = i18n lookup. No numbers unless state === 'ok'. */
export function describe(res, tr, lang = 'en', now = Date.now()) {
  if (!res || res.state === 'loading') return { state: 'loading', msg: tr('sched.loading') };
  if (res.state !== 'ok') return { state: res.state, msg: tr(res.state === 'pending' ? 'sched.pending' : res.state === 'invalid' ? 'sched.invalid' : 'sched.unreachable') };
  const s = res.s, nh = nextHalvingMs(s), days = Math.max(0, Math.ceil((nh - now) / 864e5));
  const bps = pctBps(s.minedTotalBase, s.minePoolBase);
  return {
    state: 'ok',
    epoch: String(s.era),
    perUnit: formatPerUnit(perUnitBase(s), lang),
    mined: s.minedTotalBase === null ? null : formatAgis(s.minedTotalBase, lang),
    pool: formatAgis(s.minePoolBase, lang),
    allowed: formatAgis(s.emittedUntilBase, lang),
    pctBps: bps, pct: formatPct(bps, lang),
    nextHalving: isoDay(nh), days: String(days),
    plain: tr('sched.plain'),
  };
}

const esc = x => String(x).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
/** Inner HTML for the panel body. */
export function scheduleHtml(v, tr) {
  if (v.state !== 'ok') return `<p class="text-xs ${v.state === 'loading' ? 'text-slate-400' : 'text-amber-300'}">${esc(v.msg)}</p>`;
  const cell = (k, val, cls = '') => `<div><div class="k">${esc(tr(k))}</div><div class="font-mono text-sm ${cls}">${esc(val)}</div></div>`;
  const bar = v.mined === null
    ? `<p class="text-[11px] text-amber-300 mt-1">${esc(tr('sched.minedNA'))}</p>`
    : `<div class="flex text-[11px] text-slate-400 mt-1"><span>${esc(tr('sched.mined'))} <b class="font-mono text-gold">${esc(v.mined)}</b> / ${esc(v.pool)} AGIS</span><span class="ml-auto font-mono">${esc(v.pct)}</span></div>`
      + `<div class="h-1.5 bg-slate-800 rounded mt-1" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${(v.pctBps / 100).toFixed(2)}" aria-label="${esc(tr('sched.mined'))}"><div class="h-1.5 bg-gold rounded" style="width:${Math.max(v.pctBps > 0 ? 0.5 : 0, v.pctBps / 100)}%"></div></div>`;
  return `<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">${cell('sched.epoch', v.epoch, 'text-cyan')}${cell('sched.perUnit', v.perUnit + ' AGIS', 'text-gold')}${cell('sched.allowed', v.allowed + ' AGIS')}${cell('sched.next', v.nextHalving + ' · ' + v.days + tr('sched.daysShort'))}</div>`
    + `<div class="mt-3">${bar}</div><p class="text-[11px] text-slate-500 mt-2">${esc(v.plain)}</p>`;
}
