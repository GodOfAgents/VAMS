# T33 privacy and public-data source revalidation — 2026-10-18

Status: **source-only assessment; T33 remains BLOCKED.** This document is not a
privacy approval, data-retention decision, redaction-test result, or public
release review. No application code or test was changed or executed.

## Scope and bound source snapshot

The canonical repository is branch `testnet/remediation-20260907` at HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`; the working tree is extensively
modified and untracked. The following hashes bind the inspected working-tree
bytes, not a clean release commit:

| Artifact | SHA-256 |
|---|---|
| `neuron/da/models.py` | `ad8b1ce7d9e4219471cef22127511b464752a4c0c69be9b876409785ebcc39d3` |
| `neuron/da/performance_audit.py` | `79b1dde2a6e1162bb019f13100a78d5dcc939c5c1b9a64a7f06f748a206aa474` |
| `neuron/sentinel/sentinel_node.py` | `6851359dafaf721f715b291bc744cad2e43c4794dece68fd9fdae9d006497919` |
| `neuron/tests/test_performance_audit.py` | `60077671383a85e44d4dd32bd6454524ff769280fe0d3e7bfcd51cd5e4437022` |
| `neuron/tests/test_da_live_boundaries.py` | `349f9bdeb3e0080cceced0739dbdad3810de5592d2281cc902a1f3664e2b19d0` |
| `docs/audit/privacy-publisher-inventory.json` | `9647d33860b0fc3e255e156a9d7877fcf78e05ce7b6805c5dd2bda085c5dd040` |
| `docs/audit/schemas/privacy-publisher-inventory.schema.json` | `d794ea6d68a08f06a7a27c50b4f5ad9adc104984d9198665858aea19adcd9c44` |
| `docs/audit/schemas/privacy-review.schema.json` | `43e84da932a311e2b8d18f832526d92f38d018c8d1d8f196376f5a8084760c67` |
| `scripts/security/public_content_policy_scan.py` | `bb7a7a90a0a6dbd004852988c0acfcb6ccd50361f761d40c1c481edd3ab1b512` |
| `docs/audit/control-matrix.json` | `28b9146bb2ace970c19441ab4cd8ee4f91937d56acf4f178b3639f5b4f493cf4` |

The current publisher inventory has seven route entries across `neuron/da`,
`neuron/sentinel`, and `neuron/vdso`. It records channel, payload policy,
operational-live capability, release-evidence eligibility, control references,
and named tests. It is a publisher-route inventory, not a complete data
inventory: it does not enumerate each field's data subject/category, origin,
consumer, access policy, storage location, or retention period.

## Current data paths and limits

| Path | Source behavior | Privacy consequence / evidence gap |
|---|---|---|
| Sentinel challenge report | `VAMSSentinelNode.execute_challenge` constructs and returns a dictionary containing the raw hexadecimal `nodeId`, raw `sentinelId`, raw `result.kpis`, challenge result, timestamp, and duration (`sentinel_node.py:143-175`). It may add telemetry derived from `world_state_trace`. | The in-memory report returned by this method is not the serialized public form. The caller set and any persistence or logging of this raw object are not inventoried here. `audit_node` passes it to the DA publisher and, on its current success path, to `_submit_sla_report`; the latter is presently a stub. |
| DA serialization | `AuditReport.from_sentinel_report` and `serialize` normalize IDs, validate bounded identity/result fields, filter KPIs, and allowlist selected telemetry (`models.py:43-62,101-198,239-297`). | This is a serialization boundary, not proof that all raw-report consumers use it. The pseudonym is deterministic, domain-separated SHA-256 over the identifier with a fixed public prefix and no secret key. It hides the input text in ordinary output but does not prevent dictionary recovery for guessable identifiers or cross-record linkability within a domain. |
| KPI values | `sanitize_public_kpis` rejects keys containing listed sensitive fragments and accepts only booleans or bounded finite numeric scalars (`models.py:17-35,101-129`). Strings and nested objects are not serialized as KPIs. | Key-fragment filtering and scalar type checks do not establish semantic safety for every numeric KPI. A caller can place identifying or sensitive information in a numeric value under an innocuous key. The accepted key/value inventory and disclosure policy are not bound. |
| Fidelity and gain telemetry | `sanitize_public_telemetry` accepts selected hash-shaped state identifiers, bounded scores, step numbers, telemetry labels, gain values, and anomaly fields (`models.py:140-198`). | Hash-shaped state fields remain stable correlation handles; hashing alone does not establish anonymity. Per-field disclosure, correlation, and retention review is absent. |
| Local audit history | `PerformanceAuditLog` appends pseudonymized node ID, protocol, provider blob ID, height, report hash, and timestamp to an in-memory list (`performance_audit.py:135-137,273-281`). `get_audit_history(limit)` slices the returned view but does not cap or expire the stored list (`performance_audit.py:332-334`). | Process-lifetime retention is unbounded in this object. No deletion, expiry, access-control, or export policy is established by these methods. Provider-side DA retention and access are outside this code path and remain unreviewed. |
| Public-content path scanner | `public_content_policy_scan.py` checks Git cached/non-ignored-untracked paths against only `docs/funding/**` and `docs/team/idex-*.md`. | It is not a PII/content scanner and does not inspect ignored paths or history. The retained 2026-10-03 run was on a dirty checkout and is not current evidence for the present dirty worktree. It cannot satisfy T33 public-content review. |

The publisher inventory marks Celestia and the performance-audit publisher as
operationally live-capable but ineligible for release evidence without an
independent observer. Avail, EigenDA, Near, the legacy Sentinel publisher, and
the VDSO encrypted sidecar remain non-live or otherwise ineligible in that
inventory. Those statements describe the inventory's scope and do not prove
all repository publishers or data sinks have been enumerated.

## Existing tests and retained privacy evidence

`test_performance_audit.py` contains source assertions for redacting selected
string/nested KPI values, filtering selected telemetry, domain-separated
identifier pseudonyms, and rejecting malformed public fields. These are test
definitions only; they were not run or accepted as current exact-tree test
evidence in this assessment. No test currently cited here establishes that
arbitrary numeric KPI encodings are harmless, that pseudonyms meet the owner's
linkability policy, or that every raw-report consumer follows the serializer.

`docs/audit/schemas/privacy-review.schema.json` requires a review bound to an
exact commit and artifact hashes, with a named reviewer and organization,
approved data inventory and retention policy, passing redaction tests,
public-content review, complete publisher inventory, and zero open blocking
findings. The canonical `docs/audit/evidence/` directory has no privacy review
record; its retained evidence is not sufficient for this schema.

## Gate disposition and next requirements

T33 remains **BLOCKED**. The current work supplies useful route-level and
source-level evidence, but it does not satisfy the required complete data
inventory, current redaction-test results, retention/access decision, or
artifact-bound public-release review. No status in `control-matrix.json` was
changed.

The next privacy-owned work is to approve the data categories and fields that
may leave the process, the treatment of stable pseudonyms and state hashes,
provider and local retention/access periods, and the complete producer/consumer
inventory. Then bind redaction tests and public-content review to the exact
source snapshot and produce the schema-required review with a named human and
organization. These are owner/reviewer decisions; this source assessment
selects no privacy policy. No new tests, scans, provider calls, or public
publication were authorized or performed.
