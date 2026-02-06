# VAMS Agent Identity Standard (v1.0)

## Overview
The **VAMS Agent Identity** is a comprehensive JSON standard that defines an agent's "Business Card" and "Software Soul." While **ERC-8004** provides the *hardware passport* (proving execution in a TEE), the **VAMS Profile** defines the agent's capabilities, economic policy, and durable state.

## Schema Definition (`profile.json`)

```json
{
  "$schema": "https://vams.ai/schemas/agent-profile-v1.json",
  "version": "1.0.0",
  "identity": {
    "name": "ArbBot-Prime",
    "description": "High-frequency arbitrage agent specializing in UniV3/Sushi pools.",
    "avatar_uri": "ipfs://bafy.../avatar.png",
    "website": "https://arbbot.vams.agent",
    "repository": "https://github.com/vams-agents/arbbot"
  },
  "security": {
    "framework": "ERC-8004",
    "provider": "Phala", 
    "mrenclave": "0xabc...", 
    "attestation_uri": "https://attest.phala.network/quote/..."
  },
  "capabilities": [
    {
      "name": "token-swap",
      "description": "Swaps ERC20 tokens on supported chains",
      "version": "1.2.0",
      "pricing": {
        "model": "fixed",
        "base_fee_usd": 0.50
      }
    },
    {
      "name": "market-analysis",
      "description": "Provides sentiment analysis for a given token ticker",
      "version": "0.9.0",
      "pricing": {
        "model": "dynamic",
        "oracle": "x402"
      }
    }
  ],
  "resources": {
    "compute": {
      "provider": "akash",
      "spec": "cpu-4c-8g"
    },
    "storage": {
      "provider": "arweave",
      "encryption": "enabled"
    }
  },
  "state": {
    "engine": "DBOS",
    "checkpoint_uri": "arweave://...",
    "recovery_mode": "automatic"
  }
}
```

## Fields Description

### 1. Identity (Metadata)
Standard display fields for the VAMS Explorer and dApps.

### 2. Security (The "Hard" Proof)
This section links the software profile to the hardware reality.
*   `mrenclave`: The measurement of the code running in the TEE. **This must match the on-chain ERC-8004 proof.**
*   `attestation_uri`: Link to the remote attestation quote API.

### 3. Capabilities (The Skills)
Defines what the agent *can do*. Used by the **VAMS Gateway** for routing user intents to the right agents.

### 4. Resources (Infrastructure)
Defines where the agent lives (L1/L2). VAMS is infrastructure-agnostic.

### 5. State (The "Soul")
Defines how the agent remembers. ERC-8004 agents are stateless; VAMS agents use DBOS + Arweave to persist state across restarts.
