# VAMS Documentation

**Architecture:** v0.8.0  
**Lifecycle:** Hardened pre-testnet candidate  
**Last verified:** 2026-07-14

VAMS documentation is organized by authority. Source code, tests, deployment
manifests, and commit-bound evidence override narrative or historical material.
No document in this repository proves a deployment until the corresponding
record in `contracts/CONTRACTS.md` contains verified network evidence.

## Start Here

- [Repository status](../REPO_STATUS_REPORT.md): current testnet posture and blockers.
- [Current architecture](ARCHITECTURE.md): as-built v0.8.0 component and trust-boundary map.
- [Versioning](VERSIONING.md): architecture, milestone, and runtime version meanings.
- [Developer guide](DEVELOPER_GUIDE.md) and [node operator guide](NODE_OPERATORS.md).
- [Gateway API reference](API_REFERENCE.md) and [gateway hardening guide](GATEWAY_HARDENING_BLUEPRINTS.md).
- [Private VDSO shadow worker runbook](runbooks/VDSO_SHADOW_WORKER.md): commitment-only input,
  three-backend conformance, durable checkpoints, and unsigned evidence export.
- [Polygon Amoy rehearsal](runbooks/POLYGON_AMOY_REHEARSAL.md) and
  [Cardano Pre-Prod rehearsal](runbooks/CARDANO_PREPROD_REHEARSAL.md):
  deterministic, approval-gated deployment ceremonies.
- [Audit program](audit/AUDIT_PROGRAM.md), [risk register](audit/RISK_REGISTER.md), and
  [evidence requirements](audit/EVIDENCE_REQUIREMENTS.md).

## Architecture History

The versioned architecture documents preserve design history. They are not
deployment evidence and must be read with their lifecycle headers:

- [v0.3.0](team/ARCHITECTURE_v0-3-0.md): historical design baseline.
- [v0.4.0](team/ARCHITECTURE_v0-4-0.md): ICN-inspired modular additions.
- [v0.5.0](team/ARCHITECTURE_v0-5-0.md): AUTOSKILL additions.
- [v0.6.0](team/ARCHITECTURE_v0-6-0.md): OMS security baseline.
- [v0.7.0](team/ARCHITECTURE_v0-7-0.md): cognitive-layer additions.
- [v0.8.0](team/ARCHITECTURE_v0-8-0.md): current CHC/composer additions.

## Research And Strategy

The whitepaper, tokenomics, market analysis, pitch, AgentOS, and Heart Brain
documents are design or strategy material. They must not be used to infer
deployed functionality, live integrations, token rewards, or financial terms.
Primary papers are cited externally rather than copied into the repository.

## Documentation Rules

- Use portable relative links; do not add local-file URIs or machine paths.
- Preserve original publication dates. Maintained documents carry a `Last verified` date.
- Use `implemented`, `mock-default`, `prototype`, `planned`, `deployed`, and
  `verified` precisely. `deployed` and `verified` require evidence.
- Run `python scripts/docs/validate_docs.py` before publishing documentation.
