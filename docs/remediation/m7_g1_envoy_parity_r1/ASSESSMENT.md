# M7 G1 Envoy Documentation Parity (R1)

Status: documentation correction completed; independent read-only review passed (recorded in remediation STATUS.md and SESSION_HANDOFF.md, 2026-10-02).

Observed date: 2026-10-02  
Repository: /home/GodOfAgents/code/VAMS-testnet  
Branch: testnet/remediation-20260907  
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

## Corrected claim

G1 now names the checksum-verified Envoy 1.39.1 validation of gateway/envoy.testnet.yaml that the security workflow actually runs. It separately states that this CI check alone does not establish which proxy is deployed: deployment review must validate the selected TLS-terminating proxy and loopback application bind. It also identifies gateway/Caddyfile.testnet.example as historical and unsupported for live ingress.

## Source evidence

- .github/workflows/security-gates.yml acquires Envoy 1.39.1 and verifies SHA-256 002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8, then validates gateway/envoy.testnet.yaml.
- gateway/envoy.testnet.yaml configures the TLS ingress and routes to 127.0.0.1:8000.
- gateway/server.py (SHA-256 ace02242ab38aa9fa5afa4371be21a1a7d2329d5b9241dec30c7d503ff393c7e) defines LIVE_BIND_HOST as 127.0.0.1.
- gateway/Caddyfile.testnet.example identifies itself as historical and unsupported for live Gateway use.
- The local change is limited to docs/audit/AUDIT_PROGRAM.md, SHA-256 75dd1c14c2852ad964d4b70d9905980dcbf7b98f27e10d3cfa11668b085f1784. Workflow SHA-256: 7ddeb89794f498393e9c3bb460ca1aaa74dde7b9637c590d76cdae3bbc3ec83a.

## Verification

- python3 --version - exit 0: Python 3.14.4.
- python3 scripts/docs/validate_docs.py - exit 0: Documentation validation passed.
- python3 -m unittest scripts/docs/test_validate_docs.py - exit 0: 2 tests passed.
- python3 scripts/audit/audit_program.py validate - exit 0: 36 tracks and testnet profile valid.
- python3 scripts/audit/test_audit_program.py - exit 0: 20 tests passed.
- git diff --check - exit 0.

Captured outputs:

- /home/GodOfAgents/vams-evidence/m7-g1-envoy-parity-20261002-r1/verification.json - SHA-256 9e841f4a47d7aee43bf462d22709dbde18a92645d89cbe371c948faed70e9954
- /home/GodOfAgents/vams-evidence/m7-g1-envoy-parity-20261002-r1/verification.txt - SHA-256 42ec56220dce36e78d548d58e52e1e633fa39c65711a7ef3bcaf589ee73d4dfd

## Remaining drift and impact

This documentation update does not establish a deployed proxy selection or deployment readiness. That configuration still requires separate deployment review and evidence. No runtime behavior, security posture, API, or deployment state changed, so docs/CHANGELOG.md was not changed. INV-1 through INV-10 behavior is unaffected. Deployment and gated activation paths remain disabled.
