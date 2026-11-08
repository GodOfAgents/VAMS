# Independent review: F05.2a evidence classification overlay R12

Date: 2026-10-05
Review revision: r1
Canonical checkout reviewed: `/home/GodOfAgents/code/VAMS-testnet`
Canonical branch: `testnet/remediation-20260907`
Canonical HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`

Decision: **PASS** for the exact R12 classification overlay, subject to its
synthetic evidence boundaries. This review was read-only: no simulator was
rerun and no canonical file was edited.

## Scope and checks

The exact R12 package was reviewed:

`docs/remediation/m3_f05_2a_evidence_classification_r12_20261005/`

Checks performed in canonical WSL:

- `cd .../m3_f05_2a_evidence_classification_r12_20261005 && sha256sum -c SHA256SUMS` — PASS: all four package files verified.
- Read-only structural comparison of R11 and R12 `CASE-STATUS.json` — PASS.
- Read-only verification of every hash in `EVIDENCE-LINKS.json` — PASS: all five linked artifacts match.
- `sha256sum -c docs/remediation/m3_f05_2a_unsorted_mutation_suite_r1_20261005/SCRIPT.SHA256SUMS` from the repository root — PASS.
- `sha256sum -c docs/remediation/m3_f05_2a_unsorted_mutation_suite_review_r1_20261005/SHA256SUMS` — PASS.
- Read-only inspection of linked `RUN.json` and independent review — PASS; no simulator rerun, network submission, key generation, or canonical write was performed.

## Evidence identities

- R11 source `CASE-STATUS.json` SHA-256: `65dd7accc853988cfbfe3540461c475f857553ee500f52b9e4a015b841e0dc5f`.
- R12 target `CASE-STATUS.json` SHA-256: `7f23a3ea4c8f61da2f181bcd1f54cbad68f609a25f2af86ba44427ba065884fc`.
- R12 `AMENDMENT.md` SHA-256: `fd4f5a3592504d03a6f40167168b8ce479d3464c36b385f4ccaf1ad9bc4336e`.
- R12 `COMPARISON.json` SHA-256: `63ca0ca9360f43749edd8a31363b2554c8abe9993878e8646a64d891975df374`.
- R12 `EVIDENCE-LINKS.json` SHA-256: `a40c896b2b8c8e3dca7db672c900cb00df04676cce91c661304c656fd416ef6c`.
- R12 package `SHA256SUMS` SHA-256: `d7a4a890d01f29cd6ea24be75fc42de6d66fefba98b4d103d742ea28f3b14bcc`.
- Linked unsorted capture `RUN.json` SHA-256: `7e8b92d66220857213b7c64bd547a4aeeccc4ae938e73c403b5460a1dd180f85`.
- Linked unsorted capture `SHA256SUMS` SHA-256: `46ff471ee9f553ce6bf774597825f2482c2f0d7c43d689dff56787b2cda4fc27`.
- Linked capture `SCRIPT.SHA256SUMS` SHA-256: `83ba1f3e377a2877abb6b01ce33bea9854aa190dd554b4df12b8d7590b9d6232`.
- Linked unsorted capture review SHA-256: `60f156468af739c3c56499f706149be9964d44de44be06048c86ca0bc2f25f74`.
- Linked capture-review `SHA256SUMS` SHA-256: `715901990936121793585d9f49160b96e6e6ed33325c30f29435864a16b2d018`.

## Findings

The R12 amendment records exactly one bounded transition from R11:

- `remove_key_order_guard`: `PENDING` -> `PASS`, classified as `synthetic_alternate_policy_mutation_suite`.
- The source R11 pending set contains exactly `remove_key_order_guard`; R12 has no pending mutation rows.
- All 55 negative cases are structurally unchanged, with 53 PASS and 2 PENDING.
- All 20 prior mutation PASS rows are structurally unchanged; R12 has 21/21 mutation PASS and 0 pending.
- Transaction-simulator negative totals remain 49 PASS and 2 PENDING.

The linked capture is for `applied_keys_unsorted` at
`f05_authority_policy.f05_authority_policy.mint / Mint[0]`. Its accepted
scope is synthetic alternate-applied-policy transaction-simulator mutation
evidence. The capture and review record correct applied-policy bindings,
positive control acceptance, original-negative compiled rejection, matching
one-guard mutant acceptance, body-bound ephemeral funding signatures, ADA and
native-asset conservation, clean teardown, and no persisted private keys.

## Acceptance boundary

PASS: R12 is an exact, checksum-verified, one-row successor to R11 and is
supported by the independently reviewed unsorted mutation capture. The
amendment grants mutation-suite credit only. It grants no original-policy,
full-ledger-admission, Cardano Pre-Prod, live-network, deployment-readiness,
Deposit, Slash activation, or ExecuteIntent credit. F05/M3 remains open and
readiness remains NOT READY.

