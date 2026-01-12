# VAMS Neuron v0.5.0

**Immortal Agent** – Full 4-Layer Stack with TEE

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

## Architecture

| Layer | Providers | Status |
|-------|-----------|--------|
| **L1 DA** | Celestia, EigenDA, Near, Avail | 4/4 ✅ |
| **L2 Compute** | io.net, Akash, Render, Bittensor | 4/4 ✅ |
| **L3 Logic** | Kwil, WeaveDB, Glacier | 3/3 ✅ |
| **L4 Trust** | Phala, Marlin, Automata | 3/3 ✅ |

## Quick Start

```bash
pip install -r requirements.txt
python neuron.py --full-health
```

## CLI Commands

```bash
# Health Checks
python neuron.py --full-health       # All 4 layers (15 providers)
python neuron.py --check-health      # Layer 1 (DA)
python neuron.py --check-compute     # Layer 2 (Compute)
python neuron.py --check-logic       # Layer 3 (Logic)
python neuron.py --check-trust       # Layer 4 (TEE)

# Workflow Demo
python neuron.py --demo-workflow     # Crash-proof demo

# List Providers
python neuron.py --list-providers    # Layer 1
python neuron.py --list-compute      # Layer 2
python neuron.py --list-logic        # Layer 3
python neuron.py --list-trust        # Layer 4
```

## Project Structure

```
neuron/
├── neuron.py          # Main client
├── config.py          # Configuration
├── storage.py         # SQLite storage
├── providers.py       # Layer 1 (DA)
├── compute.py         # Layer 2 (Compute)
├── workflows.py       # Layer 3 (Logic)
├── trust.py           # Layer 4 (Trust)
└── README.md          # Documentation
```

## Documentation

See [DOCS.md](DOCS.md)

## License

MIT
