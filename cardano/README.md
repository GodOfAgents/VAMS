# VAMS Cardano Brain Layer

**Lifecycle:** schema-v2 source hardening in progress; Pre-Prod deployment pending

**Last reviewed:** 2026-07-15

This directory contains the Cardano-local governance, insurance, and agent
identity controls for the faucet-only Pre-Prod profile. Source code and an
unapplied Aiken blueprint are not deployment evidence.

## Deployment boundary

Exactly four persistent spending validators are in scope:

| Validator | Authenticated state transition |
| --- | --- |
| `agent_registry.ak` | Preserves an owner-controlled agent identity asset and exact value; deregistration burns the asset and refunds the owner. Slashing is disabled. |
| `governor.ak` | Preserves a unique proposal asset through voting and emits one exact Cardano-local timelock intent after quorum. |
| `insurance_fund.ak` | Preserves a canonical fund asset and coordinates committed claim states, approvals, and exact payouts. Cross-chain deposits are disabled. |
| `timelock.ak` | Executes only configured Cardano-local target scripts after delay and before expiry. Bridge execution is disabled. |

Three one-shot minting policies authenticate creation/bootstrap and are
recorded separately from the persistent validators:

- `agent_nft.ak`: seed-UTxO-bound agent identity creation;
- `proposal_nft.ak`: seed-UTxO-bound proposal creation and terminal burn;
- `fund_nft.ak`: one-time canonical insurance-fund bootstrap.

`lib/vams/vdso.ak` remains a conformance library. It is not a validator and
must never appear in a deployment transaction or persistent-validator list.

## State model

All pre-deployment datums use `cardano_schema_version = 2`. Agent, proposal,
intent, fund, and claim states carry their full authentication asset class.
Creation policies commit to unique seed UTxOs and destination script hashes;
spending transitions preserve the authenticated asset class and exact inline
datum/value successor. Initial execution is Cardano-local only. Slashing,
cross-chain deposits, bridge execution, VDSO value operations, rewards, and
incentives fail closed.

## Build and test

Use the repository-pinned Aiken compiler and dependency versions:

```bash
cd cardano
aiken check --deny --seed 20260713 --max-success 250
aiken build
```

`aiken build` generates `plutus.json`. The blueprint still contains
parameterized templates; do not submit those templates. Follow
`docs/runbooks/CARDANO_PREPROD_REHEARSAL.md` to bind public governance and seed
parameters, apply them deterministically, independently recompute hashes, and
stop before submission for explicit approval.

## Layout

```text
cardano/
|-- aiken.toml
|-- lib/vams/
|   |-- types.ak
|   |-- utils.ak
|   |-- icb.ak
|   `-- vdso.ak              # conformance-only
|-- validators/
|   |-- agent_registry.ak    # persistent
|   |-- governor.ak          # persistent
|   |-- insurance_fund.ak    # persistent
|   |-- timelock.ak          # persistent
|   |-- agent_nft.ak         # auxiliary one-shot policy
|   |-- proposal_nft.ak      # auxiliary one-shot policy
|   `-- fund_nft.ak          # auxiliary bootstrap policy
`-- plutus.json              # generated, parameterized blueprint
```

## License

MIT - VAMS Protocol
