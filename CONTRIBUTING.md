# Contributing to AegisAI

Thanks for helping build Proof-of-Verification.

## Ground rules
- **Never commit keys, seeds or `.env`.** `.keys/` and keypair files are gitignored; PRs containing secrets are rejected and the key is considered burned.
- Devnet by default. Anything touching mainnet must be gated (`MAINNET=1 --yes-mainnet`) and reviewed by two maintainers.
- Be honest in copy: label simulated data as simulated. No price promises.

## Workflow
1. Open an issue describing the change (bug, protocol idea, node type, UI).
2. Branch `feat/<topic>` or `fix/<topic>`; small focused PRs.
3. Run locally: site (`python3 -m http.server`), miner (`python3 main.py --seconds 10`), token (`npm run plan`).
4. Protocol changes: update `docs/PROOF_OF_VERIFICATION.md` (threat model section if security-relevant).

## Good first areas
ONNX small-model verifiers · WebGPU/WASM browser verifier · commit–reveal in the coordinator · dashboard live data via Solana RPC · translations.

## Security
Report vulnerabilities privately to the maintainers, not in public issues.
