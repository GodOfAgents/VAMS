# Independent review - current-source F05 R3 canaries

Date: 2026-10-03
Result: PASS for the two synthetic canaries only.

The reviewer matched the current harness, R3 runner, registry helper, pinned Aiken binary, manifest, applied-policy artifact, transaction fixtures, shared vectors, and output captures to RUN.json. The current harness fail-closes on the pinned manifest/schema/case set, runtime identity, policy ID, artifact and transaction hashes, result schema/classification, target invocation, submitted-vector digests, and cleanup. The runner binds the sole mint policy and compiled witness hash to the applied policy ID.

Both fixtures invoked Mint[0]. The valid fixture was accepted (simulator child exit 0); the invalid-signature fixture was rejected by compiled evaluation (child exit 1). Both wrapper exits were 0 and cleanup was clean. The mode is limited to canaries and records registry not run.

This review grants no registered F05 negative-case or mutation credit and establishes no ledger admission or live-network evidence. Counts remain 45/55 negatives and 18/21 mutations. Reviewer did not rerun or edit files.
