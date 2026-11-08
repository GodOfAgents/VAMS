# M7 Default Credential Scan job — 2026-10-04

## Result

Both local workflow scanners passed against the current disposable source snapshot using pinned Python 3.12.14 under bwrap network isolation. The default credential scan and secret-history prevention scan each exited 0 with no findings. Their pass-only stdout was 32 bytes and 39 bytes respectively; raw output remains in the private evidence directory. Independent review verified the pass paths, hashes, source/status invariants, and namespaces.

The exact underlying commands were:
- python scripts/security/default_credential_scan.py
- python scripts/security/secret_history_prevention_scan.py

The explicit environment passed to both included PYTHONDONTWRITEBYTECODE=1, PYTHON_BIN=/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python, PATH=/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin, RUN_EVIDENCE_DIR=/home/GodOfAgents/vams-evidence/m7-default-credential-scan-r1-20261004, TMPDIR=/tmp/vams-default-scan.

Evidence window: 2026-10-04T18:21:18Z–2026-10-04T18:25:53Z. Pinned interpreter SHA-256 aa01d96348989f33ed998b42c83e98593b41dba83914d9899730b90c36f2e5c9; workflow SHA-256 baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c; default credential script SHA-256 d88933bad9f5ebef5a168b82ab3681509e2be4558fc21c15325c9aa62ccc07c8; secret-history script SHA-256 c83c2aacb7da23911a8d4575dd4a0c8b1860d722880864ad6a0b7e4cb3bf51cf; bwrap SHA-256 0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0.

Canonical source inventory digest before and after: 6aabfcecb467848a0e693d59eef074820076697459fcbb3315a7ddaa1ac76d78. Canonical status digest before and after: f47b9f971a82c3cdfa35a21fc169d4a271a5fe724b01a6257a69bce5405b73d0. Snapshot inventory contains 6,871 rows and matches its post-run digest. Host network namespace was 4026531833; default-scan and history-scan child namespaces were 4026532231 and 4026532293.

## Capture limitation

The recorded wrapper text substitutes [capture-netns] for its namespace-capture prelude, so the full bwrap shell wrapper is not byte-for-byte replayable from the raw command text alone. The exact underlying Python argv and explicit environment above were reconstructed from the execution call transcript. The ambient inherited environment was not enumerated. Namespace and isolation records independently support the network-isolation result. Independent review accepted the scan outcomes with this qualification; see REVIEW.md.

An earlier wrapper attempt exited 127 before either script ran because PATH pointed one directory too high. It is excluded from scan results and retained in the raw evidence record. The corrected invocations ran each scan once.

These local scans do not establish hosted workflow execution, external secret-vendor history, credential rotation, or chain/deployment readiness. They did not change source, dependencies, credentials, toolchain, Git refs, or gated activation state. F04 authority/registration, F05 ledger evidence (45/55 negatives; 18/21 mutations), T06/history adjudication, Gitleaks/M0.4 disposition, other required security/dependency/invariant/reproducibility checks, and both chain prerequisites remain open. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
