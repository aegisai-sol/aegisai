// Writes a fresh DEVNET keypair to ./.keys/devnet.json (gitignored). Never use for mainnet funds.
import fs from 'node:fs';
import { Keypair } from '@solana/web3.js';
const out = process.argv[2] || './.keys/devnet.json';
if (fs.existsSync(out) && !process.argv.includes('--force')) { console.log(`Exists: ${out} (use --force to overwrite)`); process.exit(0); }
fs.mkdirSync('./.keys', { recursive: true, mode: 0o700 });
const kp = Keypair.generate();
fs.writeFileSync(out, JSON.stringify(Array.from(kp.secretKey)), { mode: 0o600 });
console.log(`Devnet keypair written: ${out}\nPublic key: ${kp.publicKey.toBase58()}\nFund it: npm run airdrop  (or https://faucet.solana.com)`);
