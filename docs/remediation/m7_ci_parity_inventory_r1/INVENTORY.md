# M7 Source/CI Gate-Parity Inventory (R1)

Status: source inventory and diagnostic; not release evidence and not a claim that hosted CI passed.

Observed date: 2026-10-02  
Repository: /home/GodOfAgents/code/VAMS-testnet  
Branch: testnet/remediation-20260907  
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

## Evidence basis

Compared .github/workflows/security-gates.yml, scripts/audit/audit_program.py, docs/audit/AUDIT_PROGRAM.md, docs/audit/control-matrix.json, scripts/audit/validate_workflow_security.py, and scripts/audit/test_workflow_security.py. Source SHA-256 values are recorded in the external assessment.

Exact local commands:

- python3 scripts/audit/validate_workflow_security.py - exit 0; all 40 GitHub Actions uses are commit-pinned.
- python3 scripts/audit/test_workflow_security.py - exit 0; 19 tests passed.

The captured Aiken 1.1.21 --help output says that check type-checks the project and runs any tests found. CI pins Aiken v1.1.21 and runs aiken check --deny --seed 20260711 --max-success 250. Help output is retained at /home/GodOfAgents/vams-evidence/m7-ci-parity-inventory-20261002-r1/aiken-1.1.21-help.txt (SHA-256 9d43f206bfbc1f6654043519660953de2537547660ada805736bf68010737e49).

## CI coverage observed

The workflow includes Forge build/tests; Slither; Aiken; Rust 1.92.0 formatting, check, clippy, tests and cargo-audit; Python pytest, Bandit and pip-audit; reviewed and discovery Semgrep scans; frontend tests, npm audit, lint, build and bundle scan; checksum-verified Envoy 1.39.1 config validation; GitLeaks and TruffleHog full-history scans; SBOM generation/signing; commit-bound audit evidence; and a manual canary/public readiness job.

The audit-program job additionally runs deployment-source validation, testnet runtime-mode preflight, architecture/invariant traceability, documentation and VDSO evidence validation, workflow-security validation, a 100,000-epoch economic adversarial simulation, agent red-team corpus validation, and the audit regression suite.

On docs-only pull requests, the Solidity, Slither, Aiken, Rust, Python, Semgrep, frontend, Envoy, and SBOM jobs are skipped; the aggregate gate has a separate docs-only required-job list. The docs-gate job itself always runs: only Verify Team Docs Diff is conditional, while Validate Documentation Reality is unconditional. Thus the aggregate requirement for DOCS_GATE is consistent for code pull requests, pushes, and manual dispatches as well.

## Findings

**Documentation parity: Caddy versus Envoy.** G1 in docs/audit/AUDIT_PROGRAM.md names Caddy validation, while the workflow validates gateway/envoy.testnet.yaml using checksum-pinned Envoy 1.39.1. Envoy is a TLS reverse proxy and the AGENTS.md deployment instructions allow Caddy or an equivalent reviewed proxy. This inventory does not prove the deployed architecture; update G1 wording to match the tested Envoy configuration or separately specify any Caddy requirement.

## Local tool availability and limits

Forge 1.7.1, Aiken 1.1.21 and 1.1.23, Envoy 1.39.1, and pinned Python 3.12.14 are present as hashed executables outside PATH. The general PATH has python3 and an npm launcher, but no node; forge, slither, aiken, pytest, Bandit, pip-audit, Semgrep, Cargo/Rust, Caddy, Envoy, GitLeaks, TruffleHog, Cosign, Syft, and jq are not discoverable there. CI obtains some tools via pinned actions and installs. No tool was installed or fetched for this inventory.

Only the two targeted workflow-validator commands above were run. No Foundry/Aiken/Rust/Python/frontend/security suite, Envoy configuration run, SBOM, signature, or hosted workflow was executed here. The raw assessment, test transcript, and tool inventory are stored outside the source tree:

- /home/GodOfAgents/vams-evidence/m7-ci-parity-inventory-20261002-r1/assessment.json - SHA-256 b44c8ba497b4cd802417d2d8441bf292b43a97cea5f6394ba49da459d6079a5c
- /home/GodOfAgents/vams-evidence/m7-ci-parity-inventory-20261002-r1/targeted-test-transcript.txt - SHA-256 499cc426d5bb5c9d5043181633c62784378b8d281b4a60067c88cabc374e8713
- /home/GodOfAgents/vams-evidence/m7-ci-parity-inventory-20261002-r1/toolchain-inventory.json - SHA-256 5d887751aa8e98ce841de66c41a46ade93d1a1bf357172f61be2585d60f59ed2
- /home/GodOfAgents/vams-evidence/m7-ci-parity-inventory-20261002-r1/aiken-1.1.21-help.txt - SHA-256 9d43f206bfbc1f6654043519660953de2537547660ada805736bf68010737e49

No CI or readiness logic changed in this inventory. No invariant behavior is implicated. Testnet readiness remains NOT READY; deployment and gated activation paths remain disabled.

## Next single slice

Reconcile the G1 documentation with the checksum-pinned Envoy configuration that CI validates, while preserving the explicit requirement for a reviewed TLS reverse proxy. Re-run documentation validation and targeted audit-program tests, then obtain independent review. Do not claim a deployed proxy choice from CI configuration alone.
