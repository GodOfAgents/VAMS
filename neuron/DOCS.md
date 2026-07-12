# VAMS Neuron Documentation v1.0.0-icn

**Lifecycle:** Historical runtime reference; verify against current source
**Last verified:** 2026-07-12

## Overview

VAMS Neuron is an implemented runtime under pre-testnet hardening. Several
provider integrations are mock-default, prototype, or live-evidence pending;
consult `../REPO_STATUS_REPORT.md` and `README.md` before treating any route as
operational.

- **Crash-proof execution** via DBOS SDK (PostgreSQL)
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

## Architecture: 4-Layer Stack + Execution Chains

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

### Layer 5: Execution Chains (CLR Routing Targets)

> These are **not** host domains — VAMS agents are not deployed here. The CLR routes signed transactions to these chains when specific constraints are required.

| Chain | Type | Privacy | Finality | Bridge | Best For |
|-------|------|---------|----------|--------|----------|
| **Ethereum** | Account L1 | Public | ~13 min | AggLayer | High-value settlement |
| **Polygon** | L2 Rollup | Public | ~4 min | AggLayer | Default execution (VAMS L3) |
| **Arbitrum** | L2 Rollup | Public | 7 day | AggLayer | Optimistic rollup |
| **Base** | L2 Rollup | Public | 7 day | AggLayer | Coinbase ecosystem |
| **Solana** | Account L1 | Public | ~6s | Hyperlane | Non-EVM velocity |
| **SEI** | Fast EVM | Public | 380ms | LayerZero | EVM fast-lane (Twin-Turbo) |
| **Avalanche** | Account L1 | Public | ~2s | Hyperlane | Snowman++ finality |
| **Phala** | Privacy (TEE) | TEE | ~3s | Hyperlane | Confidential compute |
| **Oasis** | Privacy (ZK) | ZK | ~6s | Hyperlane | Privacy-preserving |
| **Cardano** | eUTXO (Ouroboros) | Public | ~12 min | Rosen Bridge + ICB | Formally verified settlement |
| **Midnight** | Cardano Sidechain | ZK-SD | ~1 min | Hyperlane (ZK-ISM) | Compliance-grade privacy |
| **Hydra** | State Channel | Public | ~50ms | Direct | Sub-second HFT |

### Chain Oracle Layer

The oracle sits between agents and the CLR, fetching **live metrics** from all 12 execution chains:

```python
from neuron.chain_oracle import OracleManager

oracle = OracleManager()

# Get all chain metrics (TTL-cached, 30s default)
metrics = oracle.get_all_metrics()
for name, m in metrics.items():
    print(f"{name}: gas={m.gas_price_gwei:.4f} gwei, block #{m.last_block:,}")

# Single chain lookup
eth = oracle.get_metrics("Ethereum")

# Force refresh (ignores cache)
oracle.refresh()

# Print formatted table
oracle.print_metrics_table()
```

**Standalone:**
```bash
python -m neuron.chain_oracle    # Prints live metrics for all 12 chains
```

**Metrics returned per chain:** `gas_price_gwei`, `block_time_ms`, `last_block`, `congestion_pct`, `finality_ms`, `stale` flag

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

### Execution Chain Endpoints

| Variable | Default |
|----------|---------|
| `CARDANO_RPC` | https://cardano-mainnet.blockfrost.io/api/v0 |
| `MIDNIGHT_RPC` | https://midnight.network/api/v0 |

### Chain Oracle

| Variable | Default |
|----------|---------|
| `ORACLE_CACHE_TTL` | 30 (seconds) |
| `ETHEREUM_RPC` | https://ethereum-rpc.publicnode.com |
| `SOLANA_RPC` | https://api.mainnet-beta.solana.com |
| `POLYGON_RPC` | https://polygon-rpc.com |
| `ARBITRUM_RPC` | https://arb1.arbitrum.io/rpc |
| `BASE_RPC` | https://mainnet.base.org |
| `PHALA_RPC` | https://phala.api.onfinality.io/public |
| `OASIS_RPC` | https://emerald.oasis.io |
| `BLOCKFROST_API_KEY` | (empty — required for Cardano live data) |
| `SEI_RPC` | https://evm-rpc.sei-apis.com |
| `HYDRA_RPC` | http://localhost:4001 |

### CLR v3.1 Routing

| Variable | Default | Description |
|----------|---------|-------------|
| `VAMS_CLR_SECURITY_THRESHOLD` | 10000 | USD threshold for P2 Ethereum routing |
| `VAMS_CLR_VELOCITY_THRESHOLD` | 1000 | ms threshold for P5 velocity routing |
| `VAMS_BRIDGE_PRIMARY_TIMEOUT` | 30000 | Primary bridge timeout (ms) |
| `VAMS_BRIDGE_SECONDARY_TIMEOUT` | 60000 | Secondary fallback timeout (ms) |
| `VAMS_MEV_BATCH_WINDOW` | 500 | MEV batch auction window (ms) |

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

The neuron integrates the official DBOS Python SDK to provide exactly-once, crash-safe workflow execution backed by PostgreSQL.

```python
from dbos import DBOS, SetWorkflowID
from neuron.workflows import vams_data_pipeline

# The actual workflow (defined in neuron/workflows.py):
# @DBOS.workflow()
# async def vams_data_pipeline() -> str:
#     data      = await step_gather_data()
#     inference = await step_run_inference(data)
#     action    = await step_execute_action(inference)
#     result    = await step_report_result(action)
#     return result

# Execute idempotently with a deterministic workflow ID
with SetWorkflowID("unique_run_123"):
    result = await vams_data_pipeline()
```

See [docs/WORKFLOW_ENGINE.md](docs/WORKFLOW_ENGINE.md) for complete details on setting up Postgres and writing durable steps.

### Demo
```bash
# Setup Postgres first (see README)
python neuron.py --demo-workflow
```

Output:
```
[WORKFLOW] Starting: DataPipeline (ID: demo_workflow_id)

  [1/4] Gather Data......
  [1/4] Gather Data...... [DONE]
  [2/4] Run Inference......
  [2/4] Run Inference...... [DONE]
  -- Simulated crash! --

[WORKFLOW] Restarting after crash...

  [RECOVERY] Resuming from step 3: run_inference
  [3/4] Execute Action......
  [3/4] Execute Action...... [DONE]
  [4/4] Report Result......
  [4/4] Report Result...... [DONE]
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

## CLR v3.1 Router

The Conditional L1 Router uses a 7-priority decision tree to route transactions:

```python
from clr_router import CLRouter, TransactionIntent, TrustTier

router = CLRouter()

# Route a compliance-privacy transaction
intent = TransactionIntent(
    value_usd=5000, max_latency_ms=60000,
    requires_privacy=True,
    requires_compliance_privacy=True,  # -> Midnight
)
decision = router.route(intent, TrustTier.SILVER)
print(f"Chain: {decision.chain}")        # Midnight
print(f"Bridge: {decision.target_bridge}")  # HyperlaneZKISM
print(f"Hash: {decision.routing_hash}")   # For ZK proof verification
```

**Priority Order:** P0 Compliance Privacy (Midnight) > P1 Confidential Compute (Phala) > P2 High Value $10K+ (Ethereum) > P3 KYC (Polygon CDK) > P4 Formal Verification (Cardano) > P5 Velocity: Hydra/SEI/Solana > P6 Default (utility-scored)

**Standalone:**
```bash
python clr_router.py   # Runs 7-scenario CLR demo
```

## MEV Protection

Multi-layered MEV prevention (Architecture Section 20.4.3):

```python
from mev_protection import MEVProtection, BatchPayment

mev = MEVProtection()

# Submit transaction with encrypted mempool
tx = mev.submit_protected_transaction_sync(
    tx_data=b"swap BTC/USDT", value_usd=10000
)
# tx.commitment_hash proves commitment without revealing content

# Batch settle x402 payments at uniform price (no sandwiching)
result = mev.settle_x402_batch_sync(payments)
print(f"Clearing price: {result.clearing_price} VAMS")
```

## Cross-Chain Bridge Executor

ICB-integrated bridge with Multi-ISM verification and timeout fallback:

```python
from bridge_executor import BridgeExecutor, BridgeFallbackHandler

# Direct execution
executor = BridgeExecutor(mock_mode=True)
result = executor.execute("Cardano", b"payload")
# result.icb_message contains the ICB BridgeMessage (mirrors icb.ak)
# result.ism_verified True if Multi-ISM 2/3 passed

# With fallback cascade (Primary -> Secondary -> Manual queue)
handler = BridgeFallbackHandler()
result = handler.bridge_with_fallback("Solana", b"fast_tx")
```

---

## ICN Modular Infrastructure (Phase 0-4)

The "ICN-Inspired" integration adds robust bottom-up infrastructure abstraction to VAMS:

### Multi-DA Performance Audit (Phase 0)
Routes performance reports (like SLA checks) to appropriate DA configurations based on criticality:
```python
from da.performance_audit import PerformanceAuditLog, LogCriticality

audit = PerformanceAuditLog(mock_mode=False)
receipt = await audit.publish_report(report_data, LogCriticality.P2_MODERATE)
print(f"Anchored to {receipt.provider} - Blob ID: {receipt.blob_id}")
```
*Adapters*: Celestia (Mocha), Near DA (Testnet), plus stubs for Avail and EigenDA. The `PerformanceAnchor.sol` contract enforces immutability.

### Sentinel Network (Phase 2)
Decentralized SLA enforcement via randomized challenge-response.
```python
from neuron.sentinel.sentinel_node import VAMSSentinelNode
from neuron.sentinel.challenges.gpu_challenge import GPUChallenge

node = VAMSSentinelNode(
    private_key="0x...",
    registry_addr="0xSLAEnforcerAddress",
    rpc_url="https://polygon-rpc.com",
    mock_mode=True
)
result = await node.run_challenge(GPUChallenge(), "0xprovider...")
print(f"Trust Score Update: {result.trust_update}")
```
*Challenge Types*: CPU, GPU, Memory, Storage IOPS, Latency. Slashes misbehaving providers via `SLAEnforcer.sol`.

### Resource Composition Engine (Phase 3)
Intelligent multi-provider instance deployment using standardized blueprints:
```python
from composer.composer import VAMSResourceComposer
from composer.blueprints import AI_INFERENCE_STANDARD

composer = VAMSResourceComposer()
plan = await composer.compose_instance(AI_INFERENCE_STANDARD)
print(f"Selected Candidate: {plan.selected_candidate.provider_name} (Score: {plan.selected_candidate.final_score})")
```
Agent simply requests an `InstanceBlueprint` and the Composer scores and provisions the best combination.

### Service Blocks & Macro Blocks (Phase 3)
Builder marketplace for composite capabilities:
```python
from services.registry_client import ServiceBlockClient
from services.macro_blocks import PRIVACY_SHIELD_ENTERPRISE

client = ServiceBlockClient()
deployment = await client.deploy_macro_block(PRIVACY_SHIELD_ENTERPRISE, "0xMyAgent")
```
Connects `ServiceBlockRegistry.sol` to execution nodes, enabling revenue-shared architecture.

### Regional Economics & Composed Settlement (Phase 4)
Dynamic DePIN incentives and cross-provider escrows:
```python
from neuron.economics.regional import RegionalEconomics
from neuron.composer.composer import VAMSResourceComposer

econ = RegionalEconomics()
multiplier = econ.get_current_multiplier("eu-central-1", active_nodes=800)

# Generate on-chain escrow parameters via the Composer (no separate client needed)
composer = VAMSResourceComposer()
escrow_params = composer.get_escrow_params(
    providers=["0xProvider1", "0xProvider2"],
    total_amount_wei=1000 * 10**18
)
# Submit escrow_params via your Web3 provider to ComposedSettlement.sol
```
Emissions run via `RegionAwareDEC.sol` to bootstrap infrastructure in underrepresented regions.

---

## Web3 Integration

On-chain agent registration with the VAMSAgentRegistry contract.

```python
from neuron.eth_client.registration import AgentRegistryClient

client = AgentRegistryClient(
    rpc_url="https://rpc.polygon.io",
    private_key="...",
    registry_address="0x..."
)

# Register agent (stake_amount, metadata_uri)
tx_hash = client.register_agent(
    stake_amount=100 * 10**18,  # 100 VAMS tokens
    metadata_uri="ipfs://..."
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
│  │  │   Kwil   │ │ WeaveDB  │ │ Glacier  │ │   DBOS SDK     │    │
│  │  │  (SQL)   │ │ (Arweave)│ │(Vector)  │ │ (PostgreSQL)   │    ││
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
| `test_clr_v3.py` | 19 | CLR v3.1 routing, MEV protection, Bridge + ICB |
| `test_composer.py`, `test_sentinel.py`, `test_economics.py`, et al. | 348 | ICN phases 0–4, DA routing, composer, sentinel, OMS integration |
| **Total** | **427** | **All pass** |

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
| v0.5.2 | Jan 2026 | Request Queue, L1 State Anchoring, x402 payments |
| v0.6.0 | Mar 2026 | CLR v3.1 (7-priority routing), MEV Protection, Bridge Exec, Chain Oracle |
| v1.0.0 | Apr 2026 | ICN Integration: Sentinel, Composer, Service Blocks, Multi-DA, Regional Econ |

---

## License

MIT License - See [LICENSE](../LICENSE)

---

**VAMS** - Verifiable and Agentic Modular Stack
*The Sovereign Brain for the Agentic Web*
