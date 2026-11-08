# M3.2b-R3 implementation — governance evaluator and forward provenance

Date: 2026-09-28 UTC
Repository: `/home/GodOfAgents/code/VAMS-testnet`
Baseline: M3.2b-R2 review package `/home/GodOfAgents/vams-evidence/m3-2b-r2-review-20260927-195001-829ab544571f` (SHA256SUMS SHA-256 `5dd567788e20b7fc2b9220af94469728a913c5c39675c09a1d46fc06536893ce`). R1 implementation package verification also passed (`6545dbcbe06997148b4088cf1dffff28319ede9cc5280538534a47f70ddc62ee`); accepted M3.2a-R22 verification passed (`35e89e15e545b33ecabd87cb320e93943e42ef8a66e3180102e242f556dfa1ac`).

## Scope and changes

This local remediation addressed the R2 provenance and compiled-evaluator gaps. Governance source changes bind authority continuations to the spending input address, require exact authority-token ownership on the input, require exact proposal/intent counter increments, and preserve immutable authority fields. Governance-policy authority discovery now requires a valid inline authority datum and the exact authority state asset quantity; burn handling requires exactly one unit of the selected asset. `CreateProposal` remains disabled because the frozen F05-authenticated creation contract is not available.

A forward-versioned `m3.2b-r3-dependency-manifest-v1` manifest records the current source set, raw and normalized lock digests, allowed volatile lock fields, dependency identity, blueprint bytes and every compiled program hash. The canonical lockfile was not rebuilt in place.

## Fresh verification

- R1, R2 and accepted M3.2a-R22 evidence prerequisites were verified before edits.
- Pinned Aiken 1.1.21 isolated check/build: source check passed; the checked-in blueprint was regenerated from the isolated build (SHA-256 `7477763e57c4d7471eb5badf6a54a828a5087d1cfe6e565c985474f9237e5477`).
- Forward provenance verifier and complete R9/R11/R13 provenance suite: **20 tests, OK**; isolated verifier exit 0.
- Compiled public evaluator: **36/36 public-handler rows executed**, 0 pending, 0 row failures.
- Mutation evaluator: **not accepted**. The disposable unconditional timelock-spend mutation compiles, but the current fixture is rejected before the mutated handler can return success (`mutation_not_detected`). This remains a required R3 blocker.
- Structural mutation gate therefore fails closed; no mutation result is presented as acceptance evidence.
- `git diff --check`: pass. Recursive submodule status was unchanged.

## Status and decisions

R3 is **PARTIAL / NOT ACCEPTED**. The forward provenance regression and compiled row execution are implemented, but the required mutation-sensitive compiled-handler proof and complete worst-state/one-over reconciliation are not closed. F01-F05 remain `REVALIDATED_OPEN`; Deposit and Execute remain disabled pending F05; M3 remains `OPEN`; Pre-Prod admission remains `INCONCLUSIVE`; promotion remains `NOT READY`.

Invariant impact: INV-1 through INV-10 are unchanged; this slice only hardens the Cardano governance/provenance workstream. M1/M2 containment and mock-mode behavior are unchanged. No deployment, credential, vendor, dependency installation or Git-history operation was performed.

Next step: resolve the compiled mutation-fixture/evaluator blocker, then perform the independent M3.2b-R4 review.
