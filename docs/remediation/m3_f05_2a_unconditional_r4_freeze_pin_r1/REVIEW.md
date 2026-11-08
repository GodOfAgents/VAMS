# Independent review: F05 R4 freeze-pin follow-up

Date: 2026-10-03
Result: PASS for the bounded provenance and synthetic simulator scope only.

The reviewer confirmed the probe checks the accepted FREEZE.json SHA-256 `df7d882ad8aa26b59692c65457bf888204cfbfdc3586ce2619a99f1749115c6b` before reading the family manifest, compiling Aiken, or invoking the simulator. The current probe, freeze, family, contract, harness, runner and registry hashes match `RUN.json`.

The reviewer independently reran the exact network-isolated command in `RUN.json`; it exited 0 with empty stderr. All three classifications, frozen case and submitted transaction hashes, Mint[0] policy/script bindings and cleanup results matched the capture: baseline `seed_missing` rejected; mutant positive and paired negative accepted.

Only the paired negative was run for this mutant. The transaction body and Plutus witness are rebound to the mutant policy, so ledger validity and admission are not established. No registered mutation credit is added; counts remain 45/55 negative cases and 18/21 mutations. No replay blocker was found.
