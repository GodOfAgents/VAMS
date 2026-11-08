# M3.2b-R4 mutation-harness remediation

Date: 2026-09-28 UTC
Repository: `/home/GodOfAgents/code/VAMS-testnet`

R3 prerequisite package `/home/GodOfAgents/vams-evidence/m3-2b-r3-implementation-20260928-829ab544571f` verified with SHA256SUMS digest `4faeef78ed1fcd4204d569a4f13723b6d6fa22bbd96e832673080777323fcc9a`; R2 package verified with digest `5dd567788e20b7fc2b9220af94469728a913c5c39675c09a1d46fc06536893ce`.

## Finding and correction

R3’s unconditional timelock mutation compiled but never reached the public handler. Independent localization identified two harness defects: the previous invocation shape was not the reviewed single-ScriptContext V3 boundary, and the replacement IntentDatum fixture omitted its leading `version` field. The corrected fixture also places the authority witness first, keeps the timelock input at reference 1, and binds the spending purpose to that reference. Only mutation/evaluator scripts changed; production validators, frozen JSON, blueprint, lockfile and provenance manifest were not modified.

The harness now records decode, encoding, public-entrypoint, evaluator and handler phases separately and rejects false positives from malformed CBOR, wrong purpose, wrong datum/redeemer, stale program use, evaluator failure or pre-handler rejection.

## Fresh results

- Three-way compiled result: valid original `accept`; targeted-invalid original `reject`; targeted-invalid unconditional mutant `accept`.
- Mutation source compiled and compiled program hash changed.
- Ten fresh isolated repetitions: 10/10 detected, zero repetition failures.
- Adversarial harness controls: passed, including original-program reuse, invalid fixture, evaluator failure and hash-rebind checks.
- Compiled public rows: 36/36 executed, 0 pending.
- Focused R4 harness regression: 2 tests, OK.
- Structural mutation gate: passed (80 mutation records, 9 transitions, compiled evaluator pass).
- Provenance suite: 20 tests, OK.
- Two isolated pinned Aiken 1.1.21 check/build runs: both exit 0, identical blueprint hash `7477763e57c4d7471eb5badf6a54a828a5087d1cfe6e565c985474f9237e5477`.
- Canonical lock hash remains `811aa44959682955b63dcdf4c2c8c9de887b32d39161f79ffee489f0d6520bac`; dirty-path count remains 119; `git diff --check` passes.

## Status

R4 is **LOCALLY REMEDIATED / NOT INDEPENDENTLY ACCEPTED**. This closes the R3 mutation-harness blocker only. F01-F05 remain `REVALIDATED_OPEN`; Deposit and Execute remain disabled pending F05; M3 remains `OPEN`; Pre-Prod admission remains `INCONCLUSIVE`; promotion remains `NOT READY`. INV-1 through INV-10, M1/M2 containment and mock-mode behavior are unchanged.

Next slice: independent M3.2b-R5 focused mutation delta review.
