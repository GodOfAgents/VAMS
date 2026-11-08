# Effect-store uniqueness prerequisites

Status: integrated source candidate, local controlled-driver checks only.

Effect persistence uniqueness guard27, 2026-10-31: the V3provider, V3authority
and storage4authority now inspect required primary/unique keys before transaction
bodies. Matching migration metadata alone is insufficient. The local before
regression has10tests/110failing subchecks,0errors: invalid or absent catalog
responses were ignored and bodies entered. These are controlled driver results,
not a native PostgreSQL duplicate-effect demonstration. The repaired full selected
suite passes166tests,0failures/errors/skips, including11new guard tests and12live-
mode containment tests. Windows3.12/real ECDSA fixture keys/queued driver evidence
remains distinct from authentic host policy, native PostgreSQL or live assurance.

Acquire literal table locks before the first schema SELECT freezes a serializable
snapshot; inspect required key columns/types/non-nullability, primary/unique kind,
immediate/nondeferrable/validated constraints and live/ready/valid unique B-tree
indexes with expected built-in operator classes. Reject partial/expression indexes,
inheritance/partition/unlogged tables, malformed responses, missing/extra/duplicate
keys and inspection/lock errors before yielding a protected body. Key declarations
cannot be rebound after database construction. No cache, fallback, automatic
schema repair or execution retry. Native lock/DDL-race semantics remain untested.

This checks uniqueness prerequisites only. It does not attest the whole schema,
foreign/check constraints, server integrity, privileges, triggers, RLS, backups,
WAL, TLS, storage durability or operator custody. Approved server/driver/role and
current-host manifests remain UNKNOWN. SQL parsing/execution and constraint/DDL-
race/concurrency/crash/restart/unknown-commit acceptance on real PG are NOT_RUN.
New table locks/catalog reads add operational work requiring native measurement.

DDL/migration checksums/storage versions, protocol wire/goldens, logical operation
identity, budgets and historical reconciliation semantics remain unchanged.
Only3persistence modules and test/doc files changed; no new persistent fields.
Prior privacy20source identities for affected modules need refresh/review; old
inputs/results remain historical.212field rows plus7earned-record entries remain
UNREVIEWED. No actual database, provider, key or private record was accessed.
Live constructors still reject. All restricted economics/48hours/disabled
Deposit/Slash activation/ExecuteIntent/fiat/yield remain. INV-1throughINV-10
executable controls outside persistence are untouched; uniqueness supports the
effect/budget boundary without proving token backing or external exactly-once.
F12/F13/F16and T04/T09/T15/T29/T33retain dispositions. Full A--G/BOTH chains,
13open findings/0of36verified remain. No new provider/runner input question.

Design basis

Stage F requires operation uniqueness and atomic provider effects. Existing
ASYMMETRIC-OBJECT-V3, AUTHORITY-V3, RENEWAL-V4, GCA_ACCEPTANCE and ADR-VDSO-001
require retained authority and lookup-only uncertain outcomes. A stored migration
checksum declares what was intended; it cannot establish current index state.
This guard keeps those contracts and rejects insufficient uniqueness evidence.

The [PostgreSQL constraint catalog](https://www.postgresql.org/docs/current/catalog-pg-constraint.html)
identifies key columns and associated indexes. Its [index catalog](https://www.postgresql.org/docs/current/catalog-pg-index.html)
exposes validity, readiness, liveness and immediate uniqueness state. Table locks
are acquired before schema reads, following the documented [LOCK ordering](https://www.postgresql.org/docs/current/sql-lock.html).
Expected built-in B-tree operator names follow the [PostgreSQL source catalog](https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/include/catalog/pg_opclass.dat).
These official references guide implementation; they do not qualify the unknown
runner/server version or establish that this SQL has run successfully.

Native acceptance still required

1. Supply the approved independent Linux3.12/real PostgreSQL/server/driver/CA/role
   manifest, exact version and disposable database scope; no reserved R28.
2. Execute fresh and existing migrations, verify expected19keys across10tables,
   and repeat transaction entry under the actual application role and TLS boundary.
3. Remove/alter each required key or non-null/type/index property on disposable
   copies; assert no protected body/effect/receipt/payment escapes. Measure the
   actual native body and effect, not a queued response or raised error alone.
4. Race ALTER/DROP/index changes with transaction entry, concurrent operation/
   nonce/resource collisions, fence changes, crash/commit uncertainty and restart.
   Verify lock ordering, bounded costs and no automatic retries or duplicate effects.
5. Review full schema/roles/server/trigger/RLS integrity separately and refresh
   privacy/WAL/backup/observer disposition. Authentic policy/provider isolation,
   recovery/settlement integration and independent assurance remain mandatory.

No migration or service was invoked. Existing reviewed execution restrictions and
all broader qualification gates remain. Focused local checks cannot promote either
chain to canary/public readiness or establish universal Immortal Execution.
