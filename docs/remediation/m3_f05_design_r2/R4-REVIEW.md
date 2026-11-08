# F05.1-R4 design-contract remediation

Date: 2026-09-30
Scope: design artifacts and tests only; no production implementation or F05.2.

## Baseline and prerequisites

- Origin: https://github.com/GodOfAgents/VAMS.git
- Branch/HEAD: testnet/remediation-20260907 / 829ab544571f12efe50ecb5740f129c8acb3e16f
- Preserved dirty paths: 122; recursive submodule entries: 14.
- R2 design package m3-f05-1-r2-design-20260929T211258Z-829ab544571f: SHA256SUMS 572d04b1f0e52e6f9b80dcf0fb674ae67e81c773f6c526fe87a427e6c4d9a0e7; strict manifest check passed.
- Prior R2 independent review: m3-f05-1-r2-independent-review-20260929T211258Z-829ab544571f; SHA256SUMS digest 17efbfcee541cc5f700b5128d65f495b0d302b60ff13bd5c9203919a497a0c71.
- F04 closure package m3-f04-closure-20260929T194439Z-829ab544571f: SHA256SUMS 03698b936729927df4a1c87b24d46cc4722babc814a47599cd120da6469e70c4; strict manifest check passed.
- R3 independent review package m3-f05-1-r3-independent-review-20260929T213944Z-829ab544571f: SHA256SUMS 1bd69546d5c02a02533e2cfad8a8520ab4fc26ac8e30216b928cdf5cf79af03f; strict manifest check passed. R3 verdict was FAIL and F05.2 was not authorized.

## R4 changes

Closed and versioned the F05.1 contract and validator; froze explicit byte
domains (including terminal NUL bytes), four non-boolean action codes, signed
int64 per-action quantities, checked u64 cumulative counters capped at 10^19,
ordered certificate/action fields, four canonical action vectors, authority
rotation, committee finality, replay, reserve and transaction topology. The
finality authority remains the explicit 3-of-5 testnet committee assumption,
not trustless Polygon/Mithril verification. The independent encoder does not
import the contract generator. The public CLI mutation suite applies one
semantic change at a time to disposable artifact copies and checks the
unchanged valid control.

## Fresh verification

- PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s docs/remediation/m3_f05_design_r2 -p 'test_*.py' -v — PASS, 26 tests; public harness covers 72 mutation categories.
- python3 -B docs/remediation/m3_f05_design_r2/validate_design.py — PASS; actions=4, certificate_fields=22.
- python3 -B scripts/docs/validate_docs.py — PASS.
- JSON parse — PASS for CONTRACT.json and VECTORS.json.
- Python AST/compile check — PASS for all five scoped Python files.
- git diff --check — PASS in canonical WSL checkout.
- git submodule status --recursive — 14 entries; no submodule update performed.
- Dirty path count remains 122. Protected Cardano source/artifact hashes are recorded in the external implementation package.

## Review gate and disposition

Independent R4 integration verdict: PASS for the manifest-bound snapshot at
C:/Users/aseem/VAMS-mono/.f05-r4-final-snapshot-20260930T1135Z-829ab544571f.
Its SHA256SUMS digest is
cd99178b4224e6662774877cd5a3f6671ccce40bd3447204054e4d1ca0dd4edc; all 14
entries verified. The reviewer confirmed four canonical action vectors, 72
unique executable mutation categories, semantic signed-field re-encoding,
and explicit testnet committee-trust assumptions; public validator, oracle
(5/5) and structural/mutation checks (5/5) passed. Canonical focused suite
passed 26/26; docs, JSON, compilation and git diff checks passed locally.
Review was snapshot-only; the reviewer could not inspect live WSL/Git/source
hashes. Coordinator created the snapshot from the canonical checkout and
independently rechecked protected hashes and canonical gates. The nested
target-epoch mutation re-encodes and re-signs its certificate; its focused
test passes and requires the exact semantic target-binding rejection.
F05.2 authorization: NO.

F05/F01-F03 remain REVALIDATED_OPEN; F04 remains REMEDIATED. Deposit,
SlashAgent activation and ExecuteIntent remain disabled. M3 is OPEN, Pre-Prod
admission is INCONCLUSIVE, and promotion is NOT READY. INV-1–INV-10, M1/M2
containment and mock behavior are unchanged. F05.2 is not authorized; no
production source, validator, blueprint, lockfile, provenance input,
dependency, credential, deployment state, vendor or Git history changed.
