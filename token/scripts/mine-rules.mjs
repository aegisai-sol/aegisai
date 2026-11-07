// AGIS mine reward rules for the live claim server (pure, no keys, no RPC).
// Mirrors miner/aegis_miner/mine_emit.py + mine_claim.py:
//  - reward halves every ~2y era from GENESIS
//  - network difficulty: up to FREE_WALLETS distinct wallets per UTC day get
//    full reward; beyond that each claim is scaled FREE/active so more miners
//    share the same emission instead of printing more
//  - per-wallet and whole-network UTC-day caps clip, then fail closed.
export const DECIMALS = 9;
export const ERA = 2 * 365 * 24 * 3600;
export const RATE0 = (8_500_000_000n * 10n ** 9n / 2n) / BigInt(ERA);
export const ONE_X_BPS = 10000n;
export const FREE_WALLETS = 100;

export function eraOf(tsSec, genesisSec) {
  return Math.max(0, Math.floor((tsSec - genesisSec) / ERA));
}

export function difficultyBps(active, free = FREE_WALLETS) {
  if (!Number.isInteger(active) || active < 0 || !Number.isInteger(free) || free <= 0) throw new Error('bad difficulty input');
  return active <= free ? ONE_X_BPS : ONE_X_BPS * BigInt(free) / BigInt(active);
}

// ledgerDay: { 'YYYY-MM-DD|wallet': '<base>', 'YYYY-MM-DD|*': '<base>' }
// dayWallets: array of wallets that already claimed this UTC day
export function computeClaim({ tasks, fromSec, genesisSec, unitBps, wallet, day, ledgerDay, dayWallets, dailyCap, globalCap, free = FREE_WALLETS }) {
  const era = eraOf(fromSec, genesisSec);
  const raw = (era < 256 ? RATE0 >> BigInt(era) : 0n) * BigInt(tasks) * BigInt(unitBps) / 10000n;
  const set = new Set(dayWallets || []); set.add(wallet);
  const active = set.size;
  const dbps = difficultyBps(active, free);
  let amt = raw * dbps / ONE_X_BPS;
  if (amt <= 0n) return { ok: false, error: 'reward rounds to zero', era, active, difficultyBps: Number(dbps) };
  const used = BigInt(ledgerDay[day + '|' + wallet] || 0), gused = BigInt(ledgerDay[day + '|*'] || 0);
  if (used + amt > dailyCap) amt = dailyCap - used;
  if (gused + amt > globalCap) amt = globalCap - gused;
  if (amt <= 0n) return { ok: false, error: 'daily cap reached', era, active, difficultyBps: Number(dbps) };
  return { ok: true, amount: amt, era, active, difficultyBps: Number(dbps), used, gused };
}

// ---- Device tier lock (claim msg v1 + optional device fields) ----
// Signed msg: AEGIS/mine-claim/v1|wallet|units|from|to|uuid[|tier|cores|benchMs]
// Legacy 6-field msgs are treated as tier 'phone' (k=1) = old 1 unit/sec rule.
// units are tier-weighted work units (client adds up to k per verified task/sec).
// Server max: maxUnits = floor(elapsedSec × k). units > 2×max → reject; units > max → clip to max.
// Anti-spoof (SOFT-GO heuristic, not crypto proof; same thresholds as browser bench()):
//   server needs cores>=12 && benchMs<15, else downgraded to laptop;
//   laptop needs cores>=4 && benchMs<40, else downgraded to phone.
export const TIER_K = { phone: 1, laptop: 2.5, server: 6 };
export function deviceTier(tier, cores, benchMs) {
  if (tier === undefined || tier === '') return { tier: 'phone', k: 1, downgraded: false, legacy: true };
  if (!(tier in TIER_K)) throw new Error('unknown tier');
  const c = Number(cores), ms = Number(benchMs);
  if (!(Number.isInteger(c) && c > 0 && c <= 1024 && Number.isFinite(ms) && ms > 0 && ms < 1e5)) throw new Error('bad device fields');
  let t = tier;
  if (t === 'server' && !(c >= 12 && ms < 15)) t = 'laptop';
  if (t === 'laptop' && !(c >= 4 && ms < 40)) t = 'phone';
  return { tier: t, k: TIER_K[t], downgraded: t !== tier, legacy: false };
}
export function capUnits(units, secs, k) {
  if (!(Number.isInteger(units) && units > 0 && secs > 0)) throw new Error('bad units');
  const max = Math.floor(secs * k);
  if (max < 1) throw new Error('implausible work');
  if (units > 2 * max) throw new Error('implausible work (units > 2x tier max)');
  return { units: Math.min(units, max), max, clipped: units > max };
}

// ---- Mine-pool schedule ceiling (85% pool + halving, wipe-safe via on-chain supply) ----
// Daily caps are env-tunable; this is the hard invariant they can never break:
//   (1) cumulative mined <= emittedUntil(now) <= MINE_POOL  (halving schedule, 85% pool)
//   (2) on-chain supply + amount <= MAX_SUPPLY               (hard 10B mint ceiling)
// minedTotal = max(ledger sum of every 'YYYY-MM-DD|*' day, on-chain supply - LAUNCH).
// The chain term means a wiped/lost claim ledger cannot reset the ceiling, and anyone can
// audit it from Solana alone: getTokenSupply(mint) - LAUNCH <= emittedUntil(now).
// (Burns lower supply, so the chain term is a floor; the ledger term covers burned AGIS.)
// Mirrors miner/aegis_miner/mine_emit.py emitted_until + mine_claim.py "exceeds emission schedule".
export const BASE = 10n ** 9n;
export const MAX_SUPPLY_BASE = 10_000_000_000n * BASE;
export const MINE_POOL_BASE = 8_500_000_000n * BASE;
export const LAUNCH_BASE = 1_500_000_000n * BASE; // 10% team + 5% eco minted at launch (deployments/mainnet-beta.json)

export function emittedUntil(nowSec, genesisSec) {
  if (!Number.isFinite(nowSec) || !Number.isFinite(genesisSec)) throw new Error('bad time');
  const el = Math.floor(nowSec) - Math.floor(genesisSec);
  if (el <= 0) return 0n;
  const era = Math.floor(el / ERA);
  let total = 0n;
  for (let e = 0; e < Math.min(era, 256); e++) total += (RATE0 >> BigInt(e)) * BigInt(ERA);
  const into = BigInt(el - era * ERA);
  total += (era < 256 ? RATE0 >> BigInt(era) : 0n) * into;
  return total < MINE_POOL_BASE ? total : MINE_POOL_BASE;
}

export function minedFromLedger(ledgerDay) {
  let s = 0n;
  for (const [k, v] of Object.entries(ledgerDay || {})) if (k.endsWith('|*')) s += BigInt(v);
  return s;
}

// chainSupply: BigInt base units from getTokenSupply (required; caller must fail closed if RPC is down).
export function scheduleGate({ amount, ledgerMined, chainSupply, nowSec, genesisSec, launch = LAUNCH_BASE }) {
  if (typeof amount !== 'bigint' || amount <= 0n) throw new Error('bad amount');
  if (typeof chainSupply !== 'bigint' || chainSupply < 0n) throw new Error('bad chain supply');
  if (typeof ledgerMined !== 'bigint' || ledgerMined < 0n) throw new Error('bad ledger total');
  const chainMined = chainSupply > launch ? chainSupply - launch : 0n;
  const minedTotal = ledgerMined > chainMined ? ledgerMined : chainMined;
  const allowed = emittedUntil(nowSec, genesisSec);
  const out = { minedTotal, chainMined, ledgerMined, allowed, headroom: allowed > minedTotal ? allowed - minedTotal : 0n };
  if (chainSupply + amount > MAX_SUPPLY_BASE) return { ok: false, error: 'exceeds max supply', ...out };
  if (minedTotal + amount > allowed) return { ok: false, error: 'exceeds emission schedule', ...out };
  return { ok: true, ...out };
}
