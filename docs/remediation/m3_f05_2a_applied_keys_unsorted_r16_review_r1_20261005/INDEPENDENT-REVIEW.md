# Independent paired review: applied_keys_unsorted R14/R15/R16 triad

Date: 2026-10-05
Review revision: r1
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

Decision: PASS for one synthetic negative-case attribution to the unsorted key-order guard at compiled Mint[0]. R16 confirms acceptance of the exact reviewed one-guard mutant fixture; paired with R15's compiled rejection and R14's accepted positive control, the triad supports one negative-case credit after the status/classification record is updated. The synthetic mutant does not count as a mutation-suite result.

## Scope and method

Read-only paired review of the frozen R5 applied_keys_unsorted case, R14 positive run/review, R15 negative run, R16 mutant run, the prior independent mutant-byte review, exact package checksums, and the compiled validator/mutation source. No simulator, test, build, or network command was run by this review. Only this review report and its SHA256SUMS were written; existing case, run, status, handoff, and fixture records were not changed.

Exact verification commands and results:

- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r16_20261005 && sha256sum -c SHA256SUMS` — PASS: RUN.json OK.
- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_unsorted && sha256sum -c SHA256SUMS` — PASS: all 18 case-package entries OK.
- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_applied_keys_unsorted_r15_mutant_byte_review_r1_20261005 && sha256sum -c SHA256SUMS` — PASS: INDEPENDENT-REVIEW.md OK.
- Read-only Python hash/binding consistency checks across R5, R14, R15, R16, and the byte-review report — PASS, 9/9 assertions: exact R5 manifest links, paired R15 link, byte-review link, R15 and R16 transaction/input/output hashes, recomputed negative/mutant policy IDs and runner bindings, and expected compiled outcomes/clean cleanup.
- Read-only source inspection confirmed the exact order predicate and one-condition mutation. No execution was repeated.

## Evidence identities

- R5 family manifest SHA-256: `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`.
- R5 unsorted case manifest SHA-256: `bf84b96865bb89860a25f1cbf6a9799419a17b7b71bf6249c21fabe128a27c96`.
- R14 positive RUN SHA-256: `9d40df445cca42f37aab07bb221cc54535b95d70d79e6c64a236def6c2ea6aa1`.
- R14 independent positive review SHA-256: `f08ac5add7f4096054d994ed3a1977663cf4c88096b8a5fdd295e086e09c450e`.
- R15 negative RUN SHA-256: `2943e4d762012bb8e617255d7c54102596456fa6da3b25b841896a05554790c3`.
- R16 mutant RUN SHA-256: `11ff6ab03cac0dc488af7cc486bb994bf79fd1d0fb49ee4dff8ae619ff37fd24`.
- R16 SHA256SUMS file SHA-256: `b11bb09ba7930d609a5981317dc416ff0f02bf1041ef361076c9ef71fa2fdf5b`.
- Prior R15 mutant-byte review SHA-256: `c17eecfb046a1f744b9193e2305fc9383a6fd8f077720eeb4e629509fd965aa1`.
- Immutable R3 runner SHA-256 (all three runs): `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`.
- Aiken version/hash in the runs: `1.1.21+42babe5` / `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`.
- Python version in the runs: `3.12.14`.

## Paired outcomes and bindings

- **R14 positive control:** child exit 0; `script_accepted`; target invoked; clean cleanup. Applied policy, compiled script hash, and sole mint policy ID all equal `0be38709988ea180df3b89c467e7606350038b19bcc2113164d90ae6`. Submitted transaction/input/output SHA-256 values are `4e941601f87f2ffd61a2895af5abff51a386349fff1576b2cca0c2619c9ea942`, `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, and `5197dd961bfb903bfa4cac0a59c5453d2b73620e96a26a85afdba94198388c46`. Independent R14 review passed for this positive control.
- **R15 negative:** child exit 1; `compiled_evaluation`; target Mint[0] invoked; clean cleanup. Expected policy, compiled script hash, and sole mint policy ID all equal `1fb791c31f3e1ca6ca17d0329ace7c345366359fed36096c325a2e93`. Submitted transaction/input/output hashes match the frozen R5 negative bytes: `e77240962aa9151cb780eed1df30f8305a8958c0d24bf48c7d8dea9bece1de50`, `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, and `dd662f3915fce3b7aef990ef6944c991dea967c41bbed1ef12914f517577d8a8`.
- **R16 one-guard mutant:** child exit 0; `script_accepted`; target Mint[0] invoked; clean cleanup. Expected policy, compiled script hash, and sole mint policy ID all equal `cdeb5869ebdf5f07cac1d70896a2a3ead191357b5c4331ec7d8e1ff2`. Submitted transaction/input/output hashes match the independently reviewed R5 mutant bytes: `edff293f84522fb47862709f946daaf37772e1538d2cec7987b7f20013ab34e3`, `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`, and `a46379908504afba54268ff05b63248ad970912f288f4e2e4e2951e90df07`.

The R16 record references the exact R5 family/case manifests, R15 RUN hash, and byte-review hash. I independently recomputed the Plutus V3 hash from each selected raw applied-policy CBOR; R15 and R16 identities match both the expected policy argument and all three runner binding fields. Transaction, raw-input, and raw-output digests match the exact frozen case artifacts.

## Named-condition attribution

The preserved case ID/assertion is `applied_keys_unsorted` / `compile_with_unsorted_keys_and_matching_datum` under the user's R4.1 decision C. The same five unique 32-byte keys are present in the applied parameter and matching datum. Their exact vector is not strictly increasing: key[1] > key[2], while key[0] < key[1], key[2] < key[3], and key[3] < key[4]. The R5 manifest and prior byte review record five parameter-bound valid PoPs, two final-body-bound ephemeral funding signatures, ADA and native-asset conservation, and no persisted private keys. R15 and R16 redeemer proof hashes are identical in the frozen manifest; the raw funding inputs are identical, while each candidate has its own final output/body signatures.

Production `valid_ordered_keys` checks exactly five 32-byte keys and all four adjacent strict-increasing comparisons. The reviewed mutation map replaces only `bytearray.to_int_big_endian(second) < bytearray.to_int_big_endian(third)` with `True` for `remove_key_order_guard`. The other order comparisons, exact arity, key sizes, initial-key/datum equality, and bootstrap proof verification remain. The negative and mutant therefore share the same failing unsorted pair and valid proof context; R15 rejects at the compiled Mint[0] target with the production script, while R16 accepts at the same compiled entrypoint under the mutant policy that removes only that pair's guard. This differential establishes attribution to the named order condition despite the runner's generic negative failure label.

The separate R14 sorted positive control confirms an accepted transaction/control path under its matching applied policy. It is not substituted for R16 and is not needed to infer ledger admission.

## Credit decision and boundaries

PASS: this reviewed triad supports one negative-case credit for `applied_keys_unsorted` at the `transaction_simulator` evidence layer, subject to recording the corresponding classification/count overlay. The raw attempts remain synthetic alternate-applied-policy local simulator evidence. The R16 mutant-control outcome is a one-guard attribution control, not a result from the canonical 21-case mutation suite; its record explicitly has `mutation_suite: false`. Thus mutation-suite count remains **18/21 PASS**.

This review does not award original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. It does not change STATUS.md, SESSION_HANDOFF.md, the case manifest, or any status/count record. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.