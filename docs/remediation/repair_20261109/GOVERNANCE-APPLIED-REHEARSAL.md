# Governance v2 applied-identity rehearsal (2026-11-09)

Status: **FAIL: blocking finding.** All 42 cases behave as specified on the
real compiled, applied validators, but five transaction shapes exceed the
reference per-transaction execution-memory limit. Readiness is unchanged:
13 findings open, 0 of 36 tracks verified, NOT READY.

## What changed and why

Before today, every governance v2 test (the 724-case campaign included)
called the transition *functions* with made-up script hashes. Nothing had run
the compiled validators with real parameters, so three questions were open:

1. Can a consistent deployment exist (parameters → hashes → authority
   config), with no hash cycle?
2. Do the compiled entry points accept and reject the same transactions as
   the functions?
3. Do the transactions fit Cardano's per-transaction execution limits?

New files:

- `cardano/lib/vams/governance_v2_rehearsal.ak`: ledger-shaped ScriptContext
  fixtures for every governance action, built from the applied hashes. It is
  not imported by any validator; `plutus.json` is unchanged (the driver checks
  this).
- `scripts/cardano/governance_v2_applied_rehearsal.py`: works in a temporary
  copy. It applies the bootstrap to `governance_authority_v2` and the
  resulting anchor to the other five validators using `aiken blueprint apply`.
  It then evaluates each applied compiled validator on each context with
  `aiken uplc eval`, and records the result, CPU and memory.
- `governance-v2-applied-rehearsal-20261109.json`: the run record (this
  folder).

Command (WSL D1 runner, Aiken v1.1.21):

```bash
cd ~/code/VAMS-testnet
~/.vams-tools/venv312/bin/python scripts/cardano/governance_v2_applied_rehearsal.py --out <record.json>
```

## Results

**1. Deployment is consistent.** The authority hash depends only on the
bootstrap. The other five depend only on the anchor (authority hash plus the
authority asset name, derived from the authority hash, seed, network and
epoch). The genesis config can carry all six hashes, so there is no cycle.
Synthetic applied hashes: authority `454e8731…`, governor `b7953836…`,
timelock `d9be4844…`, proposal `65f43811…`, receipt `dee9108b…`, intent
`65ff18ab…`. They change with real ceremony inputs.

**2. Entry points behave as specified (42/42).** All 32 accept cases succeed
and all 10 adversarial cases fail on the applied programs:

- ExecuteIntent stays disabled.
- An intent cancel with only two members is rejected.
- A Queue with a 24-hour delay is rejected.
- A vote that replaces a prior voter is rejected.
- A rejected-proposal refund redirected to another key is rejected.
- A forged authority reference is rejected.
- A version-1 request is rejected.
- A genesis with the wrong seed is rejected.
- A Create that sends the proposal to the wrong governor is rejected.

**3. Execution budget: blocking.** Memory per transaction, summed over all
scripts that run in it, against the 14,000,000 reference limit:

| Transaction | Scripts | Memory | Share | CPU share of 10e9 |
|---|---|---|---|---|
| Genesis | 1 | 1.51M | 11% | 6% |
| Create | 2 | 7.23M | 52% | 30% |
| Vote (1st / 2nd voter) | 2 | 7.82M / 8.93M | 56% / 64% | 32% / 36% |
| Finalize passed | 1 | 3.77M | 27% | 16% |
| Finalize rejected / cancel (1 voter) | 3 | 10.49M | 75% | 41% |
| **Queue (1 voter)** | 5 | **22.08M** | **158%** | 91% |
| Cancel / expire intent | 2 | 5.99M / 5.65M | 43% / 40% | 24% / 23% |
| **Eighth vote (8 voters)** | 2 | **16.83M** | **120%** | 64% |
| **Finalize rejected (8 voters)** | 3 | **22.42M** | **160%** | 82% |
| **Queue (8 voters)** | 5 | **41.65M** | **298%** | **159%** |

So no proposal can be queued at all, and with many voters, finalizing a
rejection and the last votes fail too. The cause is structural: every script
in a transaction re-runs the full transition check. A Queue validates the
same transaction five times (authority spend, governor spend, and the
proposal, receipt and intent policies). Each run re-derives every receipt
name and re-serializes each datum for the size check.

Applied script sizes: authority 11,611 B, governor 11,543 B, timelock
7,587 B, each policy 13,184 B. Each fits in one reference-script transaction,
and a Queue's five reference scripts total 70,293 B, under the 204,800 B
per-transaction reference limit. Reference-script fees still apply.

## Proposed repair (needs owner approval: high-risk governance change)

**Delegate to one authoritative script per transaction.** Keep the full
transition check in exactly one validator per action:

- the authority spend for Create and Queue;
- the governor spend for Vote, Finalize, Reject and Cancel proposal;
- the timelock spend for Cancel and Expire intent.

Each other script in the same transaction (the three minting policies, and
the governor spend during Queue) would check only that:

1. the authenticated governing input, found by the anchor token or the
   configured script address, is spent in this transaction; and
2. `tx.redeemers` holds a `Spend` entry for that input with the same v2
   request.

The ledger runs the governing validator for that input with that redeemer,
and that validator already checks the complete transaction, including the
exact `tx.mint`, outputs, values and signers. Delegation therefore keeps every
rule but runs it once. This is the common forwarding pattern for Plutus V3
multi-script protocols. It would be adopted only with:

- an argument that every current rejection still has one enforcing
  validator;
- re-running the 884-test Aiken suite and the 724-case campaign;
- new adversarial cases on the applied programs: a policy minting without
  the governing spend, a governing spend under a different redeemer, a
  substituted governing input, and a mint in an unrelated transaction;
- this rehearsal showing every transaction, including the eight-voter
  cases, inside the limit with margin;
- a non-author review.

The eight-voter Queue's governor check alone is 10.2M, which leaves thin
margin. The repair may also need to stop re-deriving every prior receipt
name on each vote and finalize step, for example by checking only the
appended lock.

## Limits of this evidence

- Synthetic custodians, seed UTxO, VAMS policy and amounts. Contexts are
  ledger-shaped but not ledger-validated: no fee, min-UTxO, collateral,
  balance or signature check.
- Costs use the evaluator's built-in cost model, not live Pre-Prod
  parameters.
- The limits (14,000,000 memory, 10,000,000,000 steps, 16,384 B transaction,
  204,800 B reference scripts) are reference values not confirmed against
  live Pre-Prod. The Queue overrun is large enough that this does not change
  the conclusion.
- Insurance (F01) was not part of this run.
- F02/F03 stay REVALIDATED_OPEN, and no finding or track changes status.
  This is not independent review, custody, or deployment evidence.
