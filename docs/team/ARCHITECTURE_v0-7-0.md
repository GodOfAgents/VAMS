# VAMS Architecture Addendum: v0.7.0 (Cognitive Layer Integration)

**Status:** Historical cognitive-layer milestone; implemented source with testnet restrictions
**Last verified:** 2026-07-12
**Replaces:** No prior sections deprecated. This is a **purely additive** addendum to [ARCHITECTURE_v0-6-0.md](./ARCHITECTURE_v0-6-0.md) and prior versions.
**Objective:** Formalize the integration of the off-chain VAMS Cognitive Layer (SIRA × HORMA × HIPIF × ProPlay) within the off-chain **Neuron Runtime** without touching compiled Solidity or Aiken smart contracts.

---

## 1. What Changed From v0.6.0

The v0.6.0 architecture integrated Polygon's Open Money Stack (OMS) for identity and payment rails. **v0.7.0 introduces the Cognitive Layer** to optimize memory navigation, task planning, and storage scaling under strict token context budgets.

| Subsystem | v0.6.0 Behavior | v0.7.0 Upgrade | Provenance |
|---|---|---|---|
| **Memory Search** | Flat Vector DB queries (Glacier VDB) | **SIRA Engine**: Single-shot dual-BM25 search with expected-response sketch query-expansion and Document Frequency (DF) pruning | `arXiv:2605.06647` |
| **Memory Layout** | Flat key-value and vector index arrays | **HORMA Filesystem**: Decoupled hierarchical directory layout mapping timestamped entities to raw trajectories | `arXiv:2606.11680` |
| **Context Compaction** | Monolithic logs or post-hoc summary truncation | **HIPIF Folding**: Compresses raw trial-and-error logs at subgoal boundaries into dense summaries; deletes original noisy traces | `arXiv:2606.10507` |
| **Task Planning** | Ad-hoc step reasoning kernels | **ProPlay World Model**: Directed procedure graph tracking transitional edge reliability embeddings to provide soft guidance | June 2026 Paper |
| **Memory Evolution** | Parameter state overwriting | **EvoMem Patches**: Append-only 4-tuple JSON patches recording memory transitions | `arXiv:2606.13681` |
| **Data Anchoring** | Automatic commits to Celestia DA | **V(m) Value Filter**: Consolidated 7-factor utility function filtering memory commits to prevent DA gas bloat | `arXiv:2606.12945` |

---

## 2. SIRA (Superintelligent Retrieval Agent) Search Primitive

### 2.1 Problem
Traditional agentic systems rely on vector search (flat RAG) or multi-round LLM agent loops to search directories. This introduces:
1. High token latency (waiting for multi-turn LLM loops).
2. Semantic bottlenecks where exact tokens (e.g. transaction hashes, method names) are lost in dense vector spaces.

### 2.2 SIRA Solution
We implement `SiraEngine` in `neuron/sdk/sira_engine.py` as a single-shot, dual-grouped BM25 retrieval engine:

1. **Expected-Response Sketch:** Generates query-side expansion terms ($q_{exp}$) using a fast LLM prediction.
2. **DF Pruning:** Filters expansion terms to drop hyper-common or absent words:
   \[
   0 < DF(t) \le \tau \cdot |C|
   \]
3. **Dual BM25 Scoring:** Ranks documents according to the dual-weighted formula:
   \[
   Score(d) = BM25(q_{orig}, d) + w \cdot BM25(q_{exp}, d)
   \]
   Where $w$ is a scalar balancing weight (default `1.2`) and $q_{orig}$ is the original search query.

---

## 3. HORMA Filesystem Memory Layout

### 3.1 Organization
Instead of storing memories in opaque vector spaces, the agent maps its long-term memory space (`MemoryTier.L3_STORAGE`) to a hierarchical directory structure under `.data/memory/`.

```
.data/memory/
├── workflows/
│   └── [workflow_type]/         # e.g., cross_chain_bridge, depin_matching
│       └── [entity_id]/         # e.g., token_pair, provider_id
│           ├── folded_summary.md
│           └── patches.jsonl
```

### 3.2 S-MMU Page Fault Navigation
When a query misses the L1 KV-cache and L2 RAM:
1. The S-MMU checks for the page at `.data/memory/{address}.json`.
2. If found, the page is loaded, integrity is verified via SHA-256 hash, and it is promoted through L2 to L1.
3. This decouples local disk reads from external network lookups, establishing sub-millisecond local retrievals.

---

## 4. HIPIF folding & EvoMem Patching

### 4.1 HIPIF Folding
During execution, the agent writes raw step logs to a temporary trace. Upon completing a subtask, the `fold_completed_subtask` hook is executed:
1. Summarizes the raw trace into a 10-line dense block capturing: Status, Step Count, Captured Errors, Transactions, and Outcomes.
2. Saves the summary as `folded_summary.md` in the HORMA layout.
3. Deletes the raw, token-heavy log trace.

### 4.2 EvoMem patches
When updating memory states (e.g., configurations, API changes), changes are recorded as 4-tuple JSON patches:
```json
{
  "previous_state": "...",
  "new_state": "...",
  "rationale_for_change": "...",
  "supporting_evidence": "..."
}
```
This preserves a chronological audit trail, preventing state collapse in dynamic environments.

---

## 5. ProPlay World Model Graph

The `ProPlayWorldModel` in `neuron/intelligence/world_model.py` maps nodes (high-level procedures) and edges (transitions).

1. **Reliability Edge Recording:** Every transition edge $(p_i, p_j)$ maintains a running history of rewards and intent vector embeddings representing past execution context.
2. **Suitability Score:** Calculated using cosine similarity of the current task intent vector against edge embeddings:
   \[
   s_{ij} = \text{Similarity}(\phi(intent), \phi(edge)) \cdot Reward
   \]
3. **Soft Guidance Planning:** Projects the highest-suitability transition path (via NetworkX or greedy fallback) and injects it into the prompt kernel as non-binding guidance:
   `"SOFT GUIDANCE PRIOR: Recommended procedural flow is: A -> B -> C"`

---

## 6. V(m) Consolidation Filter

Before writing state blocks to Celestia DA or L3 storage, memory utility value is scored:
\[
V(m) = 0.4 \cdot f_{util} + 0.3 \cdot f_{align} + 0.2 \cdot f_{size} + 0.1 \cdot f_{freq}
\]
Where:
- $f_{util}$ evaluates task success/failure.
- $f_{align}$ evaluates alignment and security constraints (GCA).
- $f_{size}$ evaluates text complexity.
- $f_{freq}$ evaluates task frequency.

If the value $V(m)$ fails to meet the configured threshold, the page is flagged or filtered to prevent state bloat and unnecessary transaction fees.
