# VAMS Neuron

**Runtime version:** v1.0.0-amoy
**Lifecycle:** Implemented runtime with restricted live routes
**Last verified:** 2026-07-12

Neuron is the Python runtime for routing, composition, DA reporting, SDK
capabilities, sentinel telemetry, economics, and workflow demonstrations.
It is not a deployed network client and must not be used to infer live support
for every provider named in source.

## Safety Boundary

- Local development may use explicit mock clients.
- Testnet and production environments reject mock identity, payment, bridge,
  TEE, DA, interrupt, and storage paths.
- Celestia and Near are the default live-capable DA routes; receipts remain
  required before they can support testnet evidence.
- Avail and EigenDA are structured stubs and are excluded from live operation.
- Workflow examples use DBOS durability but their external actions remain demo
  steps until real integrations and exactly-once side-effect evidence exist.

## Setup

```bash
python -m pip install -r neuron/requirements.txt
python -m pytest -q neuron/tests --tb=short -p no:cacheprovider
```

Run focused safety checks when changing live-route behavior:

```bash
python -m pytest -q \
  neuron/tests/test_runtime_safety.py \
  neuron/tests/test_gateway_auth_hardening.py \
  neuron/tests/test_sequence_wallet.py
```

## Components

| Path | Responsibility |
| --- | --- |
| `clr_router.py` | Conditional routing decisions and fail-closed compliance paths. |
| `bridge_executor.py` | Cross-chain proof/payload separation and mock rejection. |
| `da/` | Performance-audit records and DA adapters. |
| `sdk/` | Session keys, identity, storage, TEE, DA, and provider clients. |
| `composer/` | Resource matching, skill, and CHC cognitive scoring. |
| `sentinel/` | Challenge and telemetry processing. |
| `workflows.py` | DBOS-backed demo workflow orchestration. |

See [DOCS.md](DOCS.md), [workflow documentation](docs/WORKFLOW_ENGINE.md),
and the repository [documentation index](../docs/README.md).
