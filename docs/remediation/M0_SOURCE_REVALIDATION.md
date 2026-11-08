# M0 current-source revalidation — 2026-09-22

This is a discovery disposition for the recursively checked-out dirty tree at
superproject HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`. It does not
claim that later remediation milestones, deployment, or release gates pass.
Current source was inspected directly and the ledger records every finding as
either remediated in M0 (F17/F18) or truthfully revalidated and assigned to its
existing later milestone (F01-F16).

## Cardano authority and bridge — F01-F05

| Finding | Current source result | Disposition |
|---|---|---|
| F01 | `insurance_fund.ak` permits spend branches without a canonical continuing state output, full value/datum conservation, claim lifecycle, or exact payout binding. | `REVALIDATED_OPEN`; M3. |
| F02 | `CancelIntent` checks only that two arbitrary extra signatories exist; emergency delay use is not authenticated. | `REVALIDATED_OPEN`; M3. |
| F03 | Vote continuation checks do not prove unique state-asset continuity or a voting snapshot/lock; execution checks only for any timelock-address output. | `REVALIDATED_OPEN`; M3. |
| F04 | Registry transitions do not fully bind identity/stake asset quantities, continuation/burn, owner identity, or slash remainder/destination. | `REVALIDATED_OPEN`; M3. |
| F05 | ICB and Mithril helpers accept structural length/shape conditions; the Python Cardano route constructs a zero-filled mock proof. | `REVALIDATED_OPEN`; M3/M4. |

Aiken is not installed in this execution environment. No new native Aiken
transaction-context result is claimed. This does not block M0 classification:
the missing adversarial native tests are themselves part of the M3 exit
contract. Exact current file hashes are recorded in
`docs/remediation/m0_f01_f16_r1/REVIEW.md`.

## Proofs, runtime, and settlement — F06-F13

| Finding | Current source result | Disposition |
|---|---|---|
| F06 | Solidity compares an authored quote hash; Python accepts proof length. Neither invokes authenticated TEE verification. | `REVALIDATED_OPEN`; M4. |
| F07 | The configured ZKML verifier address is never called. | `REVALIDATED_OPEN`; M4. |
| F08 | The signed envelope is method/path/timestamp only; replay state is process-local; body/query/audience/nonce/expiry/revocation are absent. | `REVALIDATED_OPEN`; M2. |
| F09 | Unknown `VAMS_ENV` text is treated as non-live instead of rejected. | `REVALIDATED_OPEN`; M1. |
| F10 | Known stub routes fail closed in live mode, but canonical receipts, route completeness, and independent exact read-back remain absent. | `REVALIDATED_OPEN`; M5. |
| F11 | Cognitive sync uses mock votes, chooses an arbitrary state hash, resets drift, and reports committed without authenticated durable reconciliation. | `REVALIDATED_OPEN`; M1/M6. |
| F12 | DBOS mechanics are tested, but workflow effects are demonstrations and real interrupt/provider/payment handlers remain unimplemented. | `REVALIDATED_OPEN`; M1/M5. |
| F13 | A privileged caller flips a provider-proof boolean without receiving or binding proof evidence. | `REVALIDATED_OPEN`; M4. |

## Telemetry, provider evidence, and release evidence — F14-F16

| Finding | Current source result | Disposition |
|---|---|---|
| F14 | Anomaly scores remain uncalibrated telemetry without provenance, uncertainty/OOD handling, or authority for a conscience guarantee. | `REVALIDATED_OPEN`; M6. |
| F15 | Reachability and declared/scored metadata are not real task-execution or independent provider-admission evidence. | `REVALIDATED_OPEN`; M5. |
| F16 | Exact final-commit reproducibility, signed assurance index, deployed observations, rehearsal, privacy/backup/drill, and soak evidence remain absent. | `REVALIDATED_OPEN`; M7/M8/M9. |

The current focused Python suites for F06-F15 passed **174/174**:

- record: `20260921T201118Z-f1b815ba-m0-f06-f15-current-focused/record.json`
- record SHA-256: `82144906d708ca17633062ab38789e425074611154ea54e25bcab98eaae74fc6`
- log SHA-256: `397eaad80cf85cb9d4536b751d54a41e6af46fcb82fd4ba2aa39a47a6f3f8d45`

Those passing tests establish current implemented behavior only. They do not
convert F06-F15 into remediated findings.

## Boundary

F01-F16 are now truthfully classified for M0 and remain assigned to the
milestones already recorded in `PLAN.md`. F17 and F18 are remediated. No
finding is represented as deployed, independently assured, or release-ready.
INV-1 through INV-10 and mock-mode behavior were not changed by this
revalidation.
