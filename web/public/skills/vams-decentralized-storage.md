---
name: vams-decentralized-storage
description: Permanent, encrypted agent state storage using DBOS checkpointing and decentralized backends — Arweave for immutable archival and Iagon for cost-efficient SDK-based storage.
metadata:
  permissions:
    - storage_read
    - storage_write
    - wallet_sign
  version: 1.0.0
  author: VAMS Core Team
  license: MIT
  tags:
    - storage
    - DBOS
    - arweave
    - iagon
    - persistence
    - encryption
---

# VAMS Decentralized Storage Skill

> **"Memory is identity. Without persistent storage, an agent is born and dies every session."**

VAMS provides agents with **permanent, encrypted, decentralized storage** for state persistence. The DBOS (Durable Business Object Store) checkpointing system ensures agents can survive crashes, migrations, and hardware failures by anchoring their state across multiple storage backends.

---

## Overview

| Component | Description |
|---|---|
| **DBOS Checkpoint** | Periodic state snapshots with crash recovery |
| **AES-256-GCM** | Military-grade encryption for all stored data |
| **Arweave** | Permanent, immutable storage (pay once, store forever) |
| **Iagon** | Cost-efficient decentralized storage with SDK |
| **L3 Anchoring** | Proof hashes committed to VAMS L3 for verification |

---

## How It Works

```
Agent State (memory.json)
      │
      ▼
┌─────────────────────────┐
│   DBOS Checkpoint       │
│   Serialize + tag       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   AES-256-GCM Encrypt   │
│   Key = agent wallet    │
└────────────┬────────────┘
             │
      ┌──────┴──────┐
      ▼              ▼
┌──────────┐  ┌──────────┐
│ Arweave  │  │  Iagon   │
│ (Perm.)  │  │  (Flex.)  │
└────┬─────┘  └────┬─────┘
     │              │
     └──────┬───────┘
            ▼
┌─────────────────────────┐
│   VAMS L3 Anchor        │
│   hash(data) → on-chain │
└─────────────────────────┘
```

---

## Capabilities

### 📸 1. Create Checkpoint
Snapshot the agent's current state:

```
vams.storage.checkpoint({
  label: "post-task-42",
  data: agentState,
  provider: "iagon"  // or "arweave"
})
→ Returns: { checkpointId, storageUri, anchorTxHash }
```

### 🔄 2. Restore from Checkpoint
Recover state after a crash or migration:

```
vams.storage.restore(checkpointId)
→ Downloads encrypted blob
→ Decrypts with agent wallet key
→ Returns: restoredState
```

### 📋 3. List Checkpoints
Browse all available restore points:

```
vams.storage.listCheckpoints()
→ Returns: [{
    id: "ckpt_001",
    label: "post-task-42",
    timestamp: 1709000000,
    provider: "iagon",
    size: "2.3 MB",
    anchorBlock: 12345
  }, ...]
```

### 🗑️ 4. Prune Old Checkpoints
Remove outdated snapshots to save storage costs:

```
vams.storage.prune({
  keepLast: 10,
  olderThan: "30d"
})
```

---

## Storage Providers

### Arweave — Permanent Storage
| Property | Value |
|---|---|
| **Persistence** | Permanent (200+ year guarantee) |
| **Cost Model** | One-time payment |
| **Best For** | Critical state, identity backups, proofs |
| **Retrieval** | ~1–5 seconds via gateway |

### Iagon — Flexible Storage
| Property | Value |
|---|---|
| **Persistence** | Configurable retention |
| **Cost Model** | Pay-per-GB/month |
| **Best For** | Frequent checkpoints, working state |
| **Retrieval** | ~500ms via SDK |
| **SDK** | Python `IagonStorageSDK` class |

---

## Encryption

All data is encrypted before leaving the agent's runtime:

| Parameter | Value |
|---|---|
| **Algorithm** | AES-256-GCM |
| **Key Derivation** | HKDF from agent's ECDSA private key |
| **IV** | Random 12-byte nonce per encryption |
| **Auth Tag** | 128-bit authentication tag |
| **Key Rotation** | Automatic on agent key rotation |

### Encryption Flow
```python
# 1. Derive storage key from wallet
storage_key = HKDF(agent_private_key, salt="vams-storage", length=32)

# 2. Encrypt state
iv = random_bytes(12)
ciphertext, tag = AES_GCM_encrypt(storage_key, iv, state_data)

# 3. Upload encrypted blob
blob = iv + tag + ciphertext
upload(blob, provider="iagon")
```

---

## DBOS Checkpointing Strategy

| Strategy | Interval | Use Case |
|---|---|---|
| **Time-based** | Every 10 minutes | General agents |
| **Event-based** | After each task completion | Task workers |
| **Threshold-based** | When state diff > 1 KB | Memory-heavy agents |
| **Manual** | On-demand | Debugging, migrations |

### Crash Recovery
```
Agent starts → Check for existing checkpoints
  │
  ├── No checkpoints → Fresh start (genesis state)
  │
  └── Checkpoint found → Restore latest
        │
        ├── Decryption succeeds → Resume from checkpoint
        │
        └── Decryption fails → Alert + fallback to previous checkpoint
```

---

## Iagon SDK Integration

The VAMS Neuron client includes a native Iagon SDK wrapper:

```python
from neuron.sdk.iagon_storage import IagonStorageSDK

sdk = IagonStorageSDK(
    api_key="your-iagon-api-key",
    encryption_key=agent_wallet_key
)

# Upload
uri = await sdk.upload(encrypted_state, filename="checkpoint_001.enc")

# Download
data = await sdk.download(uri)

# Delete
await sdk.delete(uri)
```

---

## Integration

This skill works in conjunction with:
- **[vams-sovereign-identity](./vams-immortality.md)** — Encryption key derived from wallet
- **[vams-neuron-sdk](./vams-neuron-sdk.md)** — Checkpoint orchestration
- **[vams-verifiable-compute](./vams-verifiable-compute.md)** — Proof hashes anchored alongside checkpoints

---

## References

| Resource | Link |
|---|---|
| Iagon SDK | [neuron/sdk/iagon_storage.py](https://github.com/GodOfAgents/VAMS/blob/main/neuron/sdk/iagon_storage.py) |
| Neuron Source | [neuron/](https://github.com/GodOfAgents/VAMS/tree/main/neuron) |
| Architecture §Foundational | [ARCHITECTURE_v0-3-0.md](https://github.com/GodOfAgents/VAMS/blob/main/docs/team/ARCHITECTURE_v0-3-0.md) |
| Arweave Docs | [arweave.org](https://www.arweave.org/) |
| Iagon Docs | [iagon.com](https://iagon.com/) |

---

*VAMS Foundational Layer v0.3.0 · Memory is Immortality*
