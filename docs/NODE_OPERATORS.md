# VAMS Node Operator Guide

**Audience:** Suppliers — GPU / bare-metal node operators  
**Version:** v1.2.0-autoskill  
**Prerequisites:** Familiarity with the [Developer Guide](./DEVELOPER_GUIDE.md) and
[Architecture v0.5.0](./team/ARCHITECTURE_v0-5-0.md)

---

## Overview

As a **Supplier** in the VAMS network, you run a **Sentinel Node** on your hardware. The
Sentinel Node performs two jobs:

1. **Responds to audit challenges** issued by the network's Watchtower protocol
2. **Reports SLA compliance data** to the Data Availability layer for on-chain settlement

With v1.2.0-autoskill, the Sentinel Node optionally captures **model activation vectors**
during challenge responses and uses them to:

- Build a **skill profile** (behavioral fingerprint) for your node in the Composer registry
- Enable **activation-space anomaly detection** so the network can distinguish legitimate
  inference from adversarial or jailbroken responses

**Configuring the Intelligence Layer is optional but strongly recommended.** Nodes with
rich skill profiles receive higher `skill_alignment` scores from the Composer when
consumers specify skill vectors in blueprints, leading to more consistent allocation.

---

## 1. Installation

### Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.10 |
| numpy | ≥ 1.24 |
| scikit-learn | ≥ 1.3 |
| VAMS Neuron | v1.2.0-autoskill |

```bash
pip install vams-neuron==1.2.0-autoskill
```

### Verify Installation

```bash
python -c "from neuron.sentinel.sentinel_node import VAMSSentinelNode; print('OK')"
python -c "from neuron.intelligence.skill_discovery import SkillDiscovery; print('OK')"
```

---

## 2. Configuring a Basic Sentinel Node

The simplest configuration runs the Sentinel without Intelligence Layer features.
This is fully backward compatible with v1.0.0-icn behavior.

```python
# config/sentinel_config.py
import asyncio
from neuron.sentinel.sentinel_node import VAMSSentinelNode

node = VAMSSentinelNode(
    node_id="0xYOUR_NODE_ADDRESS",
    operator_key="0xYOUR_OPERATOR_PRIVATE_KEY",
    da_endpoint="https://your-da-gateway.vams.network",
    audit_interval_seconds=300,
    # No anomaly_detector = standard v1.0.0-icn behavior
)

asyncio.run(node.run_scheduler())
```

---

## 3. Enabling the Intelligence Layer

### Step 1: Configure Activation Capture

Set up an `ActivationCache` and wire it to your inference framework's forward hook.
The cache needs to be populated with real inference outputs before PCA fitting can begin.

```python
from neuron.intelligence.activation_cache import ActivationCache, ActivationMetadata
import numpy as np

# Size the cache for your hardware (10k samples × hidden_dim × 4 bytes)
# 10k × 4096 × 4 bytes ≈ 160 MB
cache = ActivationCache(buffer_size=10_000, hidden_dim=4096)

# Example: PyTorch forward hook integration
import torch

def make_activation_hook(cache, node_id, task_type):
    def hook(module, input, output):
        # For most transformer models, output is a tuple (hidden_state, ...)
        hidden = output[0] if isinstance(output, tuple) else output
        # Mean-pool the sequence dimension: (batch, seq, hidden) → (batch, hidden)
        pooled = hidden.mean(dim=1).detach().cpu().float().numpy()
        for vec in pooled:
            cache.append(
                vec,
                ActivationMetadata(
                    node_id=node_id,
                    task_type=task_type,
                    model_id="llama3-8b",
                )
            )
    return hook

# Register hook on the final transformer layer
# (Exact layer name depends on your model — use model.named_modules() to inspect)
hook_handle = model.model.layers[-1].register_forward_hook(
    make_activation_hook(cache, "0xYOUR_NODE_ADDRESS", "contract_audit")
)
```

> [!IMPORTANT]
> The hook shown above uses **mean-pooling** over the sequence dimension. The AUTOSKILL
> paper suggests the last token's hidden state may also be valid for causal models. Test
> both approaches and compare explained variance from `SkillDiscovery.get_explained_variance()`.
> Higher top-PC variance means a more informative skill decomposition.

### Step 2: Collect a Baseline (First-time Setup)

Before fitting the PCA model, collect at least **500 diverse challenge responses** across
all challenge types your node will encounter:

```python
# Run your node in "collection mode" for ~24 hours without anomaly detection
# This populates the cache with representative activations
print(f"Cache size: {cache.size} / {cache.buffer_size}")
```

A reasonable minimum is 1,000 samples per challenge type. For a node serving 3 challenge
types, collect 3,000+ samples total before fitting.

### Step 3: Fit the Skill Discovery Model

```python
from neuron.intelligence.skill_discovery import SkillDiscovery

# Retrieve all collected activations
activations = cache.get_activations()  # Returns all stored samples

# Fit the PCA skill model
discovery = SkillDiscovery(n_components=10, variance_threshold=0.90)
discovery.fit(activations)

# Inspect the result
stats = discovery.get_fit_stats()
print(f"Components fitted: {stats['n_components']}")
print(f"Total variance captured: {stats['total_variance_captured']:.2%}")
print(f"Components for 90% threshold: {stats['components_for_threshold']}")
# Example output:
# Components fitted: 10
# Total variance captured: 93.22%
# Components for 90% threshold: 8

# Save for reuse (avoids re-fitting on every restart)
discovery.save("models/skill_discovery_llama3.pkl")
print("Skill model saved.")
```

### Step 4: Set Up Anomaly Detection

```python
from neuron.intelligence.anomaly_detector import ActivationAnomalyDetector

# Initialize from the fitted SkillDiscovery model
# The detector auto-initializes its baseline from the PCA fit data
detector = ActivationAnomalyDetector(
    skill_model=discovery,
    default_threshold=3.0,   # 3-sigma: 99.7% of normal responses pass
)

# Optional: re-fit baseline from a hand-curated set of known-good responses
# This is recommended if your collection data contains any failed audits
good_activations = cache.get_activations(n=500)
detector.fit_baseline(good_activations)

print(f"Baseline fitted: {detector.is_baseline_fitted}")
```

### Step 5: Register with the Sentinel Node

```python
import asyncio
from neuron.sentinel.sentinel_node import VAMSSentinelNode
from neuron.intelligence.skill_discovery import SkillDiscovery
from neuron.intelligence.anomaly_detector import ActivationAnomalyDetector

# Load pre-fitted models (on restart, avoid re-fitting from scratch)
discovery = SkillDiscovery.load("models/skill_discovery_llama3.pkl")
detector = ActivationAnomalyDetector(discovery, default_threshold=3.0)

node = VAMSSentinelNode(
    node_id="0xYOUR_NODE_ADDRESS",
    operator_key="0xYOUR_OPERATOR_PRIVATE_KEY",
    da_endpoint="https://your-da-gateway.vams.network",
    audit_interval_seconds=300,
    anomaly_detector=detector,   # ← Enable Intelligence Layer
)

asyncio.run(node.run_scheduler())
```

---

## 4. Understanding Audit Reports

When the Intelligence Layer is enabled, every audit report submitted to the DA layer
includes two additional fields:

| Field | Type | Description |
|---|---|---|
| `activation_anomaly_score` | `float` | Mahalanobis distance from baseline centroid. Normal responses: < 3.0. |
| `adversarial_flag` | `bool` | `true` if `activation_anomaly_score > threshold` (default 3.0). |

**What happens when `adversarial_flag = true`?**

1. The DA-anchored report is flagged in the Sentinel ledger
2. The on-chain `SLAEnforcer` contract receives the flag in its settlement call
3. Repeated flags within a time window trigger a **slashing review** event
4. You (the node operator) are notified via the registered alert webhook

> [!CAUTION]
> Do not manually manipulate activation vectors to avoid anomaly detection. The
> AUTOSKILL paper demonstrates that adversarial subspaces are separable from
> normal inference patterns with high reliability. Manipulation attempts are
> likely to produce distinctive signatures that are _more_ anomalous, not less.

---

## 5. Understanding Skill Profiles

When a consumer specifies a `skill_vector` in their blueprint, the Composer uses your
node's registered skill profile to compute a **cosine similarity score** (`skill_alignment`).

Your skill profile is updated automatically after each audit round by the Sentinel Node.
To check your current profile:

```bash
# Via the Gateway API
curl -H "Authorization: Bearer <token>" \
  https://gateway.vams.network/api/v1/intelligence/skill-profile/0xYOUR_NODE_ADDRESS
```

```json
{
  "node_id": "0xYOUR_NODE_ADDRESS",
  "coordinates": [0.91, -0.14, 0.32, ...],
  "magnitude": 0.98,
  "dominant_skill": 0,
  "sample_count": 1024,
  "model_id": "llama3-8b"
}
```

**`dominant_skill: 0`** means PC0 (the highest-variance behavioral axis) is the most
prominent dimension of your node's behavior. This typically corresponds to the
primary reasoning modality the model excels at.

---

## 6. Performance & Resource Budget

| Operation | Cost | Frequency |
|---|---|---|
| Activation capture (hook) | ~0.1ms per inference | Every challenge response |
| `ActivationCache.append()` | ~0.05ms (ring buffer write) | Every challenge response |
| `AnomalyDetector.score_anomaly()` | ~1ms (PCA transform + Mahalanobis) | Every challenge response |
| `SkillDiscovery.fit()` (10k samples) | ~5-15 sec (one-time / periodic) | Monthly or on version bump |
| Memory for cache (10k × 4096 × float32) | ~160 MB | Constant |

The Intelligence Layer adds **< 2ms** of overhead per challenge response — well within the
50ms p99 SLA requirement.

---

## 7. Maintenance & Re-fitting Schedule

The PCA skill model should be re-fitted when:

1. **Model version changes** — A new model checkpoint will shift the activation distribution
2. **Monthly** — As the challenge distribution evolves, re-fitting keeps skills current
3. **After a fleet-wide model update** — Coordinate with the VAMS DevOps team

To re-fit without downtime:

```python
# 1. Fit the new model in the background (no service disruption)
new_discovery = SkillDiscovery(n_components=10)
new_discovery.fit(cache.get_activations())
new_discovery.save("models/skill_discovery_llama3_v2.pkl")

# 2. Atomic swap — the old model remains active until you restart the node
# 3. On next restart, load the new model file
```

---

## 8. Troubleshooting

### "RuntimeError: SkillDiscovery has not been fitted"
You loaded the Sentinel with `anomaly_detector` before fitting the `SkillDiscovery` model.
Either load an existing `.pkl` file or complete Steps 1–4 above before starting the node.

### Anomaly scores are consistently > 3.0 for normal responses
1. Check that `fit_baseline()` was called with **verified-good** activations (not all collected
   data — exclude any failed audit responses)
2. Try raising the threshold to `4.0` while you gather more data: `detector.default_threshold = 4.0`
3. Verify the activation hook is extracting the correct layer (final transformer layer output,
   not an intermediate layer or the LM head logits)

### Anomaly scores are consistently 0.0
Your activation vectors may all be identical or constant. Verify that:
1. The hook is registered on a layer that actually produces varying activations
2. The inference framework isn't caching / returning identical hidden states
3. `cache.size > 0` before fitting

### `skill_alignment_score` is very low (< 0.3) despite high SLA scores
Your node's skill profile may not match the consumer's requested skill vector. This is
normal — not all nodes have the same behavioral profile. Focus on challenge types that
align with your model's primary skill axis (`dominant_skill` in your profile).

---

## 9. Quick Reference

```bash
# Check current cache size
python -c "
from neuron.intelligence.activation_cache import ActivationCache
cache = ActivationCache.load('data/cache.npz')
print(f'Cache: {cache.size} samples')
"

# Fit skill model from saved cache
python -c "
import numpy as np
from neuron.intelligence.skill_discovery import SkillDiscovery
data = np.load('data/cache.npz')
discovery = SkillDiscovery(n_components=10)
discovery.fit(data['activations'])
discovery.save('models/skill_discovery.pkl')
print('Fitted and saved.')
"

# Check anomaly threshold
python -c "
from neuron.intelligence.skill_discovery import SkillDiscovery
from neuron.intelligence.anomaly_detector import ActivationAnomalyDetector
discovery = SkillDiscovery.load('models/skill_discovery.pkl')
detector = ActivationAnomalyDetector(discovery)
print(f'Threshold: {detector.default_threshold}')
print(f'Baseline fitted: {detector.is_baseline_fitted}')
"
```

---

## 10. Related Documentation

| Document | Description |
|---|---|
| [INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md) | Full module API reference |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) | Developer onboarding (all personas) |
| [API_REFERENCE.md](./API_REFERENCE.md) | REST API including Intelligence Layer endpoints |
| [team/ARCHITECTURE_v0-5-0.md](./team/ARCHITECTURE_v0-5-0.md) | Architecture addendum with data flow diagrams |
| [CHANGELOG.md](./CHANGELOG.md) | Full release history |
