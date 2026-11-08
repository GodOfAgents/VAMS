# T33 local-storage and legacy-gateway source follow-up — 2026-10-19

Status: **source-only inventory extension; T33 remains BLOCKED.** This note
does not approve a privacy policy, access or retention period, release, or
gateway behavior. No tests, database, gateway, provider, or publication path
was executed.

## Scope and bindings

Canonical checkout: branch `testnet/remediation-20260907`, HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`. The working tree contains
unrelated dirty work; the following hashes bind inspected working-tree bytes,
not a clean release commit.

| Artifact | SHA-256 |
|---|---|
| `neuron/storage/local.py` | `11ddead7b5ca4c3ad25c438446f114d3faff02b4bd8882665f2bf5571fef23a5` |
| `neuron/neuron.py` | `ad5a1222aed48bb69cba74bc3ac9175cf0cabac0e18c6450df7ba3a600333e7a` |
| `neuron/config.py` | `c41e8f3ea8f3cf1fbb84d051de1ae353d8d37d6b9ef59927ea563a05ea57c0df` |
| `neuron/gateway/server.py` | `ea9e4e2388e1bbf2ff2ac62e8afbf66a97f69821da0b1f47c90feb8584704f66` |
| `docs/audit/privacy-publisher-inventory.json` | `9647d33860b0fc3e255e156a9d7877fcf78e05ce7b6805c5dd2bda085c5dd040` |
| `docs/audit/schemas/privacy-publisher-inventory.schema.json` | `d794ea6d68a08f06a7a27c50b4f5ad9adc104984d9198665858aea19adcd9c44` |
| `docs/audit/schemas/privacy-review.schema.json` | `43e84da932a311e2b8d18f832526d92f38d018c8d1d8f196376f5a8084760c67` |
| `T33_PRIVACY_SOURCE_REVALIDATION_20261018.md` | `5422dd9597326cfac11393b78d46f98e5a35fbc401108a4b3cbe33a435dcc505` |
| `T33_PRIVACY_FLOW_SOURCE_FOLLOWUP_20261018.md` | `5b67aea9268080c768c157ed26913fb960a82d80dbd150a922ca4c1b02739156` |

## Additional source findings

1. `VamsNeuron.__init__` constructs `NeuronStorage`. `send_heartbeat`
   constructs JSON telemetry containing `node_id`, block height, provider,
   timestamp, and nonce, signs that payload, and stores the node ID, height,
   network, payload, and signature (`neuron/neuron.py:430-440`).
2. `NeuronStorage` stores those fields in its SQLite `heartbeats` table and
   returns the payload and signature from `get_unsynced_heartbeats`
   (`neuron/storage/local.py:25-42,65-96`). `mark_synced` updates sync
   metadata; the inspected class has no deletion, expiry, or retention method
   (`:98-112`). `DATABASE_PATH` comes from `VAMS_DB_PATH`, defaulting to
   `neuron_data.db` (`neuron/config.py:20`). This is source evidence only; it
   does not identify a live database, filesystem permissions, backups,
   downstream readers, or effective retention.
3. The legacy `neuron.gateway.server` logs the full registration `node_id`
   and includes heartbeat exception text in logs and an HTTP error response
   (`:80-127`). Its lifespan rejects live runtime policy, and `VamsNeuron.main`
   routes `--gateway-server` through that entrypoint (`neuron/neuron.py:806-818`).
   These are code-level restrictions, not observation that the service is
   absent or effectively blocked in a deployed environment. The endpoints
   remain data-flow inventory items for any profile that could enable them;
   otherwise the exact profile exclusion must be bound.
4. The publisher inventory schema explicitly limits its scope to
   `neuron/da`, `neuron/sentinel`, and `neuron/vdso`. It is not a schema for
   local persistence, gateway responses, logs, or a complete field-level data
   inventory. The new paths therefore expose an inventory gap; they do not
   justify changing or expanding that publisher schema without review.

## Gate disposition

T33 remains **BLOCKED**. The evidence still needs a complete producer,
consumer, recipient, storage, access, and retention inventory; owner/privacy
approval for the covered fields and linkability; exact-tree redaction and
public-content evidence; and the schema-required named independent review.
No privacy classification or policy is selected here. No finding or control
matrix status is changed.
