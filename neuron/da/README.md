# Multi-DA Performance Audit (`neuron/da/`)

This package contains DA report/receipt models, one Celestia API adapter with
live submission/retrieval code paths, non-live simulations, and structured
stubs. It is not a deployed or release-qualified multi-provider DA service.

## Overview
It prepares sanitized performance reports (SLA checks and node benchmarks) for
public Data Availability (DA) layers. Operational publication is not release
evidence: T30 additionally requires independently observed submission and exact
retrieval artifacts bound by the audit evidence manifest.

## Components
- `performance_audit.py`: The `PerformanceAuditLog` orchestrator. Mock receipts
  are explicitly unverified, and live publication succeeds only after exact
  retrieval.
- `adapters/`: Contains provider code paths at different implementation
  stages.
  - `celestia_adapter.py`: Celestia Mocha submission and exact-retrieval code
    paths. RPC failures fail closed and never mint fallback receipts. The
    adapter does not establish DAS or inclusion/finality and is not eligible
    as independent release evidence.
  - `near_adapter.py`: Local simulation only until signed submission and exact
    retrieval are implemented.
  - `avail_adapter.py` / `eigenda_adapter.py`: Local structured stubs only.
- `models.py`: Typed report and receipt models. Public reports allowlist scalar
  telemetry and replace caller-supplied node/sentinel identifiers with
  domain-separated SHA-256 pseudonyms.

## Relevant Contracts
- `contracts/src/da/PerformanceAnchor.sol`: Standalone on-chain registry mapping `(DAProtocol, blobId) -> reportHash` using a Sentinel ACL.
