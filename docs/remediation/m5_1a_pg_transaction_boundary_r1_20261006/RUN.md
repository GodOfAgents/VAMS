# M5.1a PostgreSQL transaction-boundary remediation evidence

State: ACCEPTED for transaction-control behavior with controlled driver doubles only. M5 and testnet readiness remain OPEN / NOT READY.

Accepted M5.1 plan SHA-256: 75b7097cd0cd67a76fe784ea2b1d25b5789b626b304ea0043890ab6844ea5bf8.

Changed implementation SHA-256: neuron/effect_canary.py 07627fa7c59d4a6e08e43de7c90ae60023213a186de9eb69f35fc03b31300e4a.
Focused test SHA-256: neuron/tests/test_effect_canary_postgres_transactions.py afe64882bcac2ee43d062e03ed647836f9a1a8b3ce550aaa44da789223007e07.

Commands and results, run in /home/GodOfAgents/code/VAMS-testnet with the existing pinned Python 3.12.14 runtime:

- `env VAMS_ENV=test /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -m pytest -q neuron/tests/test_effect_canary_postgres_transactions.py neuron/tests/test_effect_canary.py` - PASS, 19 passed in 6.93s.
- `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -m py_compile neuron/effect_canary.py neuron/tests/test_effect_canary_postgres_transactions.py` - PASS, no output.
- `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python scripts/audit/validate_traceability.py` - PASS, Architecture 0.8.0 and INV-1..INV-10 traceability passed.
- `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -m unittest scripts.audit.test_traceability` - PASS, 11 tests.
- `git diff --check -- neuron/effect_canary.py neuron/tests/test_effect_canary_postgres_transactions.py docs/CHANGELOG.md docs/remediation/STATUS.md docs/remediation/SESSION_HANDOFF.md` - PASS.

The focused tests use controlled psycopg2 driver doubles and fake provider/repository boundaries; no live database was contacted. They cover successful write commit, execute/fetch exceptions with rollback and close, commit failure, rollback failure while preserving the primary error and cleanup, and provider effect success followed by database commit failure. The coordinator then looks up and retries the same operation ID; provider idempotency returns the same receipt, and only the retry's successful database commit yields COMMITTED.

The context manager does not enable autocommit or change provider behavior. Authority-before-operation row-lock order and authority, budget, and operation-ID guards are unchanged. INV-1 through INV-10 implementations are not touched.

Recovery boundary: if recording indeterminate state also fails, current coordinator flow exits before immediate provider lookup. It returns an error/unknown result, never COMMITTED. Once database service is available, a rerun with the same operation ID can use the provider's idempotent path for reconciliation. This nested-failure path was assessed but not separately simulated.

Independent read-only security review: PASS on the exact implementation and test hashes above. Reviewer confirmed transaction outcomes, cleanup attempts, unchanged lock ordering and guards, and same-operation-ID recovery regression.

Evidence classification: transaction-control evidence only. PostgreSQL durability, concurrency, multiworker recovery, restart persistence, real provider, DA, independent observation, full M5, ledger admission, and live-network credit remain PENDING. No database was acquired, installed, started, or configured. No credentials, provider/DA route, observer, deployment, or gated activation was selected.
