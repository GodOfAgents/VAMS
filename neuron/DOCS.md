# VAMS Neuron Documentation

## Overview

VAMS Neuron is a multi-chain Data Availability (DA) monitor that connects to Layer 1 blockchain networks and generates cryptographically signed telemetry. It's part of the VAMS (Verifiable and Agentic Modular Stack) infrastructure.

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

---

## Quick Start

```bash
# Run with defaults (Celestia)
python neuron.py

# Use a specific provider
python neuron.py --provider near

# Check all provider health
python neuron.py --check-health
```

---

## Supported DA Providers

| Provider | Network | Block Time | Best For |
|----------|---------|------------|----------|
| **Celestia** | mocha-4 | ~12s | Default, general purpose |
| **EigenDA** | holesky | ~12s | High-value, Ethereum security |
| **Near DA** | testnet | ~1s | High-frequency, fast finality |
| **Avail** | turing | ~20s | ZK proofs, Validium |

---

## CLI Reference

### Basic Usage
```bash
python neuron.py [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--provider NAME` | `-p` | Set primary provider (celestia, eigenda, near, avail) |
| `--list-providers` | `-l` | List all available providers |
| `--check-health` | | Check health of all providers |
| `--no-failover` | | Disable automatic failover |
| `--interval SEC` | `-i` | Heartbeat interval in seconds |
| `--version` | `-v` | Show version |
| `--help` | `-h` | Show help |

### Examples

```bash
# Use Near DA with 15-second interval
python neuron.py --provider near --interval 15

# Run without failover
python neuron.py --no-failover

# List providers
python neuron.py --list-providers
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAMS_PROVIDER` | celestia | Default provider |
| `VAMS_FAILOVER` | true | Enable auto-failover |
| `VAMS_GATEWAY` | http://localhost:8000 | Gateway URL |
| `HEARTBEAT_INTERVAL` | 30 | Seconds between heartbeats |
| `CELESTIA_RPC` | https://rpc-mocha.pops.one | Celestia RPC |
| `EIGENDA_RPC` | https://disperser-holesky.eigenda.xyz | EigenDA RPC |
| `NEAR_RPC` | https://rpc.testnet.near.org | Near RPC |
| `AVAIL_RPC` | https://turing-rpc.avail.so | Avail RPC |

### Example
```bash
export VAMS_PROVIDER=near
export HEARTBEAT_INTERVAL=60
python neuron.py
```

---

## Files Generated

| File | Description |
|------|-------------|
| `node_identity.pem` | ECDSA private key (Secp256k1) - **Keep safe!** |
| `neuron_data.db` | SQLite database with heartbeats and metrics |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    VAMS Neuron v0.2                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   CLI/Args   │───►│   Provider   │───►│  Storage  │ │
│  │   Parser     │    │   Manager    │    │  (SQLite) │ │
│  └──────────────┘    └──────────────┘    └───────────┘ │
│                             │                           │
│         ┌───────────────────┼───────────────────┐       │
│         ▼                   ▼                   ▼       │
│  ┌───────────┐    ┌─────────────┐    ┌───────────────┐ │
│  │ Celestia  │    │   EigenDA   │    │ Near / Avail  │ │
│  │    RPC    │    │     RPC     │    │     RPC       │ │
│  └───────────┘    └─────────────┘    └───────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
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
  "version": "v0.2.0-alpha",
  "node_id": "41e47c55ff1d8e9c",
  "block_height": 9628553,
  "provider": "celestia",
  "timestamp": 1736703540.123,
  "nonce": "a1b2c3d4e5f67890"
}
```

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

---

## Version History

| Version | Features |
|---------|----------|
| v0.1.0 | Celestia monitoring, identity, SQLite storage |
| v0.2.0 | Multi-provider (Celestia, EigenDA, Near, Avail), CLI, failover |

---

## License

MIT License - See [LICENSE](../LICENSE)

---

**VAMS** - Verifiable and Agentic Modular Stack  
*The Sovereign Brain for the Agentic Web*
