# M7 F05 native-handler regression slice   2026-10-03

## Outcome

The bounded test-only slice is accepted for source-level and local diagnostic coverage after independent review. It adds an accepted public-fixture positive control and a seed_missing rejection at the public F05 mint handler. The test context matches the preserved _base_context helper, including the cc &cc transaction ID, input order and credentials, sponsor output datum, fee, mint, signatory and finite interval. Committee and proof bytes match the frozen canary fixture.

This is not a registered negative-case acceptance, mutation acceptance, transaction-simulator result, ledger admission, or live-network result. The test calls the public handler with a typed synthetic Aiken Transaction; it does not prove funding witnesses, transaction-body validity, or ledger script-data-hash/collateral behavior. No registered status count changes.

## Changed files

- cardano/validators/f05_authority_policy.test.ak   new native handler test module only.
- docs/remediation/m7_f05_native_handler_test_r1/ASSESSMENT.md   this record.
- docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md   current result and next-slice handoff.

Production validator source, blueprint, dependency lock and credentials were not changed by this slice. INV-1 INV-10 and mock behavior are unaffected.

## Verification

Local Aiken binary: aiken v1.1.23+8949565, SHA-256 748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3. The required Aiken 1.1.21 binary was subsequently found in the existing local evidence toolchain and the unchanged full G1 command was rerun with the final test module present. That command executed 122/122 scenarios but exited 1; its independent capture is docs/remediation/m7_aiken_g1_current_test_r1/ASSESSMENT.md. The following 1.1.23 results remain diagnostic only and do not satisfy G1.

- aiken fmt --check validators/f05_authority_policy.test.ak   exit 0.
- aiken check --debug --trace-level silent --match-tests "f05_authority_policy.{..}"   exit 0; 2/2 tests passed (public_applied_policy_fixture_accepts, public_seed_missing_regression_rejects).
- In isolated temporary copies, aiken build --trace-level silent ran once with the test module removed and once with it present, inside bwrap --unshare-net. Both exits were 0. The generated plutus.json SHA-256 matched exactly in both copies: 8b51c21590d41056ca3f7b8372f8970ffae19ab1dbfe92d9405c1bc5111d930b. Both F05 validator entries had compiledCode SHA-256 fac27d229b4af8f2df39585c4ee2727eb9f64e32fa4cb2108317522d10fbd95f. No test module appears in either production blueprint. Dependency resolution reported two packages fetched from the local cache; network access was isolated.
- The prior required full G1 command remains failed: 120/120 scenarios passed but process exit was 1 under --deny with offline Git-version certainty warnings. Do not count G1 as passing. This focused diagnostic is under 1.1.23, not the pinned 1.1.21 command.
- Existing accepted original applied-policy identity evidence remains docs/remediation/m3_f05_2a_identity_r1/REVIEW.md: two pinned 1.1.21 builds and independent direct application matched the frozen artifact and policy ID 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731. The byte-identical 1.1.23 baseline/candidate build comparison above shows this test-only addition does not change the compiled production blueprint; it is not a new pinned identity reproduction.

## Independent review

/root/identity_review reviewed the exact final test-file SHA-256 a3bc9ccafa26ae4219207a620940ca7da3296608d576725c325a4558b958336d and accepted it for this bounded source-level/diagnostic slice. The reviewer confirmed helper parity and that seed_missing removes only the seed input while retaining the funding input. The reviewer did not replay Aiken; the local 2/2 result is separately captured above.

## Remaining blockers

F05.2a remains open. The applied-parameter family still requires the owner's documented A/B/C evidence-contract decision. Four remaining signature-domain negatives require evidence that is not supplied by this native unit test. The pinned full Aiken G1 result remains failed/unverified under the available toolchain. F01 F03, M3 M9, T06/history, invariants and deployment prerequisites remain open; Pre-Prod remains INCONCLUSIVE and readiness remains NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Next single slice: r2_signature_for_other_seed, using the existing runner's ephemeral test-only committee and synthetic compiled-context evidence; the applied-parameter A/B/C decision remains separate.
