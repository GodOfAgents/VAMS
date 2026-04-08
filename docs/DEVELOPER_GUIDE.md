# VAMS Developer Onboarding Guide

Welcome to the Verifiable and Agentic Modular Stack (VAMS). This guide will help you navigate the v1.0.0-icn release, which introduces major infrastructure upgrades.

## What is VAMS?
VAMS is the "Sovereign Brain" for the Agentic Web. Instead of running your AI agents on centralized AWS servers where they can be de-platformed, or on slow blockchains where they can't afford gas, VAMS provides a verifiable, fast, and multi-provider computation layer.

---

## 1. Building as an Agent Developer (Consumer)

If you are building an AI agent (e.g., a DeFi trading bot, a research assistant), you are a **Consumer** of the VAMS network.

### Step 1: Install the SDK
```bash
pip install vams-sdk==1.0.0-icn
```

### Step 2: Define your Intent
Instead of manually renting GPUs on Akash or io.net, use the **Resource Composer**.

```python
from vams.composer import VAMSComposer
from vams.auth import VAMSAgentProtocol

auth = VAMSAgentProtocol(api_key="your_key")
composer = VAMSComposer(auth)

# Define your infrastructure needs
blueprint = composer.request_blueprint(
    target_region="us-east",
    requirements=["gpu:a100", "memory:64gb"],
    max_cost_vams="100.0" # Max 100 $VAMS per hour
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

If you own GPUs or server racks, you are a **Supplier**. Check out the `docs/NODE_OPERATORS.md` (coming soon) for instructions on installing the VAMS Sentinel node client and capturing Regional DEC emissions!
