# M1.2c local implementation review

Status: locally implemented and tested; accepted by independent M1 review.

M1.2c contains incomplete payment, bridge, escrow, recovery, legacy DA, and
provider simulations in live modes. It adds no replacement integration.
Explicit non-live simulations are non-authoritative, missing flags do not select
mock behavior, malformed/conflicting flags fail, and live construction rejects
before effects. Provider failures do not synthesize success.

INV-10 is preserved. `ICBClient.verify_bridge_proof(bridge_proof,
expected_payload_hash)` retains distinct values, and the focused test proves a
payload digest cannot be substituted for the separate proof bytes. INV-1–INV-9
are not touched.

Verification:

- final runtime/entrypoint/preflight public boundaries: 173 passed;
- integrated M1/F17/affected regression set: 624 passed;
- promotion scan, testnet preflight, deployment source scan, compilation: pass.

F10 remains open in M5. F11/F12 remain open in M6/M5. M1.2b is not reopened.
The independent M1 decision is recorded in `docs/remediation/m1_r2/REVIEW.md`.
