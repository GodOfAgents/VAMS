# F04 compiled-contract remediation R6

Date: 2026-09-29

Status: independent R6 review PASS; F04 is eligible for a separate documentation/status closure record.

## Scope and baseline

This slice remediates the independent compiled-review findings without changing
the frozen 49-row fixture, Cardano dependency semantics, credentials,
deployment state, vendors or Git history. The prerequisite package
`m3-f04-compiled-independent-review-20260929T154615Z-829ab544571f` was
verified before editing with SHA256SUMS digest
`2eb0e478fb2e7ca0fcd17fde8cfbcb580b1b11086c367cf2649d1b83d5d463a7`.

The production validator now applies total `AgentDatumV1` validation at all
public mint/spend datum seams, including raw UTF-8 DID bounds, metadata and
numeric bounds, deterministic bootstrap-bound identity derivation, direct mint
output/value binding, and direct burn owner-payout/non-identity conservation.
The generated blueprint was produced only in disposable copies with pinned
Aiken 1.1.21. `cardano/aiken.lock` was not changed.

## Test-boundary correction

The independent review found the committed evaluator had stale hard-coded
compiled-program and policy identifiers. `scripts/remediation/test_f04_public_validator.py`
now derives the current un-applied/applied program and policy identifiers from
the disposable blueprint and records them in its sanitized result.

The immutable fixture remains byte-for-byte unchanged. Three legacy mint-side
burn expectations conflict with the corrected direct-burn contract:
`deregister_wrong_payout`, `deregister_duplicate_payout`, and
`deregister_non_ada_loss`. Their original `accept` labels are not rewritten;
`fixture_reconciliation.json` records the reviewed current `reject` outcome and
the exact guard responsible. The corrected evaluator therefore executes all 49
rows and 67 evaluations with zero pending while making this semantic amendment
explicit.

The supplemental harness no longer carries the pre-remediation policy
constant. It derives the applied policy from the disposable blueprint and
uses context-bound policy values for mutation construction.

## Fresh results

- Frozen fixture contract: 49 rows / 67 evaluations; fixture hash unchanged.
- Disposable current-artifact evaluator: 49/49 rows, 67/67 evaluations, 0
  pending, 0 unreviewed mismatches; three explicit reconciliation amendments.
- Supplemental compiled matrix: 28/28 cases; module 4/4.
- Updated interface migration suite: 15/15.
- Frozen fixture contract suite: 14/14.
- Forward provenance suite: 21/21.
- Two disposable pinned-Aiken check/build runs: 120/120 tests each and
  identical blueprint `c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2`.
- JSON validation, Python compilation and `git diff --check`: pass.

## Continuity and status

Current hashes: validator
`7655acb5d48cb0abcfe85dadfe9aa9c80046bff3aeeaf0720cb706084adbb5cd`,
blueprint `c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2`,
forward manifest
`f0f27c4fbc72dffbc51d6baec2056316eefe94eedc75bdf7f9b1190741b732b0`, and
lock `6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f`.
The original fixture hash is
`18e2252e38d474c13ffece96b78bc0ee18d50b7327636f57be289063312fa224`.

Evidence packages: implementation
`/home/GodOfAgents/vams-evidence/m3-f04-r-implementation-20260929T163500Z-829ab544571f`
(SHA256SUMS `aaa4cfa8c9afabc51bcaff4bf99688d6f17af40f70f5a777ead6dd5b4fd1cc7c`),
supplemental
`/home/GodOfAgents/vams-evidence/m3-f04-r-supplemental-20260929T163500Z-829ab544571f`
(SHA256SUMS `501c5931cd728de27c2021cd64b652fcc283df25f314043b7c2d9f8f33a1585e`),
and independent review
`/home/GodOfAgents/vams-evidence/m3-f04-r6-independent-review-20260929T164500Z-829ab544571f`
(SHA256SUMS `8bf3d73fb9c5fc97511c75608c73021736ca33ad0c81c2e01a9ad07edfb1d4ff`).

The independent R6 package accepts this scoped remediation. F04 remains
REVALIDATED_OPEN until a separate documentation/status closure record.
F01-F03/F05 and M3 remain open; Deposit and ExecuteIntent remain disabled,
Pre-Prod admission is INCONCLUSIVE and promotion is NOT READY. INV-1 through
INV-10 and mock-mode behavior are unchanged. The next action is independent
F04 compiled-contract review of this remediation.
