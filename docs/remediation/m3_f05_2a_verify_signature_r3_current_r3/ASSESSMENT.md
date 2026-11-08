# F05 direct-evaluator / R3 simulator diagnostic

Date: 2026-10-04

## Result

A fresh run of the current public harness's fixed R3 canary mode passed against the currently reviewed source. It submitted only the frozen valid and invalid-signature transactions to the exact applied policy 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731 at Mint[0]. The valid transaction was accepted (simulator child exit 0); the invalid-signature transaction was rejected by compiled evaluation (child exit 1). Both wrapper exits were 0, target invocation was confirmed, and cleanup was clean.

An earlier direct UPLC run aborted before a verdict because the evaluator did not recognize Aiken's legacy verifySignature spelling. The current harness normalizes that builtin token and requires byte-identical re-encoding before evaluation; the separately accepted synthetic provenance package records a completed 57-row case run and 21 mutations. This R3 run adds current-source transaction-simulator evidence for two fixed CBOR fixtures. It does not prove that every full-harness context or mutation can be materialized as a ledger-shaped transaction under R3, because current R3 mode is canaries-only and registry was not run.

## Exact run and inputs

The final wrapper was independently reviewed before execution. It verified Python 3.12.14 and its resolved pinned executable, Aiken 1.1.21 and binary hash, exact harness/runner/registry source hashes, fixture/manifest hashes, and matching pre/post source and Git-ref snapshots. It refuses to run with preexisting output files, and only the new evidence directory was writable under network-isolated bwrap.

Exact invocation:
The outer_bwrap_argv field in RUN.json is a declared/reconstructed record of the launcher arguments, not a value introspected from the wrapper's parent process. The exact command shown here is the command issued for this execution; RUN.json alone does not independently attest the actual outer invocation.


```text
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --bind /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_verify_signature_r3_current_r3 /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m3_f05_2a_verify_signature_r3_current_r3 --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B docs/remediation/m3_f05_2a_verify_signature_r3_current_r3/run_capture.py
```

Key identities are bound in RUN.json: current harness SHA-256 1db507fe0559216a28d3768deaf12e1d56ecb76f51ef8cad1c5cec1f4449550b; R3 runner SHA-256 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c; registry SHA-256 c03230249c7e73f6929cc944b7af3e30d98b8168f8abd184fa39332a601a394e. The valid transaction hash is 765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28; invalid-signature transaction hash is 594c1b9297bff3a55c1bd7b600ad8f5d2c049471b70e667bc064212100f3754c. Shared raw input/output hashes and the policy ID are recorded in RESULT.json.

## Capture-attempt disposition

Two earlier diagnostic attempts remain preserved in sibling folders and receive no evidence credit. m3_f05_2a_verify_signature_r3_current_r1 completed the two canaries, but its wrapper did not verify the running Python identity, bind reviewed source hashes, or capture full outer bwrap argv. m3_f05_2a_verify_signature_r3_current_r2 failed closed before launching a canary because it treated the pinned python launcher symlink as disallowed. The final r3 wrapper validates its exact symlink target and interpreter, binds reviewed source hashes, records one compared pre/post snapshot and full outer argv, and refuses output overwrites.

## Classification and remaining scope

This is synthetic local transaction-simulator evidence only. It adds no registered F05 negative-case or mutation credit; accepted counts stay 45/55 negatives and 18/21 mutations. It is not ledger admission, Cardano Pre-Prod rehearsal, or live-network evidence. The earlier direct-evaluator alias failure is resolved for the current synthetic UPLC harness; no full-suite R3 simulator transaction-construction contract exists. The six applied-parameter and four proof-domain owner classifications remain pending; F04's normative identity entrypoint is also unresolved. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Independent post-run review is pending.
