# M7 targeted frontend dependency remediation

## Change

Added exact npm overrides for the five vulnerable transitive packages and updated the lockfile to the upstream patched minimums: @humanfs/node 0.16.8, baseline-browser-mapping 2.11.0, brace-expansion 1.1.21, browserslist 4.28.7, and js-yaml 4.3.2. The lockfile also updates only the required @humanfs and Browserslist dependency chain entries. Existing frontend test and bundle-scan scripts are preserved. The changelog records the security posture change.

These versions match the patched ranges in the upstream GitHub advisories linked in the pre-remediation RESULT.json. No package archives were installed and frontend/node_modules remains absent.

## Verification

RUN.json records exact commands, exit codes, and final hashes. The frontend telemetry/security test command passes 4/4 tests. Both lockfile-only npm audits pass with zero vulnerabilities across 257 resolved entries, including the production-only audit. The targeted lockfile update command exited 0.

The workflow's npm ci, lint, production build, and bundle scan were not run because dependency installation is explicitly out of scope. Those checks remain pending; this local evidence does not establish workflow/CI parity or close M7.

## Readiness impact

The local npm audit blocker is cleared for the captured lockfile. Independent integrated review PASS; see REVIEW.md. Other M7 security/evidence requirements, the unresolved F04 choice, F05 gates, full invariants, governance, both chain prerequisites, T06/history, and deployment readiness remain open. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
