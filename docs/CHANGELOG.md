# Changelog

All notable changes to the VAMS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Cardano schema-v2 authenticated state machines**: Reworked
  `cardano/lib/vams/types.ak` and the four persistent validators so agent,
  proposal, timelock, fund, and claim states carry complete authentication
  asset classes and require exact inline-datum/value successors. Added
  seed-bound `proposal_nft.ak` and `fund_nft.ak` auxiliary policies; agent,
  proposal, and fund creation policies now commit to destination scripts while
  bridge execution, cross-chain deposits, and slashing fail closed.
- **Cardano parameter application ceremony**: Added
  `scripts/deployment/cardano_preprod_apply.py` and
  `cardano-preprod-parameters.schema.json`. Unapplied blueprint entries are
  emitted only as non-deployable templates. The final tool requires ordered
  public CBOR parameters for four persistent validators and exactly one fund
  bootstrap policy, permits agent/proposal policy instances only for real
  creation transactions, applies requested scripts with Aiken, rejects
  remaining parameters, and emits separate deterministic artifacts and hashes.
- **Credential incident closure contract**: Added
  `scripts/audit/credential_incident_evidence.py` and
  `credential-incident-report.schema.json`. Canary and public readiness now
  require content-hashed public evidence for all three historical PEM
  identities, rotation/replacement, Polygon/Cardano funding impact, seven role
  classes, coordinated all-ref cleanup, clean complete-history scans, and a
  named reviewer.
- **Operational evidence producer**: Added
  `.github/workflows/operational-evidence.yml` on a dedicated protected,
  read-only evidence runner. It binds a target SHA and release stage to a fixed
  evidence root, rejects secrets, symlinks, and prebuilt aggregate manifests,
  validates the raw operational bundle, and uploads an immutable 365-day
  artifact for later promotion consumption.
- **Deterministic deployment rehearsal tooling**: Added Polygon Amoy and Cardano
  Pre-Prod runbooks plus `scripts/deployment/cardano_preprod_artifacts.py`. The
  Cardano extractor emits exactly four Plutus V3 artifacts, excludes VDSO,
  records deterministic hashes, and rejects a commit argument that does not
  match a clean Cardano source tree at repository `HEAD`.
- **Runnable private VDSO shadow worker**: Added
  `neuron/vdso/shadow_worker.py`, `neuron/vdso/shadow_postgres.py`, the Rust
  `shadow_eval` binary, and the exported Aiken `shadow_read_commitment`
  evaluator. The worker consumes strict hash-chained commitment-only baseline
  JSONL, executes Python/Rust/Aiken conformance on every read-only transition,
  persists atomic PostgreSQL checkpoints and 1,000-transition audit chunks,
  includes restart/replay regression coverage beyond `1 × 10^5` records, and emits unsigned report
  material only after the seven-day gate. It fails closed on missing backends,
  divergence, source gaps/reordering/duplicates, root mismatch, plaintext-like
  fields, mutations, and continuity gaps; no completed shadow run is claimed.
- **Private VDSO shadow composition**: Added PostgreSQL-backed atomic nonce and
  replay stores, trusted-height and on-chain-deployment verification boundaries,
  and application-lifespan composition for the private shadow service. Public
  Gateway instances do not mount VDSO routes when `VDSO_MODE=off`; shadow mode
  is read-only, non-value-bearing, and rejects sidecar publication.
- **VDSO promotion evidence**: Added fail-closed validation for a signed,
  versioned `vdso-shadow-report.json` and deployment evidence covering all seven
  empty Polygon VDSO modules. Cardano `vdso.ak` is recorded only as conformance
  evidence, never as a deployed validator.
- **Deployment identity evidence**: Added `contracts/script/utils/AuthorityIdentityValidator.sol`
  and network-specific deployment-manifest validation. Polygon evidence binds
  each Safe proxy and singleton runtime code hash, exact owners/thresholds,
  timelock bytecode and roles, transfers, and deployer-role removal. Cardano
  evidence binds multisig credentials, validator CBOR/script hashes, governor
  and timelock scripts, and control handoffs without applying EVM Safe fields.
- **Runtime/privacy evidence inventory**: Added an AST-derived publisher
  inventory and artifact-bound v2 runtime/privacy schemas so new DA, Sentinel,
  or VDSO publication sinks cannot bypass review by omission.
- **VDSO evidence hardening**: Added `docs/adr/ADR-VDSO-001.md`, corrected
  review artifacts under `docs/team/vdso/`, and a provenance-bound evidence
  manifest/schema. The ADR is `Proposed` and authorizes only side-by-side
  canary implementation work; it is not deployment or testnet-readiness
  evidence.
- **`vams-vm/`**: Added the Rust 1.92 VIR-Core v1 reference foundation with
  restricted positional CBOR, raw domain-prefixed Keccak identifiers, explicit
  Polygon/Cardano authority epochs, bounded checked-integer execution, semantic
  receipts, shared golden vectors, and fail-closed SP1/RISC Zero placeholders.
- **`contracts/src/vdso/`**: Added side-by-side object, reservation, adapter,
  program, proof, capability-routing, and execution-kernel modules. The canary
  binds host and authority epoch, uses compare-and-swap object versions and
  fencing tokens, separates semantic transitions from settlement, and keeps
  ambiguous recovery locked unless execution or non-execution is verified.
- **`neuron/vdso/` and `gateway/vdso.py`**: Added exact VIR intent encoding,
  height-aware expiry, body-bound secp256k1 requests, nonce/replay policy,
  deterministic capability routing, encrypted witness-sidecar handling,
  a ciphertext-only DA publication boundary, and shadow/canary workflow
  orchestration. Current Celestia/Near adapters are ineligible for VDSO live
  evidence; authoritative mode and unconfigured live cryptography fail closed.
- **`cardano/lib/vams/vdso.ak`**: Added the Cardano read/conformance boundary,
  shared intent vector, Polygon/Cardano wire mapping, and executable bridge
  proof/payload separation checks. Value-bearing `CONSUME` and `RESERVE` remain
  disabled for the initial Cardano canary.
- **`contracts/script/DeployVDSOCanary.s.sol`**: Added a Polygon Amoy-locked,
  empty-state deployment rehearsal that validates distinct Safe/timelock roles,
  performs role handoff, pauses the execution kernel under the distinct 2-of-3
  pause council, removes deployer pauser/admin/executor authority, activates no
  adapter/verifier/program/domain, and leaves recovery abort disabled until a
  real non-execution verifier exists.
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
- **Aiken dependency reproducibility**: Updated `cardano/aiken.toml` and
  `cardano/aiken.lock` from floating `v2` selectors to exact official
  `v2.2.0` stdlib/fuzz releases. The strict seeded check and blueprint rebuild
  pass with the resolved lockfile.
- **Cardano deployment documentation**: Updated `cardano/README.md`,
  `CARDANO_PREPROD_REHEARSAL.md`, `contracts/CONTRACTS.md`, and the status/risk
  documents to distinguish templates, applied persistent validators, and
  auxiliary one-shot policies. Cardano VDSO remains conformance-only.
- **Deployment manifest v3**: Bumped
  `deployment-manifest.schema.json` and readiness validation to `3.0.0` so
  Cardano evidence must bind exactly four persistent validators, three
  auxiliary policy templates, and the real applied fund/creation instances
  without treating template hashes as deployed scripts.
- **Gateway and Neuron secp256k1**: Replaced the unpatched `python-ecdsa`
  dependency with `cryptography` ECDSA/SHA-256 primitives using the existing
  64-byte public-key and signature encodings, low-S normalization, and
  fail-closed rejection of malformed or high-S signatures.
- **Neuron Gateway transport**: Live Gateway clients now require HTTPS;
  plaintext is allowed only for loopback development. The direct HTTP heartbeat
  fallback was removed, and credential-bearing or ambiguous Gateway URLs are
  rejected.
- **Live DA boundary**: Celestia submission failures no longer fall back to mock
  receipts and exact retrieval is mandatory. Near non-mock submission is
  disabled until signed submission and retrieval exist. Mock, Avail, EigenDA,
  and release-ineligible VDSO receipts never report verified evidence.
- **VDSO Python execution boundary**: Capability requirements are now derived
  only from signed VIR intent fields. Canary orchestration must select eligible
  adapters before external work, rejects Cardano `CONSUME`/`RESERVE`, requires
  Tier 2 hybrid authorization for every non-`READ` access and every nonzero
  settlement-cost budget, and joins every nonzero signed `sidecar_root` to the
  exact uploaded encrypted sidecar content hash.
- **VDSO settlement metadata**: Version-bumped the undeployed settlement
  semantics to `vdso-settlement-v2` in Python, Rust, Aiken, and Solidity.
  Python, Rust, and Aiken share the ten-field CBOR
  encoding; the Solidity ABI independently enforces the same schema-v2 host,
  height, authority, and proof-separation semantics. Both representations bind
  explicit source and destination hosts, require the destination to match
  domain authority, reject equal-host cross-chain claims, and preserve
  `bridge_proof_hash != payload_hash` for INV-10.
- **VDSO Gateway lifecycle and authentication**: Replaced global service state
  with application-lifespan construction, separated strict `VAMS_ENV` and
  `VAMS_NETWORK` parsing, required shared durable stores and trusted providers
  for private shadow startup, and extended DID authentication to intent,
  object, adapter, and sidecar reads.
- **Promotion evidence ordering**: Security gates now bind raw per-gate
  artifacts and the complete stage evidence bundle before generating and
  Cosign-signing the manifest. Manual promotion identifies both the immutable
  target SHA and prior evidence run rather than committing evidence into a
  self-referential release SHA.
- **VDSO Solidity admission and topology**: Restricted program activation to
  VIR-Core v1 and the three exact checked-in policy commitments, made the
  Polygon kernel reject all Cardano-authoritative state writes, and required
  an executable governance/open-executor timelock before role handoff. Proof
  configurations that require agreement now reject identical primary and
  secondary verifier addresses.
- **`docs/ARCHITECTURE.md`, `REPO_STATUS_REPORT.md`, and audit documents**:
  Added the proposed VDSO canary boundary while preserving the Polygon–Cardano
  dual-host allocation. Each state domain has one authoritative writer; a
  Cardano read-first integration phase does not demote its governance, identity,
  insurance, or native-validator authority.
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
- **`.github/workflows/security-gates.yml`**: Added VDSO evidence tests and a
  pinned Rust 1.92 VIR-Core format/check/clippy/test job to the aggregate
  security-evidence and SBOM dependency graph.
- **`contracts/CONTRACTS.md`**: Replaced stale deployed/ready language with a pre-testnet deployment evidence register for Polygon Amoy and Cardano Pre-Prod, including pending fields for addresses, tx hashes, verification status, Safe/multisig ownership, and timelocks.
- **`docs/GATEWAY_HARDENING_BLUEPRINTS.md`** and **`gateway/Caddyfile.testnet.example`**: Added the loopback-Uvicorn-behind-Caddy deployment profile and proxy-set mTLS certificate headers expected by the gateway.
- **`REPO_STATUS_REPORT.md`**: Rewrote the repository status report for the July 2026 public testnet launch window with commit-history chronology, current component maturity, verified blockers, and gated roadmap language.
- **`.github/workflows/security-gates.yml`**: Aligned CI with the current frontend and Cardano toolchains by moving frontend verification to Node.js 22, pinning Aiken to `v1.1.21`, and using `aiken check` as the Aiken verification command.
- **`.github/workflows/security-gates.yml`**: Replaced all mutable GitHub Action refs with exact commits, replaced the removed `txpipe/setup-aiken` action with the official Aiken action, and pinned Foundry and Python security-tool versions.
- **`cardano/aiken.toml`**, **`cardano/aiken.lock`**, and **`.github/workflows/security-gates.yml`**: Pinned the official `aiken-lang/fuzz` v2 package and made the Cardano gate reproducible with seed `20260713` and 250 successful cases per property.
- **`neuron/requirements.txt`**: Declared `numpy` and `scikit-learn` for the intelligence-layer modules and tests that already import vector math and Incremental PCA dependencies.
- **`neuron/da/models.py`**: Included Sentinel telemetry extras in deterministic DA audit report serialization so fidelity and SkillOps-related telemetry can be committed in report hashes.
- **`neuron/services/registry_client.py`**: Extended Service Block metadata with deterministic SkillOps manifests and fail-closed permission-scope validation.

### Security
- **Authenticated Cardano creation and execution**: Removed circular
  script-hash/policy-ID parameter dependencies by storing complete asset
  classes in schema-v2 datums while one-shot policies bind seed UTxOs and
  destination scripts. Governor/timelock preserve proposal identity, timelock
  targets are explicitly allowlisted, claims bind their canonical fund asset,
  and mock bridge/cross-chain/slashing branches remain unconditionally false.
- **Credential closure is a release gate**: Integrated the artifact-bound
  historical PEM closure validator into canary/public readiness and the
  operational evidence producer contract. A clean scanner result without
  rotation, impact, history, collaborator/fork/cache, and reviewer proof cannot
  clear the incident.
- **Pinned Gateway evidence runtime**: Digest-pinned Caddy 2 for configuration
  validation and the deployment blueprint, migrated client-auth trust to the
  current `trust_pool file` syntax, and extended the workflow validator to
  reject mutable Caddy evidence commands.
- **PostgreSQL checkpoint atomicity**: Extended the disposable integration gate
  to race eight processes over the same shadow checkpoint, verify idempotent
  serialization, restart/load continuity, replay counters, nonce/replay
  atomicity, and more than $1 \times 10^5$ durable replay records.
- **Closed VDSO deployment posture**: All seven Polygon VDSO modules must be
  paused as a deployment postcondition. Empty registries, zero active
  domains/routes/verifiers, distinct Safe-held pause/guardian/recovery roles,
  and zero deployer privilege remain mandatory manifest evidence.
- **Fail-closed runtime identity**: Unknown `VAMS_ENV` or `VAMS_NETWORK` values,
  absent durable shadow stores, missing trusted heights, unverified deployments,
  unauthenticated reads, and any shadow mutation/value/sidecar request now abort
  instead of degrading to local behavior.
- **Historical secret gate**: A fully redacted Gitleaks v8.30.1 complete-history
  scan found 1,740 matches across 15 finding-bearing commits, including three historical PEM
  private-key findings. `docs/audit/GITLEAKS_ADJUDICATION.md` blocks release
  pending rotation, role-impact review, coordinated history cleanup, and clean
  Gitleaks/TruffleHog rescans; no blanket baseline was added.
- **Secret-scanner reproducibility**: Pinned the workflow runtime versions to
  Gitleaks 8.30.1 and TruffleHog 3.95.9 instead of inheriting mutable scanner
  defaults from otherwise commit-pinned actions.
- **Safe/timelock identity**: `DeployTestnet.s.sol` and
  `DeployVDSOCanary.s.sol` now reject interface-shaped impostors by checking
  proxy runtime code, singleton identity/runtime code, exact owner counts and
  thresholds, zero transaction nonce, extension-free current state, and the
  compiled VAMS timelock runtime before rehearsal or role handoff. This does
  not prove absence of historical Safe hash preapprovals; the exact audited
  Safe release plus complete setup and `ApproveHash` history remain deployment
  evidence blockers.
- **VDSO scanner remediation**: Explicitly initialized recovery-verifier state
  and require the execution kernel to consume a successful proof-router result.
  Slither's configured fail-high gate reports zero high findings; all 19
  residual medium results are documented in `docs/audit/SLITHER_ADJUDICATION.md`.
- **VDSO DA evidence gate**: Current `NearDAAdapter` and
  `CelestiaDAAdapter` implementations are explicitly blocked from encrypted
  VDSO sidecar publication. A replacement route must inject receipt-verifier
  and blob-retriever observers that are not bound to the submitting adapter and
  establish exact retrieval-bound evidence; adapter self-verification,
  `mock_mode`, and a receipt's `verified` flag are not accepted as proof. The
  runtime blocks directly or partially bound methods; independent operational
  and deployment provenance remains a canary-admission review requirement.
- **VDSO implementation-identity gate**: The empty deployment activates no
  adapter or verifier. Upgradeable proxy implementations remain ineligible
  because an address codehash does not pin the proxy implementation; live
  activation requires an independently reviewed immutable direct deployment.
  Safe/timelock interface responses are source-level rehearsal checks only;
  deployment still requires known implementation bytecode and instance/role
  evidence.
- **VDSO canary controls**: Implemented host/epoch binding, non-timeout
  reservation recovery, destination fencing, proof/payload separation,
  classical XChaCha20-Poly1305 sidecar encryption, hybrid-suite binding for
  every Tier 2 or nonzero-settlement-cost authorization, separate
  authorization/proof/settlement labels, and fail-closed rejection of mock
  evidence. Reviewed HPKE, ML-DSA, and proof
  backends remain unconfigured; the code blocks rather than substitutes mocks.
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
- **`.github/workflows/security-gates.yml`**: Routed event names and pull-request base/head SHAs through step environment variables before shell use, eliminating the remaining direct GitHub-context interpolation from change-classification scripts.
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
- **`neuron/sentinel/challenges/latency_probe.py`**: Switched simulated RTT measurement to the monotonic performance clock; the success-path regression now injects a deterministic clock and async sleep so concurrent analyzer load cannot create a false zero-score failure.
- **`neuron/runtime_safety.py`**: Added centralized live-environment safety gates for `VAMS_ENV=staging`, `VAMS_ENV=testnet`, and `VAMS_ENV=production`.
- **`gateway/server.py`**: Gateway DA audit initialization now rejects mock audit mode in live environments before any mock DA receipt can be emitted.
- **`gateway/server.py`**: Live environments now require `GATEWAY_ADMIN_DID`, reject Basic Auth on protected control-plane routes, enforce single-use DID signatures within the 5-minute timestamp window, and bind direct Uvicorn startup to `127.0.0.1`.
- **`gateway/server.py`**: Live `/heartbeat` telemetry now requires proxy-verified mTLS client certificate headers and an allowlisted certificate fingerprint via `GATEWAY_HEARTBEAT_CERT_FINGERPRINTS`.
- **`neuron/sdk/oms_identity.py`**, **`neuron/sdk/trails_client.py`**, **`neuron/payments/coinme_client.py`**, **`neuron/sdk/avail_substrate.py`**, **`neuron/sdk/eigenda_kzg.py`**, **`neuron/sdk/iagon_storage.py`**, **`neuron/sdk/phala_tee.py`**, and **`neuron/bridge_executor.py`**: Added fail-closed live-mode checks that reject mock clients, demo credentials, mock bridge verification, and mock TEE execution in staging/testnet/production.
- **`neuron/da/adapters/avail_adapter.py`** and **`neuron/da/adapters/eigenda_adapter.py`**: Explicitly block structured stub adapters from instantiating in live environments.
- **`contracts/src/registry/ServiceBlockRegistry.sol`**: Service Block provisioning now fails closed when verifier-governed quarantine is active.

### Testing
- **2026-07-15 focused working-tree verification**: Passed 41/41 Python
  regressions covering Cardano parameter application, credential incident
  evidence, audit readiness, blueprint artifacts, and workflow supply-chain
  controls.
- **Commit handoff boundary**: Formatter commit `4d4b2e5` and implementation
  commit `202172dbf0ed29c5ff0fdea6267dd65ef55ad68c` contain this locally
  verified hardening. Local results are not substituted for the required
  signed post-history-rewrite exact-commit CI evidence.
- **Phase 6 Python verification**: On the working tree based on
  `31929a24419a9b7b9d8954cbea2df9fe1cb77a68`, the full Python aggregate passes
  753 tests with one intentional Rust-binary environment skip. The pinned real
  PostgreSQL integration remains required and was not run because no service is
  available on this host.
- **Solidity verification boundary**: Full working-tree Foundry verification
  passes 709/709 across 40 suites, with zero failures or skips. Build and
  whole-tree `forge fmt --check` pass after deterministic formatter cleanup.
  Exact-commit CI evidence remains required.
- **Audit controls**: Fifteen readiness tests, two deployment-source tests, two traceability tests, one workflow-supply-chain test, eight economic-concentration tests, and two adversarial-campaign tests passed; the 12-class agent corpus and first-party security scans also passed.
- **Economic adversarial campaign**: The seed `20260711` campaign passed 100,000 epochs with 20,000 detections per attack class, zero misses, and zero baseline false positives; synthetic evidence does not replace live beneficial-owner attestations.
- **Invariant regressions**: Focused runs passed 16 regional-emission tests, 3 stale-oracle tests, and 52 session-key/TEE/SDK tests.
- **Cardano working-tree verification**: `aiken fmt --check`,
  `aiken check --deny --seed 20260713 --max-success 250`, and `aiken build`
  pass. The suite contains 71 unit tests and 6 properties (77/77), with 250
  successful cases per property. Transaction cases cover exact creation and
  successors, duplicates, forged/replayed claims, malformed intents, premature
  execution, unauthorized cancellation, datum/value substitution, and
  fail-closed bridge/slashing paths. `cardano/lib/vams/vdso.ak` remains
  conformance-only and is not a deployable validator.
- **Cardano clean-commit template rehearsal**:
  `cardano_preprod_artifacts.py` succeeded against `202172db...` and emitted
  four persistent validator artifacts plus three auxiliary policy templates
  with `artifacts_applied=false`. No deployment address, transaction, signer,
  or operational evidence was fabricated.
- **Frontend verification status**: `node --check` passed for the Vite/config modules, `npm audit --audit-level=high` found zero vulnerabilities, and the Vite 7.3.6 production build passed with 1,712 modules transformed.
- **`neuron/tests/test_performance_audit.py`**: Added regression coverage proving sensitive and structured KPI data cannot survive DA report serialization.
- **Security scripts**: Verified `default_credential_scan.py`, `public_content_policy_scan.py`, and `mock_mode_promotion_scan.py` passed locally.
- **World-state and SkillOps targeted tests**: Verified `pytest -q neuron/tests/test_service_blocks.py neuron/tests/test_world_state_fidelity.py neuron/tests/test_world_state_phase_boundary.py` passed with 31 tests.
- **Python current-tree aggregate**: Pytest passes 753 tests in the full
  non-PostgreSQL aggregate with one Rust evaluator integration skip. The real
  PostgreSQL service test is environment-blocked locally; exact-commit CI
  remains required.
- **Python security gates**: Bandit reports no qualifying medium/high-confidence
  issue. Both Gateway and Neuron requirement sets pass `pip-audit` with no known
  vulnerabilities after removal of `python-ecdsa`.
- **VIR-Core verification**: Current-branch `cargo check --workspace
  --all-targets --locked` passes. A current-branch `cargo test` result is
  unavailable on Windows because MSVC `link.exe` is not installed. The older
  Linux 34/34 result is baseline evidence only.
- **Cross-language analyzers**: Slither 0.11.5 analyzes 181 contracts with 63
  detectors, passes the fail-high gate, and retains 19 locally adjudicated
  lower-severity results. Semgrep 1.169.0 reports zero findings across 464
  tracked files/520 rules with 99.9% parsed. Exact-commit CI rerun and external
  acceptance remain required.
- **World ID regressions**: Added five Foundry tests covering zero-verifier rejection, verifier-bound acceptance, malformed input, wrong action scope, and verifier-revert failure.
- **Syntax/hygiene**: Verified touched Python files with `py_compile`; `git diff --check` passed.
- **Docs-only PR gate**: Planned verification with `git diff --check` over `docs/team` changes only; full gates remain active for pushes to `main` and PRs with code/config/funding changes.
- **Security/build evidence boundary**: Current Python, Solidity, Aiken, Rust
  format/check/Clippy, frontend, Bandit, pip-audit, Slither, Semgrep, and
  first-party scanner results are green where executable. PostgreSQL and Rust
  linked tests remain environment-blocked, and none of the local results is
  signed exact-commit evidence. Historical Gitleaks, the three
  PEM identity rotations and role-impact proof, history cleanup, clean
  Gitleaks/TruffleHog rescans, signed SBOM, exact-commit CI, and aggregate
  Cosign evidence remain blocking.
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
- **`scripts/docs/validate_vdso_evidence.py`**: Added fail-closed validation for
  discussion hash/size/line provenance, exact eight-principle coverage,
  repository line citations, controlled maturity labels, dual-host authority,
  proposed readiness status, ADR requirements, and INV-1 through INV-10
  traceability, with stdlib regression tests.
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
