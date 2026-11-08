# M7 governance-policy warning cleanup - 2026-10-03

Status: accepted after independent integrated review. G1 remains failed.

## Scope and invariant impact

Changed only `cardano/validators/governance_policies.ak`: removed three unused imports, renamed two unused predicate callback parameters, and deleted the unreferenced private `find_intent_or_false` helper. No validator logic, redeemer branch, predicate, or test changed. No INV-1 through INV-10 enforcement changed.

Baseline source SHA-256: `60e53d156574b3fb3ac8d9f7f71533d55412fbfb717199c84521f2c8a92e6f44`; candidate source SHA-256: `da0df0fc78e55182dea92921970bb8f127e71b83eaf171b1e18a8a5022bbf73c`.

## Verification

Pinned Aiken: `aiken v1.1.21+42babe5`, executable SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`.

- Network-isolated baseline and candidate `aiken build`: both exit 0; complete `plutus.json` SHA-256 is `c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008` in both, with every compiled script hash equal.
- Warning-only `aiken check --deny --skip-tests`: exit 1, 0 errors, 7 warnings, and no warning points to `validators/governance_policies.ak`.
- Exact CI command `aiken check --deny --seed 20260711 --max-success 250` in a network-isolated snapshot: exit 1; 122/122 scenarios passed, 1865 checks, 0 errors, 7 warnings. All 73 recorded input hashes matched canonical preflight and remained unchanged in snapshot and canonical checkout.
- `git diff --check`: exit 0.

Raw outputs, exact tool/workflow/command identity, build comparison, and 73-input maps are under this directory. This is compiler and synthetic test evidence, not ledger admission or live-network evidence.

## Independent review

`/root/f05_warning_integrated_review`: PASS for the exact integrated source and evidence packet. The reviewer verified the scoped diff, baseline/candidate source hashes, all build outputs, warning results, command/tool/workflow identity and all 73-input maps. Reviewer did not edit files or rerun project tools.

## Blockers and next slice

F05 remains 45/55 negative cases and 18/21 mutations. The `r2_signature_for_other_seed` evidence-contract decision and six applied-parameter A/B/C decision remain unresolved. Seven G1 warnings remain in `agent_nft.ak`; G1 exits 1. INV-1 through INV-10 revalidation, mock containment, provenance/reproducible builds, security/dependency checks, privileged governance, Cardano Pre-Prod and Polygon Amoy prerequisites, and T06/history remain unresolved. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

The next bounded slice is the read-only F04 identity-path reconciliation recorded in `docs/remediation/m7_agent_nft_audit_r1/ASSESSMENT.md`. The current accepted R6 implementation uses `agent_registry.agent_registry.mint`, while the frozen identity spec names standalone `agent_nft.agent_nft.mint`, whose handler currently rejects all minting. Do not alter that validator until the owner selects the normative path.
