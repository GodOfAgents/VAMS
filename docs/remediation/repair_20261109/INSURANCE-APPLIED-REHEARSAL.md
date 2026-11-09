# Insurance fund applied-identity rehearsal (2026-11-09)

Status: **PASS.** 17/17 cases behave as specified on the real compiled,
applied validator. Every transaction is well inside the reference execution
limits. F01 stays REVALIDATED_OPEN because Deposit remains disabled pending
F05. This run does not change that. Readiness is unchanged: 13 findings open,
0 of 36 tracks verified, NOT READY.

## What was run

- `cardano/lib/vams/insurance_rehearsal.ak`: ledger-shaped ScriptContext
  fixtures for every insurance action. Each transition is funded by a
  separate fee input, with change returned. Claim identities are derived
  independently of the validator module.
- `scripts/cardano/insurance_applied_rehearsal.py`: applies all six
  parameters in order (genesis reference, state name, five guardians,
  threshold 3, epoch 1, 5000 bps payout cap) with `aiken blueprint apply`,
  then evaluates the applied validator on each context with
  `aiken uplc eval`. The insurance validator source and `plutus.json` are
  unchanged (the driver checks the rebuild).
- Record: `insurance-applied-rehearsal-20261109.json`.

```bash
cd ~/code/VAMS-testnet
PATH=$HOME/.vams-tools/venv312/bin:$HOME/.vams-tools/bin:$PATH \
  python scripts/cardano/insurance_applied_rehearsal.py --out <record.json>
```

## Results

The synthetic applied hash, which is also the state policy ID, is
`1f456dfa…e208`. The applied script is 7,357 bytes.

| Case | Expected | Memory (share of 14M) | Datum created |
|---|---|---|---|
| Genesis mint | accept | 0.57M (4%) | 169 B |
| Submit | accept | 1.18M (8%) | 339 B |
| Approve | accept | 1.40M (10%) | 370 B |
| Payout | accept | 1.39M (10%) | 169 B |
| Cancel | accept | 1.12M (8%) | 169 B |
| Expire | accept | 1.10M (8%) | 169 B |
| Max: submit second claim | accept | 1.79M (13%) | 707 B |
| Max: fifth approval, two claims | accept | 2.45M (18%) | **888 B** |
| Max: payout from two-claim state | accept | 2.21M (16%) | 529 B |

The highest CPU share is 10%. Each action runs one script, so there is no
repeated-check cost of the kind found in governance.

All seven adversarial cases are rejected:

- a Deposit (disabled);
- a payout below the threshold;
- a payout redirected to another key;
- an approval by a non-guardian;
- the fund moved to another script;
- a genesis with the wrong seed;
- a submit with a replayed nonce;
- a payout after expiry.

## Observation: datum headroom (setup constraint, not a blocker)

The largest state tested is two pending claims with base payout addresses
and all five guardians approving each. It serializes to 888 bytes against the
validator's 896-byte cap. The fixture values are small.

Wider integers grow the datum. A 1M ADA fund with nonce around 70,000 and
epoch around 300 gives an estimated 918 bytes. Maximum u64 values give about
948 bytes. In those states an approval *beyond* what a payout needs can be
refused while another claim is pending.

A payout needs only `approval_threshold` approvals. With 3 or 4 approvers per
claim the state is about 800–860 bytes and fits, so payouts are not blocked
at threshold 3, the configured value. A 5-of-5 threshold could block the
second claim's last approval. **Constraint for the setup ceremony: keep
`approval_threshold` ≤ 4 with five guardians, or re-measure.**

## Limits

- Synthetic guardians, claimants, seed and amounts.
- Contexts are not ledger-validated: no fee, min-UTxO, collateral, balance
  or signature check.
- Costs use the evaluator's built-in cost model, and the reference limits
  are not confirmed against live Pre-Prod.
- Deposit and the bridge path are not exercised (F05).
- Not independent review, custody or deployment evidence.
