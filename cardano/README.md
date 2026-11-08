# VAMS Cardano — Brain Layer

**Lifecycle:** Governance v2 source candidate; native qualification and Cardano Pre-Prod deployment pending
**Source reality reviewed:** 2026-10-28; native compilation, ledger checks and independent review pending

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

## Qualification prerequisites

Use the specifically authorized Aiken1.1.21 runner, reviewed pinned dependency
manifest, ledger parameters and evidence destination. Runner/Slot08 authorization
remains outstanding; these instructions do not authorize installation or execution.
Do not substitute the retained blueprint for a fresh current-source build.

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
| `governor` / `governance_policies` | Legacy governance source | Inadmissible for release; historical encodings retained |
| `governance_v2` | Authenticated governance candidate | Backed votes, exact state/refunds, 48-hour Queue; uncompiled/unreviewed |
| `timelock` | Legacy intent source | No qualified bridge execution; v2 requires 48 hours and rejects ExecuteIntent |
| `insurance_fund` | Capital custody | Bridge deposits, guardian multisig claims, 50% max payout |
| `agent_registry` | Agent DID | NFT identity (CIP-68), reputation scoring, stake slashing |

## Current evidence and release boundary

`validators/governance_v2.ak` and `lib/vams/governance_v2*` are new versioned
candidate source.61 native tests are prepared; zero have executed. Fifteen Python
reference checks establish byte/value arithmetic only. The retained `plutus.json`
is historical and does not contain qualified applied identities for this source.
Legacy governance is not an admissible release fallback. Current-source native,
cross-script, applied-budget/ledger, custody, privacy and independent review plus
enforced deployment binding remain necessary. See
[`ADR.md`](../docs/remediation/repair_20261028/ADR.md).

## Intended cross-chain flow (not qualified)

The diagram below is architectural intent. V2 ExecuteIntent always rejects until
authentic source-checkpoint/inclusion/destination/replay verification qualifies
for Cardano Pre-Prod and Polygon Amoy. A Mithril certificate alone is insufficient.


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
