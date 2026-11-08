# T33 privacy schema-to-evidence crosswalk — 2026-10-19

Status: **source-only planning crosswalk; T33 remains BLOCKED.** This file
does not approve a privacy policy, data disclosure, access or retention
period, test result, public release, or schema-compliant privacy review.

## Bound current artifacts

Canonical checkout: branch `testnet/remediation-20260907`, HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`. The worktree is dirty; these
hashes identify inspected working-tree bytes, not a clean release commit.

| Artifact | SHA-256 |
|---|---|
| `docs/audit/schemas/privacy-publisher-inventory.schema.json` | `d794ea6d68a08f06a7a27c50b4f5ad9adc104984d9198665858aea19adcd9c44` |
| `docs/audit/schemas/privacy-review.schema.json` | `43e84da932a311e2b8d18f832526d92f38d018c8d1d8f196376f5a8084760c67` |
| `docs/audit/privacy-publisher-inventory.json` | `9647d33860b0fc3e255e156a9d7877fcf78e05ce7b6805c5dd2bda085c5dd040` |
| `neuron/neuron.py` | `ad5a1222aed48bb69cba74bc3ac9175cf0cabac0e18c6450df7ba3a600333e7a` |
| `neuron/storage/local.py` | `11ddead7b5ca4c3ad25c438446f114d3faff02b4bd8882665f2bf5571fef23a5` |
| `neuron/config.py` | `c41e8f3ea8f3cf1fbb84d051de1ae353d8d37d6b9ef59927ea563a05ea57c0df` |
| `neuron/gateway/server.py` | `ea9e4e2388e1bbf2ff2ac62e8afbf66a97f69821da0b1f47c90feb8584704f66` |
| `gateway/server.py` | `ace02242ab38aa9fa5afa4371be21a1a7d2329d5b9241dec30c7d503ff393c7e` |
| `neuron/sentinel/sentinel_node.py` | `6851359dafaf721f715b291bc744cad2e43c4794dece68fd9fdae9d006497919` |
| `neuron/da/models.py` | `ad8b1ce7d9e4219471cef22127511b464752a4c0c69be9b876409785ebcc39d3` |
| `neuron/da/performance_audit.py` | `79b1dde2a6e1162bb019f13100a78d5dcc939c5c1b9a64a7f06f748a206aa474` |
| `neuron/vdso/da.py` | `84ada9c4cf724ab12f9542fef3f138929f0a751964849e99ad16b14c785882fb` |
| `neuron/vdso/sidecar.py` | `269e2449344e41621d51b3ff155c8c84f9cf2f6ced193425f2697ca6e7b0abb3` |
| `T33_PRIVACY_SOURCE_REVALIDATION_20261018.md` | `5422dd9597326cfac11393b78d46f98e5a35fbc401108a4b3cbe33a435dcc505` |
| `T33_PRIVACY_FLOW_SOURCE_FOLLOWUP_20261018.md` | `5b67aea9268080c768c157ed26913fb960a82d80dbd150a922ca4c1b02739156` |
| `T33_LOCAL_STORAGE_SOURCE_FOLLOWUP_20261019.md` | `72a58fc8a1b34724700d42d9ee7961edb8a9f9da53cc26766fce29550c60c0ed` |

`docs/audit/evidence/` currently contains only
`vdso-review-evidence.json` (SHA-256
`07016b03ca82cc797636e8ce74297714af0ee7c393307e2329abe54b7e9f6b53`). No
privacy review record or the schema-required privacy evidence bundle is
present there.

## Schema boundary

`privacy-publisher-inventory.schema.json` fixes `scope` to exactly
`neuron/da`, `neuron/sentinel`, and `neuron/vdso`. Its entries describe
publisher routes and their channel, payload policy, live capability,
release-evidence eligibility, controls, and tests. The current seven entries
are not a field-level inventory of local persistence, gateway responses,
logs, recipients, access controls, or retention. This crosswalk does not
silently expand that schema or relabel the seven entries as complete for the
whole repository.

`privacy-review.schema.json` requires an exact commit, named reviewer and
organization, review time, approved data inventory and retention policy,
passing redaction tests, public-content review, complete publisher inventory,
zero open blockers, and hash-bound evidence artifacts for those five areas.
The schema requires true/zero values; it is not evidence that any condition
has been met. No such review is created here.

## Requirement-to-evidence crosswalk

| Required privacy-review evidence | Current source evidence | Missing acceptance evidence / dependency |
|---|---|---|
| `data_inventory` | The three retained T33 source notes enumerate DA/sentinel serialization and consumers, the gateway `/da/anchors` path, local SQLite heartbeat fields, and legacy gateway logs. Current source hashes above still match the records. | One exact-tree inventory spanning every producer, consumer, external recipient, data category/field, local and provider storage, access boundary, and retention path. The notes explicitly leave runtime consumers, deployment/database access, logging destinations, and provider-side retention unverified. Privacy Lead must decide permitted fields and linkability. |
| `retention_policy` | Source shows local SQLite heartbeat rows include node ID, payload, and signature; `mark_synced` marks rows but the inspected storage class has no deletion/expiry method. Performance-audit history is process-memory and uncapped in the inspected source. | Owner/privacy approval for local DB, logs, process memory, backups, gateway history, and provider copies, including access and deletion/expiry periods. No retention period is inferred from code. |
| `redaction_tests` | Existing source review describes tests for selected KPI/telemetry filtering and pseudonymization. | Fresh results bound to the exact final source tree, including semantic review of numeric KPI disclosure, stable pseudonym/state-hash linkability, all raw-report consumers, and every in-scope output/log. Test definitions or old runs are not pass evidence here. |
| `public_content_review` | The retained publisher inventory marks Celestia/performance-audit as release-evidence-ineligible pending independent observation; the existing public-content scanner has narrow path scope. | Current exact-tree content review and redaction evidence. The existing scanner is not a general PII review and does not establish public-content safety. |
| `publisher_inventory` | The current schema-bound inventory contains seven publisher routes within its fixed three-path scope. Source notes identify additional local-storage and gateway flows outside that publisher-route view. | Privacy reviewer must reconcile complete in-scope publishers against the fixed schema and the separate field-level inventory. Any schema-scope change needs a separately reviewed design change; this crosswalk does not make one. |
| Schema review record | Current schema and inventory bytes are hash-bound above. | A named independent human and organization must approve the exact inventory, retention policy, redaction results, public-content review, and completeness; then create a schema-valid record bound to the exact commit and artifact hashes with zero blocking findings. |

## Source-observed flows requiring owner classification

- `VamsNeuron.sign_telemetry` and `send_heartbeat` create a signed JSON
  payload containing `node_id`, block height, provider, timestamp, and nonce,
  then store the ID, payload, and signature locally
  (`neuron/neuron.py:429-440`; `neuron/storage/local.py:65-112`).
- The legacy `neuron.gateway.server` logs full registration IDs and formats
  heartbeat exception text into its log and error response
  (`neuron/gateway/server.py:81-127`). This describes code, not an observed
  running service; its live-mode rejection does not prove deployment absence.
- The main gateway parses heartbeat payload identity and telemetry fields,
  stores node state in process memory, and returns the node ID and heartbeat
  count (`gateway/server.py:85-107,723-820`). The `/da/anchors` route returns
  selected audit-history records (`gateway/server.py:1073-1096`). Earlier
  source review found that `limit=0` can return the full in-memory list; no
  request or runtime access test was run here.
- Sentinel challenge reports contain raw node and sentinel identifiers and
  raw KPI objects before DA serialization (`neuron/sentinel/sentinel_node.py:143-175`).
  The existing DA serialization path pseudonymizes selected identifiers and
  filters selected fields, but source review does not prove every consumer or
  log uses that serializer (`neuron/da/models.py:43-198,240-297`).
- VDSO sidecar code defines encrypted payload, content hash, policy hash, and
  recipient-envelope fields (`neuron/vdso/sidecar.py:146`;
  `neuron/vdso/da.py:91`). The existing publisher inventory describes the
  adapter as ineligible for live evidence; this is not deployment or recipient
  access evidence.

## Disposition and next actions

This is an additive schema crosswalk and source summary, not a complete data
inventory, privacy decision, independent review, redaction run, or T33
acceptance. It leaves the fixed publisher-inventory schema unchanged and
selects no data-release, pseudonymization, or retention policy.

Next, the Privacy Lead must approve data categories/fields, identifier and
hash linkability, recipients, local/provider access, and retention. Then an
authorized exact-tree slice must complete any needed redaction tests and
public-content review. A named independent privacy reviewer must review the
resulting bound artifacts and produce the schema-required record. T33 remains
BLOCKED pending those decisions and evidence; no control-matrix status changes.

No source, schema, workflow, tests, privacy policy, runtime, provider, or
deployment state changed. No tests, scanners, gateway requests, database,
network, publication, or live service were run.
