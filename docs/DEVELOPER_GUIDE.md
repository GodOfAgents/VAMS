# VAMS Developer Onboarding Guide

Welcome to the Verifiable and Agentic Modular Stack (VAMS). This guide covers the v1.3.0-oms release, which integrates the Polygon Open Money Stack (OMS) into the modular stack.

## What is VAMS?
VAMS is the "Sovereign Brain" for the Agentic Web. Instead of running your AI agents on centralized AWS servers where they can be de-platformed, or on slow blockchains where they can't afford gas, VAMS provides a verifiable, fast, and multi-provider computation layer.

---

## 1. Building as an Agent Developer (Consumer)

If you are building an AI agent (e.g., a DeFi trading bot, a research assistant), you are a **Consumer** of the VAMS network.

### Step 1: Install the SDK
```bash
pip install vams-sdk==1.3.0-oms
```

### Step 2: Define your Intent
Instead of manually renting GPUs on Akash or io.net, use the **Resource Composer**.

```python
from vams.composer import VAMSComposer
from vams.auth import VAMSAgentProtocol

auth = VAMSAgentProtocol(api_key="your_key")
composer = VAMSComposer(auth)

# Define your infrastructure needs
# Optional: include skill_vector to match nodes proficient in a specific task type.
# Omit it entirely for standard 4-axis scoring (backward compatible with v1.0.0-icn).
blueprint = composer.request_blueprint(
    target_region="us-east",
    requirements=["gpu:a100", "memory:64gb"],
    max_cost_vams="100.0",  # Max 100 $VAMS per hour
    skill_vector=[0.92, -0.12, 0.34, 0.05, -0.21, 0.0, 0.0, 0.0, 0.0, 0.0]  # Optional
)

print(f"Got Blueprint -> {blueprint.id}")
```

### Step 3: Fund the Escrow
Fund the Master Hybrid Escrow for your generated blueprint. This protects you: if the provider goes offline, the escrow refunds the unspent portion automatically.

```python
from vams.economics import EscrowManager

escrow = EscrowManager(auth)
allocation_id = escrow.lock_funds(blueprint.id, duration_hours=24)
```

### Step 4: Execute!
Your agent is now live on the decentralized infrastructure stack. VAMS' Sentinel Network will constantly monitor the SLA of the provider.

---

## 2. Building as a DevOps Engineer (Builder)

If you are a DevOps engineer or infrastructure architect, you are a **Builder**. You package execution environments into **Service Blocks**.

### What is a Service Block?
A Service Block is a reusable infrastructure template (e.g., a Docker container running Llama 3 with a specific ZK-Proof wrapper).

### Step 1: Register your Service Block
You must stake $VAMS to register a block to prevent spam.

```solidity
// In your Hardhat/Foundry console
ServiceBlockRegistry.registerServiceBlock(
    "DeepSeek R1 + TDX Wrapper",
    "ai-inference",
    "High security inference block",
    resourceHash,
    "ipfs://...",
    500, // 5% Revenue Share on all usage!
    3    // Minimum Trust Tier required
);
```

### Step 2: Earn Yield
Whenever an Agent Developer's Resource Composer selects your Service Block, the Escrow contract automatically routes your 5% revenue share directly to your wallet!

---

## 3. Operating as a Node Provider (Supplier)

If you own GPUs or server racks, you are a **Supplier**. See **[NODE_OPERATORS.md](./NODE_OPERATORS.md)**
for full instructions on installing the VAMS Sentinel node client, enabling the Intelligence Layer,
captaining Regional DEC emissions, and understanding the Mahalanobis anomaly scoring system.

---

## 4. Working with the Intelligence Layer (v1.2.0+)

The Intelligence Layer is relevant to all three personas above:
- **Consumers** can filter nodes by skill alignment when creating blueprints
- **Builders** can package skill-optimized Service Blocks (targeting specific PC skill axes)
- **Suppliers** must configure activation capture correctly to build skill profiles

### Quick-start: Discovering Skill Axes

```python
from neuron.intelligence.activation_cache import ActivationCache, ActivationMetadata
from neuron.intelligence.skill_discovery import SkillDiscovery
from neuron.intelligence.anomaly_detector import ActivationAnomalyDetector
from neuron.intelligence.steering_engine import SteeringEngine
import numpy as np

# Step 1 — Capture activations from your model's inference loop
#            (replace with your actual forward hook output)
cache = ActivationCache(buffer_size=5000, hidden_dim=4096)
for activation in your_inference_activations:  # numpy arrays
    cache.append(activation, ActivationMetadata(node_id="my-node", task_type="security"))

# Step 2 — Discover skill directions
discovery = SkillDiscovery(n_components=10)
discovery.fit(cache.get_activations(n=2000))
discovery.save("models/skill_discovery.pkl")

print("Top variance per skill axis:", discovery.get_explained_variance()[:3])
# e.g., [0.32, 0.18, 0.12]

# Step 3 — Set up anomaly detection
detector = ActivationAnomalyDetector(discovery, default_threshold=3.0)
detector.fit_baseline(cache.get_activations(n=1000))

# Step 4 — Score a new activation
new_act = np.random.randn(4096).astype(np.float32)
report = detector.get_anomaly_report(new_act)
print(f"Anomaly score: {report.mahalanobis_distance:.2f} — adversarial: {report.is_adversarial}")

# Step 5 — Steer a model response toward a known skill direction
engine = SteeringEngine(discovery, max_alpha=0.3)
steered_activation = engine.steer(new_act, skill_index=0, alpha=0.2)
```

For the full API reference, see **[INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md)**.

### Integrating Skill Vectors into Blueprints

To request nodes with a specific skill profile, compute a reference skill vector first:

```python
# Compute a reference skill vector from audited high-quality responses
reference_activations = cache.get_activations(n=500)  # from known-good responses
profile = discovery.compute_skill_profile(reference_activations, node_id="reference")

# Use this vector when creating blueprints
blueprint = composer.request_blueprint(
    ...
    skill_vector=profile.coordinates.tolist()
)
```
---
 
 ## 5. OMS Integration (v1.3.0+)
 
 The Polygon Open Money Stack (OMS) integration provides institutional-grade identity, fiat on-ramps, and high-frequency signing capabilities.
 
 ### Step 1: Use Sequence Session Keys
 For autonomous agents performing high-frequency actions, use a **Session Key**. This prevents the need for a primary EOA to be online for every transaction.
 
 ```python
 from vams.sdk.signer import SessionKeySigner
 from vams.sdk.sequence_wallet import SequenceWalletManager
 
 # 1. Initialize the wallet manager
 manager = SequenceWalletManager(project_key="your_project_key")
 
 # 2. Create an ephemeral session key
 signer = SessionKeySigner(manager)
 session_key = signer.get_address()
 
 # 3. Authorize the session key on-chain (one-time setup via EOA)
 # agent_registry.setAuthorizedWallet(session_key)
 
 # 4. Sign transactions with the session key
 signature = signer.sign_message("Agent operation payload")
 ```
 
 ### Step 2: Setting Payout Preferences (USDC/USDT)
 Node providers can opt-in to stablecoin rewards directly via the SDK.
 
 ```python
 from vams.payments import StablecoinPayoutManager
 
 payout_manager = StablecoinPayoutManager(auth)
 payout_manager.set_preference(
     provider_id="0x123...",
     mode="STABLE_USDC"  # Options: NATIVE, STABLE_USDC, STABLE_USDT
 )
 ```
 
 ### Step 3: Institutional Routing (P3)
 To access high-security, compliant infrastructure (P3 routing), agents must pass an **OMS Identity** check.
 
 ```python
 from vams.sdk.oms_identity import OMSIdentityVerifier
 
 verifier = OMSIdentityVerifier(api_url="https://api.oms.polygon.technology/identity")
 if verifier.is_verified("0x123..."):
     print("Address is KYC-verified. P3 routing enabled.")
 else:
     print("Address requires KYC. Falling back to P2 routing.")
 ```
 
 ### Step 4: Fiat Top-up via Coinme
 Fund your agent account using fiat (credit card/debit) via the integrated Coinme rails.
 
 ```python
 from vams.payments import UniversalTopUp
 
 topup = UniversalTopUp(auth)
 topup_link = topup.request_fiat_onramp(
     amount_fiat=100.0,
     currency="USD",
     method="credit_card"
 )
 print(f"Complete top-up here: {topup_link}")
 ```

---

## 6. Working with Durable Workflows (DBOS)

The VAMS Neuron integrates the DBOS Python SDK to execute exactly-once, crash-safe workflows backed by PostgreSQL. This completely replaces the legacy SQLite checkpoint system.

For complete documentation on setting up Postgres and writing durable steps, see:
- **[WORKFLOW_ENGINE.md](../neuron/docs/WORKFLOW_ENGINE.md)**
