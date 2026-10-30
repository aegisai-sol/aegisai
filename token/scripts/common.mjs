import fs from 'node:fs';
import { Connection, Keypair, clusterApiUrl } from '@solana/web3.js';
export const SUPPLY = 1_000_000_000n;
export const DECIMALS = Number(process.env.AGIS_DECIMALS ?? 9);
export function cluster() {
  if (process.env.MAINNET === '1') return { name: 'mainnet-beta', url: process.env.SOLANA_RPC || clusterApiUrl('mainnet-beta') };
  return { name: 'devnet', url: process.env.SOLANA_RPC || 'https://solana-devnet.api.onfinality.io/public' };
}
export function connection() { return new Connection(cluster().url, 'confirmed'); }
export function loadKeypair() {
  const p = process.env.SOLANA_KEYPAIR || './.keys/devnet.json';
  if (!fs.existsSync(p)) throw new Error(`Keypair not found at ${p}. Run "npm run keygen" (devnet) or set SOLANA_KEYPAIR.`);
  return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(fs.readFileSync(p, 'utf8'))));
}
