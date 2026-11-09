# F12: native PostgreSQL crash/restart campaign (2026-11-09)

Status: **CAMPAIGN RUN ON POSTGRESQL 18.6: PASS 7/7, negative control
detects 6/6 unfinished states. Non-author review pending.** F12 stays
REVALIDATED_OPEN. This is native local evidence for one acceptance item
(kill/restart around each effect boundary on the V3 object-effect path), not
the whole finding. Readiness is unchanged: 13 findings open, 0 of 36 tracks
verified, NOT READY.

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

`--negative-control` runs the same kills but skips worker 2. The state checks
(effect count, terminal status, budget) must then fail at every kill point
that left work unfinished, and pass only at `after_accept`. This shows the
checks can fail, so a PASS is not vacuous.

## Environment

| Item | Value |
|---|---|
| Server | PostgreSQL **18.6** (Debian 18.6-1.pgdg13+2), the version named in `m5_1_postgres_qualification_plan_r1_20261006.md` |
| Image | official `postgres:18`, pinned `postgres@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42`, pulled with owner approval on 2026-11-09 |
| Container | `vams-pg18`, bound to `127.0.0.1:55433` only |
| Transport | TLS 1.3, `sslmode=verify-full`, local CA `~/.vams-tools/pg/ca.crt` |
| Driver | psycopg2 2.9.13 |
| Source base | commit `9b18755` plus the campaign script change in this slice |
| Script SHA-256 | `4c528ad28a94a6876837d2f75d02e584cc67985a9ef064053ead074c601690b7` |

## Results

Evidence files, next to this document:

- `f12-native-pg-campaign-20261109.json`: SHA-256
  `b40dbdb3d1e191cc9aa7fbbdf079c5781f8a91d52aa4c20b037f7ef7c027ec74`.
  Status PASS, 7/7.
- `f12-native-pg-negative-control-20261109.json`: SHA-256
  `1445845ef077b3cefdec67365209b9b4c8131cc72e8be9905b51cc9f7d6de5d8`.
  Status NEGATIVE_CONTROL_DETECTED, 7/7 as expected.

An earlier identical run (run 1, before the negative-control flag was added)
also passed 7/7. Only run 2 is retained as evidence.

| Kill point | State left by the kill | Recovery | Final effects | Final status | Budget (spent / reserved) |
|---|---|---|---|---|---|
| `before_reserve_commit` | no operation row (reservation rolled back) | execute | 1 | committed | 3 / 0 |
| `after_reserve` | reserved, 3 units held | execute | 1 | committed | 3 / 0 |
| `after_claim` | dispatched, provider never called | compensate | 0 | rejected | 0 / 0 |
| `provider_precommit` | dispatched, provider insert rolled back (0 effects) | compensate | 0 | rejected | 0 / 0 |
| `after_provider_commit` | dispatched, 1 provider effect | reconcile | 1 | committed | 3 / 0 |
| `accept_precommit` | dispatched (authority accept rolled back), 1 effect | reconcile | 1 | committed | 3 / 0 |
| `after_accept` | committed | reconcile | 1 | committed | 3 / 0 |

At every point:

- worker 1 exited 137;
- there was exactly one authority operation row;
- the admitted epoch and policy version (3 / 7) matched the proposal;
- a repeat `execute` was refused.

At the two compensated points, a late provider commit after compensation was
refused (`EffectV3Error`).

Negative control (no recovery): the state checks failed at 6 of 6 unfinished
points and passed only at `after_accept`.

## Observations for review

1. **Compensation drains the whole scope.** After a fenced cutover the scope
   moves from `active` to `draining`. One crash between dispatch claim and
   provider commit therefore stops that scope from admitting new work until
   an operator provisions a new scope. This is fail-safe, but it is an
   operational cost the runbook and drills (T36) should cover.
2. **PostgreSQL 18 is a hard requirement.** `neuron/effect_postgres_v3.py:249`
   and `neuron/effect_authority_store_v5.py:392` query
   `pg_constraint.conenforced`, which exists only in PostgreSQL 18. On 17 the
   store fails closed with an opaque `EffectPersistenceErrorV3` (outcome
   UNKNOWN). Deployment requirements should say "PostgreSQL 18 or later". A
   later change could add an explicit server-version check, so the error
   names the cause. Not changed here.

## Still outside this campaign

- Token payment (the Solidity settlement path, covered by its own tests).
- Real provider hosts.
- Network partition, failover and replicas.
- Power loss or kernel crash (the kills are `os._exit` at instrumented
  boundaries).
- The V4/V5 renewal and journal paths.
- Contention, query plans, WAL and backup/restore qualification (M5.1).
- Independent review.
