# F05.2a authority-datum negative family — 2026-10-02

Independent integrated review PASS for exactly 12 newly executed registered
datum-semantic negatives: datum_seed_hash, datum_seed_index, datum_epoch, datum_key_count, datum_key_length, datum_duplicate_key, datum_key_order, datum_key_binding, datum_threshold, datum_status, datum_pending_kind, datum_pending_noncanonical. Current counts are 25/55 negative
PASS, 30 pending, 0 failed; mutation count remains 1/21 PASS, 20 pending.
The historical R4 ledger and registry are preserved.

Changed canonical files: this REVIEW, CASE-STATUS, STATUS.md and
SESSION_HANDOFF.md only. No production Cardano source, accepted original fixture,
blueprint, lock, credentials, vendors, history or activation changed.
Branch `testnet/remediation-20260907`, HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`.

Exact commands/results:

- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python build_datum_semantics_family.py`:
  exit 0; 12 candidate single-datum-field fixtures generated, each with two
  verified synthetic funding signatures. Builder preserved at `/home/GodOfAgents/vams-evidence/m3-f05-2a-datum-semantics-20261002-r1`.
- Independent byte review before compiled submission: PASS 12/12, evidence
  `/home/GodOfAgents/vams-evidence/m3-f05-2a-datum-independent-review-20261002-r1/FIXTURE-REVIEW.json`.
- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python execute_datum_family.py`:
  exit 0; 26/26 rows, valid positive plus 12 negatives on each pinned Aiken
  1.1.21 and 1.1.23. Raw row results at `/home/GodOfAgents/vams-evidence/m3-f05-2a-datum-semantics-20261002-r1/RUN-RESULTS.json`.
- Independent replay and integrated review: 26/26 expected, exact single
  field deltas, 24 funding signatures, ordered raw-input linkage, Ada
  conservation and original policy identity PASS. Evidence `/home/GodOfAgents/vams-evidence/m3-f05-2a-datum-integrated-independent-review-20261002-r1/INTEGRATED-REVIEW.json`.
- `sha256sum -c SHA256SUMS` on frozen fixture candidate: all listed entries OK.
  Extended evidence manifest `/home/GodOfAgents/vams-evidence/m3-f05-2a-datum-semantics-20261002-r1/SHA256SUMS-EXEC` digest `a4c25e3f4adac8dd344154fdc1d93650554adb5ca9e4f86d02619b2ece5564ff`.
- `git diff --check`: exit 0 before status update.

The pinned compiled policy ID is
`9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`;
each negative reaches its intended original Mint[0], rejects at compiled
evaluation, and has clean wrapper/child separation. This is synthetic simulator
evidence. It does not establish ledger admission, script-data-hash/collateral,
Pre-Prod parameters/minimum ADA or live-network execution. Canonical
`cardano/plutus.json` still has no F05 handler; a separate reviewed release
provenance slice will be required.

INV-1–INV-10 and mock behavior unchanged. F05/M3 remain open, Pre-Prod
INCONCLUSIVE, promotion NOT READY. Deployment, Deposit, Slash activation and
ExecuteIntent remain disabled. T06/history and all other mandatory gates remain.

Next single slice: the frozen `remove_no_extra_asset_guard` / `authority_extra_native_asset`
compiled mutation triad, including conserved extra native asset from a
funding input, exact original and mutant program identities, a signed
rebound transaction, false-positive controls and independent review.
