# F05.2a evidence-classification amendment R8

Exactly one negative status changes from R7: r2_signature_for_other_validator_hash moves from PENDING to PASS as one transaction_simulator row. Its original case ID and assertion sign_tuple_with_another_state_validator_hash are preserved. Every other case row, pending ID, mutation row, and non-target field remains unchanged.

This reclassification is limited to R4.1 proof-domain decision B and synthetic parameter-bound simulator evidence. Positive control, normal-policy negative, same-negative one-expression PoP-preimage mutant, fixture manifests, attempts, and independent reviews are hash-linked in EVIDENCE-LINKS.json. Normal and mutant policies are separately applied synthetic policies; mutant acceptance supports attribution only.

Counts change exactly by one: negative PASS 51 to 52, PENDING 4 to 3, FAILED 0; transaction_simulator PASS 47 to 48, PENDING 4 to 3, FAILED 0. Other categories and all mutation statuses/counts are unchanged. compare_r7_to_r8.py verifies exact R7 normalization and linked hashes; COMPARISON.json records the result.

No mutation-suite, original-policy negative, full-ledger-admission, Cardano Pre-Prod, live-network, or deployment-readiness credit is granted. STATUS, HANDOFF, source, fixtures, deployment/activation gates are untouched; all other pending cases retain their status.
