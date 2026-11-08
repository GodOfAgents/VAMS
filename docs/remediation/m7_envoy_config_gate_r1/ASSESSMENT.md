# M7 Local Envoy Configuration Gate (R1)

Status: local CI-equivalent configuration observation completed; independent review pending.

Observed date: 2026-10-02  
Repository: /home/GodOfAgents/code/VAMS-testnet  
Branch: testnet/remediation-20260907  
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

## Scope and result

Executed the current gateway-config-gate locally using the already-present Envoy 1.39.1 binary. The binary SHA-256 matched the workflow pin: 002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8. The workflow version check passed; scripts/security/validate_envoy_gateway.py reported "Envoy live-ingress contract: PASS"; Envoy --mode validate accepted the temporary rendered configuration with "configuration ... OK". The targeted test_validate_envoy_gateway.py suite passed all 10 tests using the pinned Python 3.12.14 environment.

This is local synthetic CI-fixture evidence only. It proves the current source configuration passes the checked validator and Envoy parser under the captured tool versions. It does not prove external reachability, deployed proxy selection, certificate custody, runtime behavior, testnet use, ledger admission, or live-network status.

## Exact commands and verification

The captured transcript contains the expanded CI-equivalent commands, including SHA-256 verification, Envoy version check, disposable OpenSSL fixture creation, sed path substitution, static contract validation, and Envoy --mode validate.

- /home/GodOfAgents/vams-evidence/m7-envoy-config-gate-20261002-r1/verification.json - SHA-256 aeeb8e98aa578a0f5812627f17828df915cb3bc067595bfce0b8889534b40ba7
- /home/GodOfAgents/vams-evidence/m7-envoy-config-gate-20261002-r1/verification.txt - SHA-256 d13b26606fb2f91a2d9d54b4c45af4105428567ac5520a081307f43aefdc6c65

Source hashes are recorded in verification.json for the workflow, static validator, its tests, Envoy and Caddy configs, and gateway/server.py. The pinned binary hash equals the workflow's digest. The test-only CA and server private key and rendered temporary config were created under a unique /tmp directory and removed by an EXIT trap. No live credentials or keys were created; no tools were installed or fetched.

## Impact and remaining blockers

No source behavior changed in this slice; the G1 documentation correction remains the only product-document change. INV-1 through INV-10 behavior is unaffected. No changelog update is required. Deployment and gated activation paths remain disabled. F05.2a remains unresolved; full readiness remains NOT READY.
