# VAMS Intelligence Layer

**Module:** `neuron/intelligence/`  
**Version:** 0.1.0  
**Status:** Stable (v1.3.0-oms)  
**Paper Reference:** [AUTOSKILL: Characterizing Model-Native Skills](./papers/Characterizing%20Model-Native%20Skills.pdf)

---

## Overview

The **Intelligence Layer** is VAMS's AUTOSKILL-powered subsystem for understanding, monitoring, and
directing the internal behavior of AI inference nodes at the activation level.

Instead of treating node responses as black boxes, the Intelligence Layer decomposes them into
measurable **model-native skill axes** discovered through Principal Component Analysis (PCA) of
final-layer hidden states. These axes power three critical capabilities in the VAMS stack:

| Capability | VAMS Subsystem | Class |
|---|---|---|
| Capture raw model activations | All | `ActivationCache` |
| Discover latent skill directions | Intelligence Layer | `SkillDiscovery` |
| Flag adversarial node behavior | Sentinel | `ActivationAnomalyDetector` |
| Tune model behavior at inference time | Sentinel / Composer | `SteeringEngine` |

---

## Architecture

```
Model Inference
      │
      ▼
┌─────────────────┐
│  ActivationCache │  ← ring-buffer capture of final-layer hidden states
│  (ring buffer)   │
└────────┬────────┘
         │  numpy activations
         ▼
┌─────────────────┐
│  SkillDiscovery  │  ← IncrementalPCA extracts orthogonal skill directions
│  (PCA pipeline)  │
└────┬───────┬────┘
     │       │
     ▼       ▼
┌──────────┐  ┌─────────────┐
│ Anomaly  │  │  Steering   │
│ Detector │  │  Engine     │
│          │  │  h ← h+α·v  │
└────┬─────┘  └──────┬──────┘
     │               │
     ▼               ▼
 Sentinel         Sentinel /
 Audit Reports    Composer
```

---

## Module Reference

### `ActivationCache`

Thread-safe ring buffer that captures final-layer hidden states during model inference.

**Key design decisions:**
- **Non-blocking**: writes never stall the inference thread
- **Memory-bounded**: configurable ring buffer (default 10,000 samples)
- **Serializable**: exports to `.npz` for offline PCA fitting

```python
from neuron.intelligence.activation_cache import ActivationCache, ActivationMetadata

# Create a cache for a model with 4096-dimensional hidden states
cache = ActivationCache(buffer_size=10_000, hidden_dim=4096)

# Append a captured activation vector (from a forward hook)
meta = ActivationMetadata(
    node_id="node-0x1234",
    task_type="contract_audit",
    model_id="llama3-8b",
)
cache.append(activation_vector, meta)

# Retrieve the latest 1000 activations for PCA fitting
activations = cache.get_activations(n=1000)

# Export to disk for offline analysis
cache.export("activations.npz")
```

**API Summary:**

| Method | Description |
|---|---|
| `append(activation, metadata)` | Add a single activation to the buffer |
| `get_activations(n)` | Get the latest `n` activation vectors |
| `export(path)` | Save buffer to `.npz` |
| `load(path)` | Load from `.npz` |
| `clear()` | Reset the ring buffer |
| `size` *(property)* | Number of samples currently stored |

---

### `SkillDiscovery`

PCA pipeline that extracts orthogonal **model-native skill directions** from cached activations.
Each principal component (PC) represents a latent behavioral axis — for example, PC1 might
capture symbolic reasoning vs. conceptual reasoning, as described in the AUTOSKILL paper.

**Key design decisions:**
- Uses `sklearn.decomposition.IncrementalPCA` for streaming compatibility
- Fits in batches — does not require loading the entire activation set into memory
- Saves fitted model as `.pkl` for session persistence

```python
from neuron.intelligence.skill_discovery import SkillDiscovery

# Fit on 10,000 captured activation vectors
discovery = SkillDiscovery(n_components=10, variance_threshold=0.90)
discovery.fit(activations)  # activations: (10000, 4096)

# Inspect discovered skill directions
skill_vectors = discovery.get_skill_vectors()  # shape: (10, 4096)
variance = discovery.get_explained_variance()   # e.g., [0.32, 0.18, 0.12, ...]

# Project a new activation onto skill space
skill_coords = discovery.transform(new_activation)  # shape: (10,)

# Compute a node's skill fingerprint
profile = discovery.compute_skill_profile(node_activations, node_id="node-0x1234")
print(profile.dominant_skill)  # e.g., 0 = PC1 is strongest

# Measure alignment between two skill profiles
alignment = discovery.compute_skill_alignment(profile_a.coordinates, profile_b.coordinates)
# Returns value in [0.0, 1.0] — 1.0 = perfectly aligned

# Persist and reload
discovery.save("models/skill_discovery_llama3.pkl")
loaded = SkillDiscovery.load("models/skill_discovery_llama3.pkl")
```

**API Summary:**

| Method | Description |
|---|---|
| `fit(activations)` | Fit PCA on `(N, hidden_dim)` activation array |
| `transform(activations)` | Project to skill space |
| `inverse_transform(coords)` | Reconstruct from skill space |
| `get_skill_vectors()` | Get all PC direction vectors `(n_components, hidden_dim)` |
| `get_skill_vector(index)` | Get a single PC direction |
| `get_explained_variance()` | Per-component explained variance ratio |
| `compute_skill_profile(activations, node_id)` | Get a node's skill fingerprint |
| `compute_skill_alignment(profile_a, profile_b)` | Cosine similarity `[0, 1]` |
| `save(path)` / `load(path)` | Persist / reload the fitted model |
| `is_fitted` *(property)* | Whether the model has been fitted |

---

### `ActivationAnomalyDetector`

Detects adversarial or degraded node behavior by measuring how far a new activation deviates
from the learned "normal" manifold in PCA-projected skill space.

**Theory:** The AUTOSKILL paper (Section 4) demonstrates that jailbreak and adversarial
activations cluster in distinguishable subspaces. The Mahalanobis distance from the normal
cluster centroid is an effective, low-cost classifier across 32 attack types tested.

**Key design decisions:**
- Operates in **PCA skill space** (not raw hidden state space) for better signal-to-noise
- 3-sigma threshold (`default_threshold=3.0`) classifies 99.7% of normal data as benign
- Can self-initialize from the `SkillDiscovery` model's precomputed centroid

```python
from neuron.intelligence.anomaly_detector import ActivationAnomalyDetector

# Initialize with a fitted SkillDiscovery model
detector = ActivationAnomalyDetector(skill_model=discovery, default_threshold=3.0)

# Fit the baseline on known-good activations (e.g., from verified audits)
detector.fit_baseline(normal_activations)

# Score a new activation
score = detector.score_anomaly(new_activation)  # Mahalanobis distance
print(f"Anomaly score: {score:.3f}")  # > 3.0 = likely adversarial

# Binary classification
if detector.is_adversarial(new_activation):
    # Flag for slashing review
    ...

# Detailed report with per-component breakdown
report = detector.get_anomaly_report(new_activation)
print(report.to_dict())
# {
#   "mahalanobis_distance": 4.21,
#   "anomaly_score": 0.82,
#   "is_adversarial": true,
#   "threshold": 3.0,
#   "most_anomalous_component": 2,
#   "reconstruction_error": 0.043
# }

# Batch scoring
scores = detector.score_anomaly_batch(batch_activations)  # shape: (N,)
```

**API Summary:**

| Method | Description |
|---|---|
| `fit_baseline(normal_activations)` | Establish normal distribution from verified responses |
| `score_anomaly(activation)` | Mahalanobis distance from baseline |
| `score_anomaly_batch(activations)` | Batch version |
| `is_adversarial(activation, threshold)` | Binary: exceeds threshold? |
| `get_anomaly_report(activation, threshold)` | Full `AnomalyReport` breakdown |
| `is_baseline_fitted` *(property)* | Whether baseline is ready |
| `default_threshold` *(property)* | Get/set the classification threshold |

---

### `SteeringEngine`

Applies PCA-discovered skill direction vectors as **additive biases** to model hidden states,
enabling fine-grained behavioral tuning at inference time without retraining.

**Formula (from AUTOSKILL Paper, Section 3.2):**
```
h_steered = h_original + α · v_skill
```
Where `α` (alpha) controls the steering strength and `v_skill` is a unit-normalized
PC direction vector.

**VAMS use cases:**
- **Amplify**: Enhance "security analysis" skill for Sentinel audit challenges
- **Suppress**: Reduce "verbose reasoning" for latency-sensitive inference tasks
- **Compose**: Combine multiple skill directions simultaneously

**Safety guarantees:**
- `max_alpha` is hard-capped (default `0.3`; paper tests up to `0.5`) — values above `0.5` risk capability degradation
- All steering vectors are unit-normalized before application
- Pre/post-steering norm drift is tracked in engine statistics

```python
from neuron.intelligence.steering_engine import SteeringEngine

# Initialize with a fitted SkillDiscovery model
engine = SteeringEngine(skill_model=discovery, max_alpha=0.3)

# Steer a single activation (amplify skill 0 = security analysis)
steered = engine.steer(activation, skill_index=0, alpha=0.2)

# Steer a batch
steered_batch = engine.steer_batch(activations, skill_index=0, alpha=0.2)

# Apply multiple steering directions simultaneously
spec = [
    {"skill_index": 0, "alpha": 0.2},   # +security analysis
    {"skill_index": 1, "alpha": -0.1},  # -verbose reasoning
]
steered = engine.steer_multi(activation, spec)

# Pre-compute a steering vector for repeated use
vec = engine.create_steering_vector(skill_index=0, alpha=0.2)
steered = activation + vec  # equivalent to steer()

# Estimate impact without applying
impact = engine.estimate_impact(activation, skill_index=0, alpha=0.2)
# {
#   "norm_change_pct": 1.23,
#   "cosine_shift": 0.0034,
#   "projection_before": -0.12,
#   "projection_after": 0.08
# }

# Check engine stats
print(engine.get_stats())
# {"max_alpha": 0.3, "n_skill_directions": 10, "total_steerings": 512, "avg_drift_pct": 0.82}
```

**API Summary:**

| Method | Description |
|---|---|
| `steer(activation, skill_index, alpha)` | Apply steering to single activation |
| `steer_batch(activations, skill_index, alpha)` | Batch version |
| `steer_multi(activation, steering_spec)` | Apply multiple directions |
| `create_steering_vector(skill_index, alpha)` | Pre-compute bias vector |
| `create_composite_vector(steering_spec)` | Pre-compute multi-direction bias |
| `estimate_impact(activation, skill_index, alpha)` | Dry-run impact analysis |
| `get_stats()` | Engine usage statistics |
| `max_alpha` *(property)* | Safety cap on alpha |
| `n_skill_directions` *(property)* | Number of available skill axes |

---

## Integration with Sentinel

The `ActivationAnomalyDetector` is integrated into `VAMSSentinelNode.audit_node()`. When
configured, it enriches audit reports with activation-space analysis:

```python
# sentinel_node.py (simplified)
report = await self.execute_challenge(node_id, challenge_type)

if self.anomaly_detector and report.get("activation_vector"):
    activation = np.array(report["activation_vector"])
    full_report = self.anomaly_detector.get_anomaly_report(activation)

    report["activation_anomaly_score"] = full_report.mahalanobis_distance
    report["adversarial_flag"] = full_report.is_adversarial
```

The `adversarial_flag` field in the DA-anchored audit report is consumed downstream by the
on-chain `SLAEnforcer` contract for slashing decisions.

---

## Integration with Composer

The `CandidateScorer` uses cosine similarity between a blueprint's `skill_vector` and each
candidate node's `skill_profile` as a 5th scoring dimension:

```python
# Request compute optimized for security analysis tasks
blueprint = composer.request_blueprint(
    target_region="us-east",
    requirements=["gpu:a100"],
    max_cost_vams="100.0",
    skill_vector=[0.92, -0.12, 0.34, ...]  # PC coordinates for security analysis
)
```

The `skill_alignment` scorer weight defaults to `0.0` for full backward compatibility —
existing integrations that don't set `skill_vector` are completely unaffected.

---

## Safety Considerations

| Risk | Mitigation |
|---|---|
| Catastrophic model degradation from high-alpha steering | Hard `max_alpha` cap (default `0.3`) |
| Direction instability | All skill vectors are unit-normalized |
| False positive adversarial flags in Sentinel | Tunable Mahalanobis threshold (default `3.0` = 3-sigma) |
| PCA model staleness as node fleet evolves | Periodic re-fitting recommended (see Open Questions) |

---

## FAQ

**Q: Does the Intelligence Layer require PyTorch?**  
A: No. The `ActivationCache` is framework-agnostic — it accepts raw numpy arrays. Node clients
are responsible for extracting activations from whatever inference framework they use (PyTorch,
vLLM, etc.) before passing them to the cache.

**Q: How many samples are needed to fit a reliable PCA model?**  
A: The AUTOSKILL paper demonstrates that 1,000 pilot fine-tuning samples are sufficient to
identify stable principal components. For VAMS, we recommend collecting activations from
at least 500 diverse audit challenge responses before fitting.

**Q: What happens if I call `steer()` with an `alpha` above `max_alpha`?**  
A: The engine automatically clamps the value to `max_alpha` and logs a warning. The steered
activation is returned using the clamped value — no exception is raised.

**Q: Can the AnomalyDetector be used without first calling `fit_baseline()`?**  
A: If the `SkillDiscovery` model was fitted with data (which pre-computes a centroid and
covariance), the detector will auto-initialize from those values. Otherwise, calling any
scoring method before `fit_baseline()` raises a `RuntimeError`.

**Q: Where does the "skill_vector" in a blueprint come from?**  
A: It is the PCA-projected skill profile of a reference node or task type. You can derive it
by running `skill_discovery.compute_skill_profile(reference_activations).coordinates`.
