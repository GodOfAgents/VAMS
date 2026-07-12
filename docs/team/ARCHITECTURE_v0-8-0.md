# VAMS Architecture Addendum: v0.8.0 (CHC Cognitive Spec & 6-Axis Scorer)

**Status:** Hardened Pre-Testnet Candidate
**Last verified:** 2026-07-12
**Replaces:** No prior sections deprecated. This is a **purely additive** addendum to [ARCHITECTURE_v0-7-0.md](./ARCHITECTURE_v0-7-0.md) and prior versions.
**Objective:** Formalize the integration of the **Cattell-Horn-Carroll (CHC) Cognitive scoring framework** and the **6-Axis Composer Scoring Engine** in the off-chain **Neuron Composer Runtime** and the **Gateway Telemetry Server**.

---

## 1. What Changed From v0.7.0

While v0.7.0 introduced memory hierarchies, context folding, and the ProPlay world model, **v0.8.0 solves the "agent amnesia" bottleneck** by introducing verified cognitive capabilities, dynamic weight normalization, and a real-time Decagon visualization dashboard in the frontend.

| Subsystem | v0.7.0 Behavior | v0.8.0 Upgrade | Provenance |
|---|---|---|---|
| **Scoring Axes** | 5-axis ranking (Price, SLA, Latency, Regional, Skills) | **6-axis scoring engine**: Adds cognitive alignment as a first-class metric | `scorer.py` |
| **Cognitive Metric** | None | **CHC Shortfall Formula**: Measures distance between requested ability thresholds and reported node capabilities | `scorer.py` |
| **Weights Normalization** | Static weights summing to 1.0 (requires manual recalibration) | **Dynamic Self-Scaling Normalization**: Re-allocates 10% to skills and 10% to cognitive requirements when present, scaling remaining axes proportionally | `scorer.py` |
| **Node Telemetry** | Basic heartbeats exposing online status and blocks | **Enriched Telemetry**: Heartbeats transmit region, cost, credit score, TEE passports, skills, and CHC profiles | `server.py` |
| **Frontend UI** | Table-based active nodes registry list | **Split-Screen Registry & Radar Chart**: Interactive SVG radar chart visualizing the 10 CHC domains (Decagon Graph) | `App.jsx` |

---

## 2. CHC Decagon Framework

The **Cattell-Horn-Carroll (CHC) framework** defines 10 distinct cognitive abilities mapped to DePIN hardware resources and agent software workloads, replacing single-dimensional skill vectors:

| Axis | Ability | Description / DePIN Mapping |
| :--- | :--- | :--- |
| **`K`** | General Knowledge | Depth of LLM parameters, model weights quality |
| **`RW`** | Reading/Writing | Syntax parsing, structured output verification (JSON/YAML) |
| **`M`** | Mathematical | Arithmetic reasoning, floating-point GPU throughput |
| **`R`** | Fluid Reasoning | Planning, multi-hop decision loops, OOD generalization |
| **`WM`** | Working Memory | Attention retention, context window size and stability |
| **`MS`** | Memory Storage | Semantic vector indexing, long-term DBOS checkpoints |
| **`MR`** | Memory Retrieval | Haystack retrieval efficiency, cache latency |
| **`V`** | Visual | Multimodal vision models, OCR, rendering |
| **`A`** | Auditory | Audio transcription, speech synthesis |
| **`S`** | Speed | Hardware throughput, tokens-per-second, processing latency |

---

## 3. 6-Axis Composer Scoring Engine

The matching engine ranks candidate nodes against an `InstanceBlueprint` using a composite score derived from 6 independent dimensions.

### 3.1 Composite Score Calculation

The final score for a candidate node is defined as:

\[
\text{Score}_{\text{composite}} = w_{\text{price}} \cdot S_{\text{price}} + w_{\text{sla}} \cdot S_{\text{sla}} + w_{\text{latency}} \cdot S_{\text{latency}} + w_{\text{regional}} \cdot S_{\text{regional}} + w_{\text{skill}} \cdot S_{\text{skill}} + w_{\text{cog}} \cdot S_{\text{cog}}
\]

### 3.2 Default Weights Allocation

When no skill vectors or cognitive requirements are requested by a blueprint, the engine preserves backward compatibility with standard 4-axis scoring:

*   Price (\(S_{\text{price}}\)): `0.35`
*   SLA (\(S_{\text{sla}}\)): `0.30`
*   Latency (\(S_{\text{latency}}\)): `0.20`
*   Regional (\(S_{\text{regional}}\)): `0.15`
*   Skill Alignment (\(S_{\text{skill}}\)): `0.00`
*   Cognitive Alignment (\(S_{\text{cog}}\)): `0.00`

If the blueprint defines requirements, the weights are dynamically adjusted as described in Section 4.

---

## 4. Mathematical Primitives & Algorithms

### 4.1 Cognitive Shortfall Formula

The cognitive alignment score \(S_{\text{cog}}\) measures how well a node satisfies the minimum requirements requested in a blueprint. If a requirement is not met, the shortfall is penalized; exceeding a requirement does not grant additional score.

Let \(D_{\text{req}}\) be the set of cognitive dimensions requested by the blueprint, \(\text{Req}_d\) be the minimum requested value for dimension \(d \in D_{\text{req}}\), and \(\text{Profile}_d\) be the node's capability value. The shortfall score is:

\[
S_{\text{cog}} = 1.0 - \frac{1}{|D_{\text{req}}|} \sum_{d \in D_{\text{req}}} \max\left(0.0, \text{Req}_d - \text{Profile}_d\right)
\]

If a candidate node provides no cognitive profile but the blueprint has cognitive requirements, \(S_{\text{cog}} = 0.0\). If no cognitive requirements are defined, \(S_{\text{cog}} = 1.0\).

### 4.2 Dynamic Weights Normalization Algorithm

To preserve backward compatibility with existing tests and static configs while allocating weights to new dimensions on-demand, the engine implements a self-scaling normalization algorithm:

1. Let \(w_{\text{base}} = [w_{\text{price}}, w_{\text{sla}}, w_{\text{latency}}, w_{\text{regional}}]\) be the configured base weights (summing to 1.0).
2. If the blueprint has `skill_vector` requirements, set \(w_{\text{skill}} = 0.10\); otherwise \(w_{\text{skill}} = 0.00\).
3. If the blueprint has `cognitive_requirements`, set \(w_{\text{cog}} = 0.10\); otherwise \(w_{\text{cog}} = 0.00\).
4. The remaining weight budget is \(R = 1.0 - (w_{\text{skill}} + w_{\text{cog}})\).
5. The non-alignment base weights are scaled by:
   \[
   \text{Scale} = \frac{R}{\sum w_{\text{base}}}
   \]
6. The adjusted weights are:
   \[
   w'_i = w_i \cdot \text{Scale} \quad \text{for } i \in \{\text{price}, \text{sla}, \text{latency}, \text{regional}\}
   \]
7. The normalized weights sum exactly to 1.0:
   \[
   \sum w' + w_{\text{skill}} + w_{\text{cog}} = 1.0
   \]

---

## 5. Telemetry & Frontend Registry Dashboard

### 5.1 Enriched Heartbeat Payload

Node telemetry heartbeats sent to `POST /api/v1/heartbeat` are structured as signed JSON payloads containing the full NodeInfo data:

```json
{
  "node_id": "node_01",
  "public_key": "0xabc...",
  "last_block": 104230,
  "network": "Amoy",
  "region": "us-east-1",
  "cost_per_hour": 0.15,
  "credit_score": 750,
  "passports": "ERC-8004 Phala TEE",
  "skills": ["llm-inference", "vector-db-ops"],
  "cognitive_profile": {
    "K": 0.85, "RW": 0.90, "M": 0.75, "R": 0.80, "WM": 0.85, "MS": 0.95, "MR": 0.90, "V": 0.50, "A": 0.30, "S": 0.70
  }
}
```

### 5.2 Split-Screen Telemetry Registry

The Vite frontend (`frontend-vite/src/App.jsx`) is configured with a split-screen layout:
1. **Active Nodes Registry (Left Panel):** Displays real-time heartbeat statuses, TEE passport verifications, credit scores, and region badges.
2. **Agent Profile Detail & Radar Chart (Right Panel):** When a node is selected, its CHC cognitive profile is rendered as an interactive SVG radar chart mapping coordinates along 10 axes:
   \[
   x_i = x_{\text{center}} + r \cdot \text{Profile}_i \cdot \cos\left(\frac{2\pi \cdot i}{10} - \frac{\pi}{2}\right)
   \]
   \[
   y_i = y_{\text{center}} + r \cdot \text{Profile}_i \cdot \sin\left(\frac{2\pi \cdot i}{10} - \frac{\pi}{2}\right)
   \]
   Where \(r\) is the maximum radius (`120px`) and \(\text{Profile}_i\) is the value of the \(i\)-th CHC dimension.
