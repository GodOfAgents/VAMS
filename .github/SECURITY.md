# Security Policy

**Lifecycle:** Pre-testnet coordinated disclosure policy
**Last verified:** 2026-07-12

VAMS is not deployed to mainnet or public testnet. Do not test against any
third-party infrastructure, attempt to obtain funds, or perform availability
attacks.

## Reporting

Report vulnerabilities privately to `security@vams.io` with a clear impact
description, affected revision, reproduction steps, and proof of concept that
does not expose data or move value. Do not publish details before the team has
had a reasonable opportunity to investigate and coordinate a fix.

## Scope

In scope are first-party source under `contracts/src/`, `cardano/validators/`,
`neuron/`, `gateway/`, and `frontend-vite/src/`, plus deployment and CI
configuration. Third-party dependencies should be reported to their maintainers.

No public bug-bounty reward schedule, production SLA, deployed-address scope,
or completed external audit is currently represented by repository evidence.
Future bounty terms and deployment scope will be published only with verified
funding, legal terms, and deployment manifests.

## Handling

Critical reports are prioritized for immediate triage. Remediation, disclosure,
and acknowledgement timing depends on reproducibility, affected boundaries,
and whether a live deployment exists. The incident process is documented in
[`docs/audit/INCIDENT_RESPONSE.md`](../docs/audit/INCIDENT_RESPONSE.md).
