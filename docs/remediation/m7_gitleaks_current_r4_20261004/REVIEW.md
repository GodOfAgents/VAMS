# Independent post-run review — current-tree Gitleaks r4

Outcome: **PASS for capture integrity and the reported failed gate**. The reviewer verified the external wrapper SHA-256 `8bd2dc9cf930f1ff7db31cd5e19b8ce5dd64fc37a8779083525c4da02144e934`, result SHA-256 `55b8e2b55a26bfcae26effbfcaaf185decf734e1e8503f45dcfd14d7d1b4048f`, and RUN SHA-256 `5c1f5846a9372bedfdb6ef2999f3dc95d45c198c0299400c638d9bc0a810e2fd`. RUN result/script hashes match.

The sanitized counts are 864 total = 385 first-party + 479 vendor-labelled + 0 unknown. Scanner exit 1 matches the nonempty report. Git/source/workflow/config/baseline/scanner/helper fingerprints are stable. The corrected wrapper passes actual counts to `gate.reconcile`; vendor reconciliation reports false with `first-party finding detected`, and `m0_4_gate_pass` is false. The 479 vendor count is not presented as reconciliation. Scanner is pinned at 8.30.1 and used `--redact=100`; only sanitized paths/rules/line bounds/file hashes and counts remain. The raw report and streams are absent.

Limits: current unignored working-tree scope only; ignored files, Git history, remote refs, live credential safety, revocation, hosted CI, and deployment readiness are not established. The outer command is wrapper-written metadata, not independent process telemetry. Reviewer did not rerun the scan.
