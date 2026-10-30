# AGIS Mint Checklist
1. **Keypair** — `npm run keygen` (devnet) or `SOLANA_KEYPAIR=<path>`; `.keys/` is gitignored. Never paste secrets into chat/README.
2. **RPC** — set `SOLANA_RPC` to a working endpoint (see README → RPC).
3. **SOL** — ≥0.02 SOL on payer (devnet: `npm run airdrop` or faucet.solana.com).
4. **AGIS_DEV_WALLET** — set vesting/dev pubkey (15% max); unset = stays earmarked in creator ATA.
5. **Metadata** — host `metadata/agis.json` + logo on the site; `npm run metadata:plan`.
6. **Dry run** — `npm run plan`.
7. **Devnet create** — `npm run create`; check `deployments/devnet.json` + explorer (metadata name/symbol/logo).
8. **Revoke** — verify mintAuthority=null and freezeAuthority=null.
9. **Streamflow vesting** — later, for the dev 15%.
10. **No LP yet.** Mainnet only with owner OK: `MAINNET=1 npm run create -- --yes-mainnet`.
