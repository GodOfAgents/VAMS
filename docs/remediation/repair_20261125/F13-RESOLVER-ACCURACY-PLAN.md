# F13 resolver accuracy and availability measurement plan (2026-11-25)

Status: **PLAN FOR OWNER DECISION. Nothing executed.** It needs Phase 3 custody (actual resolver
signers), an authorized closed canary, testnet funding and an independent probe operator, all UNKNOWN
today. F13 stays REVALIDATED_OPEN; readiness NOT READY.

## 1. Why

The 5% bond deters meritless disputes only while the resolver's false-uphold rate $\varepsilon$ stays
below about 4.76% (`ANALYSIS.md`). Decision 10a also makes honest agents pay
$B\,[q + (1-q)\delta]$, where $q$ is the timeout rate and $\delta$ the false-reject rate. None of
$\varepsilon$, $\delta$ or $q$ has been observed. This plan turns the bond ratio from a policy value
into a calibrated one: $b > \varepsilon_U / (1 - \varepsilon_U)$, using a measured upper bound
$\varepsilon_U$.

## 2. What is measured

| Quantity | Definition | Source |
|---|---|---|
| $\varepsilon$ | Upheld meritless probes / meritless probes | Probe ledger + `DeliveryDisputeResolved` outcome |
| $\delta$ | Rejected meritorious probes / meritorious probes | same |
| $q$ | Timed-out disputes / all disputes (probes and real) | `DeliveryDisputeResolved` with state `TIMED_OUT` |
| Latency | `openedAt` to timelock `CallScheduled`, and to `CallExecuted` | Chain events |
| Margin | Time left before the 14-day deadline at execution | Derived; the operation must be scheduled by day 12 because of the 48 h delay |

## 3. Probe design

- **Blind injection.** An independent probe operator, who is not a resolver signer, opens disputes on
  probe rows using governance-admitted probe agent and provider identities. Signers are told that
  probes exist, but not which disputes they are.
- **Ground truth fixed in advance.** Each probe has a written case file: the acceptance criteria, the
  delivered output, and the correct outcome. *Meritless*: the delivery meets the criteria and the
  complaint is false. *Meritorious*: the delivery passes evidence verification but violates a
  committed acceptance criterion that the evidence does not cover; this is the class that disputes
  exist for.
- **Tamper-evident labels without code changes.** The existing `reasonHash` argument carries
  $H(\text{caseFileHash} \parallel \text{label} \parallel \text{salt})$, so the label is fixed on-chain
  when the dispute opens and revealed only after resolution. The resolver cannot invert it.
- **Mix and difficulty.** Roughly equal meritless and meritorious probes, spread across difficulty,
  and interleaved with any real disputes. Report probe difficulty, because easy probes overstate
  accuracy.

## 4. Sample size and decision rule

One-sided 95% exact (Clopper-Pearson) upper bounds (`accuracy-sample-sizes.txt`):

| Meritless probes $n$ | 0 wrong upholds | 1 | 2 |
|---|---|---|---|
| 63 | 4.64% | 7.31% | 9.66% |
| 100 | 2.95% | 4.66% | 6.16% |
| 120 | 2.47% | 3.89% | 5.15% |

- To support the current 5% bond ($\varepsilon_U < 4.76\%$): at least **62** meritless probes with
  zero wrong upholds, 98 with one, 131 with two.
- To keep a 2x margin ($\varepsilon_U < 2.5\%$): **119** with zero, 188 with one.
- **Decision rule.** If $\varepsilon_U$ is above the target: the owner chooses between raising $b$ to
  at least $\varepsilon_U/(1-\varepsilon_U)$ (for example 8.40% at $\varepsilon_U = 7.75\%$), changing
  the resolver or its procedure, or restricting disputes. If $q$ or late scheduling is material:
  resolver operations are fixed before public promotion, because decision 10a turns every timeout
  into an honest agent's loss.
- Measure $\delta$ the same way on meritorious probes and publish the honest-agent cost
  $B\,[q + (1-q)\delta]$.

## 5. Schedule and evidence

- Each probe takes at least the 48-hour delay to resolve. Scheduling and executing in batches
  (`scheduleBatch`, `executeBatch`) keeps around 120 probes feasible, but accrual will likely run past
  the seven closed-canary days into the 14-day public-observation period. Simulated time does not count.
- Evidence per probe: case file and hash, opening transaction, `reasonHash` preimage reveal, timelock
  schedule and execute transactions, outcome event, and computed latency. The statistics are computed
  by a script bound to exact transaction hashes, with raw streams retained.
- An independent reviewer audits the case files and labels before the reveal and checks the computation.

## 6. Prerequisites and authority

- Actual resolver signers and the Safe configuration (Phase 3 custody), a deployed restricted
  candidate on Amoy, and owner authorization for probe identities, funding, the probe operator role
  and signer consent. This plan grants none of these.
- Probe identities must be admitted by governance like any initiator and provider. Their activity must
  be excluded from any future reputation or reward accounting.

## 7. Limits

- Probes measure the resolver on designed cases. Real disputes may be harder or adversarially framed.
- Signers aware of probes may behave better than usual; blindness to which disputes are probes reduces
  but does not remove this.
- A few hundred cases bound the error rate; they do not establish it for every workload type.
- On testnet the bond has no market value. This plan measures adjudication quality, not real-money
  deterrence.
