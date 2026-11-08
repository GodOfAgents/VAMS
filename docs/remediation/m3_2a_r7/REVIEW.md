# M3.2a-R7 specification closure

Date: 2026-09-26
Status: local specification closure only; independent R8 review required

## Evidence baseline

The R6 package was strictly verified before editing:
`/home/GodOfAgents/vams-evidence/m3-2a-r6-review-20260926-829ab544571f` with
SHA256SUMS digest
`3721fc3b4132ba5cde694d2fbb30fd4611d0f5f504529276d7f9d0c75f6ad67f`.
The canonical manifest-v2 verifier remains runnable with lock hash
`bc314b0be1b25c2fe370bed39e0ecde3b15642f67614253a4b01cf2db746a15c`.
The lockfile and all Cardano/dependency inputs were left untouched.

## R6 finding-to-artifact mapping

- Terminal destinations, network/stake policy and immutable ADA parameters are
  closed in `GOVERNANCE_SPEC.json`; per-transition equations are referenced by
  `TRANSITION_TOPOLOGY.json`.
- Fee/change/auxiliary funding, collateral and exact output cardinality are
  enumerated in `TRANSITION_TOPOLOGY.json`, including with/without-change and
  one-over-limit mutation references.
- Canonical domains, field order, authority preimage, u32 output references,
  fixed-width fields and untruncated hashes are in `ASSET_VECTORS.json`.
- Authority, proposal, intent and lock datum schemas are serialized in
  `DATUM_VECTORS.json`; the ninth voter is rejected by the explicit cap and all
  accepted vectors are at most 896 bytes.
- Lifecycle arithmetic, queue-time binding, positive quorum and pre-F05
  Execute rejection are in `GOVERNANCE_SPEC.json` and matrix rows.
- `ACCEPTANCE_MATRIX.json` is closed and machine-validated; every row is unique,
  mutation-attributable, topology/vector-referenced and pending M3.2b evidence.

## Fresh verification

- `python3 docs/remediation/m3_2a_r7/governance_spec.py` — passed: 4 asset
  vectors, 7 datum vectors, 9 topology rows, 81 matrix rows.
- `python3 -m unittest docs/remediation/m3_2a_r7/test_governance_spec.py -v` —
  4/4 passed, including independent asset hashing, independent datum encoding,
  and topology/matrix mutation rejection.
- Manifest-v2 focused provenance suite — 18/18 passed.
- Two pinned Aiken 1.1.21 isolated runs — check/build exit 0, identical
  sanitized outputs, 9 source files and 11 blueprint programs.
- JSON parsing, Python compilation, recursive submodule capture and
  `git diff --check` — passed.

## Explicit residual boundary

R7 does not modify the verifier, validators or production types. The R6 review
found that the legacy isolated verifier accepts a disposable nonvolatile
trailing-byte mutation to a temporary `aiken.lock` because that file is excluded
from its temporary snapshot comparison. Standard provenance tests still pass,
but this remains an unresolved provenance defect and is not claimed remediated
by R7. A fresh disposable reproduction accepted a trailing newline appended
to the temporary lock after rebinding its outer hash (`verify_repository() ->
ok=True`), confirming the defect remains.

Current `governor.ak`, `timelock.ak` and `types.ak` remain legacy and still
require M3.2b implementation. No compiled governance harness or applied script
budget evidence exists. F01-F05 remain open, Deposit and Execute remain
disabled, M3 is OPEN, Pre-Prod admission is INCONCLUSIVE, and promotion is NOT
READY. INV-1–INV-10, M1/M2 containment, bridge-proof/payload-hash separation
and mock behavior are unchanged.

Next single slice: independent M3.2a-R8 specification review.
