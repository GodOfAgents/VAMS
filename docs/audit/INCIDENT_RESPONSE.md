# VAMS Testnet Incident Response

This runbook applies to Polygon Amoy, Cardano Pre-Prod, Gateway, Neuron,
Sentinel, Composer, and enabled DA integrations. Every exercise records the
commit, deployment manifest, detection time, decision time, actions,
transactions, evidence hashes, recovery point, and retrospective owner.

## Severity

| Severity | Trigger | Immediate authority |
| --- | --- | --- |
| SEV-0 | Key compromise, unauthorized value movement, supply/invariant violation, forged bridge/DA proof, governance takeover | 2-of-3 pause-only emergency council |
| SEV-1 | Identity fail-open, widespread settlement failure, persistent memory leak/poisoning, verified provider cartel threshold | Security lead plus governance Safe |
| SEV-2 | Degraded DA/provider capacity, gateway abuse, telemetry loss without incorrect settlement | On-call SRE |

## First 15 Minutes

1. Freeze public onboarding and preserve logs without copying raw prompts,
   credentials, memory traces, or PII into the incident channel.
2. Verify the alert using two independent evidence sources. Mock receipts never
   qualify as confirmation.
3. For SEV-0, invoke pause-only controls and record every transaction hash.
4. Disable the affected route in the live capability/DA configuration. Do not
   silently fall back to a stub, weaker proof, or fail-open identity path.
5. Rotate exposed credentials and certificate fingerprints using the approved
   secret store. Never place replacement material in GitHub issues or logs.

## Containment by Domain

- **Contracts/governance:** Pause affected targets, cancel pending malicious
  timelock operations, preserve state snapshots, and prohibit upgrades until
  independent review.
- **Bridge/DA:** Stop new messages, retain proof and payload separately, verify
  source finality and receipt retrieval, and quarantine replayed identifiers.
- **Gateway/identity:** Remove compromised DID/certificate entries, restrict
  CORS origins, lower rate limits, and keep institutional routes fail closed.
- **Agents/memory:** Disable the Service Block, invoke session hard reset,
  quarantine manifests, preserve only hashes/approved forensic evidence, and
  prohibit autonomous persistent mutation.
- **Economics:** Stop rewards when concentration, regional, solvency, or
  seven-day pass-through thresholds are crossed; never modify historical data.

## Recovery Gate

Recovery requires root cause, remediated commit, regression test, independent
review, clean security evidence manifest, reconciled on-chain state, verified
Safe/timelock ownership, and a successful restore/replay drill. Governance alone
cannot waive INV-1 through INV-10 or reopen a mock-backed live route.

## Required Drills

Before public testnet, execute and retain evidence for key loss, malicious
proposal cancellation, provider cartel threshold, DA outage, identity outage,
bridge replay, memory poisoning/reset, gateway certificate revocation, backup
restore, and full protocol pause/resume. Any failed drill keeps T36 unverified.
