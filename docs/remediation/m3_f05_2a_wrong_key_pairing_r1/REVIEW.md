# F05.2a wrong bootstrap proof/key pairing — 2026-10-02

Independent review accepts exactly the negative r2_wrong_key_pairing. Counts:
**35/55 negatives PASS, 20 pending; 4/21 mutations PASS, 17 pending**.
Mutation counts are unchanged. The candidate reverses the original five
64-byte signatures without changing their contents, ordered keys, transaction
body, funding witnesses, Mint map, script witness or raw UTxO vectors.

Changed canonical records: this directory's REVIEW.md and CASE-STATUS.json,
plus docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md.
Branch testnet/remediation-20260907, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f.
Policy SHA 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05,
blueprint SHA c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2,
lock SHA 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
No production source, blueprint, lock, accepted fixture or activation changed.

Exact commands/results:

- PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/build_wrong_key_pairing.py:
  exit 0. The valid proof ordering passed; reversed proofs rejected at compiled
  Mint[0] on pinned Aiken 1.1.21; wrapper exit 0 and cleanup clean. Runtime SHA
  07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Pinned Python 3.12.14 replay on Aiken 1.1.23: exit 0; same positive and
  negative outcomes, wrapper exit 0 and cleanup clean. Runtime SHA
  748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3.
- Independent case review: PASS. It verified the package manifest, exact
  reversed proof ordering, preserved signature bytes and lengths, unchanged body
  SHA256 62077b7f1bf4ef13ef236ca5a1e8037d318404cb6fdf6463af44d50638031c12,
  unchanged funding/Mint/script/raw vectors, target policy and two-runtime
  outcomes. Review SHA256
  022be5da45ad64fc076a464c3ed8d0eb19bf3e59026f9f63f4aad51524b0582f.
- git diff --check: PASS.

This is synthetic simulator evidence only, not ledger admission or live-network
behavior. INV-1–INV-10 and mock behavior are unchanged. F05/M3 remain open;
Pre-Prod is INCONCLUSIVE and promotion is NOT READY. Deployment, Deposit, Slash
activation and ExecuteIntent remain disabled. T06/history and all other
mandatory roadmap gates remain outstanding.

Next single slice: registered seed_duplicate negative only; it is not the
paired input for remove_seed_guard, which remains paired with seed_missing.
