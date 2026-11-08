# Independent R4 family review

Date: 2026-10-03
Result: PASS - independent family approval for pre-simulation gate.

Reviewed exact coordinator freeze FREEZE.json, SHA-256 df7d882ad8aa26b59692c65457bf888204cfbfdc3586ce2619a99f1749115c6b.

The independent reviewer verified all 18 package hashes with SHA256SUMS and matched the family manifest, checksum-list file, builder, case manifests, and CBOR artifacts to FREEZE.json. The freeze records three cases, 18 artifacts, checksum exit 0, zero executions, and all cases PENDING.

Without Aiken or simulator execution, the reviewer parsed and canonically round-tripped the CBOR, checked transaction body hashes, and independently verified all six serialized Ed25519 funding witnesses against each case body hash. Each public-key payment credential matched a resolved raw-output address. The reviewer recalculated 17M lovelace input = 16M outputs + 1M fee and exact minted/output asset equality for all cases. The declared deltas were confirmed: seed_missing replaces aa...aa#7 with dd...dd#8 at the same position in both body inputs and ordered raw_inputs; seed_datum_hash changes only bootstrap_tx_hash aa...aa to bb...bb; seed_datum_index changes only bootstrap_output_index 7 to 8.

This PASS meets the independent family-review prerequisite for this exact frozen package when recorded. It does not execute the simulator, admit any case, or grant ledger/live evidence. All three cases remain PENDING pending simulator execution and subsequent independent result review.
