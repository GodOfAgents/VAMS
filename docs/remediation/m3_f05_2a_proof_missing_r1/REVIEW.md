# F05.2a missing bootstrap proof negative — 2026-10-02

Independent review accepts exactly the registered negative case
r2_proof_missing. Counts: **28/55 negatives PASS, 27 pending; 3/21
mutations PASS, 18 pending**. Mutation counts are unchanged. The case reduces
only the Mint redeemer's proof list from five 64-byte proofs to four. It keeps
the transaction body, funding signatures, Mint map, applied Plutus V3 witness,
raw UTxO inputs and outputs unchanged.

Changed canonical records: this directory's REVIEW.md and CASE-STATUS.json,
plus docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md.
Branch testnet/remediation-20260907, HEAD
829ab544571f12efe50ecb5740f129c8acb3e16f. Production policy SHA
5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05,
blueprint SHA c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2,
lock SHA 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
No Cardano production source or accepted policy changed.

Exact commands/results:

- PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/build_proof_missing.py:
  exit 0. Built exact canonical-CBOR proof-list mutation and replayed untouched
  positive plus negative on pinned Aiken 1.1.21 using run_snapshot_simulation:
  valid accepted; four-proof negative reached compiled Mint[0] and rejected;
  both wrapper exit 0 and cleanup clean. Pinned binary SHA256
  07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Pinned Python 3.12.14 inline replay on Aiken 1.1.23: exit 0; valid accepted
  and negative rejected at compiled evaluation; wrapper exits 0 and cleanup
  clean. Binary SHA256
  748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3.
- Independent CBOR and integrated case review: PASS. It verified five candidate
  package hashes; identical body SHA256
  62077b7f1bf4ef13ef236ca5a1e8037d318404cb6fdf6463af44d50638031c12; Mint
  pointer [1,0]; constructor tag 121 with proof count 5->4 and 64-byte proofs;
  unchanged funding vkey witness, Mint and script witness; raw UTxO equality;
  target policy identity; and positive/negative replay on both pinned runtimes.
  Review SHA256
  bb7887b71f8a915070664674f48ed1d3d0a6cc4fcfa99b14b7aca6842fed4ad1.
  Candidate negative transaction SHA256
  d74c7c6fb8b22ec6a7908cb9becd0e7cbc1bbacdb169e474da9d2affa84167c7;
  result SHA256
  4544cdde3e5bf2106c1bd30fd0b227e968ea28066113f9f7d65f438438d16441.
- git diff --check: PASS.

This is synthetic simulator evidence only. It establishes neither full ledger
admission nor live-network evidence. INV-1–INV-10 and mock behavior are
unchanged. F05/M3 remain open; Pre-Prod is INCONCLUSIVE and promotion is NOT
READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
T06/history and all remaining mandatory roadmap gates are outstanding.

Next single slice: the contract-paired r2_invalid_proof_0 negative and
remove_bootstrap_proof_of_possession_verification compiled mutation. Keep its
exact disposable-source identity, mutation controls and independent review
separate from this accepted case-only result.
