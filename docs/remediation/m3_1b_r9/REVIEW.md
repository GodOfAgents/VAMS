# M3.1b-R9 deterministic Aiken dependency provenance

Date: 2026-09-26
Scope: dependency provenance and isolated verification only.

## Outcome

The R8 package at /home/GodOfAgents/vams-evidence/m3-1b-r8-review-20260926-829ab544571f
was strictly verified first. Its SHA256SUMS digest is
a5a9813c120cd50da5f3fffb52922f376c5fa18aef3b029d7a0e0d8adff1f165.

R4 raw aiken.lock bytes remain permanently unavailable. No historical
equivalence is claimed.

The scoped R9 boundary adds:
- cardano/aiken-dependency-manifest.json with a closed schema, compiler pin,
  project hashes, sorted dependency identities, revision tags, integrity
  digests, and deterministic package tree digests;
- scripts/remediation/verify_m3_1b_r9.py, which validates the manifest,
  rejects unknown fields and unsafe files, copies current Cardano sources and
  the resolved package cache to a disposable directory, runs only pinned
  Aiken check/build there, compares semantic lock projections, verifies
  package content, blueprint and every compiled program, and checks the
  authoritative source before and after execution;
- focused dependency-free parser, lock, package, blueprint, compiler-pin and
  source-mutation regressions in
  scripts/remediation/test_m3_1b_r9_provenance.py.

## Fresh verification

- R8 evidence package: strict checksum verification passed.
- R9 focused manifest/lock tests: 7/7 passed.
- R9 artifact/package/blueprint/source-mutation tests: 3/3 passed.
- Clean isolated verifier run 1: check 0, build 0, 14 source files, 11
  programs, blueprint
  7b39b883cdc7b55aef08554e92cb089a4b3a91a6250138c4f0b181b37cfd0a80.
- Clean isolated verifier run 2: identical source manifest, dependency hashes,
  blueprint and program hashes; check 0 and build 0.
- The two observed volatile lock fields are the only excluded fields.
- Fresh F01 public harness: 83/83 cases passed; the 16-case mutation suite
  reported no undetected mutation. Fresh INV-10 traceability validation and
  its 11 tests passed. Fresh documentation/audit JSON validation passed for
  26 JSON files, and git diff checks passed. No insurance validator, shared Cardano type,
  blueprint program or dependency/vendor file was edited in R9.

Fresh external artifacts are under
/home/GodOfAgents/vams-evidence/m3-r9-run-1.json,
m3-r9-run-2.json, m3-r9-focused-tests.log and m3-r9-artifact-tests.log.
A checksum-verified R9 evidence package is created outside the checkout.

## Status and invariant impact

F01 remains REVALIDATED_OPEN, F02-F05 are unchanged, M3 remains OPEN,
Pre-Prod admission remains INCONCLUSIVE and promotion remains NOT READY.
INV-1, INV-3 through INV-9 are untouched. INV-2 remains separately enforced;
the insurance validator is not changed. INV-10 proof/payload separation and
Deposit rejection remain unchanged. M1 containment, M2/Gateway/Envoy,
frontend /nodes, mock-mode behavior, credentials, vendors and deployment state
are unchanged.

This is local implementation and verification only, not independent acceptance.
Next slice: independent M3.1b-R10 focused review of this provenance boundary.
