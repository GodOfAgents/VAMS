# VAMS Developer Onboarding Guide

**Lifecycle:** Current implementation guide
**Last verified:** 2026-07-12

> This guide describes source-level capabilities. It does not authorize
> mainnet, public-testnet, fiat, yield, or wallet-transaction use.

Welcome to the Verifiable and Agentic Modular Stack (VAMS). The v1.3.0-oms
label is a historical integration milestone; v0.8.0 is the current architecture
version. OMS, Coinme, Trails, and related SDK paths remain mock-default or
live-evidence-pending and must fail closed outside local development.

## What is VAMS?
VAMS is the "Sovereign Brain" for the Agentic Web. Instead of running your AI agents on centralized AWS servers where they can be de-platformed, or on slow blockchains where they can't afford gas, VAMS provides a verifiable, fast, and multi-provider computation layer.

---

## 1. Building as an Agent Developer (Consumer)

If you are building an AI agent (e.g., a DeFi trading bot, a research assistant), you are a **Consumer** of the VAMS network.

### Step 1: Install the Neuron Package Dependencies
```bash
python -m pip install -r neuron/requirements.txt
```

### Step 2: Define your Intent
from neuron.composer.composer import VAMSResourceComposer
from neuron.composer.models import InstanceBlueprint, ComputeSpec, MemorySpec, StorageSpec, NetworkSpec, GPUType

composer = VAMSResourceComposer()

# Define your infrastructure needs
blueprint = InstanceBlueprint(
    name="my-custom-blueprint",
    compute=ComputeSpec(gpu_type=GPUType.A100, gpu_count=1, vcpu=4),
    memory=MemorySpec(ram_gb=64),
    storage=StorageSpec(capacity_gb=100),
    networking=NetworkSpec(region="us-east"),
    max_cost_per_hour=100.0,  # Max 100 $VAMS per hour
    skill_vector=[0.92, -0.12, 0.34, 0.05, -0.21, 0.0, 0.0, 0.0, 0.0, 0.0]  # Optional PCA coordinates
)

# Provision the blueprint using the matchmaking composer
instance = composer.provision(blueprint)

print(f"Got Instance -> {instance.instance_id}")
print(f"Total Hourly Cost -> {instance.allocation.total_hourly_cost} $VAMS")
```

### Step 3: Fund the Escrow
Fund the Master Hybrid Escrow for your generated allocation. This protects you: if the provider goes offline, the escrow refunds the unspent portion automatically. To do this, retrieve the structured parameters from the composer and submit them to the on-chain `ComposedSettlement` contract:

```python
# Generate the parameters required for a ComposedSettlement.createComposedEscrow() call
escrow_params = composer.get_escrow_params(
    plan=instance.allocation,
    blueprint=blueprint,
    duration_seconds=86400  # duration_hours=24
)
print("Escrow parameters for contract execution:", escrow_params)

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
    IServiceBlockRegistry.ServiceBlockRegistration({
        name: "DeepSeek R1 + TDX Wrapper",
        category: "ai-inference",
        description: "High security inference block",
        resourceRequirementsHash: resourceHash,
        deploymentCID: "celestia://vams-ns/blob123",
        revenueShareBps: 500, // 5% Revenue Share on all usage!
        minTrustTier: 3,      // Minimum Trust Tier required
        manifest: IServiceBlockRegistry.ServiceBlockManifest({
            manifestHash: manifestHash,
            capabilityRoot: capabilityRoot,
            permissionsBitmap: permissionsBitmap,
            manifestSigner: builder,
            manifestVersion: 1
        })
    }),
    manifestSignature
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

---

## 5. OMS Identity Verification (v1.3.0+)

The P3 Institutional Compliance routing path now requires verified KYC/KYB status via the
OMS Compliance module. This is relevant to any consumer routing large-value or regulated
transactions through the CLR.

### How P3 Routing Works

```
CLRouter.route_v3(request, agent_id)
    │
    └── P3: Institutional compliance?
            ↓
        OMSIdentityVerifier.is_verified(agent_id)
            ├── False → 403 Rejected (fail-closed)
            └── True  → Polygon CDK KYC Layer
```

**Fail-closed guarantee:** If the OMS Identity API is unreachable, the verifier returns `False`.
No request is silently passed to P3 routes without a confirmed identity check.

### Obtaining OMS Identity Verification

1. Complete KYC/KYB with Polygon OMS at [polygon.technology/oms](https://polygon.technology/oms)
2. OMS issues a verifiable credential tied to your agent's wallet address
3. Your address is now automatically approved by `OMSIdentityVerifier.is_verified()`

### Environment Setup

```bash
# Required for P3 institutional routing
export OMS_IDENTITY_API="https://api.oms.polygon.technology/identity"
export OMS_API_KEY="<your_oms_api_key>"
```

> **Note:** Without these variables set, P3 routing will always return `False` (fail-closed).
> All other CLR priority routes (P0, P1, P2, P4, P5, P6) are unaffected.

---

## 6. Stablecoin Payout Configuration (v1.3.0+ — Providers)

As a **Supplier**, you can opt-in to receive your $VAMS rewards auto-converted to USDC or USDT
at claim time via OMS stablecoin settlement rails.

### Payout Modes

| Mode | Behaviour |
|---|---|
| `VAMS_ONLY` (default) | Rewards paid in $VAMS — no change required |
| `STABLECOIN` | 100% of rewards converted to USDC/USDT at claim time |
| `HYBRID` | 50% $VAMS + 50% USDC/USDT |

### Setting Your Preference

```python
from neuron.payments.stablecoin_payout import StablecoinPayoutManager, PayoutMode
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("https://rpc.polygon.technology"))
manager = StablecoinPayoutManager(
    web3=w3,
    reward_distributor_address="0x<REWARD_DISTRIBUTOR_ADDRESS>",
    private_key="0x<YOUR_PRIVATE_KEY>"
)

# Opt-in to full stablecoin payouts
tx_hash = manager.opt_in_to_stablecoin()
print(f"Preference set: {tx_hash}")

# Check current preference
pref = manager.get_preference("0xYOUR_ADDRESS")
print(f"Current mode: {['VAMS_ONLY', 'STABLECOIN', 'HYBRID'][pref]}")
```

Alternatively, call directly on the contract:
```solidity
RewardDistributor.setPayoutPreference(PayoutMode.STABLECOIN);
```

---

## 7. Fiat Top-Up via Coinme (v1.3.0+ — Consumers)

Consumers can now fund their agent escrow accounts using **credit card or bank transfer**
via Coinme's regulated fiat-to-crypto rails. No crypto wallet pre-funding required.

### Flow

```
You (credit card / bank) → Coinme Checkout → $VAMS → ComposedSettlement Escrow
```

Coinme handles all KYC and Money Transmitter License compliance across supported jurisdictions.
VAMS applies a 2–7% gas abstraction premium for the conversion service.

### Quick Start

```python
from neuron.payments.coinme_client import CoinmeClient
from neuron.payments.universal_topup import UniversalTopUpManager

coinme = CoinmeClient()  # Uses COINME_API_KEY env var
topup = UniversalTopUpManager(coinme, escrow_manager)

# Get current conversion rate (returns float directly)
rate = coinme.get_conversion_rate(from_currency="USD", to_token="VAMS")
print(f"1 USD = {rate} $VAMS")

# Create a fiat checkout session (returns dict)
session = coinme.create_checkout(
    amount_fiat=100.0,
    currency="USD",
    dest_address="0xYOUR_AGENT_ADDRESS"
)
print(f"Complete payment at: {session['checkout_url']}")
print(f"Session ID: {session['session_id']}")

# After payment confirmation, funds are automatically deposited
# to your agent's ComposedSettlement escrow
```

### Supported Fiat Currencies

All Coinme-supported currencies are accepted (varies by jurisdiction). Common options:
`USD`, `EUR`, `GBP`, `CAD`, `AUD`. Check [coinme.com](https://coinme.com) for current coverage.

---

## 8. OMS Architecture Reference

For the complete technical architecture of all 5 OMS integration phases, see:
**[docs/team/ARCHITECTURE_v0-6-0.md](./team/ARCHITECTURE_v0-6-0.md)**

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
