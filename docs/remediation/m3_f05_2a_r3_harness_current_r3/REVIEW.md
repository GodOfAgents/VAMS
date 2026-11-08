# Independent review: current-source R3 applied-policy canaries

Verdict: PASS for the two-canary synthetic simulator scope.

All seven package checksums, three current-source hashes, six frozen-input hashes, and the pinned Aiken runtime hash match. Captured output, RESULT.json, empty stderr, and exit 0 are consistent. The current harness source includes the diagnostic correction.

The runner binds the sole Mint[0] policy to the expected applied-script hash and confirms target invocation. The valid canary is accepted; the invalid-signature canary reaches Mint[0] and is rejected. Comparing the frozen transactions shows the body and script witness are unchanged; only redeemer field 5 differs. Both cleanup assertions pass.

This adds no registered F05 case or mutation credit, ledger admission, or live-network evidence. The registry did not run. No discrepancy was found.
