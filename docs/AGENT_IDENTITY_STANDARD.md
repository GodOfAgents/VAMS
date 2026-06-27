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
  "cognitive_profile": {
    "K": 0.85,
    "RW": 0.90,
    "M": 0.75,
    "R": 0.80,
    "WM": 0.85,
    "MS": 0.95,
    "MR": 0.90,
    "V": 0.50,
    "A": 0.30,
    "S": 0.70
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

### 5. Cognitive Profile (The CHC Decagon)
Defines the agent's psychometric benchmark capabilities across the 10 Cattell-Horn-Carroll (CHC) cognitive domains. Each value is a float between `0.0` and `1.0`.
*   `K` (General Knowledge): Quality and depth of pre-trained parameters.
*   `RW` (Reading/Writing): Syntax parsing, structured formats, translation.
*   `M` (Math): Numeric reasoning, arithmetic operations, floating-point analysis.
*   `R` (Fluid Reasoning): Multi-hop planning, out-of-distribution generalization.
*   `WM` (Working Memory): Context window stability and attention retention.
*   `MS` (Memory Storage): Semantic vector databases, long-term database checkpoints.
*   `MR` (Memory Retrieval): Context recall, needle-in-a-haystack indexing efficiency.
*   `V` (Visual): Multimodal image processing, OCR, spatial geometry.
*   `A` (Auditory): Audio transcription, spectrogram analysis, text-to-speech.
*   `S` (Speed): Execution throughput, tokens-per-second, hardware latency.

Agents declare these values as **minimum cognitive requirements** inside their composed blueprints to filter matching DePIN nodes. Compute nodes report these as **capabilities** via their telemetry heartbeat payloads, which are verified by Sentinels.

### 6. State (The "Soul")
Defines how the agent remembers. ERC-8004 agents are stateless; VAMS agents use DBOS + Arweave to persist state across restarts.
