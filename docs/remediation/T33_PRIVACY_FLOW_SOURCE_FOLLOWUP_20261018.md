# T33 raw-report and gateway-consumer source follow-up — 2026-10-18

Status: **source-only inventory extension; T33 remains BLOCKED.** This is not
a privacy approval, retention decision, redaction-test result, independent
review, or deployment assessment. No application code or tests were changed or
executed.

## Scope and bindings

Canonical repository: branch `testnet/remediation-20260907`, HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`; worktree remains extensively
modified and untracked. This follow-up extends, without replacing, the source
assessment `T33_PRIVACY_SOURCE_REVALIDATION_20261018.md` (SHA-256
`5422dd9597326cfac11393b78d46f98e5a35fbc401108a4b3cbe33a435dcc505`). Its
ten previously bound source/schema hashes were re-read and still match.

Additional current working-tree bindings:

| Artifact | SHA-256 |
|---|---|
| `neuron/sentinel/sentinel_node.py` | `6851359dafaf721f715b291bc744cad2e43c4794dece68fd9fdae9d006497919` |
| `neuron/da/performance_audit.py` | `79b1dde2a6e1162bb019f13100a78d5dcc939c5c1b9a64a7f06f748a206aa474` |
| `neuron/da/models.py` | `ad8b1ce7d9e4219471cef22127511b464752a4c0c69be9b876409785ebcc39d3` |
| `gateway/server.py` | `ace02242ab38aa9fa5afa4371be21a1a7d2329d5b9241dec30c7d503ff393c7e` |
| `gateway/route_policy.py` | `15166275718db36c9c68692a98a8fccbaee0ec3342fac0102cf9989305116916` |
| `gateway/route_security.py` | `c1b56ada6d3640ba9c6bf6e5bafc01ea0eab0494805835e280aadaba47a336b0` |
| `neuron/tests/test_m2_3_gateway_routes.py` | `793c7820ac3ee8b7fdf4080720a6b847fc640894d772015e86d7384d5146cdfb` |
| `neuron/tests/test_performance_audit.py` | `60077671383a85e44d4dd32bd6454524ff769280fe0d3e7bfcd51cd5e4437022` |
| `docs/audit/privacy-publisher-inventory.json` | `9647d33860b0fc3e255e156a9d7877fcf78e05ce7b6805c5dd2bda085c5dd040` |
| `docs/audit/schemas/privacy-publisher-inventory.schema.json` | `d794ea6d68a08f06a7a27c50b4f5ad9adc104984d9198665858aea19adcd9c44` |
| `docs/audit/schemas/privacy-review.schema.json` | `43e84da932a311e2b8d18f832526d92f38d018c8d1d8f196376f5a8084760c67` |
| `docs/API_REFERENCE.md` | `b13671bc886933bccc7767c49f7cd7ddcfbba7a346eb03839c8efb90081a6d43` |
| `docs/audit/THREAT_MODEL.md` | `395b697f996ace205d5dc616ca822ac48a556c564eab49fdfeec4dc56b88ef3e` |

## Source-level producer, consumer, and sink trace

1. `VAMSSentinelNode.execute_challenge` constructs and returns an in-memory
   dictionary containing full hexadecimal `nodeId`, full `sentinelId`, raw
   challenge KPIs, challenge category, score/result, timestamp, and duration;
   optional gain and world-state-fidelity telemetry are added. It also logs
   eight-character prefixes of the node identifier and operator address.
2. `audit_node` is the production call site found for `execute_challenge` in
   the repository. It sends the raw dictionary to
   `PerformanceAuditLog.publish_sentinel_report`. Failure, exception, and
   anomaly log paths also include a node-ID prefix; one exception path formats
   the exception text into the log record.
3. `publish_sentinel_report` converts the raw dictionary to `AuditReport` and
   serializes a normalized representation for the DA adapter. That serialized
   path pseudonymizes identifiers and filters KPIs/telemetry, but does not
   establish that every other consumer or log uses the serializer.
4. When both the SLA-enforcer address and private key are configured,
   `audit_node` passes the raw report and DA response to `_submit_sla_report`.
   The current function does not use those arguments in a transaction: its
   transaction construction and send calls are commented out, while it logs
   “On-chain submission completed successfully.” This is not evidence of an
   on-chain publication or a completed data transfer.
5. `PerformanceAuditLog` appends pseudonymized `node_id`, protocol, provider
   `blob_id`, height, report hash, and timestamp to an in-memory list. The list
   has no cap or expiry. `get_audit_history(limit)` slices only the returned
   view; it does not limit stored history.
6. `gateway.server` exposes that list through `GET /da/anchors`. The route
   returns the selected history, protocol filter, and runtime summary. The
   route signature defaults `limit` to 50 but does not declare a maximum. The
   current `history[-limit:]` expression returns the entire list for `limit=0`
   (`-0 == 0`) and for a sufficiently large positive limit. This is a
   source-level observation; no request was sent. The response therefore
   requires explicit inventory and approved access/retention treatment even
   though its node identifier is pseudonymized.
7. The route policy classifies `/da/anchors` as `AUTHENTICATED_READ`, and
   `GatewayRouteSecurityMiddleware` authenticates protected routes before
   invoking the handler; live requests also pass the middleware's trusted
   ingress check. `docs/API_REFERENCE.md` describes the endpoint as an
   authenticated read. These are source/document observations only. The
   route tests were not run, and no live ingress or client authorization was
   observed.
8. `rg` found no other production call to `execute_challenge`,
   `publish_sentinel_report`, or `get_audit_history` beyond the paths above;
   tests and documentation contain additional references. This is a bounded
   source search, not proof of complete runtime or external-consumer closure.

The current publisher inventory schema intentionally limits its scope to
`neuron/da`, `neuron/sentinel`, and `neuron/vdso`, and describes publishers,
not data consumers, log destinations, access, or retention. The separate
privacy-review schema requires an approved data inventory, approved retention
policy, passing redaction tests, public-content review, complete publisher
inventory, named reviewer/organization, exact commit/artifact bindings, and
zero open blocking findings. The inventory and schema constraints do not
approve the gateway disclosure or its retention.

## T33 disposition and required decisions

This trace adds the gateway response, process-local history, identifier-prefix
logs, and conditional SLA call to the source inventory needed for review. It
does not decide whether identifier prefixes, stable pseudonyms, state/report
hashes, KPI values, provider blob IDs, or timestamps may be disclosed; who may
receive them; or how long local logs, in-memory history, and provider copies
may persist. Logging destinations and provider-side retention are not
established by these source files.

The unbounded history and `limit=0` source behavior require owner/privacy and
gateway-security review. No repair is made here. Any code change and regression
test require a separately authorized bounded slice. T33 remains BLOCKED until
the complete producer/consumer/recipient/retention inventory, owner-approved
policy, exact-tree redaction tests, public-content review, and schema-compliant
independent privacy review are available.

No tests, scanners, gateway requests, provider calls, network activity, or
publication were performed. No finding or control-matrix status was changed.
