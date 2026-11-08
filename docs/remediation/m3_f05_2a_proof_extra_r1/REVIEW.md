# F05.2a extra bootstrap proof negative — 2026-10-02

Independent review accepts exactly the registered negative r2_proof_extra.
Counts: **30/55 negatives PASS, 25 pending; 4/21 mutations PASS, 17 pending**.
Mutation counts are unchanged. This case appends a sixth 64-byte proof to the
Mint redeemer while preserving the original five proofs and order, transaction
body, funding witnesses, Mint map, applied Plutus V3 script witness and raw UTxO
vectors.

Changed canonical records: this directory's REVIEW.md and CASE-STATUS.json,
plus docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md.
Branch testnet/remediation-20260907, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f.
Policy SHA 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05,
blueprint SHA c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2,
lock SHA 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
No production source, blueprint, lock, accepted fixture or activation changed.

Exact commands/results:

- PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/build_proof_extra.py:
  exit 0. The valid five-proof positive was accepted and six-proof negative
  rejected at compiled Mint[0] on pinned Aiken 1.1.21; wrapper exits 0 and
  cleanup clean. Aiken binary SHA256
  07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Pinned Python 3.12.14 replay on Aiken 1.1.23: exit 0; same positive and
  negative outcomes, wrapper exits 0 and cleanup clean. Binary SHA256
  748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3.
- Independent integrated case review: PASS. It verified the six-file package
  manifest, canonical CBOR structure, five-to-six proof-count delta, 64-byte
  proof lengths, unchanged body SHA256
  62077b7f1bf4ef13ef236ca5a1e8037d318404cb6fdf6463af44d50638031c12, unchanged
  funding witnesses/Mint/script witness/raw vectors, exact policy binding and
  both runtime results. Review SHA256
  6f96e1d08c41d3835c1a4d10b958de008f1d70e34fe1429a8e1d5c43bbc5a9d6.
  Candidate transaction SHA256
  32dd896810177c35e1adef7f758ae674b588f394b6754167585257d216aabfae; result
  SHA256 6455e534cb9928564c3ed6e2c2afc29ba93c3d118ce5158cf16d398577918793.
- git diff --check: PASS.

This is synthetic transaction-simulator evidence only. It establishes neither
full ledger admission nor live-network behavior. INV-1–INV-10 and mock behavior
are unchanged. F05/M3 remain open; Pre-Prod is INCONCLUSIVE and promotion is NOT
READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
T06/history and other mandatory gates remain outstanding.

Next single slice: registered r2_invalid_proof_1 negative only, with its valid
positive and independent review; no mutation credit is implied.
