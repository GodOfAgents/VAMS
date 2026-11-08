# M3.2a-R5 design and forward-provenance remediation

Date: 2026-09-26
Status: local implementation only; independent R6 review required

## Scope and baseline

R5 addresses only the independent M3.2a-R4 design findings and the permitted
forward-provenance rebind. The R3 and R4 external packages were checksum
verified before editing:

- `/home/GodOfAgents/vams-evidence/m3-2a-r3-implementation-20260926-829ab544571f` — `dd8a8b92e82296da9c49a81d1b0cbc6091a8dca33d544884bc68222af68ba9da`
- `/home/GodOfAgents/vams-evidence/m3-2a-r4-review-20260926-829ab544571f` — `278b38fea72a53fad3c4b1db31ad6c48cb185923ec408f6e093d542c48c2b0fb`

The current lockfile was compared with the manifest projection before the
rebind. Requirements, package requirements, dependency integrity values and
etag integrity values were equal; the only byte differences were the two
approved etag timestamp pairs. The lockfile itself was not edited.

## Changes

- `docs/remediation/m3_2a_r1/ADR.md` now contains the normative R5 amendment:
  exact Cardano value conservation and terminal destinations, ADA/min-ADA,
  fees/change/collateral and output cardinality; literal versioned domain bytes,
  fixed-width serialization, Blake2b-256 and the 32-byte asset-name rule;
  acyclic policy bootstrap; untouched-counter preservation and authenticated
  3-of-5 authority; deterministic square-root weights, quorum/tie rules and
  inclusive/exclusive time boundaries; complete topology/budget stop rules;
  current-source reality and the unconditional pre-F05 Execute stop rule; and
  mutation-linked M3.2b acceptance additions.
- `cardano/aiken-dependency-manifest.json` moved to manifest version 2 and
  records the current lock SHA-256
  `bc314b0be1b25c2fe370bed39e0ecde3b15642f67614253a4b01cf2db746a15c`.
- `scripts/remediation/verify_m3_1b_r9.py` requires the exact forward manifest
  version while retaining semantic-lock comparison and strict hash checks.
- `scripts/remediation/test_m3_1b_r9_provenance.py` adds a current-lock
  rebind assertion and timestamp-only versus nonvolatile semantic mutation
  coverage.

No Cardano source, lockfile, blueprint, package cache, dependency, vendor,
F01 logic, deployment, credential or Git-history file was changed.

## Verification

- `python3 -m unittest scripts/remediation/test_m3_1b_r9_provenance.py -v` —
  18/18 passed.
- Canonical isolated verifier with pinned
  `/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken` —
  `ok: true`, `aiken check` exit 0, `aiken build` exit 0, 9 source files,
  11 blueprint programs.
- Semantic comparison — requirements, package graph, integrity and package
  index projections equal; only approved etag timestamps differ.

The full F01 transition/budget suites and M3.2b implementation remain out of
scope. F01-F05 stay open, F02/F03 remain `REVALIDATED_OPEN`, Deposit and Execute
remain disabled, M3 is `OPEN`, Pre-Prod admission is `INCONCLUSIVE`, and
promotion is `NOT READY`. INV-1–INV-10, M1/M2 containment, mock behavior and
INV-10 bridge-proof/payload-hash separation are unchanged.

External sanitized package: `/home/GodOfAgents/vams-evidence/m3-2a-r5-implementation-20260926-829ab544571f` (its `SHA256SUMS` is verified locally).

Next single slice: independent M3.2a-R6 review.
