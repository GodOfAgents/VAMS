# F05.2a invalid proof at ordered key 1 — 2026-10-02

Independent review accepts exactly the negative r2_invalid_proof_1. Counts:
**31/55 negatives PASS, 24 pending; 4/21 mutations PASS, 17 pending**.
Mutation counts are unchanged. Exactly byte 0 of proof index 1 flips one bit;
all five proofs remain 64 bytes and the other four proofs are unchanged. The
transaction body, funding vkey witnesses, Mint map, script witness and raw UTxO
vectors remain unchanged.

Changed canonical records: this directory's REVIEW.md and CASE-STATUS.json,
plus docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md.
Branch testnet/remediation-20260907, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f.
Policy SHA 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05,
blueprint SHA c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2,
lock SHA 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
No production source, blueprint, lock, accepted fixture or activation changed.

Exact commands/results:

- PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/build_invalid_proof_1.py:
  exit 0. The valid positive passed; proof-index-1 negative rejected at
  compiled Mint[0] on pinned Aiken 1.1.21; wrapper exits 0 and cleanup clean.
  Runtime SHA256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Pinned Python 3.12.14 replay on Aiken 1.1.23: exit 0; positive accepted,
  negative rejected at compiled evaluation, wrapper exit 0 and cleanup clean.
  Runtime SHA256 748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3.
- Independent case review: PASS. It verified six package hashes, exact ordered
  proof-index-1 byte delta, unchanged body SHA256
  62077b7f1bf4ef13ef236ca5a1e8037d318404cb6fdf6463af44d50638031c12, unchanged
  funding witnesses/Mint/script witness/raw UTxOs, target policy identity and
  two-runtime positive/negative outcomes. Review SHA256
  c422ee3c0d9102fef01c552007b4c43e95f190ba0f1cc35da59232cd4067d5f6.
  Candidate tx SHA256
  03eabae1f244f2ca220e56767ff400b5c45676aeb5cd0cbb842da8e50ef2e573;
  result SHA256 ef44ca6c2890e9fe84fdc1545e6024f5e2bc4b9465f01ad78d2819830474abac.
- git diff --check: PASS.

This is synthetic simulator evidence only. It establishes neither ledger
admission nor live-network behavior. INV-1–INV-10 and mock behavior are
unchanged. F05/M3 remain open; Pre-Prod is INCONCLUSIVE and promotion is NOT
READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
T06/history and all remaining mandatory roadmap gates remain outstanding.

Next single slice: registered r2_invalid_proof_2 negative only, with its valid
positive control and independent review.
