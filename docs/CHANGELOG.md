# Changelog

All notable changes to the VAMS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0-audit-remediated] - 2026-04-26

### Security & Audit (Sprints 0-5)
- **Comprehensive Audit Remediation:** Successfully resolved all 68 security findings identified during the Pre-Testnet Security Audit (Phases 1-8).
- **Critical Fixes:** Resolved ECDSA signature recovery in `BatchSettlement`, fixed insurance fund drain vulnerability in `TransactionCompensation`, decoupled bridge proofs, and enforced on-chain stake verification in `governor.ak`.
- **Economic Invariants:** Enforced lock periods for `VAMSStaking` emergency withdrawals, bounded rewards with strict token deposits, and implemented strict dispute solvency rules in `X402EscrowManager`.
- **Infrastructure Security:** Implemented `_disableInitializers()` across all 16 target contracts, integrated proper role grants for 14 roles via `DeployV2.s.sol`, and securely wired all pausable sentinel targets.
- **Off-chain Hardening:** Corrected MEV protection configurations, replaced predictable PRNGs in Sentinels with cryptographically secure generation, and improved secondary transport fallback mechanism in `BridgeExecutor`.

## [1.0.0-icn] - 2026-04-09

### Added
- **Multi-DA Performance Anchor:** Implemented `da/PerformanceAnchor` to natively anchor SLAs to Celestia, Polygon DA, and EigenDA, providing hardware transparency.
- **Resource Composition Engine:** Created `composer/VAMSComposer` to automatically package compute requests into matching Blueprint profiles against available nodes.
- **Master Hybrid Escrow Model:** Deployed `ComposedSettlement.sol` replacing point-to-point escrows with atomic multi-party payments for orchestrated nodes.
- **Regional Dynamic Emissions:** Launched `RegionAwareDEC.sol` and `RegionalIncentives.sol` to align inflation rewards with geographic under-served capacity, reducing datacenter centralization.
- **Service Block Registry:** Created `registry/ServiceBlockRegistry.sol` enabling builders to package verified code execution environments and earn up to 50% revenue share.
- **Sentinel Enforcer Loop:** Added `sentinel/SLAEnforcer` module executing probabilistic slashing queries based on verifiable downtime logs.
- Added extensive Documentation: `docs/API_REFERENCE.md`, `docs/DEVELOPER_GUIDE.md`, `docs/team/ARCHITECTURE_v0-4-0.md`.

### Changed
- Converted monolithic `neuron/` Python backend into independent modular logic layers: `da/`, `composer/`, `economics/`, `services/`, `sentinel/`.
- Updated `gateway/server.py` to route modular endpoints across `/da`, `/composer`, `/economics`, `/services`, `/sentinel`.
- Unified the smart contract structure under `contracts/src/` with clear stratifications: `da/`, `economic/`, `infrastructure/`, `sentinel/`.
- Relicensed the codebase to emphasize open verifiable logic.

### Deprecated
- `VAMS_BountyEscrow` is fully deprecated. Use `ComposedSettlement`.
- The older Static Inflation schedules inside the token contract are deprecated for dynamic emissions (`RegionAwareDEC.sol`).
- Monolithic agent tasks are formally deprecated in favor of Composed Blueprints.

### Removed
- Legacy static `SLA` configurations which have been centralized in the multi-da anchor logs.
