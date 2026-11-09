# F12: native PostgreSQL crash/restart campaign (2026-11-09)

Status: **CAMPAIGN WRITTEN; NOT YET RUN. Blocked on a PostgreSQL 18 server.**
F12 stays REVALIDATED_OPEN. Readiness is unchanged: 13 findings open, 0 of
36 tracks verified, NOT READY.

## Why this campaign

Every existing effect-store test (`test_effect_provider_v3.py`,
`test_effect_authority_v3.py`, `test_effect_authority_store_v5.py`,
`test_effect_pg5_migration_v5.py` and others) uses fake database drivers.
Their docstrings say so ("NOT native PG"). The F12 acceptance requires real
crash/restart evidence:

> "Kill workers before and after each external-effect boundary and before
> checkpoint persistence. Restart on a second worker."

## What the campaign does

`scripts/remediation/effect_v3_native_pg_campaign.py` exercises the real
`ObjectEffectCoordinatorV3`, `PostgresEffectAuthorityV3`,
`PostgresObjectProviderV3` and both real PostgreSQL stores, over TLS
verify-full.

For each kill point it does the following:

1. Creates fresh authority and provider databases, runs both explicit
   migrations, and installs a scope.
2. Starts **worker 1** as a separate OS process. It runs `execute` and dies
   with `os._exit(137)` at the kill point.
3. Starts **worker 2** as another fresh process. It runs the recovery
   procedure:
   - execute, if nothing was dispatched;
   - otherwise reconcile;
   - if the provider has no evidence, compensate by fenced cutover plus
     authenticated absence, which refunds the reservation.
4. Checks the databases directly:
   - exact provider effect count;
   - the authority's terminal status;
   - budget arithmetic: spent 3 or 0, reserved 0;
   - the policy epoch and version preserved in the retained admission;
   - a repeat execute is refused;
   - a late commit after compensation is refused.

| Kill point | Boundary | Expected recovery | Provider effects | Final status |
|---|---|---|---|---|
| `before_reserve_commit` | Reservation transaction open, COMMIT never sent | execute | 1 | committed |
| `after_reserve` | Reservation committed, dispatch not claimed | execute (same admission) | 1 | committed |
| `after_claim` | Dispatch claimed, provider never called | compensate (fence + absence refund) | 0 | rejected |
| `provider_precommit` | Provider insert executed, COMMIT never sent | compensate | 0 | rejected |
| `after_provider_commit` | Provider effect committed, authority not told | reconcile | 1 | committed |
| `accept_precommit` | Authority accept executed, COMMIT never sent (checkpoint) | reconcile | 1 | committed |
| `after_accept` | Everything committed; worker dies before returning | reconcile | 1 | committed |

Keys are fixed LOCAL-ONLY test keys, derived deterministically so every
process is identical. The database password reaches child processes only
through `PGPASSWORD`. It never appears in a DSN, argument or log.

## What blocked the run

The first run against the runner's PostgreSQL **17.11** container failed in
the first migration. A local diagnostic, which lets raw driver errors
through, showed the cause:

```text
column c.conenforced does not exist
```

`pg_constraint.conenforced` was added in **PostgreSQL 18**.
`PostgresEffectDatabaseV3._verify_foreign_keys_and_triggers` and
`effect_authority_store_v5.py` query it in the schema check that runs on
**every** transaction.

This is not a code defect against the project's target. The reviewed
qualification plan (`m5_1_postgres_qualification_plan_r1_20261006.md`)
names PostgreSQL 18.6, and the API docs repeatedly reference PG18. On
PostgreSQL 17 the store fails closed with `EffectPersistenceErrorV3`
(outcome UNKNOWN), which is safe but unusable.

Consequence for operators: the effect stores **require PostgreSQL 18 or
later**. That should be stated in deployment requirements. A later change
could add an explicit server-version check, so the failure names the real
cause instead of an opaque UNKNOWN.

Starting a PostgreSQL 18 container (the official `postgres:18` image, pinned
by digest, on `127.0.0.1:55433`, with the same local TLS CA) was refused by
the session's permission check because it downloads external code. It needs
the owner's approval. Nothing was worked around.

## To finish

1. **Owner:** approve pulling the official `postgres:18` image, or provide
   another PostgreSQL 18 server.
2. Run the campaign with `--port 55433`, or the provided server's settings.
   Record the JSON beside this file.
3. Investigate any kill point that does not recover as expected. That is the
   F12 evidence.
4. **Still outside this campaign:**
   - token payment (the Solidity settlement path, covered separately by its
     own tests);
   - real provider hosts;
   - network partition and failover;
   - power loss;
   - the V4/V5 renewal and journal paths.
