F05.2a evidence classification amendment R11

This successor changes exactly one mutation row: remove_key_uniqueness_order_guard moves from PENDING to PASS as synthetic_alternate_policy_mutation_suite. It preserves all 55 negative rows, all other mutation rows, original IDs and assertions, and the synthetic-only evidence boundary. The capture is transaction-simulator evidence for an alternate applied policy; it grants no original-policy, ledger-admission, Cardano Pre-Prod, live-network, or deployment-readiness credit.

Source R10: docs/remediation/m3_f05_2a_evidence_classification_r10_20261005/CASE-STATUS.json.
Separate capture: docs/remediation/m3_f05_2a_duplicate_mutation_suite_r1_20261005/RUN.json.
Independent capture review: docs/remediation/m3_f05_2a_duplicate_mutation_suite_review_r1_20261005/INDEPENDENT-REVIEW.md.

Counts after this bounded delta: 20/21 mutations PASS, 1 PENDING; negative totals remain 53/55 PASS and transaction-simulator negatives 49/51 PASS. The remaining pending mutation is remove_key_order_guard. Readiness and all gated activations remain unchanged.
