# Independent triad review: applied_keys_parameter R10/R11/R12

Date: 2026-10-05
Review result: **PASS for named-condition attribution within local synthetic alternate-policy transaction-simulator evidence only.** The original case was pending before this review; this report supports case-level synthetic credit only if the responsible evidence owner records it. It grants no mutation-suite credit and changes no case/status record.

## Scope and method

I reviewed the R5 family manifest and selected-case manifest, the exact R10 positive, R11 negative, and R12 one-guard-mutant run records, their declared checksums, and the prior independent R10, R11, and mutant-candidate reviews. I did not run a simulator, edit source or fixtures, alter classifications, or modify STATUS.md or SESSION_HANDOFF.md.

All three attempt SHA256SUMS files verify. The R5 family checksum list verifies all entries. The mutant candidate checksum list verifies all seven artifacts. The three prior review checksum files verify their respective review reports. Exact review report hashes:

- R10 positive review: bd72af850dae32100958c0d70ab4c5acfc1605485a8b1efab1d96eab424fd097.
- R11 negative review: 649b67f2a349d39baeeb2c4aae5af4d1db6af48466da2a42fa5d70aac1dc4652.
- R1 mutant-candidate exact-byte review: 6925ef8a27c7e50c9476527d9578640c19f35df8f09109d314389019e122ebd9.

The reviewed identity anchors are R5 family manifest SHA-256 3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e, R5 root checksum-file SHA-256 ad27af4dd49aac3e8d0ba570468adf5c4fc32e02b5acc3303b2f40b67e5c71f0, selected case manifest SHA-256 c9cfa8d645dcb99fa20fa9933b88190b02027f724fba3c67d081efd0c06dac24, mutant candidate manifest SHA-256 b92446fd7cee50318e5c75f591459507a913a552c13de14305691f822d969ede, and mutant candidate checksum-file SHA-256 f0536546c48dad129aabc9ddfbf5fc41202418f68df875c14257d78bdf4bb710.

## Triad identities and outcomes

- R10 RUN SHA-256: fdd13ca0572ba92c302d0e5537ee2670520570dcf25977feb39ebebaa6a3a2c9. It records an accepted positive control (script_accepted, target invoked, Mint[0]) under applied policy efec0d79e496e2df81f8e3e27734c9718655dc577070c7519645fa29. Its transaction, input, and output hashes are 97f584e0f071b774883d15237042cefddff6e7b471d58329fcb5f24a08775c7d, 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe, and 37d1a506522392074de0f58ed0bf093eb181a612c9c9118d1060eae95f911ed3.
- R11 RUN SHA-256: ca0e17acffdffe5877ee6f1b6ffc2facefbbb70a89ab29c78f488b9c5da92cad. It records rejection at compiled_evaluation with the target invoked at Mint[0], under the same applied policy ID and exact compiled-script/policy/mint binding. Its transaction, input, and output hashes are f57020cb1d5ac3a7eebf8885472c62e6c0c1c4f8f2c9f85f890beac25194413f, 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe, and c36f6ae6016bdf289d87758b37b6feab4daf13be58deadff57fdae12bf562645.
- R12 RUN SHA-256: bcd3e120ecd05b07e35f128f267da0f62f8e6c133042d854166326dfca53b19d. It records the corresponding one-guard mutant accepted (script_accepted, target invoked, Mint[0]). Its transaction, input, and output hashes are ea258404d05a61f4d325f09e699c14bd205577757268590d1f879a131246557b, 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe, and 37d8e797caf2b6daa8fdd3e436e426f7995777b7ec11c835985bc86d3fdefad9.

The R10 and R11 records bind to the same alternate applied policy, expected policy, compiled script hash, sole minted policy, fixed input vector, target entrypoint, and R5 fixture family. R12 changes the applied policy only for the reviewed mutant and records exact expected/compiled/minted policy agreement at the same Mint[0] entrypoint. The R11 negative and R12 mutant share the exact input vector and the negative Mint[0] redeemer source; the mutant candidate review confirms the negative datum/redeemer and five PoP signatures were retained while policy and mint witness were rebound. Output and transaction bytes differ as expected for policy rebinding, reminted asset identity, and body-bound funding witnesses.

## Attribution and witness assessment

The source predicate is the named condition: valid_initial_authority requires state.ordered_keys == initial_keys in cardano/lib/vams/f05_authority.ak. The selected R5 negative manifest retains the original case ID and assertion applied_keys_parameter / compile_with_different_sorted_keys_keep_datum. It records five distinct, strictly increasing 32-byte applied keys; the negative datum's ordered-key vector differs from that applied parameter vector. The positive control is the corresponding matching-key case under that same R5 applied policy.

The prior exact-byte candidate review independently rebuilt the normal policy to the R5 policy bytes and ID, then independently compiled the candidate with only this predicate replaced by True; it matched the mutant policy bytes and ID recorded in R12. It checked the negative datum/redeemer binding, five PoP signatures under the R5 applied parameter, mutant witness binding, two ephemeral funding signatures over the candidate transaction body hash, input/output address binding, and ADA/native-asset conservation. The R5 manifest records the same two funding signatures, five PoPs, body-bound signatures, conservation, and no persisted private keys for R10/R11. The per-attempt records report clean cleanup (child reaped, process group empty, descriptors closed).

Together, the control accepts with matching keys (R10), the unmutated policy rejects the mismatched-key negative at compiled Mint[0] (R11), and the otherwise corresponding negative is accepted at compiled Mint[0] after removal of only the key-equality guard (R12). The candidate's exact compiled artifact and transaction bytes were reviewed before R12 execution. This differential supports attribution of the R11 rejection to state.ordered_keys == initial_keys within this synthetic fixture and alternate-policy simulator scope.

## Limits and credit

The attempt records contain structured runner results transcribed from scoped execution; raw simulator stdout/stderr and an external execution attestation were not retained. The candidate and run reviews explicitly disclose that limit. I did not independently rederive cryptographic signatures or rerun compilation/simulation; the exact-byte mutant review reports those checks and its checksum verifies. Accordingly, this review accepts the recorded synthetic triad, subject to that capture limitation.

This supports **only case-level synthetic transaction-simulator credit for applied_keys_parameter**, pending the responsible evidence owner's classification update. It provides **no mutation-suite credit**, no original-policy credit, no full-ledger-admission credit, and no Cardano Pre-Prod or live-network credit. F05/M3 remains open; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
