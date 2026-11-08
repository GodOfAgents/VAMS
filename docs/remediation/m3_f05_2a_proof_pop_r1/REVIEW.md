# F05.2a invalid proof and proof-verification mutation — 2026-10-02

Independent integrated review accepts exactly r2_invalid_proof_0 and
remove_bootstrap_proof_of_possession_verification. Counts: **29/55 negatives
PASS, 26 pending; 4/21 mutations PASS, 17 pending**. The original policy
rejects the one-bit-corrupted first bootstrap proof; the disposable mutant,
created by replacing only the registered proof-verification call with True,
accepts it. The valid original control accepts, and stale original witness and
wrong expected policy fail closed before target invocation.

Changed canonical records: this directory's REVIEW.md and CASE-STATUS.json,
plus docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md.
Branch testnet/remediation-20260907, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f.
Canonical policy SHA 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05,
blueprint SHA c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2,
lock SHA 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
No canonical Cardano production source, blueprint, lock, accepted fixture,
credentials, vendors, history, or activation paths changed.

Exact commands/results:

- PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/run_pop_mutation.py:
  exit 0. It produced a disposable mutation triad with original valid accepted,
  original invalid-proof negative rejected at compiled Mint[0], and mutant
  rebound invalid-proof accepted. Stale original witness and wrong expected
  policy both rejected before invocation. The runner asserted clean completion
  for each row. Mutant code SHA256
  871321b655c34ed74a4cfcd9617bd978f97ae6d3029660e96db25b3c784416aa; mutant
  policy ID 8ac237f73f9c42ca62c701c6b775d6dfa5fbce5ffa92f3562f4fc5e8.
- Pinned Aiken 1.1.23 original valid/invalid replay: exit 0, positive accepted,
  invalid proof rejected at compiled evaluation, wrapper exits 0, cleanup clean.
  Binary SHA256 748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3.
  Its original binary 1.1.21 SHA256 was
  07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /mnt/c/Users/aseem/VAMS-mono/verify_pop_admission.py:
  exit 0. Exact triad admitted; wrong runtime, classifier-only rows, wrong
  transaction hash, extra row field, boolean child exit, failed cleanup,
  wrong mutant binding and constant-success invalid leg were all rejected.
  Pinned Aiken SHA remained unchanged.
- Independent integrated review: PASS_WITH_PACKAGING_LIMITATION, SHA256
  e6edf9030effd6d53a2065a9a0d6ce728fca860fc2e10ac69c9f20c20d9b72a6.
  Reviewer independently compiled the exact mutation from the canonical
  original source and reproduced the code hash and mutant policy ID, replayed
  the triad/routing controls, checked two synthetic funding signatures against
  the updated body hash, and executed all nine admission controls. Review:
  /home/GodOfAgents/vams-evidence/m3-f05-2a-proof-pop-independent-integrated-review-20261002-r1/INDEPENDENT-REVIEW.json.
- The candidate package directory named source-snapshot already contained the
  mutated policy file. The reviewer recorded this packaging limitation and
  resolved acceptance by verifying the canonical source hash and independently
  rebuilding from that canonical source. No claim relies on source-snapshot as
  pristine.
- git diff --check: PASS.

This remains synthetic transaction-simulator evidence. It establishes neither
ledger admission nor live-network behavior. INV-1–INV-10 and mock behavior are
unchanged. F05/M3 remain open; Pre-Prod is INCONCLUSIVE and promotion is NOT
READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
T06/history and all other mandatory roadmap gates remain outstanding.

Next single slice: registered r2_proof_extra negative only, with a valid
positive control and independent review; do not infer mutation acceptance from
that case.
