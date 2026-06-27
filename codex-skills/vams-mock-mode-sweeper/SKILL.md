---
name: vams-mock-mode-sweeper
description: Find, classify, and block VAMS mock-mode and stub leakage before staging, testnet, production, or security review. Use when checking DA adapters, OMS identity, Trails, Coinme, TEE, x402 recovery, bridge transports, gateway DA audit logs, environment defaults, or any code path where mock behavior could be mistaken for live proof.
---

# VAMS Mock Mode Sweeper

Use this skill to separate legitimate local simulation from unsafe live-path mocks.

## Workflow

1. Search for mock and stub indicators:
   - `mock_mode`, `mock=True`, `MOCK_MODE`, `_MOCK_MODE`
   - `NotImplementedError`
   - `Stub`, `[STUB]`, `demo-key`
   - environment defaults such as `"true"` for live clients
2. Read each hit in context. Do not classify from grep output alone.
3. Categorize each path:
   - `test-only`
   - `local-dev default`
   - `live-capable with explicit config`
   - `production blocker`
4. Check for environment gates that reject mock mode in staging/production.
5. Report every blocker with exact file and line.
6. If asked to fix, add fail-closed startup validation and tests.

## Known High-Risk Areas

Read `references/mock-mode-policy.md` before review.

## Output Shape

- **Production Blockers:** must fix before staging/testnet/prod.
- **Allowed Test Mocks:** confined to tests or explicit local dev.
- **Config Gaps:** missing env gates or unsafe defaults.
- **Required Fixes:** code and tests required.
- **Verification:** exact grep/test commands run or needed.
