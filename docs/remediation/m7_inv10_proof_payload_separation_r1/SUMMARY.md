# INV-10 focused proof/payload separation

This package records one existing focused test of the INV-10 requirement that a cross-chain proof remain separate from the payload hash. The test passed in the pinned offline Python environment under a network-disabled, read-only checkout wrapper.

The assertion is structural: it verifies the payload hash against SHA-256(payload), accepts a separate synthetic proof of at least 64 bytes, and rejects using payload-hash bytes as the proof. The current verifier checks nonempty hash and proof length; this result does not establish cryptographic proof validity, ledger admission, or live-network behavior.

No source or test files were changed. This adds no F05 case or mutation credit. F05 remains 45/55 negative cases and 18/21 mutations. The F05 applied-parameter and proof-domain choices and the F04 mint-path choice remain owner-blocked. Testnet readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
