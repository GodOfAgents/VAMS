# VAMS Neuron Documentation v0.5.2

## Overview

VAMS Neuron is a **real infrastructure client** for the Verifiable and Agentic Modular Stack. It monitors and connects to decentralized networks across four architectural layers to enable "Immortal Agents" - AI agents with:

- **Crash-proof execution** via DBOS-style checkpointing
- **Decentralized compute** from io.net, Akash, Render, Bittensor
- **Persistent memory** on Arweave/WeaveDB
- **TEE attestation** from Phala, Marlin, Automata

This is production-ready infrastructure for Web3 AI agents.

---

## Installation

### Requirements
- Python 3.9+
- pip

### Quick Install
```bash
cd neuron
pip install -r requirements.txt
```

### Dependencies
| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for RPC calls |
| `ecdsa` | ECDSA cryptography (Secp256k1) |
| `colorama` | Terminal colors |

### Optional SDK Dependencies
```bash
# For Bittensor SDK integration (optional)
pip install bittensor

# For tests
pip install pytest
```

---

## Quick Start

```bash
# Run full health check (all 15 providers)
python neuron.py --full-health

# Run crash-proof workflow demo
python neuron.py --demo-workflow

# Use a specific DA provider
python neuron.py --provider near

# Test mode (no network calls)
python neuron.py --dry-run --full-health
```

---

## 4-Layer Architecture

### Layer 1: Data Availability

| Provider | Network | Block Time | Best For |
|----------|---------|------------|----------|
| **Celestia** | mocha-4 | ~12s | Default, general purpose |
| **EigenDA** | holesky | ~12s | High-value, Ethereum security |
| **Near DA** | testnet | ~1s | High-frequency, fast finality |
| **Avail** | turing | ~20s | ZK proofs, Validium |

### Layer 2: Compute

| Provider | Type | Best For |
|----------|------|----------|
| **io.net** | GPU Clusters (H100/A100) | AI inference |
| **Akash** | Kubernetes/Docker | Persistent workloads |
| **Render** | GPU Rendering | 3D assets, visual AI |
| **Bittensor** | AI Subnets | Intelligence-as-a-Service |

### Layer 3: Logic

| Provider | Type | Best For |
|----------|------|----------|
| **Kwil** | Permissionless SQL | Relational data |
| **WeaveDB** | NoSQL on Arweave | Permanent logs |
| **Glacier** | Vector DB | Long-term memory, embeddings |
| **DBOS Workflows** | Crash-proof | Exactly-once execution |

### Layer 4: Trust (TEE)

| Provider | Technology | Best For |
|----------|------------|----------|
| **Phala** | Intel SGX | Phat Contracts, private compute |
| **Marlin** | AWS Nitro | Oyster TEE coprocessors |
| **Automata** | Multi-Prover | 1RPC privacy relay |

---

## CLI Reference

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--provider NAME` | `-p` | Set primary DA provider |
| `--list-providers` | `-l` | List DA providers |
| `--check-health` | | Check Layer 1 health |
| `--check-compute` | | Check Layer 2 health |
| `--check-logic` | | Check Layer 3 health |
| `--check-trust` | | Check Layer 4 health |
| `--full-health` | | Check all 4 layers |
| `--demo-workflow` | | Run crash-proof demo |
| `--list-compute` | | List compute providers |
| `--list-logic` | | List logic providers |
| `--list-trust` | | List trust providers |
| `--dry-run` | | Use mock providers (no network) |
| `--use-sdk` | | Enable real SDK integrations |
| `--sdk-health` | | Check health via SDK providers |
| `--no-failover` | | Disable automatic failover |
| `--interval SEC` | `-i` | Heartbeat interval |
| `--version` | `-v` | Show version |
| `--help` | `-h` | Show help |

### Examples

```bash
# Full 4-layer health check
python neuron.py --full-health

# Use Near DA with 15-second heartbeat
python neuron.py --provider near --interval 15

# Test mode (mock providers, no network)
python neuron.py --dry-run --check-trust

# SDK health check (real protocol calls)
python neuron.py --sdk-health

# Crash-proof workflow demo
python neuron.py --demo-workflow
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAMS_PROVIDER` | celestia | Default DA provider |
| `VAMS_FAILOVER` | true | Enable auto-failover |
| `VAMS_GATEWAY` | http://localhost:8000 | Gateway URL |
| `HEARTBEAT_INTERVAL` | 30 | Seconds between heartbeats |

### DA Provider Endpoints

| Variable | Default |
|----------|---------|
| `CELESTIA_RPC` | https://rpc-mocha.pops.one |
| `EIGENDA_RPC` | https://holesky.drpc.org |
| `NEAR_RPC` | https://rpc.testnet.near.org |
| `AVAIL_RPC` | https://avail-turing.api.onfinality.io/public |

### Example
```bash
export VAMS_PROVIDER=near
export HEARTBEAT_INTERVAL=60
python neuron.py
```

---

## SDK Integrations

The neuron includes real protocol SDK integrations for production use.

### Celestia DA (`sdk/celestia.py`)

```python
from sdk.celestia import CelestiaDA

da = CelestiaDA()

# Submit agent state
blob = da.submit_blob(b"agent checkpoint data")
print(f"Submitted at block #{blob.height}")

# Retrieve data
data = da.get_blob(blob.height, blob.commitment)

# Health check
health = da.check_health()
```

**Environment Variables:**
| Variable | Description |
|----------|-------------|
| `CELESTIA_AUTH_TOKEN` | Auth token for light node RPC |
| `CELESTIA_RPC` | RPC endpoint (default: localhost:26658) |

### Bittensor (`sdk/bittensor_subnet.py`)

```python
from sdk.bittensor_subnet import BittensorSubnet

bt = BittensorSubnet(netuid=1)

# Get subnet info
info = bt.get_subnet_info(1)
print(f"SN1: {info.miners} miners")

# Get top miners
miners = bt.get_active_miners(1)[:10]
```

**Subnets Supported:** SN1 (Text Prompting), SN24 (BitAgent), SN32 (It's AI), and more.

### Phala TEE (`sdk/phala_tee.py`)

```python
from sdk.phala_tee import PhalaTEE, check_all_tee_health

tee = PhalaTEE()

# Verify SGX attestation
report = tee.verify_attestation(quote_bytes)

# Multi-TEE verification (2-of-3)
valid, reports = tee.verify_multi_tee(quotes, required=2)

# Check all TEE providers
health = check_all_tee_health()
```

**Providers:** Phala (Intel SGX), Marlin (AWS Nitro), Automata (Multi-Prover)

---

## Crash-Proof Workflows

The neuron includes DBOS-style workflow checkpointing for crash-proof execution:

```python
from workflows import VamsWorkflow, checkpoint

class MyWorkflow(VamsWorkflow):
    @checkpoint("gather")
    def step_gather(self):
        return fetch_data()
    
    @checkpoint("process")
    def step_process(self, data):
        return process(data)
```

### Demo
```bash
python neuron.py --demo-workflow
```

Output:
```
[WORKFLOW] Starting: DataPipeline (ID: demo_1706424025)

  [1/4] Gather Data......
  [1/4] Gather Data...... [CHECKPOINT]
  [2/4] Run Inference......
  [2/4] Run Inference...... [CHECKPOINT]
  -- Simulated crash! --

[WORKFLOW] Restarting after crash...

  [RECOVERY] Resuming from step 3: run_inference
  [3/4] Execute Action......
  [3/4] Execute Action...... [CHECKPOINT]
  [4/4] Report Result......
  [4/4] Report Result...... [CHECKPOINT]
  [COMPLETE] Workflow finished successfully!
```

---

## The Five Pillars of Immortal Agents

The Neuron implements all five pillars from the VAMS architecture:

| Pillar | Module | Status |
|--------|--------|--------|
| 1. Durable Execution | `workflows.py` | ✅ Complete |
| 2. L1 State Anchoring | `anchoring.py` | ✅ Complete |
| 3. Transparent Failover | `sdk/*.py` | ✅ Complete |
| 4. Request Guarantee | `request_queue.py` | ✅ Complete |
| 5. Permanent Memory | `storage/arweave.py` | ✅ Complete |

---

## Request Queue (Pillar 4)

The request queue ensures agent requests are eventually processed via retry logic with exponential backoff.

```python
from request_queue import RequestQueue

queue = RequestQueue(
    persistence_path="queue_state.json",  # Durable persistence
    webhook_url="https://your-webhook.com/alerts"  # Critical alerts
)

# Enqueue a request
queue.enqueue("req_001", "inference", {"prompt": "Hello world"})

# Process queue with custom handler
async def my_handler(target, payload):
    # Your logic here
    return True  # Success

await queue.process_queue(my_handler)

# Check status
status = queue.get_status("req_001")
# {"status": "completed", "retries": 0, "error": null}
```

**Features:**
- Exponential backoff (1s base, 60s max)
- Dead letter queue for failed requests
- JSON persistence across restarts
- Webhook notifications for critical events

---

## L1 State Anchoring (Pillar 2)

Submits Merkle roots of workflow state to L1 for immortality guarantee.

```python
from anchoring import get_anchor

anchor = get_anchor()

# Compute Merkle root from checkpoint data
checkpoints = [
    {"step": "gather", "data": {...}},
    {"step": "process", "data": {...}}
]
merkle_root = anchor.compute_merkle_root(checkpoints)

# Submit to L1 (real or simulated)
receipt = anchor.submit_anchor(merkle_root, len(checkpoints))

# Verify anchor
is_valid = anchor.verify_anchor(receipt, checkpoints)

# Display receipt
print(anchor.format_receipt(receipt))
```

**Output:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  L1 STATE ANCHOR RECEIPT                                             │
├─────────────────────────────────────────────────────────────────────┤
│  Merkle Root:  0x8a3b2c1d4e5f6...12345678  │
│  Tx Hash:      0x1234567890ab...abcdef12  │
│  Block:        #19,283,103                               │
│  Status:       ✓ REAL (Polygon)                                   │
│  Checkpoints:  2 states anchored                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## x402 Micropayments

HTTP 402 payment channels for agent-to-agent and agent-to-service payments.

```python
from payments.x402 import X402Client

client = X402Client(
    wallet_address="0x...",
    private_key="..."  # Or use env VAMS_PRIVATE_KEY
)

# Create payment channel
channel = client.create_channel("0xservice...", amount_wei=1000000)

# Make micropayment
payment = client.pay(channel.id, amount=100)

# Close channel and settle
client.close_channel(channel.id)
```

---

## Web3 Integration

On-chain agent registration with the VAMSAgentRegistry contract.

```python
from web3.registration import AgentRegistryClient

client = AgentRegistryClient(
    rpc_url="https://rpc.polygon.io",
    private_key="...",
    registry_address="0x..."
)

# Register agent
tx_hash = client.register_agent(
    agent_id=bytes.fromhex("..."),
    metadata_uri="ipfs://...",
    stake_amount=100 * 10**18  # 100 VAMS
)

# Submit checkpoint
tx_hash = client.submit_checkpoint(
    merkle_root=bytes.fromhex("..."),
    agent_id=bytes.fromhex("...")
)
```

---

## Files Generated

| File | Description |
|------|-------------|
| `node_identity.pem` | ECDSA private key (Secp256k1) - **Keep safe!** |
| `neuron_data.db` | SQLite database with heartbeats and metrics |
| `workflow_checkpoints.db` | Workflow checkpoint storage |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                       VAMS Neuron v0.5.1                             │
│                    IMMORTAL AGENT INFRASTRUCTURE                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────┐                        ┌─────────────────────┐  │
│  │    CLI/Args     │                        │   Workflow Engine   │  │
│  │    (neuron.py)  │───────────────────────►│  (Crash-Proof)      │  │
│  └─────────────────┘                        └─────────────────────┘  │
│           │                                           │              │
│           ▼                                           ▼              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    LAYER 1: DATA AVAILABILITY                    ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            ││
│  │  │ Celestia │ │ EigenDA  │ │ Near DA  │ │  Avail   │            ││
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    LAYER 2: COMPUTE                              ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            ││
│  │  │  io.net  │ │  Akash   │ │  Render  │ │Bittensor │            ││
│  │  │ (GPU AI) │ │  (K8s)   │ │  (3D)    │ │ (Subnets)│            ││
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    LAYER 3: LOGIC                                ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐    ││
│  │  │   Kwil   │ │ WeaveDB  │ │ Glacier  │ │ DBOS Checkpoints │    ││
│  │  │  (SQL)   │ │ (Arweave)│ │(Vector)  │ │ (Crash-Proof)    │    ││
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘    ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    LAYER 4: TRUST (TEE)                          ││
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────┐             ││
│  │  │   Phala    │  │   Marlin   │  │    Automata    │             ││
│  │  │ (Intel SGX)│  │ (AWS Nitro)│  │ (Multi-Prover) │             ││
│  │  └────────────┘  └────────────┘  └────────────────┘             ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Cryptography

### Identity
- **Algorithm**: ECDSA with Secp256k1 curve
- **Key File**: PEM format (`node_identity.pem`)
- **Node ID**: First 16 hex characters of public key

### Heartbeat Signature
Each heartbeat is signed with the node's private key:
```json
{
  "type": "VAMS_HEARTBEAT",
  "version": "v0.5.1",
  "node_id": "41e47c55ff1d8e9c",
  "block_height": 9628553,
  "provider": "celestia",
  "timestamp": 1736703540.123,
  "nonce": "a1b2c3d4e5f67890"
}
```

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_neuron.py -v
python -m pytest tests/test_workflows.py -v
```

### Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_neuron.py` | 16 | BittensorProvider, ComputeManager, TrustManager |
| `test_sdk.py` | 29 | CelestiaDA, BittensorSubnet, PhalaTEE, MarlinOyster, Automata |
| `test_workflows.py` | 15 | CheckpointStore, DemoWorkflow, crash recovery |
| **Total** | **60** | **All pass** |

---

## Gateway (Optional)

Run the gateway server to collect heartbeats from multiple nodes:

```bash
cd gateway
pip install -r requirements.txt
python server.py
```

Dashboard: http://localhost:8000

---

## Troubleshooting

### Provider Connection Failed
```
[WARN] All providers offline, retrying...
```
**Solution**: Check internet connection, verify RPC URLs are accessible.

### Identity Load Error
```
[ERROR] Failed to load identity
```
**Solution**: Delete `node_identity.pem` and restart (new key will be generated).

### Gateway Offline
```
[INFO] Gateway offline - stored locally
```
**Solution**: This is normal if gateway isn't running. Heartbeats are stored locally.

### Dry-Run Mode
If you see `[WARN] Running in DRY-RUN mode`, this is expected when using `--dry-run`. Remove the flag for real network calls.

---

## Version History

| Version | Date | Features |
|---------|------|----------|
| v0.1.0 | Jan 2026 | Celestia monitoring, identity, SQLite storage |
| v0.2.0 | Jan 2026 | Multi-provider (Celestia, EigenDA, Near, Avail), CLI, failover |
| v0.4.0 | Jan 2026 | 4-layer stack (Compute, Logic, Trust), TEE monitoring |
| v0.5.0 | Jan 2026 | DBOS-style workflows, crash-proof checkpoints |
| v0.5.1 | Jan 2026 | Bittensor SDK integration, mock mode, 60 tests |
| v0.5.2 | Jan 2026 | Request Queue (Pillar 4), L1 State Anchoring (Pillar 2), x402 payments |

---

## License

MIT License - See [LICENSE](../LICENSE)

---

**VAMS** - Verifiable and Agentic Modular Stack  
*The Sovereign Brain for the Agentic Web*
