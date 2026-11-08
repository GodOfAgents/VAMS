# Independent exact-byte review - applied_keys_parameter mutant R1

Date: 2026-10-05
Review result: PASS for controlled synthetic mutant execution only
Candidate status: PENDING; no simulator execution or case/mutation credit was performed in this review.

## Scope

Reviewed the candidate package at docs/remediation/m3_f05_2a_applied_keys_parameter_mutant_r1_20261005/, its builder and structural test, the untouched R5 applied_keys_parameter package, canonical applied source, and R10/R11 simulator records. I did not edit the candidate or its scripts, execute a simulator, submit a transaction, or change case classification.

## Exact identities and checks

- Candidate SHA256SUMS: all seven listed artifacts verified successfully. Candidate manifest SHA-256: b92446fd7cee50318e5c75f591459507a913a552c13de14305691f822d969ede; candidate checksum-file SHA-256: f0536546c48dad129aabc9ddfbf5fc41202418f68df875c14257d78bdf4bb710.
- R5 family SHA256SUMS: all listed files verified successfully. R5 family manifest SHA-256: 3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e; root checksum-file SHA-256: ad27af4dd49aac3e8d0ba570468adf5c4fc32e02b5acc3303b2f40b67e5c71f0.
- Canonical cardano/lib/vams/f05_authority.ak SHA-256: 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3, matching the candidate's recorded original source hash.
- R10 RUN SHA-256: fdd13ca0572ba92c302d0e5537ee2670520570dcf25977feb39ebebaa6a3a2c9. R11 RUN SHA-256: ca0e17acffdffe5877ee6f1b6ffc2facefbbb70a89ab29c78f488b9c5da92cad. Both record the R5 applied-keys policy ID efec0d79e496e2df81f8e3e27734c9718655dc577070c7519645fa29, target Mint[0], the R5 positive/negative fixture hashes, and clean cleanup. R10 records accepted positive control; R11 records negative rejection at compiled evaluation. These records retain their stated limitation: no raw simulator stdout/stderr or external attestation.

## Source and compilation review

The patch changes exactly one source predicate:

state.ordered_keys == initial_keys -> True

The case ID and assertion remain applied_keys_parameter / compile_with_different_sorted_keys_keep_datum. The R5 negative transaction, datum and Mint[0] redeemer are retained; the applied policy and mint witness are rebound to the mutant policy. The mutant keeps R5's five proof signatures and exact applied parameters. Its manifest grants no case, mutation, original-policy, ledger-admission, or live-network credit.

Using pinned Python 3.12.14 and Aiken v1.1.21+42babe5 (binary SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79), I independently rebuilt the unmodified R5 policy and verified exact code and policy-ID equality. I then copied the source to a disposable temporary directory, manually replaced only the named predicate, and independently compiled it. The resulting mutant policy bytes exactly match the candidate: code SHA-256 bfcbc1361e57d2a8869848737c00b8f4d4af405ec734faa1a4ee4904413c5c42, policy ID 5fe25c314f2f1bea85b8bc03e078d0c98ac549d62e630382f488cf16. The recorded mutant-source SHA-256 also matched: 940d1ef0e823ec28aa4669ea3d7c99fea62c2838079f7e3965ba58009fc646fa.

The candidate structural test function test_r1_candidate_exact_r5_binding_and_no_simulation passed when invoked directly through pinned Python. pytest was unavailable in that runtime (No module named pytest), so no pytest result is claimed.

## Witness and conservation review

The structural test verified the five PoP signatures against the R5 applied key vector and genesis reference, exact preserved Mint[0] redeemer, mutant policy/script witness binding, and two ephemeral funding signatures over the transaction body hash. It also verified that funding addresses resolve to those witnesses and that ADA and native-asset conservation hold. No private key is present in the candidate package; the builder uses ephemeral memfd-backed keys and retains only signatures/public transaction bytes.

## Decision and limits

PASS: the exact candidate is suitable to proceed to the next separately controlled local synthetic mutant execution under the candidate mutant policy. This is not execution approval from this reviewer beyond that narrowly defined test scope, and it does not itself change the case's pending classification. Preserve the R10/R11 and mutant evidence as synthetic transaction-simulator evidence only; do not infer original-policy behavior, broader ledger admission, or live-network evidence. Keep F05/M3 open and all deployment and gated activations disabled.
