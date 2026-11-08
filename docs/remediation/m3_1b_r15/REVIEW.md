# M3.1b-R15 remediation review — 2026-09-26

R15 remediates only independent R14-01. The accepted R14 package was verified
before editing from `/home/GodOfAgents/vams-evidence/m3-1b-r14-review-20260926-829ab544571f`;
its `SHA256SUMS` SHA-256 is
`b158f4569757e80169708493d45a65f5737c166dfcae2024f8431c99c7846084`.

## Reproduction and change

The R14 pre-fix callable reproduction accepted all four TOML boolean timestamp
components (`secs_since_epoch=true/false` and
`nanos_since_epoch=true/false`) because the lock parser used an `int` check that
treated `bool` as an integer. R15 uses the existing `_strict_int` predicate for
both fields before range validation, comparison, or arithmetic. The CLI path
continues to return a sanitized nonzero JSON error without a traceback.

R15 also adds direct `_parse_package_index` tests against disposable TOML
content. They exercise canonical, missing/unknown keys, wrong containers and
scalar types, duplicate identifiers, malformed names, and the parser error
reasons directly, without first checking the outer manifest-bound file hash.

## Fresh verification

- focused R15/R9/R11/R13 provenance suite: **16 tests passed**;
- explicit timestamp matrix and direct package-index parser tests: **2 passed**;
- pinned Aiken 1.1.21 isolated verifier: **check/build passed**, 9 source files,
  11 programs;
- five historical R10 mutations: **5/5 rejected**;
- Python compilation, JSON/documentation validation, recursive submodule status,
  and `git diff --check`: passed.

External sanitized evidence is at
`/home/GodOfAgents/vams-evidence/m3-1b-r15-implementation-20260926-829ab544571f`.
It contains no raw scanner/secret material. Its `SHA256SUMS` digest is recorded
in the external package after finalization.

## Scope and status

Only `scripts/remediation/verify_m3_1b_r9.py`, its focused provenance tests,
this R15 review, status, handoff, and changelog records changed. The dependency
manifest, lockfile, Cardano sources, blueprint, resolved dependency packages,
F01 logic, deployment state, credentials, vendors, INV-1–INV-10, and mock
behavior remain unchanged. The full F01 transition/budget suites were not run.

This is local remediation, not independent acceptance. `F01 = REVALIDATED_OPEN`,
`F02–F05` are unchanged, Deposit remains disabled pending F05, `M3 = OPEN`,
Pre-Prod admission is `INCONCLUSIVE`, and promotion is `NOT READY`. Next slice:
**independent M3.1b-R16 micro-review**.
