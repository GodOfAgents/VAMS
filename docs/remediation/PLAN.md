# Dependency-ordered remediation plan

All milestones start NOT_STARTED. These M labels are this kit's project plan, not replacements for repository G0-G6 or T01-T36 gate identifiers. Map work to the current control matrix without renaming or relaxing it.

| Milestone | Finding links | Required output / exit condition |
|---|---|---|
| M0: Reconcile source and reproduce baseline | All | Current commit/toolchain inventory; native test baseline; source-linked F01-F16 revalidation; actual current control inventory. |
| M1: Strict runtime mode and demo containment | F09, F11, F12 | Unknown/missing deployment modes reject; no entrypoint bypass; simulations explicitly non-authoritative; diagnostics cannot produce live-success claims. |
| M2: Gateway request integrity and replay | F08 | Canonical versioned auth; signed body/query/audience/nonce/expiry; finite time; durable atomic replay handling; real HTTP, parallel-worker, restart and revocation tests. |
| M3: Cardano authority and state machines | F01-F05 | ADR and native adversarial transaction tests for insurance custody, authenticated state, governor voters/actions, timelock authority/delay and registry assets/slashes; valid/reject proof fixtures. |
| M4: Proof verification and settlement binding | F05-F07, F13 | Approved verifier/trust model; real backend call and authenticated public inputs; rejecting-backend/malformed-proof cases; canonical cross-language vectors; bounded fees and correct refunds/settlement. |
| M5: Real recoverable provider and DA execution | F10, F12, F15 | One real allowlisted provider/DA path, no website-as-capacity qualification; stable operation identity; restart/timeout/retry safety; independent exact read-back and bound receipts. |
| M6: Heart-Brain/GCA compatibility contract | F11, F14 plus cross-cutting | Versioned policy/anchor/decision envelope; pre-effect enforcement; policy invalidation on restart/update; denied effects absent; learned metrics telemetry-only until calibrated. |
| M7: Release engineering and evidence integrity | F16, every enabled control | Repeatable local runner/CI parity; current artifact digests and provenance; reproducible builds; controls/statuses justified; private-network/privacy/backup/drill manifests ready. |
| M8: Human-approved rehearsal and deployed observation | All enabled paths | Separate approval; testnet-only receipt/code/role/datum read-backs; real integration, outage and rollback observations; no deployment by default. |
| M9: Canary admission and actual soak | Existing profile's gate | Actual stage requirements satisfied; real seven-day closed observation under the inspected profile; explicitly logged resets/incidents; independent release decision. |

## Dependency details

M1 and M2 establish runtime boundaries. M3/M4 designs may be worked on in separate branches after M0, but shared envelopes and trust decisions must be coordinated before integration. M5 depends on relevant M2-M4 guarantees. Specify M6's envelope early, then prove enforcement using M5; do not bolt authorization onto payment after irreversible effects. M7 can begin scaffolding earlier but cannot claim final evidence before repairs and independent observations.

## M3 review contract

Test every redeemer with a realistic ledger transaction context, not only helper constants. Verify one authentic state output, assets and datum conservation; authorized unique signers; creation/minting and spending linkage; payout recipient/amount; spent approvals/nonces; real time intervals; and correct next-state identity. A repair that adds only one signature check is not full closure of the insurance or registry state machine.

## M4 design contract

Select an actual provider-specific TEE verifier and a particular ZK verifier/circuit interface. No substitute hash-equality check. Verify false, revert, malformed response, absent backend, wrong code identity, altered public inputs and domain replay. Audit activation/registry/deployment call paths too: safe library code is not enough if unsafe adapters can still be registered. Owner approval is needed for any change in the trust model.

## M5 recovery contract

Run real work on synthetic inputs. Inject crashes before and after external effects and before durable checkpointing. Recover on a second worker. Assert one authorized logical effect and no duplicate payment. Record a side-effect log or independent observer; error messages alone are not absence-of-effect evidence. Keep test-only local doubles explicitly labeled.

## M7 evidence contract

Mirror commands and pins from .github/workflows/security-gates.yml and scripts/audit/audit_program.py. Include Forge/Aiken/Rust/Python/frontend gates, security scanners, traceability/economic/red-team checks, checksum-pinned Envoy validation and commit-bound artifacts. For lockfile vulnerabilities, evaluate targeted upgrades with review; do not blindly run force-upgrade commands. Track parser limitations, valid suppressions and all skipped tests.

The audit reported missing assurance-index.json, both chain rehearsal manifests, runtime-integration.json and privacy-review.json. Recheck current state and schema. Produce each from actual observations. Store raw output outside the source tree, with content-addressed references imported through the approved evidence workflow. Diagnose dirty-tree failures precisely instead of ignoring all untracked files.

## Stage boundary without circular approval

Read the actual readiness implementation to distinguish source verification, controlled rehearsal, canary admission and observed qualification. When deployed receipts are prerequisites for admission, obtain them only under a separately approved minimal rehearsal ceremony. Do not demand a completed soak to start that soak, and do not mark it complete from simulated timestamps. Any necessary gate-architecture correction needs reviewed design and regression tests; it must not reduce assurance.

## Review and concurrency

Initially use one implementer and a separate review session. Worktree concurrency needs explicit file ownership and isolated build outputs/ports. A same-model second session is not a substitute for independent cryptographic/custody review, external observers or governance signers. Before release, rerun all enabled gates against the final exact commit and reconcile the complete set of changes.

## Tokenomics reconciliation and economic acceptance

Use [TOKENOMICS_HARDENING_RECONCILIATION_R1.md](TOKENOMICS_HARDENING_RECONCILIATION_R1.md)
as the source-backed economic gap map. Existing T17-T22/G2/G4 gates need explicit
clause-to-source-to-public-test-to-review reconciliation for vesting/GMV,
unbonding, supply, fee phases/burn, funded rewards, delegation, governance and
DEC. All new executable acceptance is PENDING; this is not implementation
authority or milestone completion.

First freeze owner-approved economic interpretations and restricted-profile
dispositions, then reproduce/remediate enabled defects in separately authorized
narrow slices. Future features may be deferred or disabled only with reviewed
scope and executable containment; missing tests or generic passing totals are
not exclusions. Preserve the faucet-only mission, zero rewards/no staking
minter and INV-8's absolute $1 \times 10^9$ cap; do not silently amend tokenomics
or demand an out-of-scope TGE for the internal testnet.

This cross-cutting work may progress independently of F04 diagnostics without
waiving the rejected runner or changing finding/milestone status. Readiness
remains NOT READY; deployment, Deposit, Slash activation and ExecuteIntent
remain disabled.
