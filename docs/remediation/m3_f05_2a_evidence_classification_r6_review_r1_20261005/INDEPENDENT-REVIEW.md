# Independent review: F05.2a evidence-classification R6

Date: 2026-10-05
Verdict: PASS for the bounded R5-to-R6 classification delta and cited synthetic evidence scope.

## Scope and integrity

Read-only comparison of R6 against the accepted R5 CASE-STATUS.json, including all negative IDs/rows, classification subtotals, source-registry identity, mutation records, the amendment, and cited R17/R18/R19 plus integrated triad-review artifacts. No source, overlay, STATUS, HANDOFF, or fixture files were edited.

R6 package checksum verification passed: AMENDMENT.md and CASE-STATUS.json both match SHA256SUMS.
- docs/remediation/m3_f05_2a_evidence_classification_r6_20261005/AMENDMENT.md SHA-256: 3ac8c7e0be6907560c519a1ec8ea0fb6e67b19f73ebab4bc9baed96958edfa5e
- docs/remediation/m3_f05_2a_evidence_classification_r6_20261005/CASE-STATUS.json SHA-256: 419e5c1dfeaa76b346ae739d092d974b853e889fa0b96283a9f09e9155cdc4f5
- docs/remediation/m3_f05_2a_evidence_classification_r6_20261005/SHA256SUMS SHA-256: 55677f3e3e08427f33aa5bc96d9d6225f836f0669c6201bcc943e2697fb5f089
- R5 baseline CASE-STATUS.json SHA-256: 0ba0d688104fde93060b2b654e2971824a64a1c58078937b8398f3de7e4977e6

The overlay preserves source registry path docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json, SHA-256 98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d, with assertions_changed=false.

## Normalized R5-to-R6 delta

Read-only Python comparison passed. The schema version advances from f05-2a-evidence-classification-r5-case-status-v1 to ...r6-case-status-v1. Out of 55 negative IDs, exactly r2_signature_for_other_seed moves from pending to pass. Its original assertion remains sign_same_tuple_with_alternate_seed, and R6 classifies it as transaction_simulator with the triad review and its supporting hashes. Every other negative ID and row is unchanged; failed remains empty.

Derived counts reconcile: registered negatives move from 49 pass / 6 pending / 0 failed to 50 / 5 / 0. Transaction-simulator subtotal moves from 45 pass / 6 pending / 0 failed (of 51) to 46 / 5 / 0. Context-only remains 3/3 pass; routing-only remains 1/1 pass. The full mutation object is byte-for-byte equal across R5/R6: 18/21 pass, 3 pending, 0 failed, with the same pending IDs and evidence.

R6 evidence references match the cited files: R17 positive RUN SHA-256 f9a86dca6d7fed12a92fb2afb59ac77836c6b963b178403f0ef77b8c9494992f; R18 negative RUN 2f3d042cd4350d821b0ce91dafa4cddfdb36dc23258eefb6115b947fd764b0be; R19 one-guard mutant RUN ecd352f4acfb379b36a05ab623f8a25a6d5e6a8be4f9181de92cba37f3c973ba; integrated triad review 997d6658265add2675332e2759a578b59eee0b0dbdfa96f6233ea510217566ee. Each actual file matched its cited SHA-256.

## Historical metadata and limits

The inherited evidence_category_clarification object is unchanged from R5. Its change_type is wording-only record correction and its nested negative_counts_unchanged values (registered 45 pass / 10 pending; transaction_simulator 41 pass) describe the earlier classification correction, not R6's current totals. I treat this as historical R5 metadata because R6's explicit amendment and negative_cases summary/classification provide the current counts. Although the nested object is not explicitly labeled predecessor metadata, it creates no substantive conflict when read in context; a future cleanup could add an applies_to=r5 label.

Credit is limited to the single synthetic test-only alternate-applied-policy transaction-simulator negative row r2_signature_for_other_seed. R19 remains attribution evidence only and adds no mutation-suite credit. No original-policy, full-ledger-admission, Cardano Pre-Prod, live-network, or readiness credit is granted. F05/M3 remains open and gated deployment/activation remains disabled.