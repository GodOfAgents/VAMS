# M7 current-tree Gitleaks r5 — failed gate, capture-time snapshot

Pinned Gitleaks 8.30.1 ran network-isolated on the corrected checkout. Capture stability passed: 5,197 tracked and unignored untracked inputs were fingerprinted before and after; source, Git, workflow, config, baseline, scanner, and helper fingerprints remained stable. The snapshot is bound to source-manifest SHA-256 dd9689d36655161dd3611f388cd82d7a9bf13f5019002a3f1ea66de5e37e9e69, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f, branch testnet/remediation-20260907, and dirty-state SHA-256 4aa4ea36de790896e645467d1b1b6ed27bb14d40ec1f208170536f42311748c5.

The report contained 864 entries: **385 first-party generic-api-key findings across 31 files**, 479 vendor-labelled matches, and 0 unknown-ownership findings. The scanner exited 1, matching the nonempty report. Baseline reconciliation failed with first-party finding detected. The 479 vendor-labelled count is not an accepted reconciliation. M0.4 remains **FAIL**.

## Scope and limitations

The scan covers only tracked and unignored untracked working-tree files from the superproject and recursively pinned submodules. It excludes ignored files, Git history, and remote refs; it does not satisfy T06. The scan result binds to the exact fingerprints above and predates importing this r5 package and appending its STATUS/HANDOFF record. It is valid for that capture-time snapshot and must not be presented as a scan of the later evidence-imported checkout.

All match values were redacted by the scanner. Raw report and scanner streams were deleted after hashing and metadata sanitization. The sanitized file contains only path, rule identifier, line range, and source-file SHA-256 per finding. No findings are closed or adjudicated by this scan. No allowlist, credential, vendor, source-code, or Git-history change was made. F04/F05 owner decisions and ledger gaps remain; accepted F05 evidence remains 45/55 negative cases and 18/21 mutations. Readiness is **NOT READY**; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Exact command and review

bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --bind /home/GodOfAgents/vams-evidence/m7_gitleaks_current_r5_20261004 /home/GodOfAgents/vams-evidence/m7_gitleaks_current_r5_20261004 --chdir /home/GodOfAgents/code/VAMS-testnet --clearenv --setenv PATH /usr/bin:/bin /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B /home/GodOfAgents/vams-evidence/m7_gitleaks_current_r5_20261004/diagnose.py

The wrapper was independently reviewed before execution; review PASS. Independent post-run review PASS; see REVIEW.md. Python runtime: 3.12.14; Gitleaks binary SHA-256 88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509; wrapper SHA-256 316dc8d04e5a05ba6851f0c1c89a34eaaf689de815926a128ac04fdb74a54c47; sanitized result SHA-256 634f4afe6a42b5cb23711b7980a2caade5a5b05ca4a9c6893bbf3d396b6b6736. The wrapper-written expected outer command is metadata, not independent process telemetry.
