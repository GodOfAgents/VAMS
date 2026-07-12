# VAMS Versioning

**Last verified:** 2026-07-12

VAMS has several version identifiers. They describe different artifacts and
must not be conflated into a deployment or release claim.

| Identifier | Meaning | Current repository value | Authority |
| --- | --- | --- | --- |
| Architecture | Protocol architecture documentation | v0.8.0 | `docs/team/ARCHITECTURE_v0-8-0.md` |
| OMS milestone | Historical OMS integration milestone | v1.3.0-oms | `docs/CHANGELOG.md` |
| Neuron runtime | CLI/runtime configuration value | v1.0.0-amoy | `neuron/config.py` |
| Gateway runtime | Gateway health/OpenAPI version | v0.2.0-alpha | `gateway/server.py` |
| Cardano package | Aiken package version | 0.1.0 | `cardano/aiken.toml` |
| Frontend package | Private frontend package version | 0.0.0 | `frontend-vite/package.json` |

There is no tagged repository release that establishes a unified production
version. The repository is an **unreleased pre-testnet candidate**. A future
release identifier must be created from a clean, tested, commit-bound release
candidate; documentation must not invent one beforehand.
