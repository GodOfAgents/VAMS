# Multi-DA Performance Audit (`neuron/da/`)

This package implements the Phase 0 (Foundation) satellite DA namespace logic.

## Overview
It routes performance reports (SLA checks, node benchmarks) to public Data Availability (DA) layers based on their criticality, ensuring an immutable and independent audit trail for the VAMS Trust Score.

## Components
- `performance_audit.py`: The `PerformanceAuditLog` orchestrator. Routes reports to the appropriate adapter.
- `adapters/`: Contains the actual implementations for various DA networks.
  - `celestia_adapter.py`: Integrates with the Celestia Mocha API testnet.
  - `near_adapter.py`: Integrates with the Near DA testnet.
  - `avail_adapter.py` / `eigenda_adapter.py`: Stubs for future integration.
- `models.py`: Pydantic models for Report Data, Criticality, and DA Protocol enums.

## Relevant Contracts
- `contracts/src/da/PerformanceAnchor.sol`: Standalone on-chain registry mapping `(DAProtocol, blobId) -> reportHash` using a Sentinel ACL.
