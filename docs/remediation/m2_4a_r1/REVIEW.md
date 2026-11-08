# M2.4a-R1 — fail-closed SQLite schema integrity

Date: 2026-09-23
Scope: M2-R2 Finding 1 only
Verdict: locally implemented and verified; independent M2 closure remains open

## Reviewed defect and disposition

The independent M2-R2 report at
/home/GodOfAgents/vams-evidence/m2-r2-20260923-NBrNpj/REVIEW.md correctly
identified that the M2.2 store accepted a current-version database after
checking only column names. Before editing, a temporary independently
constructed database retained the expected metadata, version, and columns but
omitted the replay composite primary key. One signed request was accepted
twice and reached the synthetic handler twice:

    SCHEMA_ACCEPTED=yes
    FIRST_STATUS 200
    SECOND_STATUS 200
    HANDLER_CALLS 2

The reproduction persisted no request body, signature, credential, nonce, or
raw signer. This review addresses only that finding. Raw-wire header ingress,
INV-5 traceability synchronization, frontend /nodes, F08 disposition, and M2
closure are unchanged.

## Implemented contract

gateway/replay_store.py now defines the one executable schema used for fresh
creation and validates it through complementary SQLite mechanisms:

- exact user_version and exact non-SQLite-owned sqlite_schema object set;
- exact table name/type, column count, WITHOUT ROWID, and strictness state;
- exact table_xinfo column order, declared types, nullability, defaults, and
  primary-key positions;
- exact index inventory, uniqueness/origin/partial flags, and index_xinfo
  key/auxiliary column ordering and collations;
- no application foreign keys and an enabled foreign-key connection policy;
- exact table/index declarations, preventing collation, conflict-policy,
  comparison, check, trigger, view, virtual-table, expression-index, or
  partial-index substitutes; and
- rollback-only behavioral probes for replay and revocation primary keys,
  digest/nonce checks, required values, metadata singleton/version checks, and
  nonnegative clock state.

Only SQLite-owned internal objects are omitted from the sqlite_schema object
set; the required internal primary-key indexes are still checked explicitly
through index PRAGMAs.

Every reservation, revocation, and cleanup opens the configured existing file,
enters BEGIN IMMEDIATE, and validates the schema on that same connection before
reading or mutating security state. A concurrent schema writer cannot replace
the validated schema before the operation. Initialization uses the same locked
validation. Malformed databases are neither repaired nor migrated, and
configured durable storage never falls back to another database or the
process-local test store.

Replay reservation now uses a normal INSERT. Only
SQLITE_CONSTRAINT_PRIMARYKEY plus confirmation that the exact four-field
namespace already exists becomes DUPLICATE; every other integrity or storage
failure returns the sanitized storage-failure outcome. The committed nonce
semantics, revocation ordering, bounded cleanup, restart behavior, and
single-host multi-process boundary are unchanged.

Compatibility is intentionally exact: databases created by the current M2.2
schema remain valid and retain populated replay/revocation state. A
same-version database with any executable-schema drift now fails closed and
requires an explicit future reviewed migration rather than automatic repair.

## Regression coverage

neuron/tests/test_m2_4a_replay_schema_integrity.py independently constructs 24
malformed real SQLite schemas. Cases include absent/subset/reordered/wrong
primary keys, rowid substitutions, type/null/default/collation/check drift,
missing/altered/unique/partial/expression indexes, insert-ignore/delete/rewrite
triggers, extra view/table/virtual-table objects, and malformed revocation
constraints.

Each malformed database is rejected at store startup. Each mutation is also
applied after the real Gateway has started, then exercised through signed
loopback HTTP; every request receives sanitized HTTP 503 and the handler count
remains zero. Separate tests cover startup-before-owned-activity rejection,
reservation and revocation checks after mutation, deterministic fresh schema,
valid populated-state restart, exact-once valid HTTP replay, the original
missing-key exploit, and sanitized output.

## Verification

The existing pinned Python environment was used; no dependency was installed.

- Pre-fix temporary reproduction: schema accepted; two HTTP 200 responses; two
  handler calls.
- Focused M2.4a schema/HTTP suite: **56 passed**.
- Complete M2.2 durable-store suite: **29 passed**.
- M2.1–M2.4a plus affected Gateway/F17 suite:
  **272 passed, 6 subtests passed**.
- Affected M1/runtime/Gateway/F17 suite:
  **413 passed, 6 subtests passed**.
- Highest-risk loopback restart, two-process replay/revocation, original
  exploit, and valid exact-once selection:
  **4 passed, 91 deselected**.
- Remediation/workflow regression set:
  **61 passed, 4 subtests passed**; workflow validation confirms all 40 actions
  remain commit-pinned.
- Scoped compilation, remediation JSON validation, searches for permissive
  inserts/schema handling/fallbacks/error leakage, and git diff --check:
  passed.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1 | Unchanged; no regional-emissions code changed. |
| INV-2 | Unchanged; no insurance-yield code changed. |
| INV-3 | Unchanged; no session-key lifetime code changed. |
| INV-4 | Unchanged; no session-key scope code changed. |
| INV-5 | Unchanged by this slice; the separate M2-R2 traceability finding remains open. |
| INV-6 | Unchanged; no TEE/root-EOA binding code changed. |
| INV-7 | Unchanged; no oracle code changed. |
| INV-8 | Unchanged; no token-supply code changed. |
| INV-9 | Unchanged; no reward-solvency code changed. |
| INV-10 | Unchanged; bridge proof and payload hash handling was not touched. |

Mock-mode selection and M1 containment are unchanged. The process-local store
remains an explicit non-live test/local/demo facility; configured malformed
durable storage is never replaced by it.

## Milestone status

M2.4a locally closes only M2-R2 Finding 1. F08 and M2 remain
REVALIDATED_OPEN. The next single slice is **M2.4b — reviewed raw-wire HTTP
ingress enforcement**.
