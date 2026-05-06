# Changelog

All notable changes to the VAMS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0-oms] - 2026-05-06

### Added — Phase 1: Two-Layer Identity Model
- **`neuron/sdk/signer.py`**: `SignerInterface` (ABC), `EOASigner`, `SessionKeySigner`, and `SignerFactory`
  — abstracts signing away from raw `from_key()` calls across all transactional Python modules.
- **`VAMSAgentRegistry.sol`**: New `authorizedWallet` field on the `Agent` struct;
  `setAuthorizedWallet(bytes32 agentId, address wallet)` owner-only setter;
  `isAuthorizedCaller(bytes32 agentId, address caller)` view function;
  `AuthorizedWalletSet` event.

### Added — Phase 2: Trails Transport Integration
- **`neuron/sdk/trails_client.py`**: Thin `TrailsClient` wrapper around OMS Trails API with
  `submit_intent()`, `get_status()`, and mock mode for testing.
- **`BridgeExecutor.py`**: `TRAILS` transport added to `BridgeTransport` enum;
  `TRANSPORT_MATRIX` updated to prefer Trails for the 4 AggLayer routes (Ethereum, Polygon, Arbitrum, Base)
  with AggLayer as fallback; `TrailsTransportHandler` class.

### Added — Phase 3: Sequence ERC-4337 Session Keys
- **`neuron/sdk/sequence_wallet.py`**: `SequenceWalletManager` (ERC-4337 smart wallet lifecycle)
  and `SessionKeyManager` (scoped session keys with per-TrustTier value limits: BRONZE=100 $VAMS,
  SILVER=1K, GOLD=50K, PLATINUM=unlimited; 24h validity window default).

### Added — Phase 4: Coinme Fiat Rails + Insurance Fund Yield
- **`neuron/payments/coinme_client.py`**: `CoinmeClient` — fiat-to-crypto on-ramp API wrapper
  with `create_checkout()`, `get_conversion_rate()`, and webhook handler.
- **`neuron/payments/universal_topup.py`**: `UniversalTopUpManager` — orchestrates fiat → $VAMS
  conversion, applies gas abstraction premium (2–7%), deposits to agent `ComposedSettlement` escrow.
- **`neuron/economics/yield_manager.py`**: `YieldManager` — manages Insurance Fund idle capital
  in OMS yield vaults; enforces ≤30% allocation cap and instant-withdrawal requirement.

### Added — Phase 5: Stablecoin Payouts + Enterprise RPCs + Identity
- **`neuron/payments/stablecoin_payout.py`**: `StablecoinPayoutManager` — provider opt-in
  to auto-convert $VAMS rewards to USDC or USDT via OMS stablecoin settlement rails.
  Exposes `PayoutMode` enum: `VAMS_ONLY`, `STABLECOIN`, `HYBRID`.
- **`neuron/sdk/oms_identity.py`**: `OMSIdentityVerifier` — institutional KYC/KYB verification
  via OMS Compliance module. Fail-closed: returns `False` on any network or parse error.
- **`docs/team/ARCHITECTURE_v0-6-0.md`**: New team architecture addendum covering all 5 OMS phases,
  updated CLR v3.1 decision tree, and security boundary documentation.

### Changed
- **`neuron/payments/x402.py`**: Default signer switched from `EOASigner` to `SessionKeySigner`
  for payment operations; root EOA retained for channel creation only.
- **`neuron/neuron.py`**: `SequenceWalletManager` initialised alongside existing components;
  session signer passed to `X402Client` and `trust_aggregator`.
- **`neuron/clr_router.py`**: P3 (`P3_INSTITUTIONAL_COMPLIANCE`) routing now gates on
  `OMSIdentityVerifier.is_verified(agent_id)` in addition to the existing `PLATINUM` trust tier
  check. Non-verified addresses are rejected fail-closed.
- **`neuron/chain_oracle.py`**: OMS enterprise RPC endpoints replace public fallbacks for all
  Polygon-ecosystem chains; SLA monitoring added with per-endpoint uptime/latency tracking.
- **`contracts/src/economic/RewardDistributor.sol`**: `payoutPreference` mapping
  (`address → PayoutMode`); `setPayoutPreference(PayoutMode)` function; `claimRewards()` now
  routes through conversion contract when preference is `STABLECOIN` or `HYBRID`.
- **`contracts/src/economic/VAMSInsuranceFund.sol`**: `YIELD_MANAGER_ROLE` added;
  `deployToYield(address vault, uint256 amount)` — capped at 30% of `totalFundBalance()`;
  `withdrawFromYield(address vault, uint256 amount)` — instant withdrawal path;
  `totalFundBalance()` now includes deployed capital via `totalDeployedBalance()`.
- **`contracts/src/registry/VAMSAgentRegistry.sol`**: `registerAgent()` sets `authorizedWallet`
  to the Sequence smart wallet address; all `msg.sender` checks accept authorized wallet.

### Security
- `OMSIdentityVerifier.is_verified()` is fail-closed: any exception (network, parse, timeout)
  returns `False`, preventing unauthenticated access to P3 institutional routes.
- Session keys are strictly scoped: value limit, allowed contract whitelist, and 24h validity
  window enforced by `SessionKeyManager`; limits scale with TrustTier.
- Insurance Fund yield deployment capped at ≤30% of `totalFundBalance()` to preserve solvency
  for concurrent insurance claims.
- TEE attestation binding preserved: `tee_plugin.py` always binds attestations to root EOA,
  not to session wallet identity.

### Testing
- **675 total tests passing** (619 Forge + 56 Pytest — zero regressions).
- New test coverage: `test_fiat_yield.py` (Coinme, UniversalTopup, YieldManager),
  `test_sequence_wallet.py` (session keys, tier scopes, expiry),
  `test_trails_client.py` (TrailsClient mock + fallback),
  `test_clr_v3.py` (19 tests — CLR P3 OMS gate, all routing paths, bridge regression guards).

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
