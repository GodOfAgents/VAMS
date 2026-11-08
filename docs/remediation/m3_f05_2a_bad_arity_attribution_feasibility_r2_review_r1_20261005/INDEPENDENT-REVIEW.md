Independent review: malformed applied-key attribution feasibility R2

Result: PASS for the read-only feasibility conclusion and evidence boundaries.

Reviewed assessment: docs/remediation/m3_f05_2a_bad_arity_attribution_feasibility_r2_20261005/ASSESSMENT.md
SHA-256 verified: f7d3df983614aa7f8396f5be9bea6e4aad608458c30ba34b58d78c3509084319
The assessment SHA256SUMS entry matches these bytes.

I independently checked the current source order. In valid_initial_authority, valid_ordered_keys(initial_keys) precedes state key equality and the separate valid_bootstrap_proofs call. valid_ordered_keys accepts exactly five entries and checks each key length before ordering. valid_bootstrap_proofs separately pattern-matches exactly five keys and proofs, checks signature lengths, then verifies all five signatures. Mint[0] reaches valid_initial_authority before constructing the proof message and calling valid_bootstrap_proofs. This confirms source-level ordering; it does not by itself establish compiled evaluator first-failure attribution.

I verified pinned tool identity and version:

- Aiken 1.1.21+42babe5 SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Aiken 1.1.23+8949565 SHA-256 748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3.

The current aiken tx simulate --help surface has transaction/input/output CBOR, slot/time, blueprint, and script-override options, but no internal trace, source map, or first-failure option. aiken uplc eval --help has flat/CBOR/debug options but no qualified exact-context first-failure facility. Aiken check debug/trace features described in the assessment concern test/build traces and do not supply the required unchanged-byte exact Mint[0] attribution. This conclusion is limited to the inspected pinned CLI surfaces; it is not a claim that no external evaluator could ever provide such evidence.

I verified the R4.1 contract identity: 238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171. Its requirement is exact first-rejection attribution for the unmodified compiled target at Mint[0], tied to exact program bytes and input. The contract explicitly treats guard-removal mutants as insufficient for malformed count/length attribution because other production checks independently reject. The corrected assessment accurately distinguishes the canonical UPLC builtin verifyEd25519Signature from the Aiken source helper verify_ed25519_signature. The cited harness and alias-assessment hashes match the current files; the reported normalization is constrained by count checks and exact CBOR re-encoding equality before context application.

The assessment correctly reports no malformed negative, mutant, build, or simulator execution in this reassessment and grants no credit. R9 keeps applied_keys_bad_count and applied_keys_bad_length PENDING; totals are 53/55 negative cases, 49/51 transaction_simulator cases, and 18/21 mutations. The pending classification does not imply ledger, Pre-Prod, live-network, or deployment evidence. Readiness remains NOT READY, with deployment and gated activations disabled.

No source, fixture, registry, status, or handoff file was changed by this review. No transaction or simulator was run. Review scope is feasibility-assessment integrity and attribution limits, not acceptance of either malformed case.
