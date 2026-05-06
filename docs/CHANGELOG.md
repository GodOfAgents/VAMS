# Changelog

All notable changes to the VAMS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1-dbos] - 2026-04-30

### Changed
- **Layer 3 Workflow Engine:** Replaced custom SQLite-based checkpoint engine
  (`CheckpointStore`, `DemoWorkflow`, `@checkpoint`) with the official DBOS Python SDK.
  - `neuron/workflows.py` fully rewritten using `@DBOS.step()` and `@DBOS.workflow()` decorators
  - Steps are now async, exactly-once, and crash-safe via Postgres-backed state
  - `run_demo_workflow()` now uses `SetWorkflowID` for idempotent execution

### Added
- `neuron/dbos_config.py` — singleton DBOS init with dual Postgres strategy (Docker / Neon)
- `neuron/.env.example` — environment template with annotated Postgres connection options
- `neuron/scripts/setup_dbos.sh` — one-command developer onboarding script
- `neuron/docs/WORKFLOW_ENGINE.md` — operator reference for the durable workflow engine

### Removed
- Custom `CheckpointStore` (SQLite), `DemoWorkflow`, `VamsWorkflow`, `@checkpoint` decorator
- `workflow_checkpoints.db` is no longer written (SQLite file is now obsolete)

### Testing
- `neuron/tests/test_workflows.py` fully rewritten (15 new tests, DBOS `TestClient` harness)

---

## [1.3.0-oms] - 2026-05-03

### Added
- **Polygon Open Money Stack (OMS) Integration:** Unified identity, payments, and transport layer for institutional-grade reliability.
- **Two-Layer Identity Model:** Integrated `VAMSAgentRegistry.authorizedWallet` (on-chain) and `OMSIdentityVerifier` (off-chain) for multi-tiered compliance.
  - Support for Session Keys and Authorized Signers via `SignerInterface`.
- **Sequence ERC-4337 Session Keys:** Integrated `SequenceWalletManager` and `SessionKeySigner` for non-custodial, high-frequency agent operations.
- **Trails Transport Integration:** Refactored `CLRouter` to v3.1, adding native support for AggLayer chains via `TrailsClient`.
- **Coinme Fiat Rails:** Implemented `coinme_client.py` and `universal_topup.py` for compliant fiat-to-crypto on-ramps.
- **Stablecoin Payouts:** Added `StablecoinPayoutManager` and updated `RewardDistributor` with `PayoutMode` preferences (USDC/USDT).
- **Enterprise Infrastructure:** Enriched `ChainOracle` with enterprise RPC endpoints, SLA monitoring, and latency-aware failover.
- **OMS Identity Gating:** P3 Institutional Routing in `CLRouter` is now strictly gated by `OMSIdentityVerifier` for KYC/compliance.

### Changed
- `VAMSAgentRegistry.sol`: Added `setAuthorizedWallet` and `isAuthorizedCaller` for session key compatibility.
- `RewardDistributor.sol`: Added `PayoutMode` enum and updated `claimRewards` to support stablecoin settlement.
- `CLRouter`: Decision tree logic updated to v3.1 with identity-aware routing paths.
- `ChainOracle`: Caching layer now prioritizes enterprise endpoints with 30s TTL.

### Testing
- **Foundry:** 619 tests passing (covering v2 contract suite and OMS extensions).
- **Pytest:** 56 tests passing (covering Neuron logic and OMS SDK integrations).
- **Aiken:** 79 tests passing (Cardano integration).

---

## [1.2.0-autoskill] - 2026-04-29

### Added
- **Intelligence Layer (`neuron/intelligence/`):** New AUTOSKILL-powered subsystem implementing
  PCA-based model-native skill discovery, activation-space anomaly detection, and
  inference-time steering based on the AUTOSKILL paper methodology.
  - `ActivationCache`: Thread-safe ring-buffer capture of final-layer model activations
    (framework-agnostic, numpy interface, `.npz` export)
  - `SkillDiscovery`: `IncrementalPCA` pipeline extracting orthogonal skill direction vectors
    with `.pkl` persistence and streaming support
  - `ActivationAnomalyDetector`: Mahalanobis-distance-based anomaly scoring in PCA skill space
    (3-sigma default threshold, per-component breakdown via `AnomalyReport`)
  - `SteeringEngine`: Non-destructive inference-time bias injection (`h ← h + α·v`) with
    hard `max_alpha` safety cap (default `0.3`) and unit-normalized direction vectors
- **`docs/INTELLIGENCE_LAYER.md`**: New comprehensive module guide covering all 4 classes,
  API references, integration examples, and safety considerations.
- **`docs/team/ARCHITECTURE_v0-5-0.md`**: New team architecture addendum documenting the
  Intelligence Layer data flow, modified subsystems, and validation results.
- **`docs/NODE_OPERATORS.md`**: Supplier guide for configuring and operating Intelligence
  Layer-enhanced Sentinel nodes.

### Changed
- `VAMSSentinelNode.audit_node()`: Audit reports now optionally include `activation_anomaly_score`
  (Mahalanobis distance) and `adversarial_flag` (bool) when an `ActivationAnomalyDetector` is
  configured. Existing behavior is fully preserved when no detector is provided.
- `VAMSSentinelNode.run_scheduler()`: Challenge selection is now AUTOSKILL-informed, weighting
  challenge types toward historical node skill gaps (`_node_skill_gaps` dict). Falls back to
  cryptographically-random selection when no detector is configured.
- `CandidateScorer`: Added 5th scoring dimension `skill_alignment` using cosine similarity
  between blueprint `skill_vector` and node `skill_profile`. Weight defaults to `0.0` for
  full backward compatibility with existing integrations.
- `InstanceBlueprint`: New optional field `skill_vector: Optional[List[float]] = None`.
- `ScoredCandidate`: New field `skill_alignment_score: float = 0.0`.
- `ScorerWeights`: New field `skill_alignment: float = 0.0`.

### Security
- `SteeringEngine` enforces hard alpha cap (`max_alpha`, default `0.3`) preventing adversarial
  agents from injecting catastrophic steering magnitudes. Values above `max_alpha` are silently
  clamped and logged as warnings.
- All `SteeringEngine` direction vectors are unit-normalized before application, ensuring
  consistent, bounded impact regardless of raw PCA component magnitudes.
- Validated: `α=0.5` steering achieves +9.2% security task accuracy with <1% degradation on
  unrelated capabilities (formatting tasks). Full safety validation in
  `neuron/tests/test_steering_prototype.py`.

### Testing
- 373 tests passing (zero regressions across all existing suites).
- Added `neuron/tests/test_steering_prototype.py`: Phase 4 prototype validation tests.

---

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
