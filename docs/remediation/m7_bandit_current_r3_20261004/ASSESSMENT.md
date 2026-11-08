# M7 current-source Bandit R3

Date: 2026-10-04
Checkout observed by coordinator: HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f, branch testnet/remediation-20260907, dirty tree preserved.

## Result

Pinned Bandit 1.9.4 scanned the current Python source under neuron/ and gateway/ using the workflow severity and confidence thresholds, -ll -ii. Scanner exit was 0 with zero findings and zero scanner errors. The stable source inventory contained 190 Python files with path/content manifest SHA-256 a84b810486e2939c19b8b7458553a0446721e52051f9431e9d8694fcee540d0d before and after the scan. The current source inventory independently recomputed after the run matches that digest.

The run used a network-disabled bubblewrap sandbox, a read-only canonical checkout, and an external evidence directory. The raw Bandit report and source snippets were not retained. The corrected external RUN record names the R3 runner and records that scan-time HEAD and workflow-file hashes were not captured. The source inventory and scanner hashes bind the static result; the provenance limitation is retained.

## Review and scope

Independent evidence verification and security review passed the exact external R3 package and its corrected invocation record. This is qualified local static-analysis evidence only. It does not establish hosted CI execution, scan-time commit/workflow provenance, runtime safety, other scanners, complete security posture, ledger admission, chain behavior, or deployment readiness. The earlier unreviewed R2 result is stale and remains a separate, unaccepted record; its finding disposition is not inferred from this scan.

No application source, tests, toolchain, credentials, vendors, Git refs, or activation state changed in this slice. INV-1 through INV-10 were not touched. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
