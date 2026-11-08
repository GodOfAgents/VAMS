# Current-source Python workflow test gate

Date: 2026-10-04

## Result

The source-bound offline run used Python 3.12.14, pytest 9.1.1, and the already-present Envoy 1.39.1 binary whose SHA-256 matches the workflow pin. The capture mirrors the workflow's split: collect the root suite excluding docs/remediation/m3_f05_design_r2/test_design.py, run that root suite, then run the design test separately. It sets VAMS_ENV=test and VAMS_ENVOY_BIN to the verified local binary. Pytest cache writes were disabled for the read-only checkout.

Collection exited 0 with 1,693 tests collected. The root suite exited 1 with 1,683 passed, 10 failed, and 444 subtests passed. The separate design suite exited 1 with 9 passed and 1 failed. The source inventory contained 381 Python inputs and its digest was unchanged; workflow SHA-256, Git HEAD, and filtered dirty-state digest were also unchanged. Independent review PASSed capture integrity and confirmed Python gate status FAIL.

## Commands

Outer invocation:
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --bind /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_pytest_current_r1 /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_pytest_current_r1 --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B docs/remediation/m7_pytest_current_r1/run_pytest_snapshot.py

The wrapper ran the CI root command with `-p no:cacheprovider --ignore=docs/remediation/m3_f05_design_r2/test_design.py`, then the separate design test with `-p no:cacheprovider docs/remediation/m3_f05_design_r2/test_design.py`. Both used `-v --tb=short`, `VAMS_ENV=test`, and the recorded `VAMS_ENVOY_BIN`.

## Limits and next action

Only sanitized counts, output hashes, source/tool identities, and state digests are retained. Raw pytest output was not retained, so failing test identities and tracebacks are not yet established. This is a failing local test result, not hosted CI evidence and not ledger, testnet, or deployment evidence. It grants no F05 case or mutation credit. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: identify the exact failing test identities and classify the failures using a new offline diagnostic capture, without changing production source.
