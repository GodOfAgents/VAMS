# VAMS Neuron v0.5.2

**Immortal Agent** – Full 4-Layer Stack with TEE

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)
[![Tests](https://img.shields.io/badge/tests-79%20passed-brightgreen.svg)](#testing)

## What is VAMS Neuron?

VAMS Neuron is a **real infrastructure client** that connects to decentralized networks across four architectural layers. It's designed for building "Immortal Agents" - autonomous AI agents with:

- **Persistent Memory** - Survives crashes via checkpoint recovery
- **Decentralized Compute** - No single point of failure
- **Cryptographic Identity** - ECDSA key pair, verifiable signatures
- **TEE Attestation** - Trusted execution environment support
- **Request Guarantee** - Durable queue with retry and webhooks
- **L1 State Anchoring** - Merkle root submission to Polygon CDK
- **Chain Oracle** - Live metrics from 10 execution chains for CLR routing

## Architecture

| Layer | Providers | Status |
|-------|-----------|--------|
| **L1 Data Availability** | Celestia, EigenDA, Near, Avail, Iagon | 5/5 ✅ |
| **L2 Compute** | io.net, Akash, Render, Bittensor, Phala | 5/5 ✅ |
| **L3 Logic** | Kwil, WeaveDB, Glacier + DBOS Workflows | 3/3 ✅ |
| **L4 Trust** | Phala (SGX), Marlin (Nitro), Automata | 3/3 ✅ |
| **L5 Execution Chains** | Cardano (eUTXO), Midnight (ZK-SD) | 2/2 ✅ |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run full health check (all 17 providers)
python neuron.py --full-health

# Run crash-proof workflow demo
python neuron.py --demo-workflow
```

## CLI Commands

```bash
# Health Checks (Real Network Calls)
python neuron.py --full-health       # All 4 layers (17 providers)
python neuron.py --check-health      # Layer 1 (DA)
python neuron.py --check-compute     # Layer 2 (Compute)
python neuron.py --check-logic       # Layer 3 (Logic)
python neuron.py --check-trust       # Layer 4 (TEE)

# Workflow Demo
python neuron.py --demo-workflow     # Crash-proof execution demo

# List Providers
python neuron.py --list-providers    # Layer 1
python neuron.py --list-compute      # Layer 2
python neuron.py --list-logic        # Layer 3
python neuron.py --list-trust        # Layer 4

# Testing Mode
python neuron.py --dry-run --full-health  # Mock providers (no network)

# SDK Integration (Real Protocol Calls)
python neuron.py --sdk-health             # Check real SDK providers
python neuron.py --use-sdk                # Enable SDK mode
```

## Demo Output

```
 __     ___    __  __ ____    _   _ _____ _   _ ____   ___  _   _ 
 \ \   / / \  |  \/  / ___|  | \ | | ____| | | |  _ \ / _ \| \ | |
  \ \ / / _ \ | |\/| \___ \  |  \| |  _| | | | | |_) | | | |  \| |
   \ V / ___ \| |  | |___) | | |\  | |___| |_| |  _ <| |_| | |\  |
    \_/_/   \_\_|  |_|____/  |_| \_|_____|\___/|_| \_\\___/|_| \_|

[00:18:25] [  INFO  ] Node ID: 41e47c55ff1d8e9c
[00:18:25] [  INFO  ] Version: v0.5.1

[00:18:25] [   L1   ] LAYER 1: Data Availability Providers

  [OK] CELESTIA     1740ms | Block #9836950
  [OK] EIGENDA      1156ms | Block #5053377
  [OK] NEAR         1786ms | Block #234071245
  [OK] AVAIL        2243ms | Block #2889669
  [OK] IAGON        1892ms | Block #4321012

[00:18:30] [   L2   ] LAYER 2: Compute Providers

  [OK] IO.NET         1219ms
  [OK] AKASH          1631ms
  [OK] RENDER         1080ms
  [OK] BITTENSOR      1000ms
  [OK] PHALA_CP       1342ms

[00:18:34] [   L3   ] LAYER 3: Logic Providers

  [OK] KWIL         2153ms | Relational Backbone - Permissionless SQL
  [OK] WEAVEDB      1178ms | Permanent Logs - NoSQL on Arweave
  [OK] GLACIER      1163ms | Long-Term Memory - Vector DB

[00:18:38] [   L4   ] LAYER 4: Trust Providers (TEE)

  [OK] PHALA        2115ms | Intel SGX
  [OK] MARLIN        951ms | AWS Nitro
  [OK] AUTOMATA     1133ms | Multi-Prover
```

## Project Structure

```
neuron/
├── neuron.py          # Main client entry point
├── config.py          # Configuration & provider endpoints
├── providers.py       # Layer 1: Data Availability
├── compute.py         # Layer 2: Compute (io.net, Akash, Bittensor)
├── workflows.py       # Layer 3: Logic + DBOS-style checkpoints
├── trust.py           # Layer 4: TEE providers
├── anchoring.py       # L1 State Anchoring (Merkle roots)
├── request_queue.py   # Request Guarantee (retry + webhooks)
├── chain_oracle.py    # Chain Oracle (live metrics for 10 CLR chains)
├── clr_router.py      # Conditional L1 Router (Smart Routing)
├── agent_comms.py     # Agent-to-Agent Communication (Signed Messages)
├── demo_cli.py        # Interactive CLI demo
├── sdk/               # Real protocol SDKs
│   ├── celestia.py        # Celestia DA (blob operations)
│   ├── bittensor_subnet.py # Bittensor (metagraph, subnets)
│   └── phala_tee.py       # Multi-TEE (Phala, Marlin, Automata)
├── storage/           # Decentralized storage clients
│   ├── arweave.py         # Arweave permanent storage
│   ├── kwil.py            # Kwil SQL client
│   └── local.py           # Local SQLite fallback
├── payments/          # Payment protocols
│   └── x402.py            # x402 micropayments
├── web3/              # On-chain integration
│   ├── registration.py    # Agent registry client
│   └── abi.json           # Contract ABIs
├── tests/             # Unit & integration tests (100+ total)
│   ├── test_neuron.py     # 16 tests (providers, managers)
│   ├── test_sdk.py        # 29 tests (Celestia, Bittensor, Phala)
│   ├── test_workflows.py  # 15 tests (checkpoints, recovery)
│   ├── test_gateway.py    # API server tests
│   ├── test_oracle.py     # Oracle & Cache tests
│   ├── test_clr_router.py # Router logic tests
│   ├── test_comms.py      # Messaging signature tests
│   └── test_economics.py  # Circuit breaker tests
├── README.md
├── DOCS.md
└── requirements.txt
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Expected output
============================= 60 passed in 44.29s =============================
```

## Documentation

See [DOCS.md](DOCS.md) for full documentation including:
- Environment variables
- Provider details
- Cryptography
- Troubleshooting

## License

MIT
