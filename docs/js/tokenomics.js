// AGIS mining tokenomics. Shared by miner.html and rwa.html. Mirrors token/scripts/claim-server.mjs.
export const MINT = 'GhSiU95vtKwn7FBAW1u5krxYP2PnpFPotb1LJFZkbzhW';
export const MAX_SUPPLY = 10_000_000_000, MINING_SHARE = 0.85;      // 85% mining, 10% team, 5% ecosystem
export const GENESIS = Date.parse('2026-10-31T00:00:00Z'), ERA_MS = 2 * 365 * 864e5; // halving every ~2 years
// Half the mining pool is emitted in era 0; each era halves.
export const ERA0_POOL = MAX_SUPPLY * MINING_SHARE / 2;
export const era = (t = Date.now()) => Math.max(0, Math.floor((t - GENESIS) / ERA_MS));
export const nextHalving = (t = Date.now()) => GENESIS + (era(t) + 1) * ERA_MS;
// Device power tiers (benchmarked in-browser, see bench()).
export const TIERS = { phone: { k: 1, label: 'Phone' }, laptop: { k: 2.5, label: 'Laptop / PC' }, server: { k: 6, label: 'Server' } };
export const BASE_PER_UNIT = 0.006738;           // matches claim-server RATE0/10000 at era 0 (not uncapped 0.01)
export const DAILY_CAP = 100, JOB_CAP = 25;       // AGIS per wallet per day / per RWA job
// Difficulty rises with active miners: D = 1 + log2(1 + miners/1000)
export const difficulty = miners => 1 + Math.log2(1 + miners / 1000);
// Reward for N verified units: base × tier × halving / difficulty
export const unitReward = (tierK, miners, t) => BASE_PER_UNIT * tierK / 2 ** era(t) / difficulty(miners);
// RWA job multiplier: bigger / longer / heavier verify = more AGIS
export function rwaFactors(bytes, pages = 1, kind = 'doc') {
  const size = 1 + Math.log2(1 + bytes / 262144);            // +1 per 4× over 256 KB
  const duration = 1 + Math.min(4, pages / 10);              // longer docs need more passes
  const compute = { doc: 1, image: 1.5, deed: 2, financial: 2.5 }[kind] || 1;
  return { size, duration, compute, mult: size * duration * compute };
}
export const rwaReward = (bytes, pages, kind, tierK, miners) => Math.min(JOB_CAP, 2 * rwaFactors(bytes, pages, kind).mult * unitReward(tierK, miners));
export const estUnits = (bytes, pages) => Math.ceil(20 * (1 + bytes / 262144) * (1 + pages / 10));
// Quick CPU bench → tier
export function bench() { const t0 = performance.now(); let x = 0; for (let i = 0; i < 3e6; i++) x = (x + i * 2654435761) >>> 0; const ms = performance.now() - t0, c = navigator.hardwareConcurrency || 2;
  return { ms, cores: c, tier: c >= 12 && ms < 15 ? 'server' : (c >= 4 && ms < 40 && !/Mobi|Android|iPhone/i.test(navigator.userAgent)) ? 'laptop' : 'phone' }; }
// Honest jobs queue (browser-local until the coordinator jobs API is online)
export const jobs = { all: () => JSON.parse(localStorage.agisJobs || '[]'), save: a => localStorage.agisJobs = JSON.stringify(a.slice(-200)) };
