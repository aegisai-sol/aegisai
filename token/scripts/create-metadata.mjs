// Create Metaplex Token Metadata (V3) for AGIS. MUST run while payer is still mint authority (before revoke).
// Usage: AGIS_MINT=<mint> npm run metadata   |  npm run metadata:plan
import { PublicKey, Transaction, sendAndConfirmTransaction } from '@solana/web3.js';
import mpl from '@metaplex-foundation/mpl-token-metadata';
import { cluster, connection, loadKeypair } from './common.mjs';
const { createCreateMetadataAccountV3Instruction, PROGRAM_ID } = mpl;

export const META = {
  name: 'AegisAI', symbol: 'AGIS',
  uri: process.env.AGIS_METADATA_URI || 'https://bold-thistle-3z5f.here.now/metadata/agis.json',
};
export function metadataPda(mint) {
  return PublicKey.findProgramAddressSync([Buffer.from('metadata'), PROGRAM_ID.toBuffer(), mint.toBuffer()], PROGRAM_ID)[0];
}
export async function createMetadata(c, payer, mint, mutable = true) {
  const ix = createCreateMetadataAccountV3Instruction(
    { metadata: metadataPda(mint), mint, mintAuthority: payer.publicKey, payer: payer.publicKey, updateAuthority: payer.publicKey },
    { createMetadataAccountArgsV3: { data: { ...META, sellerFeeBasisPoints: 0, creators: null, collection: null, uses: null }, isMutable: mutable, collectionDetails: null } });
  return sendAndConfirmTransaction(c, new Transaction().add(ix), [payer]);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const DRY = process.argv.includes('--dry-run'); const net = cluster();
  console.log(`AGIS metadata | cluster=${net.name} | ${JSON.stringify(META)} | program=${PROGRAM_ID.toBase58()}`);
  if (DRY) { console.log('DRY RUN: would send CreateMetadataAccountV3 (isMutable=true, 0% royalty). Requires payer = current mint authority. ~0.0056 SOL rent.'); process.exit(0); }
  if (net.name === 'mainnet-beta' && !process.argv.includes('--yes-mainnet')) { console.error('Mainnet requires --yes-mainnet'); process.exit(1); }
  if (!process.env.AGIS_MINT) { console.error('Set AGIS_MINT=<mint pubkey>'); process.exit(1); }
  const mint = new PublicKey(process.env.AGIS_MINT);
  const sig = await createMetadata(connection(), loadKeypair(), mint);
  console.log(`Metadata ${metadataPda(mint).toBase58()} created: ${sig}`);
}
