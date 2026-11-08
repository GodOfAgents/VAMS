# M2.2 durable replay and revocation current-source revalidation

Date: 2026-10-03
Status: PASS for the focused M2.2 SQLite replay suite; independent review PASS.

## Verification

The focused neuron/tests/test_m2_2_durable_replay.py suite passed 29/29 under pinned Python 3.12.14 / pytest 9.1.1, network isolated, checkout read-only, and evidence output isolated. It uses disposable SQLite databases and spawned local processes. Exact command, hashes, output, and exit are recorded here.

Coverage includes same-nonce races across processes, distinct nonces, restart and revocation persistence, revocation ordering, transactional/storage failure, bounded cleanup, schema/path and permission rejection, no live-mode process-local fallback, authentication before nonce consumption, raw request material exclusion, and gateway startup ordering. Credentials and identities are synthetic.

## Limits

This establishes local SQLite behavior for the declared single-host shared-filesystem boundary. It does not establish PostgreSQL or multi-host durability, external identity-provider operation, live ingress/TLS, or deployment readiness. No source, credential, vendor, or deployment state changed.
