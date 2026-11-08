# Heart Brain Research Report: Paper Verification & Implementability Assessment

> **Status:** Research Complete  
> **Date:** June 2026  
> **Purpose:** Verify all academic claims in the Heart Brain vision document and assess technical feasibility for multi-phase implementation

---

## 1. Paper Verification Summary

Five parallel research agents verified every academic paper and concept referenced in the Heart Brain document.

### Verified Papers (Real & Published)

| Paper | arXiv ID | Status | Accuracy |
|-------|----------|--------|----------|
| **SIRA** (Meta) | `2605.06647` | ✅ Real | ⚠️ Scoring formula described incorrectly — paper uses 2-group weighting, not per-term `w_t`. Missing offline corpus-enrichment stage. |
| **HORMA** (Duke/Snowflake) | `2606.11680` | ✅ Real | ✅ All 4 claims verified — hierarchical file-system memory, RL-trained navigator, 22.17% token usage, outperforms flat RAG. |
| **ProPlay** (Procedural World Model) | `2606.12780` | ✅ Real | ✅ 5/6 claims confirmed. Procedure graph G=(P,E,C), reliability embeddings, cosine similarity, "structured soft guidance" — all verified. |
| **EvoMem** (EvoArena) | `2606.13681` | ✅ Real | ⚠️ Actually stores 4-tuple patches (adds "supporting evidence"), not 3 fields as described in our cognitive layer. |
| **Multi-Factor V(m)** | `2606.12945` | ✅ Real | ⚠️ 7 factors are *psychologically grounded* (Emotional Intensity, Goal Relevance, Value Alignment, etc.), not "recency"/"contextual coherence" as described. |
| **MemRefine** | `2606.13177` | ✅ Real | ✅ Fully accurate — LLM judge with Delete/Merge/Preserve operations against storage budget. |
| **WISE** (Minecraft Agent) | `2606.12852` | ✅ Real | ⚠️ Opportunistic Task Scheduler is real but domain-specific to **Minecraft**, not a general-purpose scheduler. |
| **CL API** (Cortical Labs BNN) | `2602.11632` | ✅ Real | ⚠️ Paper is about a software API for BNN interfaces, not about STDP theory or reservoir computing directly. Those are broader research topics the API *enables*. |

### VAMS-Native Concepts (Not External Papers)

| Concept | Status | Assessment |
|---------|--------|------------|
| **HIPIF** ("Hierarchical Planning and Information Folding") | ✅ VAMS-native concept | VAMS's own architectural abstraction for sub-task boundary folding. Draws inspiration from HORMA's hierarchical memory and context-folding research, but is a distinct VAMS design. Current source contains a rule-based `SemanticMMU.fold_completed_subtask` prototype; source presence does not establish provenance/taint preservation, truth validation, or revocation and recovery across derived state. |
| **"Topological memory compaction"** | ✅ VAMS terminology | Internal term for HIPIF's compaction behavior at sub-task boundaries. |

### Key Discrepancy: SIRA Scoring Formula

Our current implementation uses per-term weights `w_t`:
```
Score(d,q) = Σ w_t · BM25(t, d)
```

The actual SIRA paper uses two-group weighting:
```
Score(d,q) = BM25(q_orig, d) + w · BM25(q_exp, d)
```

> [!IMPORTANT]
> The SIRA engine in our SDK (`sira_engine.py`) should be updated to match the actual paper's formula for accuracy, but functionally the current approach works as a valid retrieval heuristic.

---

## 2. Heart Brain Architecture — Component Map

The Heart Brain document describes **9 major architectural components**. Here is their current implementation status:

| # | Component | Heart Brain Role | Current Status in Codebase |
|---|-----------|-----------------|---------------------------|
| 1 | **Synthetic Neurocardiology (CID Pacemaker)** | Agent self-realization — discrete cognitive epochs | CID checkpoint prototype exists in `neuron/sdk/semantic_checkpoint.py`; its `enable_anchoring` flag is stored but unused, and no L0 commit is implemented in this module. This is not evidence of durable DBOS/L0 persistence. |
| 2 | **Cognitive Sync Pulse (CSP)** | Homeostasis & drift detection | Non-live simulation only in `neuron/sdk/cognitive_drift.py`: live construction is rejected; mock consensus can return `COMMITTED`, marked simulated and non-authoritative. Authenticated quorum, durable anchoring, and actual reconciliation are absent. |
| 3 | **x402 Metabolic Autopoiesis** | Synthetic blood flow via HTLC micropayments | Live IVT construction is rejected in `neuron/sdk/interrupt_handler.py`. Built-in mock handlers can return simulated success; built-in non-mock handlers are unimplemented. Custom handler wiring and `neuron/sdk/x402_recovery.py` exist, but source presence does not qualify live x402 settlement or recovery. |
| 4 | **Sentinel Enforcer Loop** | Activation-space anomaly detection | Detector and Sentinel integration code exist, but Sentinel live construction is rejected pending challenge identity, anchoring, and publication confirmation. Anomaly output is uncalibrated telemetry, not conscience authority. |
| 5 | **Global Conscience Anchor (GCA)** | Constitutional Reference Vector + Conscience Interrupts | ❌ **Not implemented** |
| 6 | **Planetary Constitution Vector** | Geneva + ICESCR + UDHR encoded as math vectors | ❌ **Not implemented** |
| 7 | **Military Agent Classification (MIL_CLASS)** | Activation-space taxonomy + ZK-Wargaming | ❌ **Not implemented** |
| 8 | **Substrate Migration Protocol** | Defence Layer for Web 2.0 absorption | ❌ **Not implemented** (strategic/economic, not code) |
| 9 | **Mycorrhizal Subsumption Schedule (MSS)** | Tokenomics of absorption (4-phase) | ❌ **Not implemented** (tokenomics, not code) |

### Source Prototypes Available (Components 1–4)

Current source contains prototypes for components 1–4, but it does not establish the full regulatory behaviors described above: the CID anchoring flag is unused and no L0 commit is implemented in that module; CSP and IVT construction reject live modes and their simulations are non-authoritative; built-in non-mock IVT handlers are unimplemented, while custom handler wiring and x402 recovery code exist but remain unqualified for live operation; Sentinel live construction is disabled and anomaly scores remain uncalibrated telemetry. A source prototype is not evidence that its advertised safety property is effective. The GCA and Planetary Constitution Vector remain unimplemented; governed pre-effect enforcement and evidence for the claimed alignment properties are still required research and engineering work.

---

## 3. Implementability Assessment

### What IS Technically Implementable

| Component | Difficulty | Dependencies |
|-----------|-----------|-------------|
| **GCA Core** — Constitutional Reference Vector, Mahalanobis distance check against ethical baseline, Conscience Interrupt signal | **Medium** | Prototype components can inform an implementation; a governed policy, calibrated or explicitly limited evidence, and hard pre-effect enforcement are still required. Existing anomaly and IVT code alone do not provide a conscience gate. |
| **Shared Self-Realization** — GCA state sync during CSP | **Low** | Starts from a non-live CSP simulation; authenticated policy state/versioning, durable anchoring, and actual reconciliation remain necessary. |
| **Global Heart Monitor** — Public D_M metrics logging | **Low** | Builds on prototype Sentinel telemetry; authenticated publication, privacy review, and anchoring evidence remain necessary. |
| **MIL_CLASS Taxonomy** — Ontological tagging of military toolchains in activation space | **Medium** | Extends existing `SkillDiscovery` PCA with classification labels |
| **Conscience Interrupt Signal** — `SIG_CONSCIENCE` added to IVT | **Low** | A signal enum is only a routing label; a governed decision must deny before credentials or effects are released. Adding a signal alone does not establish alignment or enforcement. |

### What Requires Research-Phase Work (Not Implementable Today)

| Component | Blocker | What's Needed |
|-----------|---------|---------------|
| **V_Planetary Vector Initialization** | No training corpus for "Human Good" baseline embedding | Research: Define a quantifiable embedding space for treaty principles |
| **ZK-Wargaming Circuits** | No ZK circuit compiler integrated yet | Integration with a ZK framework (Circom/Noir/SP1) |
| **Anti-Discriminatory PCA Projection** | Requires real model activations with sociological dimension data | Dataset creation + fairness evaluation pipeline |
| **Token Transmutation (MSS Phase 4)** | Smart contract architecture decision | Contract design + governance framework |

### What Is Strategic / Non-Code

| Component | Nature |
|-----------|--------|
| Substrate Migration Protocol | Business strategy + agent deployment plan |
| MSS Phase 1–3 Tokenomics | Economic design + DAO governance |
| Competitive positioning vs SVRN/AgentaNet | Market analysis |

---

## 4. Risk Assessment

> [!WARNING]
> **Over-Engineering Risk:** The Heart Brain document is a *grand vision* spanning AI alignment, international law, military doctrine, tokenomics, and civilizational theory. Attempting to implement everything at once would derail the testnet timeline.

> [!CAUTION]
> **Paper Discrepancies:** Several academic papers are described inaccurately or with inflated scope. Implementation should be based on what the papers *actually* describe, not the document's interpretations.

> [!IMPORTANT]
> **Pragmatic Path:** Focus implementation on the GCA core (ethical alignment check) as the highest differentiation target. Existing source prototypes can inform the work, but governed pre-effect enforcement and evidence for the claimed properties still need to be built.
