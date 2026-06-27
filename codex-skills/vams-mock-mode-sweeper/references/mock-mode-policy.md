# VAMS Mock Mode Policy

Mock mode is allowed only for deterministic unit tests, demos, and local dry-runs.
Mock mode must never provide evidence for deployment, security posture, DA proofs,
identity verification, escrow state, bridge execution, or TEE trust.

High-risk current paths:

- `neuron/da/adapters/avail_adapter.py`: structured stub, always mock.
- `neuron/da/adapters/eigenda_adapter.py`: structured stub, always mock.
- `neuron/sdk/avail_substrate.py`: `AVAIL_MOCK_MODE` defaults to true.
- `neuron/sdk/eigenda_kzg.py`: `EIGENDA_MOCK_MODE` defaults to true.
- `neuron/sdk/trails_client.py`: `TRAILS_MOCK_MODE` defaults to true.
- `neuron/sdk/oms_identity.py`: `OMS_MOCK_MODE` defaults to true.
- `neuron/payments/coinme_client.py`: mock can be selected by env or demo key.
- `neuron/sdk/phala_tee.py`: `PHALA_MOCK_MODE` defaults to true.
- `gateway/server.py`: DA audit mode is controlled by `VAMS_MOCK_MODE`.
- `neuron/sdk/interrupt_handler.py`: real handlers include `NotImplementedError`.

Minimum live-mode gate:

- Read `VAMS_ENV` or equivalent.
- If environment is `staging`, `testnet`, or `production`, reject all live-path mocks.
- Emit clear startup failure naming the offending component.
- Add tests for rejection and allowed local behavior.
