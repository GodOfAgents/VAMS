# Changelog

All notable changes to the VAMS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Documentation reality sync**: Added a canonical documentation index,
  current v0.8.0 architecture reference, versioning policy, machine-readable
  documentation manifest, and CI-checkable documentation validator.
- **`contracts/script/DeployTestnet.s.sol`**: Added the Polygon Amoy ceremony with on-chain Safe threshold validation, 48-hour timelock, treasury-only initial allocation, distinct emergency council, role handoff, and deployer postcondition checks.
- **`contracts/script/DeployTestnet.s.sol`** and **`docs/audit/testnet-profile.json`**: Disabled staking rewards for the first public-testnet profile and withheld staking minter authority, preventing reward accrual against a fully allocated fixed supply.
- **`scripts/audit/deployment_readiness.py`** and **`scripts/audit/economic_concentration.py`**: Added source-level ceremony enforcement and linked-owner, HHI, top-four, regional, thin-liquidity, and seven-day reward-return analysis.
- **`scripts/audit/run_economic_adversarial.py`** and **`docs/audit/economic-adversarial-report.json`**: Added a profile-bound, seeded 100,000-epoch campaign across five concentration and reward-loop attack classes.
- **Architecture and invariant evidence**: Added machine-readable v0.3.0-to-v0.8.0 traceability, a ten-invariant source/test index, a cross-boundary threat model, strict runtime/privacy/independent-review schemas, and CI validators.
- **`frontend-vite/src/config.js`**: Added an environment-bound, HTTPS-only production gateway origin and an explicit read-only testnet capability profile.
- **`neuron/tests/test_delivery_proof_fail_closed.py`**: Added regression coverage requiring real TEE and ZK proof verifiers.
- **`docs/audit/`** and **`scripts/audit/audit_program.py`**: Added the 36-track testnet audit program, machine-readable control matrix, risk register, testnet profile, finding/evidence/deployment schemas, commit-bound evidence generation, structural regression tests, and a fail-closed readiness command.
- **`scripts/audit/audit_program.py`** and **`.github/workflows/security-gates.yml`**: Split promotion into `canary` and `public` readiness, require a clean commit, signed aggregate evidence, commit-bound artifact hashes, stage-specific deployment manifests, and cryptographic Cosign verification in the manual promotion job.
- **`docs/audit/INCIDENT_RESPONSE.md`**: Added severity definitions, first-15-minute containment, domain-specific recovery gates, and mandatory pre-testnet incident drills.
- **`docs/audit/agent-red-team-corpus.json`** and **`scripts/audit/validate_agent_red_team.py`**: Added 12 mandatory deny-class attacks covering prompt injection, capability escalation, identity/TEE failures, memory poisoning, reward hacking, bridge confusion, CHC spoofing, and duplicate side effects.
- **`neuron/sentinel/world_state_fidelity.py`** and **`neuron/sentinel/sentinel_node.py`**: Added telemetry-only world-state fidelity reporting for long-horizon agent audits, including state hashes, divergence step, invalid-action step, staleness, and false-progress scoring.
- **`contracts/src/registry/ServiceBlockRegistry.sol`** and **`contracts/src/interfaces/IServiceBlockRegistry.sol`**: Added EIP-712 SkillOps manifest metadata, permission bitmaps, verifier quarantine controls, and provisioning rejection for quarantined Service Blocks.
- **`neuron/tests/test_world_state_fidelity.py`** and **`neuron/tests/test_world_state_phase_boundary.py`**: Added deterministic world-state fidelity and phase-boundary regression coverage.
- **Cardano property tests**: Added seven seeded Aiken properties covering integer-square-root bounds, basis-point safety and monotonicity, inclusive ranges, strict bridge nonce ordering/replay rejection, and insurance payout caps.

### Changed
- **Repository documentation**: Replaced stale deployment, API, test-count,
  local-path, and mock-integration claims with source-backed pre-testnet
  boundaries; historical version documents now carry lifecycle and verification
  metadata.
- **Nineteen upgradeable Solidity contracts**: Migrated from the removed OpenZeppelin 5.5 `ReentrancyGuardUpgradeable` dependency to the current storage-slot `ReentrancyGuard`, restoring full compilation.
- **`contracts/foundry.lock`**: Reconciled the OpenZeppelin Contracts revision with the parent repository's pinned gitlink (`239795bea728c8dca4deb6c66856dd58a6991112`) so dependency resolution uses the same immutable revision.
- **`contracts/src/token/VAMSToken.sol`**: Enforced the absolute $1 \times 10^9$ supply ceiling; only previously burned supply can be reminted within the annual cap.
- **`contracts/src/governance/VAMSTimelockController.sol`** and **`GovernorExecutor.sol`**: Raised the executable governance floor from 24 to 48 hours.
- **`neuron/da/performance_audit.py`**: Restricted default live DA routes to Celestia/Near and made disabled explicit targets fail closed instead of silently rerouting.
- **`neuron/sdk/semantic_mmu.py`**: Added safe HORMA paths, bounded hashed access logs, reviewer-authorized EvoMem persistence/L3 erasure, constrained HIPIF deletion, and session hard reset.
- **`frontend-vite/`**, **`gateway/server.py`**, and **`gateway/Caddyfile.testnet.example`**: Added production origin validation, stricter CSP, explicit live CORS configuration, bounded CORS methods/headers, content-length and chunked-body request limits, and browser permission restrictions.
- **`README.md`**: Replaced the stale fixed test-count badge with the 36-track audit-program status and linked the executable testnet assurance program.
- **`audit.md`** and **`REPO_STATUS_REPORT.md`**: Reclassified v0.6.0 test totals as historical evidence, made current CI verification deployment-blocking, and aligned Phase 6 priorities with the 36-track program.
- **`.github/workflows/security-gates.yml`**: Restricted the lightweight `Docs Verification` path to `docs/team/**/*.md` only; funding/proposal material no longer qualifies for docs-only bypass.
- **`contracts/CONTRACTS.md`**: Replaced stale deployed/ready language with a pre-testnet deployment evidence register for Polygon Amoy and Cardano Pre-Prod, including pending fields for addresses, tx hashes, verification status, Safe/multisig ownership, and timelocks.
- **`docs/GATEWAY_HARDENING_BLUEPRINTS.md`** and **`gateway/Caddyfile.testnet.example`**: Added the loopback-Uvicorn-behind-Caddy deployment profile and proxy-set mTLS certificate headers expected by the gateway.
- **`REPO_STATUS_REPORT.md`**: Rewrote the repository status report for the July 2026 public testnet launch window with commit-history chronology, current component maturity, verified blockers, and gated roadmap language.
- **`.github/workflows/security-gates.yml`**: Aligned CI with the current frontend and Cardano toolchains by moving frontend verification to Node.js 22, pinning Aiken to `v1.1.21`, and using `aiken check` as the Aiken verification command.
- **`.github/workflows/security-gates.yml`**: Replaced all mutable GitHub Action refs with exact commits, replaced the removed `txpipe/setup-aiken` action with the official Aiken action, and pinned Foundry and Python security-tool versions.
- **`cardano/aiken.toml`**, **`cardano/aiken.lock`**, and **`.github/workflows/security-gates.yml`**: Pinned the official `aiken-lang/fuzz` v2 package and made the Cardano gate reproducible with seed `20260711` and 250 successful cases per property.
- **`neuron/requirements.txt`**: Declared `numpy` and `scikit-learn` for the intelligence-layer modules and tests that already import vector math and Incremental PCA dependencies.
- **`neuron/da/models.py`**: Included Sentinel telemetry extras in deterministic DA audit report serialization so fidelity and SkillOps-related telemetry can be committed in report hashes.
- **`neuron/services/registry_client.py`**: Extended Service Block metadata with deterministic SkillOps manifests and fail-closed permission-scope validation.

### Security
- **`neuron/sdk/interrupt_handler.py`**, **`neuron/storage/arweave.py`**, and **`neuron/payments/delivery_proof.py`**: Excluded incomplete live economic routes and changed TEE/ZK delivery proofs from soft acceptance to verifier-required failure.
- **`contracts/script/DeployVAMS.s.sol`**: Blocked the second legacy broad deployment path by default.
- **`neuron/da/models.py`**: Added bounded scalar KPI sanitization before public DA serialization, rejecting raw world-state traces, prompts, credentials, nested payloads, non-finite numbers, and oversized values while retaining benchmark evidence.
- **`neuron/da/models.py`**: Replaced arbitrary telemetry serialization with explicit schemas for world-state fidelity, continual-learning gain, and anomaly fields; public KPIs no longer accept free-form strings.
- **`contracts/script/DeployV2.s.sol`**: Blocked the legacy deployer-controlled deployment profile by default; public testnet requires a separate audited Safe/timelock ceremony.
- **`.github/workflows/security-gates.yml`** and **`scripts/security/`**: Added Slither, Semgrep, TruffleHog, default credential, public-content policy, mock-mode promotion, and Caddy config gates.
- **`gateway/server.py`**: Live environments now reject wildcard CORS origins.
- **`scripts/audit/economic_concentration.py`**: Require beneficial-owner attribution for reward flows and only flag sub-seven-day returns when the return recipient is the operator owner, eliminating unrelated-transfer false positives.
- **`RegionAwareDEC.sol`**: Made 30% the immutable governance ceiling for regional emissions instead of allowing configuration up to 100%, preserving INV-1 under privileged calls.
- **`neuron/sdk/sequence_wallet.py`**: Restricted session validity to 1-24 hours and rejected empty or non-core contract allowlists, preserving INV-3 and INV-4.
- **`neuron/trust_plugins/tee_plugin.py`**: Removed agent/session fallback identity and require an explicit non-zero root EOA for TEE proof encoding, preserving INV-6.
- **`CommitRevealOracle.sol`**: Added permissionless post-deadline resolution to an immutable fallback value with replay protection, preserving INV-7 without caller-selected stale values.
- **`.github/workflows/security-gates.yml`**: Removed direct workflow-input interpolation from the readiness shell step, defaulted non-dispatch runs to the canary stage through a quoted environment variable, and excluded generated Foundry/Vite caches from owned-source Semgrep analysis.
- **`neuron/sdk/oms_identity.py`**, **`neuron/sdk/trails_client.py`**, and **`neuron/payments/coinme_client.py`**: Removed placeholder API-key fallbacks and fail closed outside mock mode when explicit live credentials are missing.
- **`neuron/services/registry_client.py`**: Service Blocks now expose fail-closed memory policy metadata to prevent unreviewed persistent prompt-memory mutation in live paths.
- **`neuron/sentinel/sentinel_node.py`**: Added telemetry-only `continualLearningGain` reporting without slashing, reward, routing, or regional-bonus impact.
- **`contracts/src/trust/plugins/WorldIDPlugin.sol`**: Replaced structural proof acceptance with the configured World ID verifier, binding proofs to the service/delivery signal and the VAMS action external nullifier; malformed proofs and verifier failures now return false.
- **Solidity CEI hardening**: Added missing reentrancy guards to Service Block registration, SLA slash retries, and security-budget updates; reordered payment, escrow, staking, hardware, Sentinel, and registry effects before external interactions.
- **Solidity precision and storage**: Replaced sequential voting-power divisions with `Math.mulDiv`, consumed provider rejection reasons, cached storage-array lengths, and made constructor-only references immutable.
- **`neuron/intelligence/skill_discovery.py`**: Replaced executable pickle persistence with a bounded, schema-checked NumPy archive loaded with `allow_pickle=False`.
- **`neuron/sentinel/sentinel_node.py`**: Moved weighted challenge selection and scheduler jitter to OS-backed `SystemRandom` and prevented negative scheduler delays.
- **`neuron/sdk/akash_orchestrator.py`**: Resolves and verifies the Akash CLI as an absolute regular-file path before live subprocess execution and applies execution timeouts.
- **`gateway/server.py`** and **`neuron/gateway/server.py`**: Tightened default local/direct server binds from `0.0.0.0` to `127.0.0.1` to satisfy the security gate and keep direct startup loopback-first.
- **`neuron/storage/local.py`**: Normalized heartbeat IDs to integers before constructing the parameterized SQLite `IN` clause.
- **`neuron/runtime_safety.py`**: Added centralized live-environment safety gates for `VAMS_ENV=staging`, `VAMS_ENV=testnet`, and `VAMS_ENV=production`.
- **`gateway/server.py`**: Gateway DA audit initialization now rejects mock audit mode in live environments before any mock DA receipt can be emitted.
- **`gateway/server.py`**: Live environments now require `GATEWAY_ADMIN_DID`, reject Basic Auth on protected control-plane routes, enforce single-use DID signatures within the 5-minute timestamp window, and bind direct Uvicorn startup to `127.0.0.1`.
- **`gateway/server.py`**: Live `/heartbeat` telemetry now requires proxy-verified mTLS client certificate headers and an allowlisted certificate fingerprint via `GATEWAY_HEARTBEAT_CERT_FINGERPRINTS`.
- **`neuron/sdk/oms_identity.py`**, **`neuron/sdk/trails_client.py`**, **`neuron/payments/coinme_client.py`**, **`neuron/sdk/avail_substrate.py`**, **`neuron/sdk/eigenda_kzg.py`**, **`neuron/sdk/iagon_storage.py`**, **`neuron/sdk/phala_tee.py`**, and **`neuron/bridge_executor.py`**: Added fail-closed live-mode checks that reject mock clients, demo credentials, mock bridge verification, and mock TEE execution in staging/testnet/production.
- **`neuron/da/adapters/avail_adapter.py`** and **`neuron/da/adapters/eigenda_adapter.py`**: Explicitly block structured stub adapters from instantiating in live environments.
- **`contracts/src/registry/ServiceBlockRegistry.sol`**: Service Block provisioning now fails closed when verifier-governed quarantine is active.

### Testing
- **Solidity aggregate**: The post-change `forge test` run passed 643/643 tests across 32 suites. Exact-commit CI evidence remains pending.
- **Audit controls**: Fifteen readiness tests, two deployment-source tests, two traceability tests, one workflow-supply-chain test, eight economic-concentration tests, and two adversarial-campaign tests passed; the 12-class agent corpus and first-party security scans also passed.
- **Economic adversarial campaign**: The seed `20260711` campaign passed 100,000 epochs with 20,000 detections per attack class, zero misses, and zero baseline false positives; synthetic evidence does not replace live beneficial-owner attestations.
- **Invariant regressions**: Focused runs passed 16 regional-emission tests, 3 stale-oracle tests, and 52 session-key/TEE/SDK tests.
- **Cardano verification**: `aiken check --deny --seed 20260711 --max-success 250` passed 33 unit tests and 7 properties over 1,750 generated cases, totaling 1,783 checks with zero errors or warnings. Transaction-level validator state-machine properties remain required.
- **Frontend verification status**: `node --check` passed for the Vite/config modules, `npm audit --audit-level=high` found zero vulnerabilities, and the Vite 7.3.6 production build passed with 1,712 modules transformed.
- **`neuron/tests/test_performance_audit.py`**: Added regression coverage proving sensitive and structured KPI data cannot survive DA report serialization.
- **Security scripts**: Verified `default_credential_scan.py`, `public_content_policy_scan.py`, and `mock_mode_promotion_scan.py` passed locally.
- **World-state and SkillOps targeted tests**: Verified `pytest -q neuron/tests/test_service_blocks.py neuron/tests/test_world_state_fidelity.py neuron/tests/test_world_state_phase_boundary.py` passed with 31 tests.
- **Python aggregate**: The post-change isolated suite passed 569/569 with one third-party `websockets.legacy` deprecation warning. Exact-commit CI evidence remains pending.
- **Python security gates**: Bandit scanned 24,800 lines with 0 high findings and no reportable medium/high-confidence issue; `pip-audit` found no known vulnerabilities in either the Gateway or Neuron declared dependency graph.
- **Cross-language analyzers**: Semgrep auto rules reported 0 findings across 393 owned files and 517 executed rules. Slither analyzed 169 contracts with 0 high findings; all 18 residual medium results match `docs/audit/SLITHER_ADJUDICATION.md`.
- **World ID regressions**: Added five Foundry tests covering zero-verifier rejection, verifier-bound acceptance, malformed input, wrong action scope, and verifier-revert failure.
- **Syntax/hygiene**: Verified touched Python files with `py_compile`; `git diff --check` passed.
- **Docs-only PR gate**: Planned verification with `git diff --check` over `docs/team` changes only; full gates remain active for pushes to `main` and PRs with code/config/funding changes.
- **Security/build gates**: Current first-party credential, mock-mode, and public-content scans passed; npm audit/build, Forge build/tests, Aiken unit tests, full pytest, Bandit, pip-audit, Semgrep blocking severity, Slither high impact, and `git diff --check` passed. TruffleHog, Gitleaks, signed SBOM, and aggregate CI evidence remain pending.
- **`neuron/tests/test_runtime_safety.py`**: Added regression tests for local mock allowance and live-environment rejection across OMS, Trails, Coinme, DA adapters, DA audit logging, and bridge mock paths.
- **`neuron/tests/test_gateway_auth_hardening.py`**: Added regression tests for DID signature replay rejection, live-mode Basic Auth rejection, live-mode loopback binding, and live heartbeat client certificate enforcement.

## [0.8.0] - 2026-06-23

### Added — Phase 7: CHC Cognitive Scoring & 6-Axis Composer Scoring
- **`neuron/composer/models.py`**: Added `cognitive_requirements` (`Dict[str, float]`) to `InstanceBlueprint` for defining agent capability targets.
- **`neuron/composer/scorer.py`**: Implemented the 6-axis composition ranking engine with the **Cattell-Horn-Carroll (CHC) cognitive shortfall scoring formula**:
  $$S_{\text{cog}} = 1.0 - \frac{1}{|D_{\text{req}}|} \sum_{d \in D_{\text{req}}} \max\left(0, \text{Req}_d - \text{Profile}_d\right)$$
- **`neuron/composer/scorer.py`**: Implemented dynamic weights scaling that adjusts weights proportionally (dedicating 10% to skills and 10% to cognitive requirements when present) while maintaining the 1.0 sum constraint, preserving backward compatibility.
- **`gateway/server.py`**: Extended `NodeInfo` dataclass and heartbeat registration payloads to accept node cognitive profiles, TEE passports, credit scores, registered skills, hourly cost, and regions.
- **`frontend-vite/src/App.jsx`**: Built a new split-screen dashboard layout with an interactive SVG-based Radar Chart visualizing the 10 CHC domains (Decagon Graph) in light/dark modes.

### Testing
- Fully verified via 28 unit tests in `test_chc_scoring.py` and `test_composer_scorer.py` verifying dynamic scaling, shortfall math, edge cases, and 100% test success rate.

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
- **1,083 total tests passing** (619 Forge + 37 Aiken + 427 Pytest — zero regressions).
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
