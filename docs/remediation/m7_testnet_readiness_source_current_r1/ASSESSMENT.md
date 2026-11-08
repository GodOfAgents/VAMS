# Testnet deployment source and runtime-mode gate revalidation

Date: 2026-10-03
Status: all four local source/preflight commands passed; independent review pending.

## Verification

Pinned Python 3.12.14 and pytest 9.1.1 were run offline with a cleared environment, a read-only checkout, and only the evidence directory writable. Each CI-equivalent command is captured separately with exact bwrap argv, stdout, stderr, exit code, source hashes, and tool versions in RUN.json.

- Deployment ceremony source scan: exit 0; required source snippets passed. The scanner explicitly says Safe ownership, role transfer, and explorer evidence remain runtime gates.
- Deployment ceremony source tests: exit 0; 3 tests passed.
- Testnet live-mode preflight with only VAMS_ENV=testnet set: exit 0; sanitized output reports mode testnet, classification live, and gateway_mock_enabled false.
- Runtime preflight suite: exit 0; 27 tests passed. Pytest cache was disabled to avoid writing into the read-only checkout.

## Scope and limits

This is static source and local configuration evidence only. It does not verify deployed Safe identities, on-chain role ownership, addresses, explorer evidence, approved wallet credentials, chain connectivity, Cardano Pre-Prod or Polygon Amoy state, or the full release/security gates. It is not deployment-readiness evidence and does not authorize a deployment ceremony.
