# M5 / F10 / T30 DA source revalidation — 2026-10-18

Status: **source inspection only; no test, provider call, live integration, or
independent review. No finding or track is closed by this note.**

Repository: `/home/GodOfAgents/code/VAMS-testnet`, HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`. The worktree is dirty; these
observations bind the file bytes listed below, not a clean release commit.

## Current-source observations

| Source file | SHA-256 | Inspected lines | Observation |
|---|---|---:|---|
| `neuron/da/performance_audit.py` | `79b1dde2a6e1162bb019f13100a78d5dcc939c5c1b9a64a7f06f748a206aa474` | 39–57, 300–314 | The live-capable routing set contains Celestia only. Near, Avail, and EigenDA are separately configured but are not live-capable. `verify_report` reconstructs a `DAReceipt` directly from mapping fields. |
| `neuron/da/models.py` | `ad8b1ce7d9e4219471cef22127511b464752a4c0c69be9b876409785ebcc39d3` | 201–236 | `DAReceipt` is a plain dataclass with annotated fields and no field-agreement or runtime validation in the class. This does not satisfy the open canonical strict-receipt requirement by itself. |
| `neuron/da/adapters/celestia_adapter.py` | `0498c0c4fc3d69ab72bd989efae82577917e6f1c601efb43f59957f98fef1f3e` | 26–44, 50–135, 137–188 | Celestia has live submission and retrieval code paths; `verify_blob` hashes retrieved bytes against the receipt commitment. The adapter sets `release_evidence_eligible = False`; this path does not provide an independent observer or establish provider inclusion/finality. |
| `neuron/verifiers/celestia_light_client.py` | `79795899bb6d3f9e608b6ec80a14f90fbe6b8a78198b6d306e800bd2db8ed889` | 43–87 | Live construction raises `LiveModeSafetyError`. In non-live mode, mock sampling is non-authoritative; the non-mock probe requests only `header.NetworkHead` and returns false. It does not sample or verify the requested data root. |
| `neuron/da/adapters/near_adapter.py` | `6d797515bbce468c3e7e0579e38ef315002798ed766505a7cc7985db97ea338b` | 42–68 | Non-mock submission raises until signed blob-store submission and exact retrieval exist; verification returns false and retrieval returns no bytes. |
| `neuron/da/adapters/avail_adapter.py` | `20e471706c4587feddafbb0c93c3e730fc000b0ce9da30af52edcef228c31c02` | 53–96 | Live construction is rejected. The available submission creates a simulated, non-authoritative receipt; verification returns false and retrieval is unavailable. |
| `neuron/da/adapters/eigenda_adapter.py` | `5cc57044bcff0712b0f4a1a9cf43ccaa7c54e317635af590502bc475a3c02050` | 45–95 | Live construction is rejected. The available submission creates a simulated, non-authoritative receipt; verification returns false and retrieval is unavailable. |
| `neuron/da_router.py` | `d09f2592c87ec8bda0c00cf26240a332a73259c2e1d417094848bdd8d72ea30c` | 40–58, 129–147 | The legacy router rejects live runtime and rejects non-mock operation. Its mock path supplies placeholder Polygon signatures and treats other provider verification optimistically; it is not live evidence. |
| `neuron/verifiers/polygon_dac_client.py` | `9369f438673bd7e9e9eca4ec1dc5173c0076cca6cd6dff4ce694c43e6bd44751` | 4–24 | The placeholder DAC client increments its valid-signature count for every supplied item. The commented-out `ecrecover` is not implemented; the 2-of-N label is not cryptographic verification. |

## Gate disposition

F10 remains `REVALIDATED_OPEN`; T30 remains `blocked`. The current testnet
evidence requirement calls for both Celestia Mocha and Near Testnet receipts,
`mock_mode=false`, distinct submitter and retrieval-observer identities,
provider-native inclusion/finality references, and exact retrieved bytes whose
hash matches the submitted payload. No such owner-observed evidence package is
present in this source inspection. Near's current live path is blocked, and the
Celestia adapter's release-evidence eligibility is false.

The missing evidence remains real provider submission, exact independent
retrieval, inclusion/finality, strict receipt identity/field agreement, and
failure/recovery observations. No route is promoted from mock or source-level
capability declarations. A real route and separate observer require external
provider access and an appropriately authorized integration effort.

## Documentation reconciliation

Corrected the current-state claims in `docs/L3_CHAIN_AND_DA.md`,
`neuron/da/README.md`, and `REPO_STATUS_REPORT.md`, and recorded the correction
in `docs/CHANGELOG.md`. The prior statements that VAMS performs Celestia DAS,
achieves a 99.9% availability guarantee, or verifies Polygon DAC signatures
were not supported by current source. No runtime source or behavior changed.

No tests, builds, provider calls, external transactions, or network requests
were run. The T30 gate, all deployment/activation gates, and overall readiness
remain unchanged.
