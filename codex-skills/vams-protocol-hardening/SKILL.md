---
name: vams-protocol-hardening
description: Harden VAMS protocol code, gateway surfaces, deployment scripts, CI gates, and runtime integrations for Phase 6 pre-testnet readiness. Use when implementing or reviewing security controls, authentication, mTLS, Caddy/TLS deployment, rate limiting, input validation, CI scans, role ownership, key management, mock-mode gates, or invariant-preserving fixes.
---

# VAMS Protocol Hardening

Use this skill to convert a VAMS subsystem from prototype or mock-tolerant code
into a reviewed pre-testnet candidate.

## Workflow

1. Establish source reality from code, not docs alone.
2. Identify affected layer: contracts, Cardano, Neuron, gateway, frontend, CI, or deploy.
3. Read `references/hardening-checklist.md`.
4. Map the change to invariants and mock-mode risk.
5. Prefer fail-closed controls over permissive fallbacks.
6. Add narrow tests for the control and regression path.
7. Update `docs/CHANGELOG.md` for security posture or API behavior changes.

## Required Review Questions

- Does the change remove or introduce a trusted third party?
- Does it weaken a cap, timelock, whitelist, proof boundary, or fail-closed path?
- Does it accept mock evidence in a live environment?
- Are secrets, deployer keys, or default credentials present?
- Are tests and CI gates sufficient for the affected subsystem?

## Output Shape

- **Hardening Delta:** what changed or must change.
- **Invariant Impact:** INV-1 through INV-10 touched or not touched.
- **Security Controls:** auth, validation, rate limits, keys, mocks, CI.
- **Verification Evidence:** commands and results, or pending commands.
- **Blockers:** anything preventing testnet readiness.
