# F04 Option B owner decision - 2026-10-06

Scope: DESIGN ONLY. This is the latest owner selection, not implementation, deployment, ledger admission or milestone closure.

The owner selects Option B: retain per-bootstrap identity policy IDs. Multiple quorum-authorized pre-registration anchors created with different anchor seeds are explicitly permitted. Final registration must consume the same committed bootstrap reference, limiting successful registration to at most one for that exact OutputReference.

This is not global DID uniqueness. No stateful uniqueness is authorized; no uniqueness guarantee exists across different bootstrap references.

Standalone agent_nft remains normative; registry-side minting must reject. Anchor issuance requires the founding owner plus 3 of 5 committed guardians; genesis registration preserves all-five guardian proof of possession and existing recovery thresholds/delays. Anchor_seed is in the fixed shared anchor policy redeemer, distinct from bootstrap_ref.

Authorized writes are only new versioned design/contract/matrix artifacts and required documentation records. Production source, blueprint, lockfile, provenance, dependencies, credentials and deployment are read-only. Existing dirty work and prior evidence verdicts must be preserved.

The required preflight package manifest is bfded41c96ee0af2e5d6c66c63f3dfc98a6b7d372ff643917cee692a95d74a40. Its enclosing-launcher/API-search capture limitations remain in scope; this design cannot retroactively grant missing execution credit.

Agent A owns anchor/dependency contracts. Agent B owns genesis/consumer contracts. Agent C is an independent read-only reviewer of the frozen integrated artifacts. The coordinator freezes the acceptance matrix, exact compiled-fixture/mutation/budget/provenance requirements and verification evidence.

Structural design validation grants no compiled execution, ledger or live-network credit. Stop after independent design review and propose exactly one bounded implementation scope for separate authorization.

INV-9, M5 and the historical M2 anomaly remain open. Readiness is NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
