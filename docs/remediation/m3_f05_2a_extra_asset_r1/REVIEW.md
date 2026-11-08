# F05.2a conserved extra-asset negative and mutation — 2026-10-02

Independent integrated verdict: PASS for exactly `authority_extra_native_asset`
and `remove_no_extra_asset_guard`. Current counts: **26/55 negatives PASS,
29 pending; 2/21 mutations PASS, 19 pending**. Historical R4, prior accepted
ledgers and the frozen registry are retained without rewriting.

Branch `testnet/remediation-20260907`; HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`. Changed canonical files:
this review, CASE-STATUS.json, STATUS.md and SESSION_HANDOFF.md. No Cardano
production source, blueprint, lock, accepted original fixture, credential,
vendor, history or activation changed. Policy SHA
`5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05`,
blueprint SHA `c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2`,
lock SHA `6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f`.

Exact commands/results:

- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python build_extra_asset_fixture.py`:
  exit 0; one synthetic fixture, funded other-policy asset 1 input / 1 output,
  body-bound test Ed25519 signatures. Builder and manifest:
  `/home/GodOfAgents/vams-evidence/m3-f05-2a-extra-asset-fixture-20261002-r1/`.
- Independent byte review before execution: PASS; `.../m3-f05-2a-extra-asset-independent-byte-review-20261002-r1/BYTE-REVIEW.json`.
- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python execute_extra_negative.py`:
  exit 0; original valid plus negative on each pinned Aiken 1.1.21 and 1.1.23,
  4/4 correct; raw rows in fixture `RUN-RESULTS.json`.
- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python run_extra_asset_mutation.py`:
  exit 0; original valid accepted, original extra-asset rejected, disposable
  guard-removal mutant accepted; stale original witness and wrong-policy controls
  reject before invocation. Exact build/apply argv, stdout/stderr/exits, CBOR and
  results at `/home/GodOfAgents/vams-evidence/m3-f05-2a-extra-asset-mutation-20261002-r1/`.
- Same runtime with `extra_admission_controls.py`: exit 0; pinned runtime and
  closed triad admission PASS; constant-success, classifier-only, wrong-runtime,
  wrong-artifact, malformed field/type and cleanup controls all reject.
- `sha256sum -c SHA256SUMS` on fixture: all entries OK. Extended fixture
  `SHA256SUMS-EXEC` digest `4d67ce8cceef47e44a3f5e04be1f7b4fe5882b66229f715222041b5777dd031e`;
  mutation package `SHA256SUMS` digest
  `ec0ddeef214024b06e813774676b825b3ba9eb03d7b9b47a393602d77a78d60f`.
- `git diff --check`: exit 0 before this record.

Independent review recomputed one-line source deletion, verified 47 other .ak
files identical, compiled original/mutant script identities, two signed funding
witnesses, 17,000,000 lovelace input = 16,000,000 output + 1,000,000 fee,
one extra asset in/out, and replayed all five triad/routing rows on pinned
Aiken 1.1.21 plus the original pair on 1.1.23. It tested 11 false-positive
admission mutations. Review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-extra-asset-independent-integrated-review-20261002-r1/INTEGRATED-REVIEW.json` (SHA256 `2170eab6fb78e6c94adeec5e40ba00bb1a3985d36c80f579085658efc4eb276d`).

This is synthetic simulator evidence only. No script-data-hash, collateral,
ledger admission, current Pre-Prod parameter/minimum-ADA or live-network
evidence is inferred. Canonical `cardano/plutus.json` lacks F05 handlers;
release provenance requires its own reviewed slice.

INV-1–INV-10 and mock behavior unchanged. F05/M3 remain open; Pre-Prod
INCONCLUSIVE; promotion NOT READY. Deployment, Deposit, Slash activation and
ExecuteIntent remain disabled. T06/history and every other mandatory gate
remain required.

Next single slice: `output_stake_credential` negative and its paired
`remove_no_stake_credential_guard` compiled mutation, with exact signed fixture,
original/mutant program identity, false-positive controls and independent review.
