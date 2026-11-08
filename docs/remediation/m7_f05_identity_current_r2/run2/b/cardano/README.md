# VAMS Cardano — Brain Layer

**Lifecycle:** Implemented source; Cardano Pre-Prod deployment pending
**Last verified:** 2026-07-12

> **"The Brain"** — Governance sovereignty, insurance custody, and agent identity on Cardano.

## Architecture

```
cardano/
├── aiken.toml              # Project config
├── lib/vams/
│   ├── types.ak            # Shared datums & redeemers
│   ├── utils.ak            # Math, validation, time helpers
│   └── icb.ak              # ICB bridge verification
├── validators/
│   ├── governor.ak         # Quadratic voting governance
│   ├── timelock.ak         # Intent emission → Polygon
│   ├── insurance_fund.ak   # Capital custody + claims
│   └── agent_registry.ak  # Agent DID + NFT identity
│   └── agent_nft.ak       # One-shot agent NFT minting policy
└── plutus.json             # Generated blueprint (after build)
```

## Prerequisites

- [Aiken](https://aiken-lang.org) (`aikup` → `aiken`)
- WSL (Windows) or native Linux/macOS

```bash
# Install Aiken
curl -sSfL https://install.aiken-lang.org | bash
aikup
aiken --version
```

## Build & Test

```bash
cd cardano/

# Type-check and run tests
aiken check

# Compile to Plutus Core
aiken build

# View generated blueprint
cat plutus.json
```

## Validators

| Validator | Purpose | Key Features |
|-----------|---------|-------------|
| `governor` | On-chain governance | Quadratic voting, quorum, double-vote prevention |
| `timelock` | Intent relay | 48h/24h delay, Mithril proof, nonce replay protection |
| `insurance_fund` | Capital custody | Bridge deposits, guardian multisig claims, 50% max payout |
| `agent_registry` | Agent DID | NFT identity (CIP-68), reputation scoring, stake slashing |

## Cross-Chain Flow

```
Cardano (Brain)          ICB Bridge            Polygon (Hands)
─────────────────       ──────────            ─────────────────
Governor: Propose
  → Vote (quadratic)
  → Pass ──────────→ Timelock: Queue
                        → Delay 48h
                        → Execute ──→ ICB Relay ──→ GovernorExecutor
                                                     → Apply on Polygon
```

## License

MIT — VAMS Protocol
