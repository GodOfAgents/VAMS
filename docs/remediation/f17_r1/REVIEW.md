# F17-R1 gateway lifecycle disposition

Date: 2026-09-22  
Superproject HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`  
Disposition: **REMEDIATED**

## Source result

`gateway/server.py` owns both background components inside the FastAPI lifespan:

- startup starts the economics keeper and creates the offline-node cleanup task;
- shutdown cancels and awaits the cleanup task, clears the global handle, and
  stops the keeper in `finally`;
- import no longer starts the keeper.

`neuron/economics/keeper.py` uses a stop event, a named owned thread, an
interruptible wait, and a blocking join. `start()` clears the event and remains
idempotent; `stop()` signals and joins the owned worker.

## Environment resolution

The prior Starlette TestClient/AnyIO hang was not reproduced in the preserved
Python 3.12.14 environment when unrelated pytest plugins were disabled and the
required `pytest_asyncio` plugin was loaded explicitly. No dependency was
installed or changed. This isolates the earlier behavior to nondeterministic
test-environment plugin loading rather than an active gateway lifecycle defect.

## Verification

- Focused lifecycle regression: 1/1 passed. The test performs two complete
  TestClient startup/shutdown cycles and after each asserts `cleanup_task is
  None`, keeper `_running` is false, and no live thread named
  `vams-economics-keeper` exists.
- Affected gateway suite: 39/39 tests plus 6 subtests passed.
- Direct economics keeper suite: 8/8 passed, including daemon lifecycle.
- Durable local command record:
  `/home/GodOfAgents/vams-evidence/m0-20260909/20260921T200200Z-8233a726-f17-gateway-lifecycle-final/record.json`.
  Record SHA-256:
  `6c7c7035442af0259cf954db0be47099752b066a4e48ae2017b9128200489aa2`;
  command-log SHA-256:
  `f7633350dd93c3646f273da5d876979f7ff89913fd5928f264c57eee23730a29`.
  Exit 0, no timeout, and identical source commit/tree before and after.

## Scope

F17 lifecycle ownership is remediated locally. This does not assert deployment,
hosted-CI observation, M0 completion, or testnet readiness. INV-1 through
INV-10 and mock-mode behavior are untouched.
