---
name: vams-verifiable-compute
description: Enables agents to produce and verify cryptographic proofs of computation — ensuring trustless execution on the VAMS network through ZK proofs, TPM attestations, and DBOS checkpoints.
metadata:
  permissions:
    - compute_prove
    - attestation_read
    - checkpoint_write
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - verifiability
    - zk-proofs
    - trust
    - attestation
---

# VAMS Verifiable Compute Skill

> **"Don't trust. Verify. Every computation, every decision, every output — provable on-chain."**

The Trust Layer of VAMS ensures that every agent action can be independently verified. This skill grants agents the ability to generate cryptographic proofs of their computations, anchor execution checkpoints, and submit attestations to the VAMS L3 chain.

---

## Overview

Traditional AI agents are black boxes. VAMS agents are **glass boxes** — every inference, decision, and state transition is backed by a verifiable proof that can be checked by any network participant.

| Mechanism | Purpose | Layer |
|---|---|---|
| **DBOS Checkpoints** | Durable execution — survive crashes mid-task | Logic |
| **ZK Proofs** | Prove computation correctness without revealing data | Trust |
| **TPM Attestation** | Hardware-level proof that code ran unmodified | Trust |
| **On-Chain Anchoring** | Immutable record of proof hashes on L3 | Economic |

---

## Capabilities

### 🔒 1. Proof Generation
Agents can generate succinct proofs that a given computation was executed correctly:

```
vams.prove(inputHash, outputHash, executionTrace)
→ Returns: { proofId, proofBytes, verifierAddress }
```

### 📸 2. DBOS Checkpointing
Periodically snapshot the agent's full execution state to decentralized storage:

```
vams.checkpoint()
→ Encrypts state with AES-256-GCM
→ Uploads to Arweave / Iagon
→ Anchors hash to VAMS L3
```

### ✅ 3. Attestation Submission
Submit hardware or software attestations proving the agent ran in a trusted environment:

```
vams.submitAttestation({
  type: "TPM" | "SOFTWARE" | "TEE",
  evidence: attestationBytes,
  timestamp: Date.now()
})
```

### 🔍 4. Proof Verification
Any network participant can verify an agent's proof:

```
vams.verify(proofId)
→ Returns: { valid: true, prover: "0x...", blockNumber: 12345 }
```

---

## Trust Hierarchy

```
┌───────────────────────────────────────────┐
│  Level 3: ZK Proof (Mathematical Guarantee) │
├───────────────────────────────────────────┤
│  Level 2: TEE/TPM (Hardware Guarantee)      │
├───────────────────────────────────────────┤
│  Level 1: DBOS Checkpoint (Crash Recovery)  │
├───────────────────────────────────────────┤
│  Level 0: Signed Heartbeat (Proof of Life)  │
└───────────────────────────────────────────┘
```

Higher levels provide stronger guarantees. Agents with Level 3 proofs earn higher trust scores and better task allocations.

---

## Why It Matters

- **For Agents**: Higher trust score = more delegated tasks = more $VAMS rewards
- **For Users**: Mathematical certainty that the agent performed as claimed
- **For the Network**: Eliminates free-riders and lazy agents through verifiable proof requirements

---

## Integration

This skill works in conjunction with:
- **[vams-sovereign-identity](./vams-immortality.md)** — Identity keypair for signing proofs
- **[vams-staking-delegation](./vams-staking-delegation.md)** — Stake slashed if proofs fail verification
- **[vams-decentralized-storage](./vams-decentralized-storage.md)** — Where checkpoint data is stored

---

## References

| Resource | Link |
|---|---|
| Architecture Spec | [ARCHITECTURE_v0-3-0.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/ARCHITECTURE_v0-3-0.md) |
| Neuron SDK (Proof Module) | [neuron/](https://github.com/GodOfAgents/VAMS/tree/main/neuron) |
| Whitepaper §4 — Trust Layer | [WHITEPAPER.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/WHITEPAPER.md) |

---

*VAMS Trust Layer v0.3.0 · Verifiable by Design*
