# Independent review: F05 unconditional-success R4 exact context

Date: 2026-10-03
Result: PASS for the bounded synthetic simulator scope only.

The reviewer inspected the integrated probe, run manifest and captures against the current public mutator, mutation contract, R3 runner/registry, R4 family manifest/freeze and exact fixture files. Recorded hashes matched current files; all 18 R4 family checksums passed.

The reviewer independently replayed the exact network-isolated command recorded in `RUN.json`; it exited 0 with empty stderr. It reproduced the frozen base policy identity, baseline `seed_missing` compiled rejection, mutant positive-control acceptance and mutant paired-negative acceptance. Each case invoked the target Mint[0], matched its expected policy/script hash and completed with clean teardown. The mutant uses its own distinct policy ID and corresponding witness; its input/output vectors remain the exact frozen fixture vectors.

No registered mutation credit is warranted. Only one of the 55 negatives was tested for this mutation, and the probe does not establish funding-witness ledger validity or ledger admission. Counts remain 45/55 negative cases and 18/21 mutations.

Minor observation: the probe verifies the family-manifest hash and case artifact hashes, but does not pin the exact FREEZE.json hash in its own preflight. The captured RUN.json records the current freeze hash; this did not affect the review or its result.
