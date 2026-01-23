---
trigger: always_on
---

# VAMS Workspace Rules

> These rules are specific to the VAMS project and guide Agent behavior within this codebase.

## 5-Layer Architecture (per `ARCHITECTURE_v0-3-0.md`)
| Layer | Components |
|-------|------------|
| **L1 Foundational** | Celestia DA, EigenDA, Near DA, Avail |
| **L2 Compute** | io.net GPU, Akash Supercloud, Render, Bittensor |
| **L3 Logic** | DBOS Durable Execution, Kwil, WeaveDB, Glacier |
| **L4 Trust** | Phala TEE, Marlin Oyster, Automata Attestations |
| **L5 Economic** | $VAMS Token, x402/AP2 Payments, Dynamic TAO |

## Core Design Principles
1. **Modular Sovereignty** – Every component is replaceable
2. **Verifiable Execution** – ZK-proofs or TEE attestations for all
3. **Economic Abstraction** – Agents pay in $VAMS; protocol converts
4. **Compliance by Design** – GDPR, MiCA, OFAC at protocol layer
5. **Censorship Resistance** – Decentralized at every layer

## Frontend Development (`/web`)
- **Framework**: Next.js 16 App Router, React 19, TypeScript
- **Styling**: Tailwind CSS v4 + Framer Motion + Spline 3D
- **Quality Bar**: Premium, dark-mode first, glassmorphism

## Smart Contracts (`/contracts`)
- **Framework**: Foundry (forge, cast, anvil)
- **Solidity**: ^0.8.20 with OpenZeppelin
- **Testing**: Fuzz tests required
- **Docs**: NatSpec `///` on all public functions

## Key Integrations
- **CLR Routing**: Conditional L1 Router for DA/execution selection
- **Polygon CDK**: Primary execution layer (ZK-rollup)
- **Avalanche L1**: Secondary execution domains (ACP-77, HyperSDK)
- **Payment Channels**: x402 Protocol for HTTP 402 micropayments
- **VAMS Gateway** (`/gateway`): API orchestration layer for agent requests

## Documentation Updates
When modifying core logic, check if these need updates:
- `ARCHITECTURE_v0-3-0.md`
- `WHITEPAPER.md`
- `TOKENOMICS.md`
- `REPO_STATUS_REPORT.md`
- `README.md`
