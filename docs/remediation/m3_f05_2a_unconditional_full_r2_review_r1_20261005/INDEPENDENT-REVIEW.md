Independent review: F05.2a unconditional-success full R2 capture

Result: PASS for the direct-UPLC synthetic capture and its stated evidence limits.

Reviewed package: docs/remediation/m3_f05_2a_unconditional_full_r2_20261005/
- RUN.json SHA-256: 0ba7df6632bdca84bfc71ae43c02f36fb2b4e44884ae31c40e15e4b44d0244e3
- ASSESSMENT.md SHA-256: bf06cb340cd6953dc4a091d9c8f9143ed4b2e123585b1b53bd21337ae1eaa64e
- Both hashes match SHA256SUMS when checked from the package directory.

I independently parsed RUN.json. Top-level status is pass, failures is empty, entrypoint is f05_authority_policy.f05_authority_policy.mint, ledger label is Plutus V3, and there are 57 unique baseline evaluation rows. The canonical bootstrap positive accepts with exit 0; all 56 negative evaluation rows reject with exit 1. There are 21 unique compiled mutation records.

The unconditional_success row has a separately rebound positive control that accepts with exit 0. It contains 55 unique subcases, in the same order and with the same IDs as the 55 negative assertions in docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json. Every subcase records accepted=true and exit=0, plus a policy ID, script SHA-256, context SHA-256, genesis-reference CBOR SHA-256, and initial-keys CBOR SHA-256. All recorded hashes have the expected 64-character form. The per-case provenance patterns are consistent: the applied genesis-reference case has its own genesis-parameter digest; each of the five applied-key cases has its own changed key-parameter digest; other cases retain the common baseline parameter digests. Each applied-parameter case has its own policy and script identity. The 55 contexts are not all identical, and the run reports the direct UPLC mint entrypoint.

The run labels this row synthetic_direct_uplc_context_only; no_transaction_witness_or_ledger_credit. The assessment explicitly says this capture contains no transaction witness, body-bound funding signature, ledger admission, Pre-Prod, live-network, or deployment evidence. It also retains the registered mutation ledger at 18/21 pending independent review and a separate classification decision. This review grants no mutation-suite, original-policy, ledger, live-network, or readiness credit and makes no classification change.

Pinned toolchain check: the assessment identifies Aiken 1.1.21. The current pinned executable reports aiken v1.1.21+42babe5 and SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. The current harness main path requires the supplied Aiken version to contain 1.1.21. The RUN schema does not itself carry a tool binary hash or version field, so the toolchain linkage rests on the assessment plus the harness version gate; the independent review verified the pinned executable identity separately.

The harness source hash is 69cfe31833f9f7f6128ed0de9e90130a054df07256459122e2501d89c4ccd216, matching the bytes used in the prior focused harness review. That review ran the focused harness pair with the pinned Python test runner: 65 passed. No simulator or transaction was run for this review.

The capture and assessment describe the fixture as synthetic-only. No production validator, fixture registry, credentials, deployment state, STATUS, HANDOFF, or classification file was changed by this review.
