# M3.1b-R3 bounded public-validator remediation

Date: 2026-09-25
Disposition: locally remediated; independent M3.1b-R4 required
F01: `REVALIDATED_OPEN`

## R2 prerequisite and reproduction

The independent R2 package verified recursively; its `SHA256SUMS` SHA-256 is
`2b302cd6d9c3173ee1b66900f3b97751e1c67f4a70cb76beb09f4dadeaeaba9d`.
Fresh disposable R1-source mutations reproduced all material gaps: no guardian,
input/output or fund-asset cap; no finite genesis check; and public-handler,
Submit-signature and payout-removal mutations each left 104/104 tests green.
Temporary copies were outside the repository and are not acceptance inputs.

## Implementation

- `cardano/validators/insurance_fund.ak` enforces the finite contract in the
  adjacent amendment, including finite genesis time and cheap shape checks.
- Critical native cases now construct a missing Submit signature, a genuinely
  duplicated next approver list, a payout that retains the selected claim, and
  enabled Submit transitions for all immutable-policy mutations.
- `scripts/remediation/test_m3_1b_public_validator.py` independently encodes
  complete Plutus V3 contexts, reproduces the fixed claim-ID CBOR vector, fully
  applies all six script parameters, and evaluates the compiled mint/spend
  entrypoint. Forty-five public cases cover every enabled transition, interval
  and cap edges, policy mutations, replay-sensitive state, and maximum shapes.

Replacing either public handler with success is detected by the compiled suite.
Removing claimant authorization, payout removal, genesis interval enforcement,
immutable policy enforcement, or the combined duplicate-approval controls is
also detected in disposable compiled mutations.

## Applied-script measurements

The fully applied script is 6,983 CBOR bytes. Sanitized maximum cases:

| Transition | CPU | Memory | Context CBOR bytes |
| --- | ---: | ---: | ---: |
| Genesis | 439,548,899 | 1,293,050 | 3,201 |
| Submit | 1,073,264,955 | 2,709,870 | 4,857 |
| Approve | 1,274,339,347 | 3,251,777 | 5,511 |
| Payout | 1,281,524,317 | 3,211,456 | 5,220 |
| Cancel | 1,090,237,576 | 2,824,784 | 5,251 |
| Expire | 1,086,830,967 | 2,813,909 | 5,220 |

These are local Aiken evaluator units and encoded script-context sizes, not a
ledger transaction-size or Pre-Prod admission claim. No authoritative local
Pre-Prod parameter snapshot was available and none was fetched.

Build-only identity changed from blueprint
`1cb965882b7bf549513380e07dd26b4b9c4be26df039463751562392eccb76bb`
and unapplied hash `2e252badb182e9bdbd46e399155ff22c436abf222cc7278095b333c7` to blueprint
`4e45eb9a4ffe60cd91647fab2f7127d61f2a858bb53bc73622861d37b193a8d3`
and unapplied hash `dbd26da1f503a2e882bcef159d39e2c28bcec4d07bf66c83078dd848`.

## Verification

- verified Aiken: `aiken v1.1.21+42babe5`, SHA-256
  `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`;
- `aiken fmt --check`: passed;
- full isolated `aiken check --seed 424242`: 115/115, including 70/70
  insurance tests;
- compiled public boundary: 45/45 expected outcomes;
- fresh blueprint copied byte-for-byte to `cardano/plutus.json`;
- mutation, documentation, JSON, submodule and diff checks are recorded in the
  external package.

The sanitized package is
`/home/GodOfAgents/vams-evidence/m3-1b-r3-20260925-829ab544571f`.
Its `SHA256SUMS` SHA-256 is
`785f86a5f0a8765151731a8d42b5beef99b15bc9782df3b5412bd1042287f6e1`.

F01 stays open because F05 deposit authority remains unresolved and R4 has not
independently accepted this bounded implementation. F02-F05 and M3 are
unchanged/open; promotion is not ready.
