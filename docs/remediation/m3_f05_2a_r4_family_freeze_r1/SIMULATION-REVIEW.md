# Independent review of R4 simulator execution

Date: 2026-10-03
Result: PASS for synthetic transaction-simulator evidence only.

The reviewer verified that the coordinator FREEZE.json still has SHA-256 df7d882ad8aa26b59692c65457bf888204cfbfdc3586ce2619a99f1749115c6b and that the family checksum list passes all 18 files. SIMULATION-RUN.json parses, its stdout/stderr/exit capture hashes match, and its recorded hashes for run_family.py, capture_simulator.py, the R3 runner, Aiken binary, and family fixtures match current files.

The preserved first attempt ran only Aiken version identification and failed on the version-prefix assertion before entering the case loop or invoking a transaction simulator.

The reviewer independently replayed the exact network-isolated command. seed_missing, seed_datum_hash, and seed_datum_index each reproduced: wrapper exit 0; simulator child exit 1; compiled_evaluation with target Mint[0] invoked; exact frozen transaction/raw-input/raw-output hashes; exact applied policy/script hash; clean teardown.

Limitations: this accepts only the three compiled target rejections at synthetic local simulator scope. The captured classifications do not identify the precise internal guard trace, and they establish neither Cardano ledger admission nor live-network behavior. No case or mutation count was changed by this review.
