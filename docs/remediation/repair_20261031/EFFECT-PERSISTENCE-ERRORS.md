# Bounded effect persistence errors

Status: integrated source candidate; local fixture evidence only.

Persistence error/privacy repair28, 2026-10-31: driver failures in connection,
session/body/commit/close now expose EffectPersistenceErrorV3 with a bounded stage
and outcome UNKNOWN. Backend messages, SQLSTATE, cursor/query and diagnostic
objects are omitted from public error attributes and ordinary traceback/logger
rendering. The selected driver Error hierarchy is recognized without inspecting
payloads or initializing a different backend while handling failure. This is not
protection against process locals/debuggers or native driver/server logs/notices.

Before regression:11local tests/12failing subchecks,0errors/skips reproduced raw
synthetic detail in public rendering. After repair,177selected runtime tests pass,
including11new tests and12live-candidate containment controls. Unknown commits
return no receipt, preserve original operation identity and never retry/refund.
Domain/non-driver errors and process interrupts retain existing semantics; cleanup
failures do not replace the primary failure. A close failure after returned commit
also yields UNKNOWN and requires reconciliation. These are controlled driver/error
and real ECDSA fixture tests, not native PostgreSQL or live evidence.

Privacy source refresh:15fresh inputs with one candidate overlay;6parser tests
pass, product modules never imported/executed. Existing10table/71column,17class/
111field and4grant/28field declarations unchanged. All212prior field IDs/UNKNOWN
decisions preserved with current source anchors; stage/outcome add2nonpersistent
diagnostic slots.214rows plus7separate earned-record entries remain UNREVIEWED.
15source/required-infrastructure flows now include the error boundary. Historical
privacy20sources/results remain intact; no real private data, DB or key was read.

No DDL/checksum/storage/receipt/wire/action/policy/budget/fence/settlement changes.
Live constructors remain blocked. Authentic host policy/key isolation, actual
SQL/locks/DDL races/concurrency/crash/restart/TLS/roles and log/backup/observer
privacy acceptance remain UNKNOWN/unqualified. Native PostgreSQL/frozen full CI/
scanners/independent review remain required; local tests do not qualify them.
All INV-1throughINV-10underlying controls preserved. Existing restricted economics,
48hours and disabled Deposit/Slash activation/ExecuteIntent/fiat/yield stay.
F12/F13/F16/T04/T29/T33retain dispositions; full A--G/BOTH chains remain ACTIVE,
13open findings/0of36verified. No new UNKNOWN input question or external authority.

Design and interface

Stage G requires privacy review of effect modules, database/WAL/backups, receipts
and observers. Stage F requires lookup-only uncertain outcomes and preserved
operation identity. The existing privacy packet explicitly leaves log boundaries
unqualified. Raw driver exceptions crossed that boundary despite bounded protocol
errors; this repair adds one typed exception and no new execution route.

`EffectPersistenceErrorV3.stage` is CONNECT, SESSION, BODY, COMMIT or CLOSE.
`outcome` is always UNKNOWN. Neither field permits dispatch, retry, refund or
settlement. Do not serialize native exception context/locals or reinterpret an
error as signed evidence. Existing coordinator reconciliation catches failures
without issuing a new operation; the provider returns a receipt only after a
successful transaction. Synthetic tests observe those calls, not native effects.

[Psycopg documents](https://www.psycopg.org/docs/module.html#psycopg2.Error) backend
messages and diagnostic/cursor attributes on its error hierarchy. [PostgreSQL's
error fields](https://www.postgresql.org/docs/current/protocol-error-fields.html)
can include detail and internal queries. This implementation bounds public
rendering of selected driver errors rather than copying or parsing those fields.
The references do not qualify the unknown actual server/driver/runtime versions.

Privacy source packet

`VAMS-implementation-20261029/privacy-review28` is a local source-only refresh.
It preserves the old212field identities and all UNKNOWN decisions, rebinds lines/
source hashes, and adds2diagnostic slots. The packet is214selected slots, not214
distinct personal-data categories or full-project approval.7earned-record slots
remain separate. Current canonical byte confirmation is required after integration;
the candidate inventory is not relabelled as previously executed on another tree.

Still required: independent owner/reviewer dispositions, permitted raw workload
classes/consent, publication and observer ACLs, retention/deletion/tombstones,
provider/key isolation, actual TLS/SQL roles, native logs/notices and telemetry
sinks, privileged debugging, WAL/replica/backup/restore and loss/incident drills.
Hashes/faucet-only funds do not make raw content public. The receipt lookup is
not independent exact-byte retrieval; no public content-read route is introduced.

Native acceptance must exercise real driver/server failure categories across
connect/session/schema/query/cursor/commit/close and cleanup, validate bounded
actual log/transport output, and establish no duplicate effects/payments or
receipt escape under unknown commits. Local fake driver classes do not supply
that evidence. No service contact, install, signing, migration or deployment.
