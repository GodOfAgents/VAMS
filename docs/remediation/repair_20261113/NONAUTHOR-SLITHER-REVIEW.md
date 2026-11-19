# Non-author Slither source review — 2026-11-13

**Lifecycle follow-up (2026-11-14):** The requested callback/lifecycle tests are
now implemented and locally verified. They exposed checkpoint payout replay and
deposit reentry defects; the repaired source and new evidence supersede the
earlier source-only conclusions for that component. See
[callback/lifecycle regressions](CALLBACK-LIFECYCLE-REGRESSIONS.md). The original
review and approval-history snapshots below remain historical evidence; they do
not describe the final source or establish release readiness.

**Approval follow-up (2026-11-13):** The owner approved and applied the exact
TOKENOMICS.md 2.3.0 proposal (SHA-256
`c2d9c0021a6548e163007cb57fcefa8416e5573db0f9729c86d17d68669701f8`).
The review-hold paragraphs and receipts below describe the earlier pre-approval
snapshot. This documentation update does not activate economic features or
provide release/deployment acceptance; readiness remains NOT READY.

The legacy attestation retirement and all 61 residual Medium finding identities
received source-first non-author AI review. No additional production defect was
identified or reproduced. No production source or tests changed in this slice.
This is a supporting evidence record, not an acceptance ledger or deployment grant.
Readiness remains **NOT READY**; the full A–G program, both chains and 13 open /
0 of 36 verified audit-track status are not promoted.

## Review coverage and source binding

| Review record | Residual IDs | SHA-256 |
| --- | ---: | --- |
| legacy-callbacks | 6 | `beaeced6451a9a23f23883615c6ade8d613d2d0e7c957173ce425dc2e57195e5` |
| codec-returns | 41 | `97d091ea9a5d4478429a5ac870cece34f789a986642ceb41954e7ed0a0c26466` |
| math-guards | 14 | `f180153d7acbc1336bafb262a657d6db2fd0cab720199593712a874467e0cad9` |

The legacy-callbacks reviewer also assessed the retired ERC-8004 entrypoint,
preimage, ABI/callers and four existing regression methods. Its verdict is PASS
for source-level fail-closed containment: the unconditional revert occurs before
registry/verifier calls; verifier replacement cannot enable acceptance. It does
not attest an enclave or modify an already deployed immutable adapter.

Records live under `C:/Users/aseem/VAMS-mono/VAMS-slither-nonauthor-20261113-03/`
(E3), in `reviews/`. Every current Medium ID is assigned once, with its own
verdict, rationale, source locations, evidence and remaining gap. E3
`REVIEW-COVERAGE.json` has SHA-256 `afa20690187e96433f39509cb0fe66a180b6c9a6701db561f4667b8416e9a6c2`.
Its ID set equals the fresh scanner's 61 Medium IDs without omissions or extras.
It preserves reviewers' actual conclusions rather than replacing them with a
group-level pass.

The selected 239-file runtime/test/script/configuration source manifest remains
`938ee1157ad1034ab37c3724d1c4a36c9d5b51b6193394b854ad9e43f7417631`.
E3 `BASELINE.json` (SHA-256
`fdc1783cd98d6642ba252b9c0cb4fd525cd5daa161645b54f434ab8881cc3fb0`)
reconciled 243 selected inputs/docs across Windows and canonical WSL before
review. Canonical HEAD remains
`4f0f7887efb384e883b9de4d7c56387479e471a5`, dirty `remediation/phase1`.
The fresh Slither JSON has SHA-256
`cfef7904096846ea43ef4c6830d36737501829010ce8cedf8601c315d9779233`,
identical to the report reviewed by all three reviewers. No detector,
configuration, exclusion or suppression changed.

Root requested `gpt-6-luna` / `high` for each worker. Actual runtime model/effort
are not exposed through the review tool; original self-reported metadata was
corrected in separate `*-metadata.json` errata, preserving the original reports.
Reviewers could not execute in WSL (E_ACCESSDENIED). They verified mirror source
hashes and read tests/raw evidence; canonical reconciliation and fresh execution
were performed separately by the primary on the owner-operated runner. This is
not independent execution, human assurance, custody approval or hosted CI.

## Findings and limits

The 20 initialization and 21 return-value items were independently traced through
decode failure/success paths, signature checks and downstream settlement. The
four arithmetic and ten equality items were checked against exact window/cap
math and discrete state/existence semantics. The six callback items were traced
through shared guards, exact consumed timelock frames, agent/provider authority,
and configured dependency boundaries. Reviewers found no justified production
repair; speculative source changes were not made.

Remaining verification gaps are retained:

- Direct malicious escrow-manager callbacks for TwoPhaseCommitManager.
- Direct create/refund callbacks for ComposedSettlement.
- A direct nested-relay case for Heartbeat V3.
- Checkpoint duplicate/missing/finalize/challenge lifecycle tests. Timestamp
  existence sentinels assume positive transaction timestamps; genesis-prepopulated
  state and other portability profiles are not qualified.
- Authentic DCAP/collateral, root custody, live providers, clients outside the
  repository and retirement of old deployed immutable adapters.

The callback reviewer explicitly confirmed the missing tests are verification
gaps, not reproduced production defects, and do not block source-level confidence
in the unconditional retirement. The full suite cannot stand in for these tests.
ComposedSettlement's unchanged 24,401-byte runtime has only 175 bytes of EIP-170
headroom. All 28 Optimization findings remain unadjudicated in this scope.

## Fresh gate evidence

Heavy jobs ran sequentially, offline, network-isolated, with FFI disabled, pinned
tools/dependencies, two threads, 600-second bounds and source identity checks.
No install, provider call, signing, funding, role or deployment action occurred.

| Gate | Result | Retained record |
| --- | --- | --- |
| Full Solidity | 1,242 passed, 0 failed/skipped, 83 suites | E1 `NONAUTHOR-FULL-01.json/.stdout/.stderr` |
| Size | Exit 0; existing compiler/lint warnings retained | E1 `NONAUTHOR-SIZES-01.json/.stdout/.stderr` |
| Slither 0.11.5 | Exit 0; 0 High, 61 Medium, 28 Optimization | E2 `NONAUTHOR-SLITHER-01.json/.stdout/.stderr`; decoded streams/report also in E3 |

E1 is `VAMS-slither-medium-20261113-01`; E2 is
`VAMS-slither-medium-20261113-02`, under the same workspace. Commands reuse the
retained hash-bound runners with phase/label `full NONAUTHOR-FULL-01`,
`sizes NONAUTHOR-SIZES-01` (manifest pin `938ee115…7631`) and
`slither NONAUTHOR-SLITHER-01` (manifest pin `881b9ec3…98c3`). These are completed
single-use execution labels, not instructions to resubmit them. Each receipt
contains complete outer argv, tool/dependency hashes, configuration/environment,
raw stream hashes and source/Git bindings. Each Forge stdout begins with the
complete inner argv. Fresh tests replace neither prior failures nor required
future integration/operational gates; counts from overlapping runs are not added.

## Restricted profile and user review hold

INV-6 containment remains in force. INV-1 through INV-5 and INV-7 through INV-10
enforcement is unchanged. Owner decisions 3/4 still require disabled TEE routes
without authentic qualification, zero emissions/rewards, no staking minter,
inactive vesting/buyback/reward distribution/delegation/slashing/token governor,
and frozen-unset DEC floor/decay/tail. Both Amoy and Cardano Pre-Prod remain in scope.

TOKENOMICS.md remains byte-for-byte unchanged at SHA-256
`d60363950557c354acae91771d0badc71ba2aad4456dc2564ec8409c6e15cd74` pending the user's review.
E3 `TOKENOMICS.proposed.md` and `TOKENOMICS.proposed.diff` are review artifacts
only. They summarize verified repairs, source-review limits and fresh gates;
they do not change allocations, approved economics, activation or readiness.
Apply them only after the user reviews and authorizes this proposed update.

Documentation integration is constrained to four named files with retained
preimages and exact before/after hashes. E3 `DOCS-INTEGRATION-RECEIPT.json` records
the completed copy and unchanged 239 runtime inputs/Tokenomics hold. The final
assessment separately records docs and scoped-secret checks. No authoritative
track/gate acceptance status is manually cleared.
