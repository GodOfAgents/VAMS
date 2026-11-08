# F05 public-harness R3 snapshot canaries

Date: 2026-10-03
Status: accepted after independent integrated review; synthetic-only evidence.

## Change

Added a separate --tx-sim-r3-canaries mode to scripts/remediation/test_f05_2a_authority_bootstrap_public.py. It validates the existing checksum-pinned canary manifest, Aiken runtime, applied-policy artifact, and shared transaction vectors, then runs only the frozen valid and invalid-signature transactions through f05_2a_tx_sim_runner_r3.py. It requires the R3 result schema, exact sole Mint[0] policy and script hash, expected simulator child exit/classification, target invocation, submitted byte hashes, and complete clean teardown. The existing --tx-sim-canaries mode, third wrong-credential case, and mutation suite were left unchanged.

The first attempt confirmed the Aiken runtime version and binary hash, then failed before transaction-simulator invocation because the new subprocess call lacked a sys import. The failed invocation is preserved as FIRST-ATTEMPT.* (exit 1). The import was added; the identical bounded mode then passed. That first attempt is not validator or simulator evidence.

## Verification

- Python AST parse of the updated public harness: exit 0.
- Direct trailing-whitespace/final-newline check of the untracked harness and assessment: exit 0. git diff --check: exit 0 for tracked changes; it does not inspect the untracked harness.
- Network-isolated pinned invocation:
  bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B scripts/remediation/test_f05_2a_authority_bootstrap_public.py --aiken /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken --tx-sim-r3-canaries
  Exit 0; status pass; exactly two cases. The valid fixture has wrapper/child exits 0 and script_accepted. The invalid-signature fixture has wrapper exit 0, simulator child exit 1, and compiled_evaluation. Both invoke the target policy and report clean cleanup. Full JSON stdout, stderr, exit, first-attempt failure, and exact hashes are adjacent; RUN.json binds the command and all relevant inputs.

## Evidence boundary

This is synthetic local transaction-simulator evidence only. It proves this test harness mode reaches the exact frozen policy and distinguishes these two fixture outcomes. It does not qualify a registered F05 negative or mutation, establish ledger admission, or establish live-network behavior. Counts stay 45/55 negative cases and 18/21 mutations. No INV-1 through INV-10 enforcement or mock behavior changed.

Independent integrated review PASS. The reviewer independently replayed the network-isolated CLI and verified source/manifest/tool/fixture/capture hashes, exact two-case scope, fail-closed result controls, target invocation, policy binding, and cleanup. No functional blocker was found. Testnet readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
