# VAMS Node Operator Guide

**Audience:** Suppliers — GPU / bare-metal node operators
**Version:** v1.3.0-oms
**Prerequisites:** Familiarity with the [Developer Guide](./DEVELOPER_GUIDE.md) and
[Architecture v0.6.0](./team/ARCHITECTURE_v0-6-0.md)

> [!NOTE]
> This guide covers both the v1.2.0-autoskill Intelligence Layer (Sections 1–5) **and** the
> new v1.3.0-oms OMS integration (Sections 6–10: stablecoin payouts, enterprise RPCs, session
> keys, OMS identity). If you are upgrading from v1.2.0, jump directly to **Section 6**.

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
| VAMS Neuron | v1.3.0-oms |

```bash
pip install vams-neuron==1.3.0-oms
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

## 11. Related Documentation

| Document | Description |
|---|---|
| [INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md) | Full Intelligence Layer module API reference |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) | Developer onboarding (all personas) |
| [API_REFERENCE.md](./API_REFERENCE.md) | REST API including Intelligence Layer and OMS endpoints |
| [team/ARCHITECTURE_v0-6-0.md](./team/ARCHITECTURE_v0-6-0.md) | OMS integration architecture — all 5 phases |
| [role-management-keys.md](./role-management-keys.md) | YIELD_MANAGER_ROLE, OMS key rotation, session key expiry |
| [CHANGELOG.md](./CHANGELOG.md) | Full release history |

---

## 6. What Changed in v1.3.0-oms for Operators

| Area | Before v1.3.0 | After v1.3.0 |
|---|---|---|
| Reward currency | $VAMS only | $VAMS, USDC, or USDT (operator choice) |
| Chain RPC infrastructure | Public fallbacks | OMS enterprise RPCs for Polygon-ecosystem chains |
| Agent signing | Raw EOA for all operations | Session keys for payment ops; EOA for registration |
| Institutional routing (P3) | PLATINUM trust tier only | PLATINUM + OMS KYC/KYB (fail-closed) |
| TEE attestation binding | EOA | Unchanged — session keys do **not** affect TEE attestation |

**Required new environment variables:**

```bash
export OMS_API_KEY="<your_oms_api_key>"                      # OMS Console: polygon.technology/oms
export OMS_IDENTITY_API="https://api.oms.polygon.technology/identity"
export OMS_POLYGON_RPC_PRIMARY="https://oms.polygon.technology/rpc/polygon"
export OMS_POLYGON_RPC_SECONDARY="https://rpc2.oms.polygon.technology/rpc/polygon"
```

> [!CAUTION]
> Never commit `OMS_API_KEY` to version control. Use a secrets manager or
> a `.env` file excluded by `.gitignore`.

---

## 7. Stablecoin Payout Setup

By default, rewards are paid in `$VAMS`. You can opt-in to USDC/USDT at any time
using the `StablecoinPayoutManager`. This is reversible and takes effect on the next
`claimRewards()` call.

### Payout Modes

| Mode | Value | Description |
|---|---|---|
| `VAMS_ONLY` | 0 | 100% $VAMS (default) |
| `STABLECOIN` | 1 | 100% USDC or USDT via OMS rails |
| `HYBRID` | 2 | 50% $VAMS, 50% stablecoin |

### Python SDK (recommended)

```python
from neuron.payments.stablecoin_payout import StablecoinPayoutManager, PayoutMode
from web3 import Web3
import os

w3 = Web3(Web3.HTTPProvider(os.getenv("POLYGON_RPC")))

manager = StablecoinPayoutManager(
    web3=w3,
    reward_distributor_address="0x<REWARD_DISTRIBUTOR_ADDRESS>",
    private_key=os.getenv("OPERATOR_PRIVATE_KEY")
)

# Check current mode
current = manager.get_preference(manager.account.address)
mode_names = {0: "VAMS_ONLY", 1: "STABLECOIN", 2: "HYBRID"}
print(f"Current payout mode: {mode_names[current]}")

# Opt-in to 100% USDC/USDT
tx = manager.opt_in_to_stablecoin()
print(f"Set to STABLECOIN — tx: {tx}")

# Or opt-in to 50/50 split
tx = manager.opt_in_to_hybrid()
print(f"Set to HYBRID — tx: {tx}")

# Revert to $VAMS-only
tx = manager.set_preference(PayoutMode.VAMS_ONLY)
print(f"Reverted to VAMS_ONLY — tx: {tx}")
```

### REST API

```bash
curl -X POST https://<your-gateway>/api/v1/economics/payout-preference \
  -H "Content-Type: application/json" \
  -d '{
    "provider_address": "0xYOUR_ADDRESS",
    "mode": "STABLECOIN",
    "signature": "0x<EIP-712_signed_request>"
  }'
```

> **Note:** Stablecoin conversion uses OMS settlement rails. Output currency
> (USDC or USDT) is determined by the OMS liquidity pool at claim time.
> Both are ERC-20 on Polygon.

---

## 8. OMS Enterprise RPC Configuration

The `ChainOracle` in `neuron/chain_oracle.py` reads RPC URLs from environment
variables at startup. OMS enterprise endpoints for Polygon-ecosystem chains offer
99.9% SLA-backed uptime with per-endpoint latency monitoring tracked in
`ChainMetrics.rpc_latency_ms`.

### RPC Endpoint Map (v1.3.0)

| Chain | Env Variable | Default Value | OMS-Provided? |
|---|---|---|---|
| Polygon | `POLYGON_RPC` | `https://oms.polygon.technology/rpc/polygon` | ✅ Yes |
| Ethereum | `ETHEREUM_RPC` | `https://oms.polygon.technology/rpc/ethereum` | ✅ Yes |
| Arbitrum | `ARBITRUM_RPC` | `https://arb1.arbitrum.io/rpc` | ❌ Public |
| Base | `BASE_RPC` | `https://mainnet.base.org` | ❌ Public |
| Cardano | `CARDANO_RPC` | `https://cardano-mainnet.blockfrost.io/api/v0` | ❌ Blockfrost |
| Solana | `SOLANA_RPC` | `https://api.mainnet-beta.solana.com` | ❌ Public |
| SEI | `SEI_RPC` | `https://evm-rpc.sei-apis.com` | ❌ Public |
| Phala | `PHALA_RPC` | `https://phala.api.onfinality.io/public` | ❌ Public |
| Avalanche | `AVALANCHE_RPC` | `https://api.avax.network/ext/bc/C/rpc` | ❌ Public |

### Recommended `.env` additions

```env
# Override public defaults with OMS enterprise endpoints
POLYGON_RPC=https://oms.polygon.technology/rpc/polygon
ETHEREUM_RPC=https://oms.polygon.technology/rpc/ethereum

# Fallback (ChainOracle auto-uses cache if primary fails)
OMS_POLYGON_RPC_SECONDARY=https://rpc2.oms.polygon.technology/rpc/polygon

# Oracle cache TTL in seconds (default 30)
ORACLE_CACHE_TTL=30
```

### Verifying oracle health

```python
from neuron.chain_oracle import OracleManager, OracleStatus

oracle = OracleManager()
oracle.print_metrics_table()  # Prints Gas/Block/Congestion/SLA% for all 12 chains

# Per-chain status check
statuses = oracle.get_status()
for chain, status in statuses.items():
    icon = {"live": "✅", "stale": "⚠️", "offline": "❌"}.get(status.value, "?")
    m = oracle.get_metrics(chain)
    sla = f"{m.uptime_pct:.1f}%" if m else "N/A"
    print(f"{icon} {chain:12} SLA: {sla}")
```

A `stale=True` metric means the oracle returned cached data because the live RPC call
failed. The neuron continues operating (graceful degradation). If SLA% drops below
**95%** for an OMS enterprise endpoint, raise a ticket via the OMS Console.

---

## 9. Session Key Management

Session keys (Sequence ERC-4337) are automatically provisioned when your node registers.
You only need to understand scope limits and the revocation procedure.

### Value caps per TrustTier

| TrustTier | Max Value / Tx | Validity | Re-issue without root key? |
|---|---|---|---|
| BRONZE | 100 $VAMS | 24 h | Yes (up to 3 consecutive) |
| SILVER | 1,000 $VAMS | 24 h | Yes (up to 5 consecutive) |
| GOLD | 50,000 $VAMS | 24 h | Yes (with governance approval) |
| PLATINUM | Unlimited | 24 h | Yes (with governance approval) |

Value caps are enforced on-chain by the Sequence `EntryPoint` — a compromised session key
**cannot** exceed its cap regardless of the attacker's intent.

### Revoking a compromised session key (emergency)

```bash
# Must be signed by the root EOA (owner), not the session key itself
cast send <AGENT_REGISTRY_ADDRESS> \
  "setAuthorizedWallet(bytes32,address)" \
  <YOUR_AGENT_ID> \
  "0x0000000000000000000000000000000000000000" \
  --private-key $OPERATOR_PRIVATE_KEY \
  --rpc-url $POLYGON_RPC
```

> [!WARNING]
> After calling `setAuthorizedWallet(..., address(0))`, payment operations will
> fail until a new session key is provisioned. Restart the Neuron service to
> auto-provision a fresh one.

---

## 10. OMS Identity Verification (P3 Routing)

If your node handles **regulated or institutional payloads** via the P3 CLR path,
your operator address must pass OMS KYC/KYB verification. Without it, P3 routes
return `403` (fail-closed). Standard operators using P4–P6 routing are **not**
affected.

### Getting verified

1. Go to [polygon.technology/oms](https://polygon.technology/oms)
2. Complete the KYC/KYB flow for your operator address
3. OMS issues a verifiable credential — no further VAMS configuration is required
4. `OMSIdentityVerifier.is_verified(your_address)` returns `True` automatically

### Checking status locally

```python
from neuron.sdk.oms_identity import OMSIdentityVerifier

verifier = OMSIdentityVerifier()  # reads OMS_IDENTITY_API and OMS_API_KEY from env
result = verifier.is_verified("0xYOUR_OPERATOR_ADDRESS")
print(f"OMS verified: {result}")
```

> **Stub mode:** Until `OMS_API_KEY` is set to a real key from the OMS Console, the
> verifier uses a stub (addresses starting with `0x99` auto-verify). Set the real key
> before any production P3 routing.

### OMS API key rotation

Rotate `OMS_API_KEY` every **90 days**. See
[role-management-keys.md §5](./role-management-keys.md) for the full procedure.

Quick check after rotation:

```python
from neuron.sdk.oms_identity import OMSIdentityVerifier
v = OMSIdentityVerifier()
print('API URL:', v.api_url)
print('Real key set:', v.api_key != 'demo-key')
```

### Troubleshooting (OMS)

| Symptom | Likely Cause | Fix |
|---|---|---|
| P3 route returning `403` | `is_verified()` returning `False` | Check `OMS_API_KEY`; verify address at polygon.technology/oms |
| `demo-key` in logs | `OMS_API_KEY` not set | Set env var; verifier is in stub mode |
| `stale=True` for Polygon chain | OMS RPC unreachable | Check `OMS_POLYGON_RPC_PRIMARY`; oracle auto-falls-back to cache |
| Session key rejected | Expired (>24 h) or over value cap | Restart Neuron — auto-provisions new session key |
| `setAuthorizedWallet` tx fails | Caller is not agent owner | Use root EOA private key, not session key |
| Stablecoin payout not converting | OMS rails unavailable | Check OMS Console; rewards remain as $VAMS until rails recover |
| `payoutPreference` returns `0` | Not yet set | Call `opt_in_to_stablecoin()` or `opt_in_to_hybrid()` |


| Document | Description |
|---|---|
| [INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md) | Full module API reference |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) | Developer onboarding (all personas) |
| [API_REFERENCE.md](./API_REFERENCE.md) | REST API including Intelligence Layer endpoints |
| [team/ARCHITECTURE_v0-6-0.md](./team/ARCHITECTURE_v0-6-0.md) | Architecture addendum with data flow diagrams |
| [CHANGELOG.md](./CHANGELOG.md) | Full release history |
