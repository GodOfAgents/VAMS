# F04 documentation-only closure

Date: 2026-09-30
Status: REMEDIATED after independent R6 acceptance

## Scope and decision

This record reconciles the current F04 ledger only. It does not change the
Cardano source, fixture, evaluator, blueprint, lockfile, provenance
implementation, dependencies, vendors, credentials, deployment state or Git
history. The earlier compiled review remains historical evidence of the
pre-remediation blocker; the R6 implementation and independent review resolve
that blocker for the bounded Option-B registry scope.

F04 is now REMEDIATED. F01-F03 and F05 remain REVALIDATED_OPEN; M3 remains
OPEN; Deposit and ExecuteIntent remain disabled; post-F05 SlashAgent
activation remains blocked on F05 authority, finality and replay; Pre-Prod
admission remains INCONCLUSIVE; promotion remains NOT READY.

## Evidence chain

All prerequisite packages were verified with sha256sum -c SHA256SUMS before this
record. The SHA-256 digests of the manifest files are:

| Package | SHA256SUMS digest |
| --- | --- |
| /home/GodOfAgents/vams-evidence/m3-f04-compiled-independent-review-20260929T154615Z-829ab544571f (failed historical review) | 2eb0e478fb2e7ca0fcd17fde8cfbcb580b1b11086c367cf2649d1b83d5d463a7 |
| /home/GodOfAgents/vams-evidence/m3-f04-r-implementation-20260929T163500Z-829ab544571f | aaa4cfa8c9afabc51bcaff4bf99688d6f17af40f70f5a777ead6dd5b4fd1cc7c |
| /home/GodOfAgents/vams-evidence/m3-f04-r-supplemental-20260929T163500Z-829ab544571f | 501c5931cd728de27c2021cd64b652fcc283df25f314043b7c2d9f8f33a1585e |
| /home/GodOfAgents/vams-evidence/m3-f04-r6-independent-review-20260929T164500Z-829ab544571f | 8bf3d73fb9c5fc97511c75608c73021736ca33ad0c81c2e01a9ad07edfb1d4ff |

The repository state at closure is origin https://github.com/GodOfAgents/VAMS.git,
branch testnet/remediation-20260907, HEAD
829ab544571f12efe50ecb5740f129c8acb3e16f, 122 pre-existing dirty paths and
14 recursive submodules. Protected continuity hashes are recorded in the R6
review and prerequisite evidence manifests.

## Accepted implementation and results

- The immutable contract contains 49 fixture rows and 67 evaluations; all
  49/49 rows and 67/67 evaluations execute with zero pending and three legacy
  mint-side burn expectation amendments recorded explicitly in
  docs/remediation/m3_f04_impl_r4/fixture_reconciliation.json.
- Supplemental compiled coverage is 28/28; supplemental tests are 4/4;
  interface migration is 15/15; the frozen fixture suite is 14/14; and the
  forward provenance suite is 21/21.
- Two isolated pinned Aiken 1.1.21 runs pass 120/120 each and produce the
  byte-identical blueprint recorded in the R6 review.
- The accepted Option-B identity contract preserves exact raw UTF-8 DID bytes,
  requires 32-256 bytes and a UTF-8 round trip, and performs no normalization
  or reinterpretation.
- Forward provenance intentionally resets to the current lock hash. Historical
  lock bytes were unavailable, so this record makes no retroactive historical
  continuity claim.
- The production validator applies total datum validation, deterministic
  bootstrap-bound identity binding, exact mint linkage, linked terminal burn,
  owner payout and non-identity value conservation. SlashAgent remains
  fail-closed until F05 supplies reviewed authority, finality and replay.

## Invariant and release boundary

| Invariant | Impact |
| --- | --- |
| INV-1 | Unchanged; regional emissions controls were not touched. |
| INV-2 | Unchanged; insurance yield cap was not touched. |
| INV-3 | Unchanged; session-key expiry was not touched. |
| INV-4 | Unchanged; session-key contract allowlist was not touched. |
| INV-5 | Unchanged; OMS identity and CLR fail-closed controls were not touched. |
| INV-6 | Unchanged; TEE root-identity binding was not touched. |
| INV-7 | Unchanged; oracle freshness/fallback was not touched. |
| INV-8 | Unchanged; token supply cap was not touched. |
| INV-9 | Unchanged; reward solvency was not touched. |
| INV-10 | Unchanged; bridge proof and payload hash remain separate. |

M1/M2 containment and mock-mode behavior are unchanged. Closing F04 does not
enable Deposit, ExecuteIntent, deployment, Cardano Pre-Prod admission, or
promotion. F05 remains the next authoritative tranche for cross-chain
authority, finality and replay and is required before F01 Deposit, F04
post-F05 SlashAgent activation or governance ExecuteIntent can be enabled.

## Verification

The closure checks were: strict verification of all four prerequisite package
manifests; JSON parsing; documentation and audit-ledger validation; recursive
submodule status; protected-hash comparison; and git diff --check. No Aiken
run, new runtime evidence, dependency installation, network access, deployment,
credential change, vendor change, commit or Git-history operation was performed
by this documentation-only slice.

The next single milestone is F05 cross-chain authority, finality and replay
design/implementation, which gates the still-disabled custody and governance
effects.
