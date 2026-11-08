# F05.2a stake-credential negative and mutation — 2026-10-02

Independent integrated review accepts exactly `output_stake_credential` and
`remove_no_stake_credential_guard`. Current counts: **27/55 negatives PASS,
28 pending; 3/21 mutations PASS, 18 pending**. The mutation is a disposable
source copy with exactly the stake-credential guard removed; canonical source,
blueprint, lock, original transaction and all pre-existing dirty work remain
preserved.

Changed canonical records: this directory's `REVIEW.md` and
`CASE-STATUS.json`, plus `docs/remediation/STATUS.md` and
`docs/remediation/SESSION_HANDOFF.md`. Branch `testnet/remediation-20260907`,
HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`. Production policy SHA
`5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05`,
blueprint SHA `c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2`,
lock SHA `6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f`.

Exact verification and results:

- Independent pre-execution fixture review: PASS. The synthetic authority output
  changes only its address from the enterprise script address to the same
  payment script credential plus a script stake credential. Two test-only
  funding signatures bind the transaction body; inputs 17,000,000 lovelace =
  outputs 16,000,000 + 1,000,000 fee. Evidence:
  `/home/GodOfAgents/vams-evidence/m3-f05-2a-stake-independent-byte-review-20261002-r1/BYTE-REVIEW.json`.
- `run_stake_mutation.py` under pinned Python 3.12.14: exit 0. Original valid,
  original stake-negative and rebound mutant stake-positive triad passed on
  pinned Aiken 1.1.21 with stale-witness and wrong-policy routing controls; the
  original valid/negative pair also passed on pinned Aiken 1.1.23 (4/4).
- Independent compiled replay: PASS. It verified the sole source deletion,
  applied parameters, compiled witness identity, signatures and value topology.
  Aiken 1.1.21 SHA256
  `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`; Aiken
  1.1.23 SHA256
  `748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3`.
  Evidence: `/home/GodOfAgents/vams-evidence/m3-f05-2a-stake-independent-compiled-review-20261002-r1/REVIEW.json`.
- `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-stake-credential-mutation-20261002-r1/stake_admission_controls.py`:
  exit 0. Exact triad admitted; fake runtime, constant-success invalid leg,
  classifier-only rows, wrong submitted hash, extra field, boolean exit,
  false cleanup, integer invocation and false pass were all rejected. Pinned
  Aiken SHA before/after remained the expected value. Output:
  `ADMISSION-CONTROLS.json`, SHA256
  `d32c9e8a53e5ed77d8b8ea8a5f9d4474c9fab8e892b87f407184b3c9b7f0d368`.
- Independent admission review: PASS, SHA256
  `7e9e5550a3d2dbb7a0fde75df3ded3b4cd28b5bb878fe0b599d3bdf0424edbaf`.
  It verified the frozen candidate manifest and independently assessed the exact
  integrated triad, controls, byte review and compiled review.
- `git diff --check`: PASS.

This is synthetic transaction-simulator evidence only. It does not establish
ledger admission, collateral/script-data-hash validity, current Pre-Prod
parameters/minimum ADA, or live-network behavior. `cardano/plutus.json` lacks
F05 validator provenance; that needs its own reviewed slice. INV-1–INV-10 and
mock behavior are unchanged. F05/M3 remain open; Pre-Prod is INCONCLUSIVE and
promotion is NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent
remain disabled. T06/history and all other mandatory gates remain outstanding.

Next single slice: execute and independently review the registered
`r2_proof_missing` negative only. Its case-level mutation is `redeem_with_four_proofs`;
it is not the compiled mutation pair. The compiled
`remove_bootstrap_proof_of_possession_verification` mutation is paired by the
frozen contract with `r2_invalid_proof_0` and remains a later, separate slice.
