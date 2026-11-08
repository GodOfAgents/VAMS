# F04 canonical identity-policy anchor gate - 2026-10-04

Implementation remains BLOCKED before source changes. Standalone `agent_nft.agent_nft.mint` remains the owner-approved path and registry-side minting must reject. The current design cannot have registry spends authenticate the policy ID supplied in a datum. An alternate mint policy can satisfy its generic mint/datum/output checks. Keeping policy ID equal to registry script hash reinstates the rejected Option-B coupling.

A read-only security review checked the existing F05 authority artifacts and found no F04 anchor: `AuthorityStateV3` has no F04 policy ID or registry hash; F05 state spends reject all spends; approved F05 identity evidence covers only the F05 singleton. The review also rejected the proposed single global anchor as specified: `agent_nft` is parameterized by a consumed per-identity `bootstrap_ref`, so applied policy IDs vary by registration and one singleton cannot authorize repeated registrations. The F04 owner must choose a revised identity-policy model. Exact decision options and test needs are in `ANCHOR-DECISION.md`.

## Current-source baseline

Canonical HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, branch `testnet/remediation-20260907`; checkout was already dirty. No validator or protected Cardano file changed.

Pinned Aiken v1.1.21+42babe5 was invoked by absolute path (not on default PATH), binary SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`. Network-isolated disposable-copy command `aiken check --deny --seed 20260711 --max-success 250` exited 0: 122/122 tests passed (115 unit, 7 property), 0 failed. This is Aiken baseline evidence only; paired Plutus V3 policy/registry contexts were not tested.

`git diff --check`: PASS, exit 0. No paired evaluator/harness, ledger admission, simulator, Cardano Pre-Prod, or live-network evidence was produced.

Validator SHA-256: `agent_nft.ak` e28ff520d07f73a622a093b362f66411678d535bbb48cf2aecbcd8011204caba; `agent_registry.ak` 7655acb5d48cb0abcfe85dadfe9aa9c80046bff3aeeaf0720cb706084adbb5cd.

Next single slice: owner selects identity-policy model A or B in `ANCHOR-DECISION.md`; then produce a versioned design and obtain independent review before implementation. F05 remains 45/55 negatives and 18/21 mutations. Readiness NOT READY; deployment, Deposit, Slash activation, ExecuteIntent disabled.
