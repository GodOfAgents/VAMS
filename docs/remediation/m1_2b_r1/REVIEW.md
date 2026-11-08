# M1.2b local implementation review

Date: 2026-09-22

Scope: Avail, EigenDA, and Trails live-mode enforcement only. This is local
implementation evidence, not an independent M1 closure review, provider or DA
certification, deployment approval, or closure of F09/F10/M1.

## Source-reality classification

- Avail and EigenDA DA adapters: structured stubs, not live-capable. They remain
  disabled from live construction and selection.
- Avail SDK: structured stub. Signed Substrate submission and authoritative
  retrieval are not implemented/audited, so no live path was promoted.
- EigenDA SDK: live-capable but previously misconfigured. Its proxy path is now
  explicit and fail-closed, but provider confirmation is not independent KZG,
  inclusion, finality, or availability proof.
- Trails SDK: live-capable but previously misconfigured. Endpoint/auth and
  provider response contracts are now explicit and fail closed.

## Implemented boundaries

- Every scoped adapter/SDK flag uses the sole frozen `RuntimePolicy` resolver.
  Missing flags default off; malformed, conflicting, and live mock selection
  fail before network/evidence effects.
- Explicit test/local/demo simulations use `simulated:` identifiers,
  unverified results, and `non-authoritative` provenance. They do not carry a
  live-looking transaction, block, commitment, KZG, inclusion, or verification
  claim.
- EigenDA real mode requires an explicit endpoint, validates submission,
  retrieval, and status fields, and fails closed on timeout, malformed data,
  provider error/failure, or bounded polling exhaustion.
- Trails real mode requires explicit endpoint and non-placeholder auth, validates
  exact provider fields, sanitizes diagnostics, and never invents an intent,
  status, settlement time, or transaction hash after failure.
- The DA orchestrator snapshots the central policy/configuration and rejects a
  simulated receipt in live operation. `TrailsClient.require_live_result()`
  rejects simulated and non-live status.
- The scoped components lock effective mode, endpoint, credential/transport
  selection, timeout, polling, and DA protocol configuration after construction.
  Reassignment and attempted removal of the guard fail closed.
- Explicit regressions prove missing transport dependencies, Trails
  authentication failure, and a failed live DA provider cannot select or
  manufacture a mock/stub success.

## Verification

- `test_m1_2b_da_trails_runtime.py`: 65 passed.
- Combined affected/root/M1.1/M1.2a/F17 set: 321 passed.
- Mock-mode promotion scan: passed.
- Python compilation, scoped mock-default/consumer/runtime-definition searches,
  JSON validation, and `git diff --check`: passed.

The provider tests use deterministic fake transports at the network seam. No
dependency install or external provider request was used as evidence.

## Finding and invariant impact

- INV-1–INV-10: unchanged. Bridge proof/payload separation (INV-10) is not
  modified.
- F17 remains `REMEDIATED`; gateway lifespan source was not changed.
- F09 remains `REVALIDATED_OPEN` pending M1.2c, all executable entry points,
  deployment preflight, and independent M1 closure review.
- F10 remains `REVALIDATED_OPEN` for M5; no independent DA reader, exact
  inclusion/finality/KZG proof, or release-evidence eligibility is claimed.
- Mock-mode impact is confined to the scoped Avail, EigenDA, Trails, DA result,
  promotion-scan, and affected test boundaries.

## Remaining M1 inputs

M1.2c owns `neuron/payments/coinme_client.py`,
`neuron/bridge_executor.py`, `neuron/sdk/x402_recovery.py`,
`neuron/sdk/interrupt_handler.py`, `neuron/payments/x402.py`,
`neuron/payments/payment_channel.py`, `neuron/payments/batch_settlement.py`, and
the remaining inventoried defaults in `neuron/config.py`,
`neuron/mev_protection.py`, `neuron/sdk/iagon_storage.py`,
`neuron/sdk/akash_orchestrator.py`, `neuron/sentinel/sentinel_node.py`,
`neuron/da_router.py`, `neuron/verifiers/celestia_light_client.py`, and
`neuron/neuron.py`. Bridge source was deliberately not changed in M1.2b.
Independent M1 closure review follows all scoped M1 implementation slices.
