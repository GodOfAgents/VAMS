# M7 local frontend npm audit

## Result

The two lockfile-only audit commands exited 1 at the configured high-severity threshold. The full dependency tree reports five affected package identities, including three high-severity identities; the production-only tree reports two affected identities, including high-severity Browserslist. Exact sanitized advisories and affected lockfile nodes are in RESULT.json.

The current lock contains @humanfs/node 0.16.7, baseline-browser-mapping 2.9.18, brace-expansion 1.1.18, browserslist 4.28.1, and js-yaml 4.3.1. The existing brace-expansion and js-yaml overrides explicitly pin affected versions. Registry reports indicate fixes are available, but this record does not infer or apply package upgrades.

## Verification and scope

RUN.json binds the run to the current workflow, package manifest, lockfile, wrapper, Node/npm binaries, and sanitized report. The commands used npm audit --package-lock-only with both the complete tree and --omit=dev, retaining no node_modules and no raw report. The workflow runs npm audit after npm ci; CI parity, frontend tests, lint, build, and production-bundle scanning remain unverified by this slice.

The scan queried current npm advisory metadata. No package or tool was installed and no manifest or lockfile was changed by the scan.

## Readiness impact

The npm audit security gate fails. This is a blocker to M7 and testnet readiness. Vulnerable-dependency remediation requires its own targeted change, regression verification, and independent review. No claim of readiness follows from this audit.
