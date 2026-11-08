# M7 current Python workflow gate — disposable overlay r4

The current offline workflow split passed with pinned Python 3.12.14, pytest 9.1.1, and Envoy 1.39.1: **1,699/1,699 main tests** and **10/10 design tests**, both exit 0. This is four more main cases than r3, matching the four new parameterized INV-5 denial cases. The source inventory contains 385 Python inputs and excludes this evidence package; its digest was stable before and after the run (`55a9b9128d5b28082abddca91c90bb76b04ba60d86503aa615d0e1dcb21569e9`). Workflow SHA-256, HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, and filtered dirty-state fingerprint were also stable during the capture.

The outer run used network-disabled bwrap, a disposable writable overlay over the canonical checkout, a dedicated evidence bind, and temporary JUnit/output files. The pre-run reviewer caught and blocked the first r4 runner revision because its Python inventory included the evidence package. That revision was not executed. The final reviewed runner skips all paths beneath its `EVIDENCE_REL`; its SHA-256 is recorded in RUN.json. A fresh pre-run review PASSed before execution.

The capture retained result counters, normalized failing-test identifiers (none), source/workflow/Git fingerprints, and hashes of transient JUnit/stdout/stderr. Raw JUnit and pytest output were deleted. RUN.json's expected outer command is wrapper-written metadata, not independent process telemetry; the reviewer must account for that limitation.

Exact outer command:

`bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --dir /tmp/vams-evidence --bind /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_pytest_tmp_overlay_r4 /tmp/vams-evidence --overlay-src /home/GodOfAgents/code/VAMS-testnet --tmp-overlay /home/GodOfAgents/code/VAMS-testnet --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B /tmp/vams-evidence/run_pytest_snapshot.py`

This is local Python test evidence only. It does not establish hosted CI, F05 ledger admission, live OMS/provider behavior, chain rehearsal, or deployment readiness. The accepted F05 ledger remains 45/55 negative cases and 18/21 mutations; F04 normative identity and F05 evidence classifications remain owner decisions. Readiness remains **NOT READY**; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
