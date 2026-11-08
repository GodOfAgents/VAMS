# Independent review: F05.2a evidence-classification R5

Date: 2026-10-05
Review revision: r1
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

Decision: PASS for integrity, the single-row R4-to-R5 classification delta, linked evidence identity, and stated synthetic scope. R5 changes only applied_keys_unsorted from pending to transaction_simulator pass, preserving its original case ID/assertion and every other row and mutation entry.

## Scope and method

Read-only review of the R5 overlay against the independently accepted R4 overlay, frozen source registry, and all six linked R14/R15/R16 and review artifacts. No simulation, tests, builds, or network operations were run. No edits were made to the overlay, STATUS.md, SESSION_HANDOFF.md, registry, fixtures, or run records. Only this report and its SHA256SUMS were written.

Exact verification commands/results:

- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_evidence_classification_r5_20261005 && sha256sum -c SHA256SUMS` — PASS: AMENDMENT.md and CASE-STATUS.json OK.
- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_evidence_classification_r4_20261005 && sha256sum -c SHA256SUMS` — PASS: AMENDMENT.md and CASE-STATUS.json OK.
- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_evidence_classification_r4_review_r1_20261005 && sha256sum -c SHA256SUMS` — PASS: INDEPENDENT-REVIEW.md OK; that review verdict is PASS.
- Read-only Python normalized row comparison — PASS: same 55 negative case IDs; sole state change is applied_keys_unsorted pending -> pass; 47 other pass rows and six remaining pending rows are identical; full mutation object and source_registry object are identical.
- Read-only Python evidence-link verification — PASS: all six R5 supporting paths exist and match their declared SHA-256 values; the direct triad evidence path/hash also matches.
- Frozen registry SHA-256 and selected case/assertion check — PASS.

## Artifact identities

Accepted R4 predecessor:
- AMENDMENT.md: `81fe9a052d369e054448c1d91c101f17abebfa681a1c7cb73e2eae62e6017026`.
- CASE-STATUS.json: `be9fb62f8f84cbb84fbdea7ae5bcb2a95d1a99771d717c8a73a55efb2e99ffdc`.
- SHA256SUMS file: `85a17b080aeed0f75552a9006a885994e88c089dd5366a20eebac8d327b8ca87`.
- Accepted R4 independent review: `e01e172c2f32f8eb22102e6cfcfd7d8e86df029512d356a85e5c92cfc3607939` (PASS).

R5 overlay reviewed:
- AMENDMENT.md: `c09c741b477ace277877c064eaa4a93eae79f1a2a4938924a826ed019c9a1878`.
- CASE-STATUS.json: `0ba0d688104fde93060b2b654e2971824a64a1c58078937b8398f3de7e4977e6`.
- SHA256SUMS file: `bf86f37a93a68037338762678b1c75258298abaedfe0649f76662bb02a2a97a8`.

Frozen registry:
- Path: `docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json`.
- SHA-256: `98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d`.
- Its selected row remains `applied_keys_unsorted` / `compile_with_unsorted_keys_and_matching_datum`; both R4 and R5 repeat the same registry path/hash with `assertions_changed: false`.

## Normalized delta and totals

R4 has 55 registered negative cases, with 48 pass, seven pending, and zero failed. Its transaction_simulator subtotal is 44/51 pass, seven pending, zero failed. R5 preserves the same 55 IDs and changes only the row state for `applied_keys_unsorted` from pending to pass classified as `transaction_simulator`. All 47 other pass rows and six remaining pending rows are byte-identical as parsed records; failed remains empty. The row retains its ID and evidence assertion, and cites the exact triad review plus the six supporting artifacts.

R5 totals correctly reconcile to:
- Negative cases: 49/55 pass, six pending, zero failed.
- transaction_simulator: 45/51 pass, six pending, zero failed.
- Mutations: 18/21 pass, three pending, zero failed.

The complete mutation ledger is unchanged between R4 and R5, including all rows and pending IDs. Thus the R16 one-guard mutant remains an attribution control and does not add mutation-suite credit.

## Linked evidence identity and scope

Each linked artifact exists and hashes to the value in the R5 overlay:

- R14 positive RUN: `9d40df445cca42f37aab07bb221cc54535b95d70d79e6c64a236def6c2ea6aa1`.
- R14 independent positive review: `f08ac5add7f4096054d994ed3a1977663cf4c88096b8a5fdd295e086e09c450e`.
- R15 normal-policy negative RUN: `2943e4d762012bb8e617255d7c54102596456fa6da3b25b841896a05554790c3`.
- R15 independent mutant-byte review: `c17eecfb046a1f744b9193e2305fc9383a6fd8f077720eeb4e629509fd965aa1`.
- R16 one-guard mutant RUN: `11ff6ab03cac0dc488af7cc486bb994bf79fd1d0fb49ee4dff8ae619ff37fd24`.
- R16 independent paired triad review: `9f3b58dc98ee5144705db7f4101181904a93166d7d6b3e5730688e922216e54b`.

The R5 amendment and status row accurately characterize the evidence as local synthetic alternate-applied-policy transaction-simulator evidence. The negative is supported by the accepted positive control, compiled Mint[0] rejection, exact one-guard mutant acceptance, and independent paired attribution review. The overlay grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

This review approves the R5 evidence-classification overlay within those limits. It does not edit or append to STATUS.md or SESSION_HANDOFF.md; the owner may record the accepted overlay and next-slice decision separately.