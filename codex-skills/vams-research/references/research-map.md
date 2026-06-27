# VAMS Research Map

`audit.md` is the canonical academic alignment index. Before mapping research
into code, read `audit.md` sections "Academic References & Research Foundations"
and the matching R-family below. This file is a routing guide, not a replacement
for the audit.

## Academic Families From `audit.md`

- R1 Agentic Economy & Intelligent Delegation: CLR Router, agent principals,
  Web 4.0 identity, agent-native execution. Start with `neuron/clr_router.py`,
  `neuron/sdk/sequence_wallet.py`, `neuron/sdk/oms_identity.py`, and
  `contracts/src/registry/VAMSAgentRegistry.sol`.
- R2 Verifiable Computation & Oracle Security: Commit-Reveal2, MEV resistance,
  ZKML roadmap, hybrid TEE/ZK verification. Start with
  `contracts/src/oracle/CommitRevealOracle.sol`,
  `contracts/src/economic/BatchSettlement.sol`, and trust plugins.
- R3 Data Availability & Modular Architecture: DAS, polynomial multiproofs,
  modular orchestration, sidecar scheduling. Start with `neuron/da/`,
  `contracts/src/da/PerformanceAnchor.sol`, `neuron/providers.py`, and
  `gateway/server.py`.
- R4 Trust, Reputation & Sybil Resistance: AgentReputation, AetherWeave,
  MeritRank, trust-as-a-service. Start with
  `contracts/src/trust/VAMSTrustAggregator.sol`,
  `contracts/src/sentinel/SLAEnforcer.sol`, and `neuron/trust.py`.
- R5 Intelligence Layer & Activation-Space Steering: AutoSkill, activation
  steering, language-guided skill discovery, Mahalanobis OOD detection. Start
  with `neuron/intelligence/activation_cache.py`,
  `neuron/intelligence/skill_discovery.py`,
  `neuron/intelligence/steering_engine.py`, and
  `neuron/intelligence/anomaly_detector.py`.
- R6 Account Abstraction, TEE & Confidential Computing: ERC-4337 session keys,
  TEE abstraction, confidential Web3 attestation. Start with
  `neuron/sdk/sequence_wallet.py`, `neuron/trust_plugins/tee_plugin.py`, and
  `neuron/sdk/phala_tee.py`.
- R7 Token Economics & Sustainable DePIN: DeTEcT, EconAgentic, insurance
  tokenomics. Start with `contracts/src/economic/RegionAwareDEC.sol`,
  `contracts/src/economic/VAMSInsuranceFund.sol`,
  `neuron/economics/dec_regional.py`, and `neuron/economics/yield_manager.py`.
- R8 Cross-Chain Security & Formal Verification: Cardano formal verification,
  eUTXO properties, bridge security taxonomy, cross-chain attack detection.
  Start with `cardano/validators/`, `neuron/bridge_executor.py`, and
  `contracts/src/infrastructure/`.
- R9 Durable Execution & Fault Tolerance: DBOS and crash-recoverable AI agent
  workflows. Start with `neuron/workflows.py`, `neuron/dbos_config.py`, and
  checkpoint/DA anchoring paths.

## Cognitive Layer Addenda

- SIRA search: `neuron/sdk/sira_engine.py`, query expansion, DF pruning, dual
  BM25 scoring.
- HORMA memory layout: `.data/memory/workflows/[workflow_type]/[entity_id]/`.
- HIPIF folding: dense workflow summaries and deletion of noisy traces.
- EvoMem patching: append-only JSONL tuples of state deltas and evidence.
- V(m) consolidation:
  `V(m)=0.4 f_util + 0.3 f_align + 0.2 f_size + 0.1 f_freq`.
- ProPlay world model: `neuron/intelligence/world_model.py`.
- CHC scoring: `neuron/composer/models.py`, `neuron/composer/scorer.py`,
  `neuron/tests/test_chc_scoring.py`.

## Research Review Rules

- Use `audit.md` as the first stop for VAMS academic references.
- Do not cite a paper as implemented unless code and tests prove it.
- Separate `implemented`, `partial`, `stub`, `mock-default`, and `planned`.
- Do not import thresholds from papers into live code without parameter tests.
- Document business, security, and mathematical impact in `docs/CHANGELOG.md`
  when implementation changes.
