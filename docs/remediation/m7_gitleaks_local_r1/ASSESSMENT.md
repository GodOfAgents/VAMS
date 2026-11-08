# M7 local GitLeaks gate evidence

## Result

The allowlist regression passed. The complete local Git-history scan passed for refs available in this checkout: 76 commits and approximately 25,035,910 bytes scanned, with an empty, fully redacted JSON report. Network access was disabled.

The current-tree vendor-baseline gate failed with `first-party finding detected`. A second network-isolated diagnostic used the gate's source staging, baseline, vendor-pin and sanitized-classification helpers. It reported 567 total findings: 479 vendor identities, zero unknown-ownership findings, and 88 first-party `generic-api-key` findings across 13 files. The raw report was fully redacted and deleted; only paths, rule IDs, line ranges, file hashes and aggregate counts were retained in `CURRENT-TREE-SANITIZED.json`. The main gate does not emit `CURRENT-TREE.json` on this failure path. This slice is not accepted.

## Finding scope

The 13 first-party paths are:

- `docs/remediation/m3_f04_design_r1/ASSET_VECTORS.json`
- `docs/remediation/m3_f04_fixtures_r1/FIXTURES.json`
- `docs/remediation/m3_f04_fixtures_r1/fixture_contract.py`
- `docs/remediation/m3_f05_design_r2/VECTORS.json`
- `docs/remediation/m7_aiken_g1_current_test_r1/INPUTS.json`
- `docs/remediation/m7_f05_warning_identity_r1/g1-final/INPUTS.json`
- `docs/remediation/m7_f05_warning_identity_r1/g1/INPUTS.json`
- `docs/remediation/m7_governance_policies_warnings_r1/g1-final/INPUTS.json`
- `docs/remediation/m7_governance_warnings_r1/g1-final/INPUTS.json`
- `docs/remediation/m7_governor_warnings_r1/g1-final/INPUTS.json`
- `docs/remediation/m7_insurance_warnings_r1/g1-final/INPUTS.json`
- `docs/remediation/m7_timelock_warnings_r1/g1-final/INPUTS.json`
- `scripts/remediation/f05_2a_tx_sim_evidence_contract.py`

Existing records describe the R4 vectors as synthetic test vectors and the G1 `INPUTS.json` files as source-provenance manifests; structural inspection found 292 64-hex leaves in each manifest. This supports a false-positive hypothesis for those records, but does not adjudicate every match. No raw match values or source snippets were inspected or retained.

## Scope and limits

No source, vendor, credential, test-vector, or Git-history content was remediated. This evidence does not establish coverage of remote/unavailable refs, incident closure, ledger admission, or live-network behavior. It does not authorize credential changes, secret rotation, history rewriting, fetches, transactions, or deployment. Read [RUN.json](RUN.json) and [CURRENT-TREE-SANITIZED.json](CURRENT-TREE-SANITIZED.json) for the pinned commands and sanitized identities; [history-report.json](history-report.json) is the empty redacted history report.

## Gate disposition

Not accepted: the current-tree gate fails. The next decision is how to adjudicate these test/provenance matches while preserving frozen evidence and keeping the scanner fail-closed. Do not claim M7 security completion or testnet readiness.
