# Independent review: F05.2a evidence classification R4

Date: 2026-10-05
Review result: **PASS** for record integrity, case preservation, and the narrowly declared synthetic transaction-simulator classification.

## Scope and method

This was a read-only review of R4 against R3 and the frozen source registry, plus the cited R10/R11/R12 attempt records, triad review, and exact-byte mutant candidate review. No simulator, tests, source edits, or classification edits were performed.

The frozen source registry, `docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json`, has SHA-256 `98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d`. R4 repeats the exact path and hash with `assertions_changed: false`. The original registry has 55 negative cases. Their IDs match exactly across registry, R3, and R4. Because R4 retains the source registry identity unchanged, all source mutation/assertion descriptors remain anchored to the same original registry; the selected assertion is specifically `applied_keys_parameter / compile_with_different_sorted_keys_keep_datum`.

R4 JSON parsed with a duplicate-key-rejecting object hook. Its package checksums pass with `sha256sum -c` from the R4 package directory. R4 artifact hashes are:

- `AMENDMENT.md`: `81fe9a052d369e054448c1d91c101f17abebfa681a1c7cb73e2eae62e6017026`
- `CASE-STATUS.json`: `be9fb62f8f84cbb84fbdea7ae5bcb2a95d1a99771d717c8a73a55efb2e99ffdc`
- `SHA256SUMS`: `85a17b080aeed0f75552a9006a885994e88c089dd5366a20eebac8d327b8ca87`

## Classification comparison

The only changed negative-case disposition from R3 is `applied_keys_parameter`, pending in R3 and transaction-simulator pass in R4. Its registry ID and assertion are unchanged. All other negative-case rows, including evidence fields, are unchanged. R4 reports 48/55 pass, 7 pending, 0 failed; transaction-simulator 44/51 pass, 7 pending, 0 failed; context-only 3/3 and routing-only 1/1 remain unchanged.

The full mutation ledger is structurally identical between R3 and R4. It remains 18/21 pass, 3 pending, 0 failed, with pending IDs `unconditional_success`, `remove_key_uniqueness_order_guard`, and `remove_key_order_guard`.

## Cited evidence and binding

The R4 ledger cites these exact records; current file hashes match the cited hashes:

- R10, `docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r10_20261005/RUN.json`: `fdd13ca0572ba92c302d0e5537ee2670520570dcf25977feb39ebebaa6a3a2c9`. It records positive acceptance at compiled Mint[0] under the alternate applied policy.
- R11, `docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r11_20261005/RUN.json`: `ca0e17acffdffe5877ee6f1b6ffc2facefbbb70a89ab29c78f488b9c5da92cad`. It records compiled evaluation rejection with target invocation at Mint[0], under the same applied policy and exact policy/mint binding.
- R12, `docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r12_20261005/RUN.json`: `bcd3e120ecd05b07e35f128f267da0f62f8e6c133042d854166326dfca53b19d`. It records the negative witness accepted at Mint[0] under the corresponding mutant policy.
- Independent triad review, `docs/remediation/m3_f05_2a_applied_keys_parameter_triad_review_r1_20261005/INDEPENDENT-REVIEW.md`: `893a0474e9a3e039834501c139cb546f563d6f708d3428ec0024cbc577492958`. Its outcome is PASS for named-condition attribution in local synthetic alternate-policy transaction-simulator scope.
- Exact-byte mutant candidate review, `docs/remediation/m3_f05_2a_applied_keys_parameter_mutant_r1_review_r1_20261005/INDEPENDENT-REVIEW.md`: `6925ef8a27c7e50c9476527d9578640c19f35df8f09109d314389019e122ebd9`; its SHA256SUMS verifies. It records the exact one-predicate mutation and matching compiled mutant policy, retained negative datum/redeemer and five PoP signatures, body-bound ephemeral funding signatures, conservation, and no simulator execution at candidate-review time.

The triad review confirms the R10/R11 shared alternate policy and input context, and that R12 changes the policy only for the reviewed one-guard mutant while preserving the negative datum/redeemer and input context. This supports attribution to the named ordered-keys equality condition for this synthetic fixture and simulator path.

## Limits

R4 limits credit to a synthetic alternate-applied-policy transaction simulator. It grants no mutation-suite, original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. The runner records are locally transcribed structured results; raw simulator stdout/stderr and external attestation are unavailable. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
