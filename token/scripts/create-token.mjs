// AegisAI (AGIS) SPL token: create mint -> mint 1,000,000,000 to creator ATA -> revoke mint authority -> (optional) revoke freeze.
import fs from 'node:fs';
import { Keypair, LAMPORTS_PER_SOL, PublicKey } from '@solana/web3.js';
import { transfer, createMint, getOrCreateAssociatedTokenAccount, mintTo, setAuthority, AuthorityType, getMint, getMinimumBalanceForRentExemptMint } from '@solana/spl-token';
import { createMetadata } from './create-metadata.mjs';
import { SUPPLY, DECIMALS, cluster, connection, loadKeypair } from './common.mjs';

const args = new Set(process.argv.slice(2));
const DRY = args.has('--dry-run');
const KEEP_FREEZE = args.has('--keep-freeze');
const net = cluster();
const DEV_PCT = BigInt(process.env.AGIS_DEV_PCT ?? 15); // OWNER LOCKED: 15%
if (DEV_PCT < 0n || DEV_PCT > 15n) { console.error('AGIS_DEV_PCT must be 0..15'); process.exit(1); }
const DEV_WALLET = process.env.AGIS_DEV_WALLET || null; // vesting contract / dev wallet pubkey
const raw = SUPPLY * 10n ** BigInt(DECIMALS);
const explorer = (k, t = 'address') => `https://explorer.solana.com/${t}/${k}${net.name === 'devnet' ? '?cluster=devnet' : ''}`;

console.log(`Developer allocation ${DEV_PCT}% -> ${DEV_WALLET || '(AGIS_DEV_WALLET unset: stays in creator ATA, earmarked)'}`);
console.log(`AegisAI (AGIS) token | cluster=${net.name} | supply=${SUPPLY} | decimals=${DECIMALS} | raw=${raw}`);
if (DRY) {
  console.log(`\nDRY RUN plan (no network, no signing):
  1. createMint(decimals=${DECIMALS}, mintAuthority=payer, freezeAuthority=payer)
  2. getOrCreateAssociatedTokenAccount(payer)
  3. mintTo(ATA, ${raw})
  3b. transfer ${DEV_PCT}% (${raw*DEV_PCT/100n} raw) to dev/vesting wallet ATA
  3c. CreateMetadataAccountV3 (AegisAI/AGIS, uri metadata/agis.json)
  4. setAuthority(MintTokens -> null)   => supply fixed forever
  5. setAuthority(FreezeAccount -> null) => ${KEEP_FREEZE ? 'SKIPPED (--keep-freeze)' : 'nobody can freeze holders'}
  6. verify getMint(): mintAuthority=null, supply=${raw}
  Est. cost: ~0.0015 SOL rent (mint) + ~0.002 SOL (ATA) + ~5 tx fees  => < 0.01 SOL`);
  process.exit(0);
}
if (net.name === 'mainnet-beta' && !args.has('--yes-mainnet')) { console.error('MAINNET=1 also requires --yes-mainnet. Aborting.'); process.exit(1); }

const c = connection(), payer = loadKeypair();
const bal = await c.getBalance(payer.publicKey);
console.log(`Payer ${payer.publicKey.toBase58()} balance ${bal / LAMPORTS_PER_SOL} SOL (mint rent ${(await getMinimumBalanceForRentExemptMint(c)) / LAMPORTS_PER_SOL})`);
if (bal < 0.01 * LAMPORTS_PER_SOL) { console.error('Need >= 0.01 SOL. Devnet: npm run airdrop'); process.exit(1); }

let mint;
if (args.has('--revoke-freeze-only')) {
  mint = new PublicKey(process.env.AGIS_MINT);
} else {
  const mintKp = Keypair.generate(); // vanity mint: pass a pre-ground keypair via AGIS_MINT_KEYPAIR
  const mk = process.env.AGIS_MINT_KEYPAIR ? Keypair.fromSecretKey(Uint8Array.from(JSON.parse(fs.readFileSync(process.env.AGIS_MINT_KEYPAIR, 'utf8')))) : mintKp;
  mint = await createMint(c, payer, payer.publicKey, payer.publicKey, DECIMALS, mk);
  console.log(`1. Mint created: ${mint.toBase58()}`);
  const ata = await getOrCreateAssociatedTokenAccount(c, payer, mint, payer.publicKey);
  console.log(`2. Creator ATA: ${ata.address.toBase58()}`);
  console.log(`3. Minted: ${await mintTo(c, payer, mint, ata.address, payer, raw)}`);
  if (DEV_PCT > 0n && DEV_WALLET) {
    const devAta = await getOrCreateAssociatedTokenAccount(c, payer, mint, new PublicKey(DEV_WALLET), true);
    console.log(`3b. Dev allocation ${DEV_PCT}% -> ${devAta.address.toBase58()}: ${await transfer(c, payer, ata.address, devAta.address, payer, raw * DEV_PCT / 100n)}`);
  }
  if (process.env.AGIS_SKIP_METADATA !== '1') console.log(`3c. Metadata created: ${await createMetadata(c, payer, mint)}`);
  console.log(`4. Mint authority REVOKED: ${await setAuthority(c, payer, mint, payer, AuthorityType.MintTokens, null)}`);
}
if (!KEEP_FREEZE) console.log(`5. Freeze authority REVOKED: ${await setAuthority(c, payer, mint, payer, AuthorityType.FreezeAccount, null)}`);
const info = await getMint(c, mint);
const out = { cluster: net.name, mint: mint.toBase58(), decimals: info.decimals, supply: info.supply.toString(), mintAuthority: info.mintAuthority?.toBase58() ?? null, freezeAuthority: info.freezeAuthority?.toBase58() ?? null, explorer: explorer(mint.toBase58()), devAllocationPct: Number(DEV_PCT), devWallet: DEV_WALLET };
fs.mkdirSync('./deployments', { recursive: true });
fs.writeFileSync(`./deployments/${net.name}.json`, JSON.stringify(out, null, 2));
console.log('\nVerified:', out);
if (out.mintAuthority !== null) { console.error('ERROR: mint authority still set'); process.exit(2); }
