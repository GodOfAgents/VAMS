# M3.2a-R9 remediation of R8 findings

Date: 2026-09-26
Status: local remediation only; independent M3.2a-R10 review required.

## Evidence baseline

The accepted R8 package was verified before editing:
/home/GodOfAgents/vams-evidence/m3-2a-r8-review-20260926-829ab544571f
with SHA256SUMS digest
48321f11b286df7bb190c0e499b2651c0ba3538d4fd813a465259ba3a62dfa06.
The repository baseline was origin https://github.com/GodOfAgents/VAMS.git,
branch testnet/remediation-20260907, HEAD
829ab544571f12efe50ecb5740f129c8acb3e16f, and 114 dirty paths. The raw
cardano/aiken.lock hash remains
bc314b0be1b25c2fe370bed39e0ecde3b15642f67614253a4b01cf2db746a15c.

## R8 finding map

- The R7 validator now uses duplicate-key rejection, exact nested schemas,
  strict integer predicates, fixed widths and enums, closed IDs, topology
  equations, one-over controls, and a reference/mutation registry. The
  spec:encoding reference is now spec:encoding.output_reference; pre-F05
  ExecuteIntent rows reference the implementation-boundary rule rather than a
  fabricated topology.
- Asset and datum vectors are checked against canonical fixture schemas, not
  merely self-recomputed bytes. Proposal nine-record metadata, field order,
  widths, target-domain encoding and topology cardinalities are mutation-tested.
- Manifest version 3 binds the authoritative raw lock hash and a normalized
  nonvolatile digest. Only decimal values in the two approved etag timestamp
  fields are normalized to zero; LF/UTF-8, exact TOML structure and semantic
  projections remain required. Temporary snapshots include normalized
  aiken.lock bytes instead of omitting the file.
- A separate independent oracle under this directory reconstructs enterprise
  addresses, all four asset names, datum sizes, value conservation, topology
  counts and fail-closed ledger-parameter preflight. It does not import the R7
  generator, constants or vectors. Min-ADA and applied budgets remain pending.

## Verification

- R7/R9 machine-spec tests: 9/9 passed.
- R9 independent address/value/topology oracle: 6/6 passed.
- Complete provenance suite: 20/20 passed.
- Two isolated pinned Aiken 1.1.21 verifier runs: both check and build exit 0,
  9 source files, 11 programs, identical source/package/blueprint results.
- Raw lock hash and Cardano source/dependency continuity remained unchanged.
- No Cardano validators, shared types, plutus.json, lockfile, dependency
  packages, credentials, deployment state or vendors were modified.

## Status boundary

R9 is local remediation, not independent acceptance. F01-F05 remain open,
Deposit and Execute remain disabled, M3 is OPEN, Pre-Prod admission is
INCONCLUSIVE and promotion is NOT READY. M3.2b is not authorized; next slice is
independent M3.2a-R10 final specification/provenance review.

INV-1 through INV-10, M1/M2 containment, bridge-proof/payload-hash separation,
mock behavior and deployment state are unchanged. The continuity anchor for
R8/R9 is the checksum-verified external evidence package; this does not claim
protection against arbitrary replacement of both a repository and an accepted
manifest.
