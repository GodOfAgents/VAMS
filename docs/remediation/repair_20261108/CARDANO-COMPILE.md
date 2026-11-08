# Cardano source compiles under native Aiken 1.1.21 — 2026-11-08

## Defect

The first native compilation of the integrated `cardano/` source (authorized
by owner decision 2 of 2026-11-08) failed. Earlier checkpoints prepared Aiken
cases but never compiled them. Control: committed `829ab54` passes
(50 tests, 1,793 checks).

## Repairs (type-level; no validator rule changed)

| File | Error | Repair |
|---|---|---|
| `validators/f04_anchor_policy.ak` | `expect Constr(2, fields) = raw` is not a legal cast of raw `Data`; `builtin` used without import | `let Pair(constructor_index, fields) = builtin.un_constr_data(raw)` then `expect constructor_index == 2`; add `use aiken/builtin` |
| `validators/f04_anchor_policy.ak` | `list.at` returns `Option<ByteArray>` inside the anchor-name preimage | `guardian_at` helper with `expect Some(...)`; `valid_anchor_datum` already requires exactly five guardians, so a missing index fails instead of hashing a default |
| `validators/f04_anchor_policy.ak` | warnings under `--deny`: `expect` on single-constructor redeemer; unused `maximum_u16` | `let` binding; constant removed (every 2-byte field is bounded more tightly by existing equality/range checks) |
| `validators/governance_v2.test.ak` | `ByteArray` and two datum branches returned where `Data` is declared | annotated `let x: Data = ...` upcasts; test-only |

## Results

`aiken check --deny --seed 20260711 --max-success 250` (CI form): exit 0,
2,627 checks, 0 errors, 0 warnings; 884 tests pass, 0 fail. Per module:
governance_v2.test 724, insurance_fund 73, action_context.test 36, vams/utils
15, agent_registry 10, vams/icb 10, vams/vdso 10, agent_nft 2,
agent_registry.test 2, f05_authority_policy.test 2. `aiken build`: exit 0.
Raw stream: `~/vams-baseline-logs/aiken-phase1.txt` on the runner.

## Blueprint

The tracked `cardano/plutus.json` was stale: eight validators
(`governance_v2.*` x6, `f04_anchor_lock`, `f04_anchor_policy`) were absent, and
`governance_policies.authority_policy`, `.intent_policy`, `.proposal_policy`,
`governor.authority_validator` and `timelock.timelock_validator` hashes no
longer matched source. It is replaced with the fresh default `aiken build`
output; the prior file is retained on the runner as
`plutus.before-phase1.json`. CI runs only `aiken check` and never regenerates
the blueprint; adding a blueprint-freshness gate is recommended.

## Limits

This is compilation and unit/property evidence on the owner-operated runner.
It does not establish ledger-context transactions with real signatures,
execution budgets against current Pre-Prod parameters, applied parameterized
script identities, coverage of all 81 obligations, the 48-hour queue-anchor
timing resolution, or independent review. F01–F03 remain open; readiness
remains NOT READY.
