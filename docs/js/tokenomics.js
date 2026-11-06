// AGIS mining tokenomics. Shared by miner.html and rwa.html.
// Mirrors token/scripts/mine-rules.mjs + claim-server UNIT_BPS=1 (soft-go share of era emission).
export const MINT = 'GhSiU95vtKwn7FBAW1u5krxYP2PnpFPotb1LJFZkbzhW';
export const MAX_SUPPLY = 10_000_000_000, MINING_SHARE = 0.85;      // 85% mining, 10% team, 5% ecosystem
export const GENESIS = Date.parse('2026-10-31T00:00:00Z'), ERA_MS = 2 * 365 * 864e5; // halving every ~2 years
export const ERA_SEC = 2 * 365 * 24 * 3600;
// Integer RATE0 (base units / sec) matches mine-rules.mjs; UNIT_BPS=1 → each verified unit earns RATE0/10000.
export const RATE0_BASE = Number((8_500_000_000n * 10n ** 9n / 2n) / BigInt(ERA_SEC)); // 67383307965
export const UNIT_BPS = 1;
export const FREE_WALLETS = 100;
export const ONE_X_BPS = 10000;
// Half the mining pool is emitted in era 0; each era halves.
export const ERA0_POOL = MAX_SUPPLY * MINING_SHARE / 2;
export const era = (t = Date.now()) => Math.max(0, Math.floor((t - GENESIS) / ERA_MS));
export const nextHalving = (t = Date.now()) => GENESIS + (era(t) + 1) * ERA_MS;
// Device power tiers (benchmarked in-browser, see bench()).
export const TIERS = { phone: { k: 1, label: 'Phone' }, laptop: { k: 2.5, label: 'Laptop / PC' }, server: { k: 6, label: 'Server' } };
// AGIS per verified unit at era 0, 1x difficulty (RATE0_BASE / 1e9 / 10000 * UNIT_BPS).
export const BASE_PER_UNIT = RATE0_BASE / 1e9 / 10000 * UNIT_BPS; // ≈ 0.0067383307965
export const DAILY_CAP = 100, JOB_CAP = 25;       // AGIS per wallet per day / per RWA job
// Network difficulty (mine-rules): full reward until FREE_WALLETS claim today; then FREE/active.
export function difficultyBps(active, free = FREE_WALLETS) {
  const a = Number(active) || 0, f = Number(free) || FREE_WALLETS;
  if (!Number.isInteger(a) || a < 0 || !Number.isInteger(f) || f <= 0) throw new Error('bad difficulty input');
  return a <= f ? ONE_X_BPS : Math.floor(ONE_X_BPS * f / a);
}
/** Multiplier in [0,1] from active wallets today. Kept as `difficulty` name for callers. */
export const difficulty = (active) => difficultyBps(active) / ONE_X_BPS;
// Reward for one verified unit: base × tier_share × halving × difficultyBps/10000
// tierK capped at 2 on claim path (server: Math.min(dev.k, 2)).
export const unitReward = (tierK, activeWallets = 1, t) =>
  BASE_PER_UNIT * Math.min(Number(tierK) || 1, 2) / 2 ** era(t) * difficulty(activeWallets);
// RWA job multiplier: bigger / longer / heavier verify = more AGIS
export function rwaFactors(bytes, pages = 1, kind = 'doc') {
  const size = 1 + Math.log2(1 + bytes / 262144);            // +1 per 4× over 256 KB
  const duration = 1 + Math.min(4, pages / 10);              // longer docs need more passes
  const compute = { doc: 1, image: 1.5, deed: 2, financial: 2.5 }[kind] || 1;
  return { size, duration, compute, mult: size * duration * compute };
}
export const rwaReward = (bytes, pages, kind, tierK, activeWallets) =>
  Math.min(JOB_CAP, 2 * rwaFactors(bytes, pages, kind).mult * unitReward(tierK, activeWallets));
export const estUnits = (bytes, pages) => Math.ceil(20 * (1 + bytes / 262144) * (1 + pages / 10));
// Quick CPU bench → tier
export function bench() { const t0 = performance.now(); let x = 0; for (let i = 0; i < 3e6; i++) x = (x + i * 2654435761) >>> 0; const ms = performance.now() - t0, c = navigator.hardwareConcurrency || 2;
  return { ms, cores: c, tier: c >= 12 && ms < 15 ? 'server' : (c >= 4 && ms < 40 && !/Mobi|Android|iPhone/i.test(navigator.userAgent)) ? 'laptop' : 'phone' }; }
// Honest jobs queue (browser-local until the coordinator jobs API is online)
export const jobs = { all: () => JSON.parse(localStorage.agisJobs || '[]'), save: a => localStorage.agisJobs = JSON.stringify(a.slice(-200)) };
