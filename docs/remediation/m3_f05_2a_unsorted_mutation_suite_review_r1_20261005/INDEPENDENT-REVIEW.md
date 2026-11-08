# Independent review: F05.2a unsorted mutation-suite capture

Date: 2026-10-05
Review revision: r1
Canonical checkout reviewed: /home/GodOfAgents/code/VAMS-testnet
Canonical branch: testnet/remediation-20260907
Canonical HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

Decision: PASS for the recorded synthetic alternate-applied-policy mutation-suite capture, subject to the stated evidence boundaries. This review is read-only: the simulator was not rerun and canonical files were not edited.

## Scope and commands

Reviewed the exact capture package, capture script, R5 applied_keys_unsorted fixture family, and prior independent R5 reviews. The following read-only checks passed:

- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_unsorted_mutation_suite_r1_20261005 && sha256sum -c SHA256SUMS` — PASS: RUN.json OK.
- `cd /home/GodOfAgents/code/VAMS-testnet && sha256sum -c docs/remediation/m3_f05_2a_unsorted_mutation_suite_r1_20261005/SCRIPT.SHA256SUMS` — PASS: capture script OK.
- `cd /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_unsorted && sha256sum -c SHA256SUMS` — PASS: fixture manifest and all 18 fixture artifacts OK.
- Each prior R14, R15, and R16 independent-review directory `sha256sum -c SHA256SUMS` — PASS: all three review reports OK.
- Read-only source inspection of the capture script and RUN.json — PASS: no simulator rerun, key generation, network submission, or canonical write was performed by this review.

## Evidence identities

- Capture RUN.json SHA-256: `7e8b92d66220857213b7c64bd547a4aeeccc4ae938e73c403b5460a1dd180f85`.
- Capture package SHA256SUMS file SHA-256: `46ff471ee9f553ce6bf774597825f2482c2f0d7c43d689dff56787b2cda4fc27`.
- Capture SCRIPT.SHA256SUMS file SHA-256: `83ba1f3e377a2877abb6b01ce33bea9854aa190dd554b4df12b8d7590b9d6232`.
- Capture script SHA-256: `a0a221071b7dc5e88b453a26375a3b9791906faac7c3107ab6411994374e10ed`.
- Immutable R3 runner SHA-256: `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`.
- R5 family manifest SHA-256: `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`.
- R5 unsorted fixture manifest SHA-256: `bf84b96865bb89860a25f1cbf6a9799419a17b7b71bf6249c21fabe128a27c96`.
- Prior R14 positive-control review SHA-256: `f08ac5add7f4096054d994ed3a1977663cf4c88096b8a5fdd295e086e09c450e`.
- Prior R15 mutant-byte review SHA-256: `c17eecfb046a1f744b9193e2305fc9383a6fd8f077720eeb4e629509fd965aa1`.
- Prior R16 paired review SHA-256: `9f3b58dc98ee5144705db7f4101181904a93166d7d6b3e5730688e922216e54b`.

## Findings

The capture is explicitly for the preserved R4.1 case `applied_keys_unsorted` and mutation `remove_key_order_guard`, at `f05_authority_policy.f05_authority_policy.mint / Mint[0]`. It sets `mutation_suite: true`, uses the R5 applied-parameter fixture family, and records the scope as synthetic alternate-applied-policy transaction-simulator evidence only.

The capture records three independently bound runs using the pinned Python 3.12 path and Aiken 1.1.21 path with the immutable R3 runner:

- Positive control: policy `0be38709988ea180df3b89c467e7606350038b19bcc2113164d90ae6`; `script_accepted`; target invoked; wrapper and child exits 0; clean teardown.
- Original negative: policy `1fb791c31f3e1ca6ca17d0329ace7c345366359fed36096c325a2e93`; `compiled_evaluation`; target invoked; clean teardown; rejection is retained as a recorded compiled result pending classification overlay.
- Matching one-guard mutant: policy `cdeb5869ebdf5f07cac1d70896a2a3ead191357b5c4331ec7d8e1ff2`; `script_accepted`; target invoked; wrapper and child exits 0; clean teardown.

Each RUN binding reports compiled script hash, expected policy ID, and the sole policy ID equal to the command policy. Submitted transaction, raw-input, and raw-output hashes match the checksummed R5 fixture artifacts. The R5 manifest and capture record two valid body-bound ephemeral funding signatures per fixture, ADA and native-asset conservation, five proof signatures bound to the applied parameter, and `private_keys_persisted: false`. The capture script independently verifies fixture hashes, these validation metadata fields, expected simulator stage, target invocation, clean cleanup, policy binding, and submitted artifact hashes before writing RUN.json.

The capture script uses only the existing frozen fixture family and output record. It does not alter production validators or the fixture registry. No live key, credential, transaction, or network operation is present in the reviewed evidence.

## Acceptance and limits

PASS: the exact unsorted mutation-suite capture is internally consistent, checksum verified, correctly bound to the intended applied policies and Mint[0] entrypoint, and supported by the prior independent R5 byte and paired reviews. The mutation-suite row is eligible for a separate classification overlay after this review.

This review grants no original-policy credit, full-ledger-admission credit, Cardano Pre-Prod credit, live-network credit, or deployment-readiness credit. It does not promote a negative-case row by inference. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. No status or canonical evidence record was changed by this review.