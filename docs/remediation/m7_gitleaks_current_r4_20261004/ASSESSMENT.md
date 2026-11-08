# Current-tree Gitleaks result — r4

The pinned Gitleaks 8.30.1 scanner ran on the current unignored source tree under network-disabled bwrap with the checkout read-only and only an external evidence directory writable. The capture included 5,189 tracked and unignored untracked files across the superproject and recursively pinned submodules. The scan found 864 redacted report entries: 385 first-party `generic-api-key` matches across 31 files, 479 vendor-identity matches, and zero unknown-ownership matches. The scanner exited 1 as expected for the nonempty report. Source, Git, workflow, config, baseline, scanner, and helper fingerprints remained stable.

The pinned vendor-baseline reconciliation did not pass: it correctly stopped at the 385 first-party findings. The 479 vendor count is a classification count and is **not** accepted baseline reconciliation. The overall M0.4 Gitleaks gate is **FAIL**. No matched values or source lines were retained or disclosed. The sanitized report records only paths, rule IDs, line bounds, file hashes, and aggregate counts. The raw report and scanner streams were deleted/not retained.

An earlier r3 capture was not accepted because its wrapper passed hardcoded zero first-party counts to the reconciliation helper. R4 passes the observed counts and accurately records reconciliation failure. The independent reviewer inspected only sanitized artifacts and confirmed the corrected fail-closed result.

Exact reviewed outer command:

`bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --bind /home/GodOfAgents/vams-evidence/m7_gitleaks_current_r4_20261004 /home/GodOfAgents/vams-evidence/m7_gitleaks_current_r4_20261004 --chdir /home/GodOfAgents/code/VAMS-testnet --clearenv --setenv PATH /usr/bin:/bin /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B /home/GodOfAgents/vams-evidence/m7_gitleaks_current_r4_20261004/diagnose.py`

The scan covers current tracked and unignored untracked source files. It excludes ignored files, Git history, and remote refs, so it is separate from T06/history evidence and does not establish credential/provider revocation, incident closure, hosted CI, ledger admission, or deployment readiness. No allowlist, credential, vendor, source, or history change was made. Readiness remains **NOT READY**; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
