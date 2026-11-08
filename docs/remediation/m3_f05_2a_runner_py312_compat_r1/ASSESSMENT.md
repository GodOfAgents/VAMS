# F05 simulator-runner Python compatibility rerun - 2026-10-03

Status: accepted after independent read-only review. Both currently available runtimes pass the focused runner unit suite.

## Scope

No source or test files changed in this verification slice. Current runner SHA-256 is `3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c`; current test SHA-256 is `511c8ac4ae9fc03a5cc167287838ed99e7296652fdc9397fe6819d8e5cf566e8`. The runner includes the sealed-file handling for `F_SEAL_WRITE`. No INV-1 through INV-10 enforcement or mock-mode behavior changed.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python scripts/remediation/test_f05_2a_tx_sim_runner_r3.py` — Python 3.12.14; exit 0; 16/16 tests passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/remediation/test_f05_2a_tx_sim_runner_r3.py` — Python 3.14.4; exit 0; 16/16 tests passed.

Exact command, runtime, exit code, stdout/stderr hashes and captured transcripts are in `RUN.json` and adjacent files. The test module is byte-identical to the frozen 2026-10-01 handoff copy and invokes a fake Aiken executable for these boundary tests. This establishes Python runtime compatibility and runner behavior only; it does not execute real Aiken or a transaction simulator. It grants no registered F05 negative-case or mutation credit, ledger admission, or live-network evidence.

The prior `docs/remediation/m3_f05_2a_identity_r1/REVIEW.md` records an earlier Python 3.12 failure for the sealed-snapshot tests. The current exact runner/test files now pass under Python 3.12.14; this rerun supersedes that failure only for these files and does not close other F05 gates.

## Independent review

`/root/f05_py312_review`: PASS for the exact current runner/test hashes and captured results. The reviewer confirmed Python 3.12.14 and 3.14.4 both exit 0 with 16 tests, and compared current code with the frozen historical runner. The compatibility fix supplies Linux UAPI sealing constants only when Python lacks them, still requires `F_ADD_SEALS`, reads back `F_GET_SEALS`, verifies content, and maps sealing errors to `SnapshotError`. The historical Python 3.12 blocker is superseded for these exact current runner/test files. Reviewer did not rerun tests or edit files.

## Remaining blockers and next slice

F05 remains 45/55 negative cases and 18/21 mutations. Ten negative cases and three mutations remain pending. The six applied-parameter variants require the A/B/C evidence-contract decision in `docs/remediation/m3_f05_2a_applied_genesis_parameter_design_r1/DECISION-REQUIRED.md`; four proof-domain negatives remain pending, including `r2_signature_for_other_seed` whose exact frozen-contract route still requires controlled signing or a separately amended evidence contract. This runner suite changes none of those facts.

Next single slice: apply the owner's selected A/B/C evidence treatment to the six applied-parameter cases, then run only its required bounded verification and obtain independent integrated review. Readiness remains NOT READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
