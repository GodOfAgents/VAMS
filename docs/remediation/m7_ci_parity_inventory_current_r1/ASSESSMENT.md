# Current M7 workflow/toolchain inventory

Date: 2026-10-04
Checkout: 829ab544571f12efe50ecb5740f129c8acb3e16f, branch testnet/remediation-20260907
Workflow SHA-256: baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c

## Result

The current security workflow pins Forge 1.7.1, Aiken 1.1.21, Python 3.12, pytest 9.1.1, Bandit 1.9.4, pip-audit 2.10.1, Slither 0.11.5, Semgrep 1.169.0, Node 22, Gitleaks 8.30.1, and TruffleHog 3.95.9. It includes Solidity build/tests, strict Aiken check, Python tests/security scans, reviewed and discovery Semgrep, frontend install/audit/lint/build/bundle scan, and full-history Gitleaks/TruffleHog.

Version-only checks confirm the pinned Forge, Aiken, Python tools, Gitleaks, and Node are present off PATH. npm 11.17.0 is a Windows launcher in the WSL PATH. Node 22.23.2 is present off PATH; the older inventory's wording that no node was discoverable refers only to PATH and should not be read as binary absence. No solc executable was found on PATH or under preserved toolchains; frontend node_modules is absent. Slither, Semgrep, and TruffleHog are unavailable locally.

No tests, builds, or scans ran in this inventory slice. Forge may try to acquire solc, pip-audit service checks require network, npm ci would fetch dependencies, and Slither/Semgrep/TruffleHog are unavailable, so none were invoked. Workflow configuration and local binary presence are not evidence of a passing hosted workflow. Exact commands, observed versions and availability, and limitations are in RUN.json.

## Next single slice

Run the already-installed pinned Bandit scan offline against neuron/ and gateway/ with the checkout read-only and a dedicated evidence directory. Capture sanitized output and exit; do not install or fetch anything.
