# F05 unconditional-success mutation through R3

Date: 2026-10-03
Status: bounded synthetic probe accepted after independent review; no registered mutation credit.

## Change

Updated only the test-only unconditional_success source mutator in scripts/remediation/test_f05_2a_authority_bootstrap_public.py. Its former source anchor described the old multiline handler and no longer matched the current two-line validator body, so mutation compilation stopped before running. The mutator now replaces the current redeemer destructuring and validate_bootstrap call with a matching redeemer pattern and True.

Added probe.py and captures under this directory. The probe reconstructs the genesis reference and initial keys from the frozen synthetic transaction's input and inline state datum, compiles the current base, and requires its applied policy ID to equal the accepted frozen ID before compiling the mutant. It then binds each generated witness to its own Mint[0] policy hash.

## Verification

- The first feasibility invocation stopped at the stale mutation anchor with RuntimeError before the mutant was compiled or any transaction simulator was run.
- After the targeted anchor correction, the network-isolated probe passed:
  bwrap --unshare-net --ro-bind / / --tmpfs /tmp --ro-bind /home/GodOfAgents/.cache /home/GodOfAgents/.cache --dev-bind /dev /dev --proc /proc --setenv HOME /home/GodOfAgents --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B docs/remediation/m3_f05_2a_unconditional_r3_mutation_r1/probe.py
  Exit 0. The reconstructed base policy equals 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731. The mutant compiled to code SHA-256 5d91cb54daa12160e98851f559918e0c15029376f9728549a311a7932f6b0250 and policy ID 1ff0752a9eb66b2a298ca96b504be91dcc2032b19a93522d332f34c9.
- Baseline seed_missing transaction: R3 child exit 1, classified compiled_evaluation, target invoked, clean teardown.
- Mutant valid transaction: child exit 0, classified script_accepted, target invoked, clean teardown.
- Mutant seed_missing transaction: child exit 0, classified script_accepted, target invoked, clean teardown.
- The separate public --tx-sim-r3-canaries mode was rerun after the source edit: exit 0, valid accepted and invalid-signature rejected, both with exact frozen policy binding and clean cleanup.
- Python AST parsing, direct whitespace/final-newline checks for the untracked harness/probe, JSON parsing, and git diff --check passed. git diff --check covers tracked changes only; the direct check covered the untracked Python files.

RUN.json and adjacent outputs bind exact commands, current sources, fixture inputs, mutant code/policy identifiers, per-case transaction hashes, and classifications.

## Evidence limits

This is synthetic local R3 transaction-simulator mutation evidence. It reproduces the accepted base policy and one paired negative for unconditional_success, but does not test the mutant against all 55 negative fixtures or establish ledger admission. The probe removed the seed from the transaction body while retaining the canonical positive control's raw-input vector, outputs, and signatures. The reviewer confirmed that the registered R4 seed_missing candidate replaces the seed reference in both the body and ordered raw-input vector and binds different transaction/raw-input/raw-output hashes. Therefore this replay is neither the exact registered case nor evidence of a ledger-reachable transaction. Do not promote the registered mutation from this slice. The accepted ledger remains 45/55 negative cases and 18/21 mutations. No validator behavior, INV-1 through INV-10 enforcement, or mock behavior changed.

Independent integrated review PASS for the bounded synthetic probe: the reviewer verified current hashes and independently replayed all three outcomes, exact Mint[0] binding, and clean teardown. Review does not remove the raw-input-vector/conservation limitation above. Testnet readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
