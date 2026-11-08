# Independent R9 classification overlay review

Outcome: PASS for the exact integrated R8-to-R9 classification delta.
Case: r2_signature_for_other_epoch / sign_tuple_with_nonzero_epoch.

Independent read-only verification establishes that only this original negative case moves from PENDING to PASS in the transaction_simulator category. Removing the new target pass row, restoring its pending membership and count summaries, and normalizing the R9 schema label reconstructs R8 CASE-STATUS exactly. Mutation rows, limits, source registry, inherited metadata, context-only and routing-only records, and all other negative rows are unchanged.

The resulting counts are 53/55 negatives PASS, two PENDING, zero FAILED; transaction_simulator 49/51 PASS, two PENDING, zero FAILED. The two pending IDs are applied_keys_bad_count and applied_keys_bad_length. Mutations remain 18/21 PASS and three PENDING with byte-identical mutation objects. The target preserves the original assertion registry entry and R4.1 B scope. All original-policy, mutation-suite, ledger-admission, Pre-Prod, live-network and readiness scope flags are false.

The integrated epoch triad was independently reviewed in r2, SHA-256 e0e028d80a308efd0120d8954735d28e35da3f56d900f536442e7b17e9546357: positive accepts, normal negative rejects, and independently compiled epoch-only mutant accepts the same negative proofs. That review and the r2 exact-byte review support the linked r1 attribution result and exact target evidence. The target primary evidence SHA-256 1539bd1a6e303f1ba984761d59cf27a359ed606cc40c0c628ce144e6703e6f66 matches its retained integrated r1 review. No additional credit is inferred.

All 74 R8 top-level evidence links are preserved exactly, and all 90 R9 top-level links verify. Including nested case-evidence and target supporting references, 115 recorded link hashes verify; 152 entries in linked checksum manifests also verify. R9 package SHA256SUMS verifies. CASE-STATUS SHA-256 e451d01483bf42e808523ca99943c44f49642d86f83d83cb574a03c99218eebb; package SHA256SUMS SHA-256 02cedc46ea2d8cef419baa480fc264621c3996efb866d75b8d0133634ee64a5f.

The EVIDENCE-LINKS case_evidence object is inherited R8 validator-hash metadata and remains unchanged. Current epoch evidence is explicit in the target CASE-STATUS row and added file links. The inherited evidence_category_clarification object retains historical R5 counts; current counts are in negative_cases.summary and classification and the R9 amendment/comparison. These historical objects are not current totals or epoch credit assertions.

VERIFY-OVERLAY.py contains the exact successful read-only verification payload executed through scoped WSL Python's base64-decoded -c input. Exit 0. No simulator, build, live transaction or state-changing protocol operation was performed in this overlay review. Only this separate review directory was written; STATUS/HANDOFF untouched.

INV-1 through INV-10 are not touched by the evidence-only overlay. F05/M3 stays OPEN and readiness NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled. Independent classification PASS grants exactly the preserved synthetic alternate-applied-policy transaction_simulator row; all documented mandatory gates still apply.
