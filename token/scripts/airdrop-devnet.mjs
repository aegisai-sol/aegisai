import { LAMPORTS_PER_SOL } from '@solana/web3.js';
import { cluster, connection, loadKeypair } from './common.mjs';
if (cluster().name !== 'devnet') { console.error('Airdrop is devnet-only.'); process.exit(1); }
const kp = loadKeypair(), c = connection();
const sig = await c.requestAirdrop(kp.publicKey, 1 * LAMPORTS_PER_SOL);
await c.confirmTransaction(sig, 'confirmed');
console.log(`Airdropped 1 SOL to ${kp.publicKey.toBase58()} | balance ${(await c.getBalance(kp.publicKey)) / LAMPORTS_PER_SOL} SOL`);
