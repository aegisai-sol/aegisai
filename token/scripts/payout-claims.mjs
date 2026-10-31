// AGIS claim payout CLI: verifies wallet-signed mining claims and mints AGIS to the claimer's wallet.
// Usage: MAINNET=1 SOLANA_KEYPAIR=.keys/<mint-authority>.json node scripts/payout-claims.mjs claims.json [--send]
// Default is DRY RUN. Keys are read from disk only; never printed.
import fs from 'node:fs';
import crypto from 'node:crypto';
import bs58 from 'bs58';
import { PublicKey } from '@solana/web3.js';
import { getOrCreateAssociatedTokenAccount, mintTo } from '@solana/spl-token';
import { connection, loadKeypair, DECIMALS } from './common.mjs';

const MINT = new PublicKey('GhSiU95vtKwn7FBAW1u5krxYP2PnpFPotb1LJFZkbzhW');
const GENESIS = Number(process.env.AGIS_GENESIS || Date.parse('2026-10-31T00:00:00Z') / 1000);
const ERA = 2 * 365 * 24 * 3600;
const RATE0 = (8_500_000_000n * 10n ** 9n / 2n) / BigInt(ERA);       // pov-r/mine-emit/2
const UNIT_BPS = BigInt(process.env.UNIT_BPS || 1);                    // share of 1s emission per verified task (bps)
const DAILY_CAP = BigInt(process.env.DAILY_CAP_AGIS || 100) * 10n ** BigInt(DECIMALS);
const MIN_SOL_LAMPORTS = 3_000_000; // ~ATA rent (2,039,280) + fees
const LEDGER = process.env.LEDGER || './deployments/claims-ledger.json';

const verify = (wallet, msg, sigB64) => {
  const der = Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), Buffer.from(bs58.decode(wallet))]);
  const key = crypto.createPublicKey({ key: der, format: 'der', type: 'spki' });
  return crypto.verify(null, Buffer.from(msg, 'utf8'), key, Buffer.from(sigB64, 'base64'));
};
const ledger = fs.existsSync(LEDGER) ? JSON.parse(fs.readFileSync(LEDGER, 'utf8')) : { seen: {}, day: {} };
const claims = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const send = process.argv.includes('--send');
const conn = connection();
const payer = loadKeypair();
const bal = await conn.getBalance(payer.publicKey);
console.log('payer', payer.publicKey.toBase58(), 'lamports', bal, send ? 'SEND' : 'DRY RUN');
for (const c of [].concat(claims)) {
  try {
    // msg format: "AEGIS/mine-claim/v1|<wallet>|<tasks>|<from_iso>|<to_iso>|<digest>"
    const [dom, w, tasks, from, to, dg] = c.msg.split('|');
    if (dom !== 'AEGIS/mine-claim/v1' || w !== c.wallet) throw 'bad message';
    if (!verify(c.wallet, c.msg, c.sig)) throw 'bad signature';
    if (ledger.seen[dg]) throw 'replay';
    const secs = (Date.parse(to) - Date.parse(from)) / 1000, n = Number(tasks);
    if (!(secs > 0 && n > 0 && n <= secs)) throw 'implausible work (max 1 task/sec)';
    const era = Math.floor((Date.parse(from) / 1000 - GENESIS) / ERA);
    let amt = (RATE0 >> BigInt(Math.max(era, 0))) * BigInt(n) * UNIT_BPS / 10000n;
    const day = new Date().toISOString().slice(0, 10), k = day + '|' + w, used = BigInt(ledger.day[k] || 0);
    if (used + amt > DAILY_CAP) amt = DAILY_CAP - used;
    if (amt <= 0n) throw 'daily cap reached';
    console.log(w, 'tasks', n, '->', Number(amt) / 10 ** DECIMALS, 'AGIS');
    if (!send) continue;
    if ((await conn.getBalance(payer.publicKey)) < MIN_SOL_LAMPORTS) throw 'payer SOL too low';
    const ata = await getOrCreateAssociatedTokenAccount(conn, payer, MINT, new PublicKey(w));
    const tx = await mintTo(conn, payer, MINT, ata.address, payer, amt);
    console.log('  minted tx', tx);
    ledger.seen[dg] = tx; ledger.day[k] = String(used + amt);
    fs.writeFileSync(LEDGER, JSON.stringify(ledger, null, 1));
  } catch (e) { console.log('reject', c.wallet, String(e)); }
}
