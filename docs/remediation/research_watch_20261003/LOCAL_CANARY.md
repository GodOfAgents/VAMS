# Local effect canary operator guide

This is a local qualification harness. It is not a staging or testnet provider and does not authorize chain writes.

## Boundaries

- Run the operator CLI in a separate trusted process. Do not put the PostgreSQL DSN or either provider key in model context or inference-process environment.
- Set VAMS_ENV to exactly local, test, or demo in the operator and provider processes.
- The provider binds to 127.0.0.1 only and refuses a public host. Use a dedicated private directory for its SQLite file; the service rejects directories that are accessible to other users.
- Use two distinct random keys of at least 32 bytes encoded as hex. Keep writer and observer keys in secret stores. The observer uses a different authenticated route, though this initial service does not establish an independent operator.
- The DSN uses application tables prefixed vams_effect_; DBOS uses its own configured system database.
- Use synthetic bytes and an implementation digest built from the exact provider artifact. Budget and action ceilings are integer units without monetary meaning.

## Provider process configuration

Configure VAMS_EFFECT_PROVIDER_DB, VAMS_EFFECT_WRITER_KEY, VAMS_EFFECT_OBSERVER_KEY, VAMS_EFFECT_TARGET_ID, and VAMS_EFFECT_IMPLEMENTATION_DIGEST. Set VAMS_ENV=local, test, or demo. Start it with:

    python3 -m neuron.effect_provider

The service uses port 8765 by default and only listens on IPv4 loopback.

## Operator commands

With VAMS_EFFECT_DATABASE_URL set to an isolated PostgreSQL database:

    python3 -m neuron.effect_canary_cli init

Provisioning is an operator action. Choose the principal, task, provider target and pinned implementation digest, object prefix, expiry, policy revision, authority epoch, aggregate budget, and maximum cost of one write. The object prefix must begin with the principal and a slash.

    python3 -m neuron.effect_canary_cli provision --principal PRINCIPAL --task TASK --target TARGET --implementation-digest SHA256 --object-prefix PRINCIPAL/TASK --budget-units 10 --max-cost-units 2 --policy-revision 1 --authority-epoch 1 --expires-at UNIX_SECONDS

For synthetic input under 1 MiB:

    python3 -m neuron.effect_canary_cli write --principal PRINCIPAL --task TASK --target TARGET --implementation-digest SHA256 --object-key PRINCIPAL/TASK/OBJECT --cost-units 1 --policy-revision 1 --authority-epoch 1 --expires-at UNIX_SECONDS --content-file PATH

The CLI generates an operation UUID unless the operator supplies one. Retries must reuse the original UUID and exact action. A provider timeout leaves its outcome indeterminate until the same operation is looked up and reconciled.

## Qualification limits

The provider persists object bytes and its idempotency ledger in one SQLite transaction. PostgreSQL stores current authority, aggregate reservations/spend, operation state, and observation receipts. These systems have not been exercised together because this environment lacks a PostgreSQL server/client and the repository Python environment. The observation endpoint uses a separate credential but runs in the same provider process; independent observation requires a separately operated observer and remains an admission criterion.
