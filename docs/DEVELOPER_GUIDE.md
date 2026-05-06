# VAMS Developer Onboarding Guide

Welcome to the Verifiable and Agentic Modular Stack (VAMS). This guide covers the **v1.3.0-oms** release, which integrates Polygon's Open Money Stack (OMS) — adding institutional identity routing, ERC-4337 session keys, Coinme fiat on-ramp, Insurance Fund yield, and stablecoin payouts — on top of the v1.2.0-autoskill Intelligence Layer.

## What is VAMS?
VAMS is the "Sovereign Brain" for the Agentic Web. Instead of running your AI agents on centralized AWS servers where they can be de-platformed, or on slow blockchains where they can't afford gas, VAMS provides a verifiable, fast, and multi-provider computation layer.

---

## 1. Building as an Agent Developer (Consumer)

If you are building an AI agent (e.g., a DeFi trading bot, a research assistant), you are a **Consumer** of the VAMS network.

### Step 1: Install the SDK
```bash
pip install vams-sdk==1.2.0-autoskill
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

# Get current conversion rate
rate = coinme.get_conversion_rate(from_currency="USD", to_token="VAMS")
print(f"1 USD = {rate.rate} $VAMS (fee: {rate.fee_pct}%)")

# Create a fiat checkout session
session = coinme.create_checkout(
    amount_fiat=100.0,
    currency="USD",
    dest_address="0xYOUR_AGENT_ADDRESS"
)
print(f"Complete payment at: {session.checkout_url}")
print(f"Session expires: {session.expires_at}")

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
