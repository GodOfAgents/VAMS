# VAMS Developer Onboarding Guide

**Lifecycle:** Current implementation guide
**Last verified:** 2026-07-12

> This guide describes source-level capabilities. It does not authorize
> mainnet, public-testnet, fiat, yield, or wallet-transaction use.

Welcome to the Verifiable and Agentic Modular Stack (VAMS). The v1.3.0-oms
label is a historical integration milestone; v0.8.0 is the current architecture
version. OMS, Coinme, Trails, and related SDK paths remain mock-default or
live-evidence-pending and must fail closed outside local development.

## Local session-key boundary

Scoped update, 2026-11-01: this paragraph and the builder-fee note below were
checked against current source; the rest of this guide keeps its dated scope.

`SessionKeyManager.create_session_key` is a local-only interface through a
configured `SequenceWalletManager`. Both its immutable runtime policy and the
current `VAMS_ENV` must be non-live (`test`, `local` or `demo`). Live modes reject
with `LiveModeSafetyError`; missing/invalid runtime configuration also rejects.
`verify_session_scope` returns `False` for live or unknown contexts before cache
access. Local validity remains 1-24 hours and requested contracts must be in the
configured VAMS whitelist. A local cached record does not establish on-chain
account restrictions or an authenticated current grant.

Actual session-grant policy/root/epoch verification, credential custody, bundler
and ERC-4337 enforcement remain unqualified. A mock flag cannot enable live use.
## What is VAMS?
VAMS is the "Sovereign Brain" for the Agentic Web. Instead of running your AI agents on centralized AWS servers where they can be de-platformed, or on slow blockchains where they can't afford gas, VAMS provides a verifiable, fast, and multi-provider computation layer.

---

## 1. Building as an Agent Developer (Consumer)

If you are building an AI agent (e.g., a DeFi trading bot, a research assistant), you are a **Consumer** of the VAMS network.

### Step 1: Install the Neuron Package Dependencies
```bash
python -m pip install -r neuron/requirements.txt
```

### Step 2: Plan locally

The current Composer scores and allocates local simulations. It does not create
provider resources, release credentials, lock escrow or prove execution. Explicit
SDK simulation requires `VAMS_ENV=test`, `local` or `demo`; default construction
rejects provisioning. Gateway composition and synthetic catalogues are available
only in `demo`. Existing authentication requirements still apply.

```python
from neuron.composer.composer import VAMSResourceComposer
from neuron.composer.blueprints import get_blueprint

# Use already-configured non-live runtime policy and synthetic candidate data.
composer = VAMSResourceComposer(simulation=True)
blueprint = get_blueprint("AI_INFERENCE_STANDARD")
# composer.provision(blueprint, node_data=your_local_candidates) returns SIMULATED.
```

Local records and price quotes are non-authoritative. A simulated allocation has
no provider receipt or escrow transaction and earns no payment. Listing and
removing its local record remain possible after runtime changes; removal releases
no external resource. `list_active_instances()` excludes simulated records.

### Step 3: Construct settlement requests separately

`get_escrow_params` is retired and rejects. `build_escrow_request` accepts a typed
`SettlementTransactionBuilder`, explicit integer token units and authentic
on-chain registration identities/terms. It does not accept float quotes or local
simulation as execution evidence. Review `neuron/composer/settlement.py` for the
exact typed request contract. Construction is not signing or deployment authority.

### Step 4: Qualify real execution

An authenticated registry reader, provider admission/execution/receipt consumer,
and actual end-to-end qualification are still required. Neither this example nor
a local simulation demonstrates a live service or testnet readiness.

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

### Step 2: Builder fees

Selecting a Service Block does not itself trigger payment. Settlement snapshots
its registered builder fee, capped at 5,000bps, when creating the allocation.
After delivery is recognized, the provider's claim pays that locked builder share
directly; the separate protocol fee is 5bps. The 500bps (5%) value in the example
is not a global fixed rate. Restricted-profile rewards and real yield remain
inactive; live wallet, proof/backend and deployment qualification are still open.

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
