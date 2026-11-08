# Repair77: finite nonnegative composer weights

Candidate source only. ScorerWeights previously accepted sum-preserving negative
components and NaN totals, and score() did not revalidate mutated configuration.
The repair validates six declared numeric fields without coercion, then checks
the unchanged total tolerance. Every score call validates before filtering or an
empty return. A second pass rejects oversized components before mixed numeric
addition, preserving a ValueError contract for arbitrarily large positive ints.

The order matters: all negative/type/nonfinite checks precede the oversized
component guard, so a negative field is diagnosed even if another field balances
it with 1.01. Valid weights, the existing dynamic 0.10 budgets, static custom
configuration, smallest positive subnormals and prior normalization tests remain.

Evidence: COMPOSER-WEIGHT-VALIDATION-77-R4-LINUX-BEFORE-01.json retains native exit
1 with 18 methods, 31 assertion failures and 13 errors. AFTER-01 retains native
exit 0 with 18 methods and zero failures/errors/skips/protected I/O. These are
isolated actual-module stdlib tests with package initializer bypass, not full
pytest, actual ASGI, provider cooperation, on-chain proof or live qualification.
No historical or canonical source76 counts are added to this campaign.

Direct scorer APIs now reject invalid configuration. Existing ComposerError
mapping and failed_simulations telemetry for scoring ValueError need a separate
caller follow-up. Caller review found no unsafe allocation/dispatch fallthrough;
the current composer remains explicitly non-live simulation infrastructure.

This repair contributes prerequisites for F11/F14 and T07/T22/T24. INV-1 through
INV-10 enforcement is unchanged. Fees, integer settlement, provider proof and
effect authority, restricted disablements and actual both-chain qualification
remain separate. Eighteen findings, thirteen open, zero of thirty-six tracks
verified and NOT READY remain. Integration, combined-source checks and non-author
package/evidence closeout are required before local canonical acceptance.
