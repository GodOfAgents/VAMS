# VAMS

**Verifiable and Agentic Modular Stack**
**Architecture:** v0.8.0
**Status:** Hardened pre-testnet candidate
**Last verified:** 2026-07-12

VAMS is a multi-layer protocol implementation for verifiable agent execution,
resource composition, identity, and economic coordination. It includes Solidity
contracts, Cardano validators, a Python Neuron runtime, a FastAPI Gateway, and
a React frontend.

VAMS is not mainnet-ready and has not been deployed to public testnet. The
first testnet profile is faucet-only: staking rewards, real fiat, real yield,
and wallet transactions are disabled. Deployment and readiness evidence is
tracked fail-closed in [the status report](REPO_STATUS_REPORT.md),
[deployment register](contracts/CONTRACTS.md), and
[audit program](docs/audit/AUDIT_PROGRAM.md).

## Documentation

- [Documentation index](docs/README.md)
- [Current architecture](docs/ARCHITECTURE.md)
- [Versioning](docs/VERSIONING.md)
- [Repository status and roadmap](REPO_STATUS_REPORT.md)
- [Developer guide](docs/DEVELOPER_GUIDE.md)
- [Node operator guide](docs/NODE_OPERATORS.md)
- [Gateway API reference](docs/API_REFERENCE.md)
- [Audit and architecture report](audit.md)

## Repository Layout

| Path | Purpose |
| --- | --- |
| `contracts/` | Foundry Solidity contracts, tests, and deployment scripts. |
| `cardano/` | Aiken validators for governance, timelock, insurance, identity, and agent NFTs. |
| `neuron/` | Python runtime, SDK, DA, composer, economics, sentinel, and bridge components. |
| `gateway/` | FastAPI control-plane service and Caddy testnet template. |
| `frontend-vite/` | Read-only testnet frontend. |
| `docs/` | Current guides, architecture history, audit controls, and research context. |

## Implementation Boundary

| Component | Current state |
| --- | --- |
| EVM contracts | Implemented in source; Polygon Amoy deployment evidence pending. |
| Cardano validators | Implemented in source; Cardano Pre-Prod deployment evidence pending. |
| Celestia and Near DA | Live-capable code paths; receipt evidence pending. |
| Avail and EigenDA DA | Structured stubs; blocked from live environments. |
| OMS, Trails, Coinme, TEE, bridge, interrupts, storage | Mock-default or incomplete paths fail closed in live environments. |
| Gateway | Implemented; live DID, mTLS, TLS, rate-limit, and load evidence pending. |
| Frontend | Read-only profile; wallet transactions disabled. |

## Local Verification

Install the toolchains before running the relevant subsystem commands.

```bash
git clone https://github.com/GodOfAgents/VAMS.git
cd VAMS
git submodule update --init --recursive

cd contracts
forge build --sizes
forge test -vvv

cd ../cardano
aiken check --deny --seed 20260711 --max-success 250

cd ..
python -m pip install -r gateway/requirements.txt -r neuron/requirements.txt
python -m pytest -q --tb=short -p no:cacheprovider

cd frontend-vite
npm ci
npm audit --audit-level=high
npm run build
```

Run the documentation and audit structure checks from the repository root:

```bash
python scripts/docs/validate_docs.py
python scripts/audit/audit_program.py validate
python scripts/audit/validate_traceability.py
```

Passing local checks is not release evidence. The canary and public readiness
commands require a clean commit, signed evidence, live integration records, and
deployment manifests.

## License

MIT. See [LICENSE](LICENSE).
