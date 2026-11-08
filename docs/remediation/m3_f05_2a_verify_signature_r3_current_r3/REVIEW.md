# Independent review: F05 current-source R3 canaries

Verdict: PASS for the bounded synthetic simulator canary slice; no F05 ledger credit.

The independent reviewer recomputed hashes for RUN.json, RESULT.json, the capture wrapper, current harness, R3 runner and registry, manifest, applied-policy CBOR, both transactions, shared vectors, and pinned Python/Aiken tools. All match the captured identities. Python resolves to the pinned 3.12.14 executable; Aiken is the pinned 1.1.21 binary. The recorded before/after Git snapshots agree at HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f with 9 refs and 89 reachable commits, and current source/input hashes match across execution.

Current harness code verifies manifest and artifact digests, applied policy ID, exact Mint[0] witness binding, both expected simulator classifications, and clean process-group/snapshot-descriptor cleanup. RESULT records the valid fixture accepted (child exit 0) and invalid-signature fixture rejected by compiled evaluation (child exit 1); both wrapper exits are 0 and both target invocations are confirmed. Only the two fixed canaries ran; the registry and full suite were not part of this simulator invocation.

The assessment accurately distinguishes the historical legacy-builtin alias failure from the current synthetic UPLC harness, which now normalizes the token and requires byte-identical script re-encoding. The accepted F05 synthetic provenance package remains synthetic UPLC evidence; the R3 run adds only these two fixed synthetic transaction-simulator canaries. Neither grants case/mutation ledger credit, chain ledger admission, or live-network evidence. F05 stays 45/55 negatives and 18/21 mutations.

Caveat: RUN.json's outer_bwrap_argv is reconstructed metadata, not introspected from the wrapper's parent process. The assessment records the exact command issued for this run, but RUN.json alone does not independently attest that outer invocation. This limitation does not change the bounded result classification.
