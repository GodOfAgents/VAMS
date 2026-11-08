# Independent review: applied_keys_unsorted R15 mutant bytes

Date: 2026-10-05
Review revision: r1
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

Decision: PASS for exact-byte integrity, applied-policy binding, and eligibility of the one-guard mutant-control fixture for simulator execution. This is not a mutant execution result and awards no mutation credit.

## Scope and method

Read-only review of the R5 applied_keys_unsorted fixture package, the R15 negative simulator record, the R14 positive-control record/review, the immutable R3 runner/classifier, validator source, builder, and evidence-contract mutation map. No files other than this review report and its checksum manifest were written. No tests, builds, simulators, or network operations were run. Existing case/attempt/status/handoff records were not changed.

Commands and results:

- cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_unsorted && sha256sum -c SHA256SUMS — PASS; all 18 entries reported OK.
- sha256sum docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/FAMILY-MANIFEST.json docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r14_20261005/RUN.json docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r15_20261005/RUN.json scripts/remediation/f05_2a_tx_sim_runner_r3.py cardano/lib/vams/f05_authority.ak cardano/validators/f05_authority_policy.ak — identities recorded below.
- Read-only Python recomputation of the applied policy identity as blake2b(0x03 || applied_policy_cbor, digest_size=28) — negative ID and mutant ID both match the fixture/RUN records.
- Targeted source reads of valid_initial_authority, valid_ordered_keys, Mint[0], the runner result classifier, builder, and the one-guard mutation table — findings below.

## Exact evidence identities

- R5 family manifest SHA-256: 3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e.
- R5 unsorted case manifest SHA-256: bf84b96865bb89860a25f1cbf6a9799419a17b7b71bf6249c21fabe128a27c96.
- R15 RUN SHA-256: 2943e4d762012bb8e617255d7c54102596456fa6da3b25b841896a05554790c3.
- R14 positive RUN SHA-256: 9d40df445cca42f37aab07bb221cc54535b95d70d79e6c64a236def6c2ea6aa1.
- R14 independent positive-review SHA-256: f08ac5add7f4096054d994ed3a1977663cf4c88096b8a5fdd295e086e09c450e.
- Immutable R3 runner SHA-256: 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c.
- R5 fixture generator SHA-256: 9c72cc24a96b1e68663397ab724292056e532691b78dd324813b614f92cb3f96.
- Evidence-contract mutation map SHA-256: d82e2b5592eb604e04553eac93a0857546545d4eb8c4854d649b40312111a8ef.
- Authority library SHA-256: 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3.
- Mint validator SHA-256: e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8.

Exact mutant-control artifact hashes from the independently verified case manifest and case-local SHA256SUMS:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| one-guard-mutant-control.applied-policy.cbor | 3455 | 91be07bf413a20f95710f2aab5d72a618386ff3cdf264c70d7a5d5777235f31e |
| one-guard-mutant-control.genesis_ref.cbor | 39 | 5e0115ddb460b0c9eab9bba6499740f9e32cbf5e41fa02eb7f0a99d91473f086 |
| one-guard-mutant-control.initial_keys.cbor | 172 | 384c02f75ee4721b8b0cd50afc82572cd66473f7564c3b01414907362a17a509 |
| one-guard-mutant-control.raw_inputs.cbor | 73 | 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe |
| one-guard-mutant-control.raw_outputs.cbor | 79 | a46379908504afba54268ff05b63248ad970912f288f4e2e4e2951e90df07 |
| one-guard-mutant-control.tx.cbor | 5092 | edff293f84522fb47862709f946daaf37772e1538d2cec7987b7f20013ab34e3 |

## Findings

The case ID and assertion remain applied_keys_unsorted / compile_with_unsorted_keys_and_matching_datum. The mutant applied-policy ID is cdeb5869ebdf5f07cac1d70896a2a3ead191357b5c4331ec7d8e1ff2; recomputing the Plutus V3 policy hash from the exact applied-policy CBOR yields this same ID. It is a separately compiled alternate policy, not the original policy.

The negative uses five unique 32-byte keys, with the same ordered byte vector in its applied parameter and datum. The sole descending adjacent pair is key[1] > key[2]; the other three adjacent comparisons are increasing. The manifest records five valid PoP signatures bound to the applied parameter, two valid body-bound ephemeral funding signatures, ADA and native-asset conservation, and no persisted private keys. The mutant-control validation record carries the same five PoP signature bytes and key vector, plus two body-bound funding signatures for its own transaction body; it records ADA/native conservation and no persisted private keys. These signature/conservation statements are fixture-manifest assertions; this audit verified exact byte hashes and bindings, but did not independently re-derive signatures or run a ledger validator.

The evidence-contract mutation map and builder identify the one-condition change precisely: in valid_ordered_keys, replace bytearray.to_int_big_endian(second) < bytearray.to_int_big_endian(third) with True. The first/third/fourth strict-order comparisons, five-key arity, 32-byte lengths, state/parameter equality, and bootstrap proof verification remain in source. This removes the single failing comparison for the R5 unsorted vector while retaining all other checks. The mutant fixture has its own policy, transaction, output bytes, and funding signatures.

R14 is the accepted positive control under policy 0be38709988ea180df3b89c467e7606350038b19bcc2113164d90ae6; its independent review passed for that positive control only. R15 binds the negative transaction to policy 1fb791c31f3e1ca6ca17d0329ace7c345366359fed36096c325a2e93, reports target Mint[0] invocation, compiled evaluation rejection, and clean cleanup.

The runner classifier recognizes the exact Aiken transcript as either script_accepted or generic compiled_evaluation. It does not expose the failing expect or predicate. Accordingly, R15 alone does not prove that the named ordering assertion caused rejection. The source and fixture make the order comparison the expected failing guard, but execution-time attribution remains unproven until the one-guard mutant is accepted and an independent reviewer checks the paired results.

## Eligibility and evidence boundary

The mutant-control fixture bytes are independently reviewed for case-local checksum integrity, exact applied-policy binding, key-vector shape, designated one-condition mutation, and the recorded proof/funding/conservation structure. It is eligible for the next bounded simulator execution using the immutable runner and the mutant policy ID above. This review does not claim that the mutant has run or been accepted. After execution, obtain an independent paired negative/mutant attribution review before giving the negative case credit or changing classification.

Keep R15 negative PENDING until that paired post-run review. Keep the mutant pending until its own run and review pass. All evidence remains local synthetic alternate-applied-policy simulator evidence only. It grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.