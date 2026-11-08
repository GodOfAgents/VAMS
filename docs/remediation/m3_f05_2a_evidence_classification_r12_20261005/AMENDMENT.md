F05.2a evidence classification amendment R12

This successor changes exactly one mutation row: remove_key_order_guard moves from PENDING to PASS as synthetic_alternate_policy_mutation_suite. It preserves all 55 negative rows, all other mutation rows, original IDs and security assertions, and the synthetic-only evidence boundary. The linked capture is transaction-simulator evidence for an alternate applied policy; it grants no original-policy, full-ledger-admission, Cardano Pre-Prod, live-network, or deployment-readiness credit.

Source R11: docs/remediation/m3_f05_2a_evidence_classification_r11_20261005/CASE-STATUS.json.
Separate capture: docs/remediation/m3_f05_2a_unsorted_mutation_suite_r1_20261005/RUN.json.
Independent capture review: docs/remediation/m3_f05_2a_unsorted_mutation_suite_review_r1_20261005/INDEPENDENT-REVIEW.md.

The capture records a positive control, the preserved original negative, and a matching one-guard mutant at f05_authority_policy.f05_authority_policy.mint / Mint[0], with applied-policy bindings, valid body-bound ephemeral funding witnesses, ADA and native-asset conservation, clean teardown, and no persisted private keys. Its acceptance is limited to the named mutation suite.

Counts after this bounded delta: 21/21 mutations PASS; negative totals remain 53/55 PASS and transaction-simulator negatives 49/51 PASS. Readiness and all gated activations remain unchanged. F05/M3 remains open.
