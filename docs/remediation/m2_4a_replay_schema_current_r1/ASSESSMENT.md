# M2.4a replay-schema integrity current-source revalidation

Date: 2026-10-03
Status: PASS for the focused M2.4a schema-integrity suite; independent review PASS.

## Verification

The focused neuron/tests/test_m2_4a_replay_schema_integrity.py suite passed 56/56 under pinned Python 3.12.14 / pytest 9.1.1, network-isolated with read-only source and a separate writable evidence folder. Exact command, hashes, output, and exit are recorded here.

Coverage includes 24 malformed schema forms, post-startup schema mutation, fail-closed startup before activity, no automatic repair or overwrite, deterministic valid schema, preservation of populated replay/revocation state, loopback duplicate-request handling, and sanitized failures.

## Limits

This is disposable local SQLite and loopback integration with synthetic fixtures. It does not establish PostgreSQL, multi-host or production database behavior, public TLS ingress, real provider effects, external identity, or testnet readiness. No source, credentials, vendor, or deployment state changed.
