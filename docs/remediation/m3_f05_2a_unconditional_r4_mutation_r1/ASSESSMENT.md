# F05 unconditional-success mutation using exact R4 context

Date: 2026-10-03
Status: PASS for the bounded synthetic simulator scope after independent review.

## Bounded slice

This probe pairs the registered `unconditional_success` mutant with the frozen R4 `seed_missing` transaction and its own exact resolved-input and output vectors. It also runs the same mutant against the frozen positive control. The base policy is freshly compiled from current Cardano source and must equal the accepted applied policy before any simulator call.

The probe changes the transaction's mint policy and output asset policy to the compiled mutant policy and replaces the Plutus V3 witness with the mutant script. It leaves each frozen fixture's raw-input and raw-output vector byte-identical. The exact baseline `seed_missing` transaction is also run unchanged.

## Results

The pinned, network-isolated command in `RUN.json` exited 0. Baseline `seed_missing` reached Mint[0] and was rejected (`compiled_evaluation`, child exit 1). The mutant accepted both the frozen positive control and the paired `seed_missing` context (`script_accepted`, child exit 0). All three runner wrappers exited 0, verified the exact bound policy/script hash, and reported clean process and snapshot teardown.

Base policy ID: `9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`.
Mutant policy ID: `1ff0752a9eb66b2a298ca96b504be91dcc2032b19a93522d332f34c9`.
Mutant compiled-code SHA-256: `5d91cb54daa12160e98851f559918e0c15029376f9728549a311a7932f6b0250`.

The captured transaction, resolved-input and output hashes are preserved in `RUN.stdout`; exact source-fixture hashes and tool/source hashes are in `RUN.json`. Probe syntax, whitespace, structured-output parsing and `git diff --check` passed. Independent integrated review passed; see `REVIEW.md`.

## Evidence limits

This is synthetic local transaction-simulator evidence. It exercises one registered paired negative, not the full 55-case unconditional-success contract. Rebinding the body to the mutant changes the transaction body and invalidates the original funding signatures; the R3 simulator result demonstrates Plutus invocation and behavior, not ledger validity or admission. No registered mutation credit is added. Accepted counts remain 45/55 negative cases and 18/21 mutations.

No validator, production harness, applied script, invariant, mock-mode behavior, credential, ledger, or network state was changed. INV-1 through INV-10 enforcement was not assessed by this probe.

Testnet readiness remains NOT READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
