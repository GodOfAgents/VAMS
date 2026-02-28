---
name: vams-x402-payments
description: Agent-native crypto payments using the x402 HTTP payment protocol — enabling autonomous micropayments, API monetization, and machine-to-machine economic activity without human intervention.
metadata:
  permissions:
    - wallet_sign
    - payment_send
    - payment_receive
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - payments
    - x402
    - micropayments
    - crypto
    - agent-economy
---

# VAMS x402 Payments Skill

> **"HTTP 402: Payment Required. The status code the internet forgot — and agents remembered."**

The **x402 protocol** enables AI agents to send and receive crypto payments as naturally as making HTTP requests. Built on the HTTP 402 status code standard, it allows agents to pay for API calls, storage, compute, and services — all without human wallets or manual approvals.

---

## Overview

| Parameter | Value |
|---|---|
| **Protocol** | x402 (HTTP 402 Payment Required) |
| **Supported Tokens** | $VAMS, USDC, MATIC, ETH |
| **Payment Chain** | VAMS L3 (primary), Polygon PoS (fallback) |
| **Min Payment** | 0.001 $VAMS (~$0.0001) |
| **Settlement** | Instant on L3, ~2s finality |
| **Authorization** | Agent wallet signature (no human approval) |

---

## How x402 Works

The x402 protocol extends standard HTTP with a payment flow:

```
Agent                          Service Provider
  │                                  │
  │  1. GET /api/inference           │
  │ ────────────────────────────────▶│
  │                                  │
  │  2. 402 Payment Required         │
  │     x-payment-amount: 0.5       │
  │     x-payment-address: 0x...    │
  │     x-payment-chain: vams-l3    │
  │ ◀────────────────────────────────│
  │                                  │
  │  3. Sign & send payment TX       │
  │  4. GET /api/inference           │
  │     x-payment-proof: 0x...      │
  │ ────────────────────────────────▶│
  │                                  │
  │  5. 200 OK { result: "..." }    │
  │ ◀────────────────────────────────│
```

---

## Capabilities

### 💸 1. Send Payments
Pay for any x402-compatible service automatically:

```
vams.pay({
  recipient: "0x...",
  amount: "0.5",
  token: "VAMS",
  memo: "inference-request-42"
})
→ Returns: { txHash, blockNumber, receipt }
```

### 📥 2. Receive Payments
Register as a service provider and accept x402 payments:

```
vams.payments.registerService({
  endpoint: "/api/my-service",
  price: "0.1",
  token: "VAMS",
  description: "My AI inference API"
})
```

### 🧾 3. Invoice Generation
Create structured payment requests:

```
vams.payments.createInvoice({
  amount: "10.0",
  token: "VAMS",
  description: "Batch processing — 100 items",
  expiry: 3600  // 1 hour
})
→ Returns: { invoiceId, paymentUri, qrCode }
```

### 📊 4. Payment History
Track all incoming and outgoing payments:

```
vams.payments.getHistory({ limit: 50 })
→ Returns: [{
    type: "SENT",
    amount: "0.5",
    recipient: "0x...",
    timestamp: 1709000000,
    txHash: "0x..."
  }, ...]
```

---

## Use Cases

| Scenario | Payment Flow |
|---|---|
| **API Call** | Agent pays per-request for external AI inference |
| **Storage** | Agent pays Iagon/Arweave for state backup |
| **Compute** | Agent pays L3 validators for priority execution |
| **Data Feed** | Agent pays oracle for real-time market data |
| **Agent-to-Agent** | Worker agent pays verifier agent for attestation |
| **Human Services** | Agent pays freelancer for off-chain work |

---

## Payment Channels (Streaming)

For high-frequency micropayments, VAMS supports **payment channels**:

```
// Open a channel
const channel = await vams.payments.openChannel({
  recipient: "0x...",
  deposit: "100",
  token: "VAMS"
});

// Stream micropayments
await channel.pay("0.001");  // instant, off-chain
await channel.pay("0.001");  // no gas cost per payment

// Close and settle on-chain
await channel.close();
→ Single on-chain TX settles the final balance
```

---

## Security

| Feature | Description |
|---|---|
| **Spending Limits** | Daily and per-transaction caps configurable |
| **Allowlist** | Only pay to verified contract addresses |
| **Receipt Proofs** | Every payment generates a verifiable receipt |
| **Dispute Resolution** | On-chain evidence for payment disputes |
| **Rate Limiting** | Max payments per minute to prevent drain attacks |

---

## Integration

This skill works in conjunction with:
- **[vams-sovereign-identity](./vams-immortality.md)** — Wallet for signing payments
- **[vams-neuron-sdk](./vams-neuron-sdk.md)** — Transaction submission
- **[vams-tokenomics](./vams-tokenomics.md)** — $VAMS token used for payments

---

## References

| Resource | Link |
|---|---|
| x402 Standard | [x402.org](https://x402.org) |
| VAMS Token | [VAMSToken.sol](https://github.com/GodOfAgents/VAMS/blob/main/contracts/src/token/VAMSToken.sol) |
| Architecture §Economic | [ARCHITECTURE_v0-3-0.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/ARCHITECTURE_v0-3-0.md) |

---

*VAMS Economic Layer v0.3.0 · Money for Machines*
