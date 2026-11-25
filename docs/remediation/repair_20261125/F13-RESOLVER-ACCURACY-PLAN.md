# F13 resolver accuracy and availability measurement plan (2026-11-25)

Status: **REVISED PLAN; no probes executed and no operational authorization granted.**
This revision corrects denominators, fixes sampling and stopping, and keeps required
evidence before public promotion. Actual custody, an authorized closed canary, funding,
an independent probe operator and operational acceptance limits remain UNKNOWN. F13 stays
REVALIDATED_OPEN; readiness NOT READY. All decision-10/10a/10b contract parameters remain
unchanged. The fixed quotas below plan evidence collection; they authorize no live work.

## 1. Quantities and outcome accounting

Separate truth classes $M$ (meritless complaint) and $H$ (meritorious complaint).
For each class retain counts $U_c$, $R_c$, $T_c$ for upheld, rejected and timed-out cases:

$$N_c=U_c+R_c+T_c,\qquad D_c=U_c+R_c.$$

Every enrolled, opened probe appears exactly once. An OPEN dispute past its resolution
deadline counts as a missed-deadline timeout even before `finalizeTimeout` is called;
retain the finalized chain observation and later timeout event separately. Do not omit
unfinalized timeouts. Immature cases are PENDING and prevent the final assessment.

| Quantity | Definition | Interpretation |
|---|---|---|
| $\varepsilon$ | $U_M/D_M$ | Wrong upholds **among decided meritless probes** |
| $\delta$ | $R_H/D_H$ | Wrong rejections **among decided meritorious probes** |
| $q_M$ | $T_M/N_M$ | Meritless-probe timeout rate |
| $q_H$ | $T_H/N_H$ | Meritorious-probe timeout rate |
| Latency | Opening to `CallScheduled` and successful `CallExecuted` | Also retain cancellations and failed executions |
| Execution margin | `openedAt + 14 days - executionTime` | Must be strictly positive for `resolve` |

When $D_c=0$, conditional accuracy is UNKNOWN, not zero. Pooled real/probe timeout rates
are diagnostics; never substitute them for the class-specific $q_M$ or $q_H$. Real cases
with unknown ground truth cannot enter an accuracy denominator.

For row amount $A>0$, actual posted bond $B$, and incremental gas/capital cost $C\geq0$:

$$EV_M=(1-q_M)\varepsilon(A+B)-B-C,$$
$$L_H=B[q_H+(1-q_H)\delta]=B\frac{T_H+R_H}{N_H},$$
$$EV_H=(1-q_H)(1-\delta)A-L_H-C.$$

For 100 meritorious cases with 20 timeouts, 8 wrong rejections and 72 correct upholds,
$\delta=8/80=0.10$ and $q_H=0.20$. With $A=100$, $B=5$, expected bond loss is **1.40 VAMS
(1.40% of the row)**. Substituting $8/100$ into the conditional formula wrongly gives
1.32 VAMS. The count identity above independently checks this result.

The [decision-10b design, section 4](F13-BOND-FLOOR-DISPUTE-CAP-DESIGN.md#4-effects-and-trade-offs)
gives floor-row equations. The 4.7619% reference threshold concerns proportional bonds
with zero costs and zero timeouts; it is not every floor-dominated row's threshold.

## 2. Probe design and prerequisites

- An independent operator, who is not a resolver signer, fixes case files and correct
  labels before enrollment. Meritless complaints concern deliveries meeting committed
  acceptance criteria. Meritorious complaints concern deliveries passing the evidence
  verifier but violating an acceptance criterion outside its coverage. Ambiguous ground
  truth is unsuitable for an accuracy probe.
- Before any outcome, freeze/hash the enrollment manifest: candidate/tool/configuration
  identities, chain/settlement, cases and sampling distribution, labels, randomized order,
  batches, quotas, confidence budget, assessment point, acceptance limits and failure
  rules. Independent label review and signer consent are prerequisites, not AI appointments.
- Signers know probes exist but should not know which disputes are probes or their labels.
  Commit through existing `reasonHash` to canonically encoded case hash, label and a
  cryptographically random salt; reveal after outcomes are fixed. Public identities,
  content and timing can expose probes despite hidden labels. Guaranteed blindness is
  not established.
- Draw independent cases from a predeclared fixed workload/difficulty distribution within
  each truth class. Exact binomial bounds require independent Bernoulli trials with a
  constant class-specific probability, including the conditional model among decisions.
  Correlated signer/batch failures, changed procedures or an incompatible fixed-stratum
  design invalidate the pooled-binomial interpretation. Treat that campaign as descriptive
  until an appropriate analysis is preregistered.
- Actual custody/Safe wiring, admitted identities/routes, disclosure/privacy review,
  funding, signer consent, operator independence and separate launch authority remain
  required. No deployment, signing, funding or admission is authorized here.

## 3. Fixed sample and stopping rule

**One campaign contains exactly 120 enrolled/opened probes per truth class: 240 total.**
Freeze those quotas before the first outcome. Respect the existing 20-OPEN-disputes limit
per agent; predeclare batches and authorized identities. No extra identities are implied.

There is **one acceptance assessment**, after all 240 cases have resolved or crossed
their deadlines, with finality and independently checked labels/evidence. Intermediate
monitoring may stop for safety but cannot accept. Missing enrollment/evidence or a safety
stop gives INCOMPLETE/NOT ACCEPTED; do not discard, replace or silently shrink the sample.

Do not add cases until a bound turns green, select a favorable prefix, or pool a failed
campaign into a new one. A repeat or changed procedure/resolver needs a separately
authorized, preregistered design addressing repeated testing across campaigns. No automatic
retries or 95% coverage across repeated attempts are granted.

Continuous acceptance testing is **deferred**. Howard, Ramdas, McAuliffe and Sekhon,
[*Time-uniform, nonparametric, nonasymptotic confidence sequences*, arXiv:1810.08240v5](https://arxiv.org/html/1810.08240v5),
sections 1 and 6, explains fixed-sample bounds versus optional stopping and time-uniform
alternatives under stated assumptions. This plan uses a fixed assessment; it implements
no confidence sequence and transfers no paper guarantee to VAMS.

## 4. Confidence bounds and acceptance

Allocate family error probability 0.05 across four one-sided bounds:
$\varepsilon_U$, $\delta_U$, $q_{M,U}$ and $q_{H,U}$. Each uses
$\alpha_i=0.05/4=0.0125$: 98.75% individual coverage, at least 95% simultaneous coverage
by the union bound **under the stated sampling assumptions**. Independence between the
four bounds is not required.

For $k$ adverse outcomes among $n$ relevant observations, the exact upper bound $p_U$ solves

$$\sum_{j=0}^{k}\binom{n}{j}p_U^j(1-p_U)^{n-j}=\alpha_i.$$

For $k=n$, use $p_U=1$; for $n=0$, UNKNOWN prevents acceptance. Accuracy uses $n=D_M$ or
$D_H$; timeout bounds use $n=N_M$ or $N_H$. Consequently 120 enrollments need not produce
120 decisions. These are planning examples, not alternative stopping points:

<!-- BEGIN F13 CONFIDENCE TABLE -->
| Decided cases n | 0 wrong decisions | 1 | 2 |
|---|---|---|---|
| 63 | 6.7192% | 9.7065% | 12.2816% |
| 100 | 4.2874% | 6.2119% | 7.8775% |
| 120 | 3.5858% | 5.1998% | 6.5982% |
<!-- END F13 CONFIDENCE TABLE -->

- Support for the unchanged 5% proportional bond, without relying on gas or timeout
  penalties, requires **strictly** $\varepsilon_U<1/21=4.761904\ldots\%$, equivalently
  $0.05>\varepsilon_U/(1-\varepsilon_U)$. Use exact values, not rounded percentages.
  Equality is break-even, not strict deterrence. A failing bound changes no parameter.
- For an individual floor row use $b_{eff}=B/A>\varepsilon_U/(1-\varepsilon_U)$. This is
  a risk-neutral monetary-model comparison for the declared workload mix, not proof
  against resolver capture, collusion or external gains.
- Before launch, owner/reviewer must fix numeric availability and honest-agent-loss
  limits for the named row/workload range in the manifest. Those operating limits remain
  UNKNOWN here; UNKNOWN cannot accept. A conservative honest-loss bound is
  $B[q_{H,U}+(1-q_{H,U})\delta_U]$. Report $EV_H$ with the actual floor bond and costs.
  Good meritless-error results cannot excuse honest-agent timeouts.
- Failed bounds/limits, invalid assumptions or insufficient evidence give NOT ACCEPTED.
  Any parameter, procedure or custody change needs its own decision and requalification.

## 5. Stage ordering and evidence

Seven actual consecutive closed-canary days are a **minimum**, not a promotion deadline.
Complete and independently accept all required F13 measurement evidence in the authorized
closed canary **before public promotion**. Extend the closed canary when collection,
14-day timeout maturation, finality or review takes longer. Incomplete probes cannot be
carried into public observation to satisfy an earlier promotion gate.

After required gates and all 36 tracks are accepted, preserve the separate subsequent
14-day public-observation period and exposure/concentration requirements. Extra closed
time cannot replace it; simulated time counts for neither stage. Polygon Amoy and Cardano
Pre-Prod evidence remains separately required; this plan waives neither chain.

Retain per-probe commitments, reviewed ground truth, opening transaction, `reasonHash`
reveal, schedule/cancel/failed-execute/successful-execute receipts, outcome or missed-deadline
observation, finality, latency and execution margin. Scheduling must be **strictly before**
`openedAt + 12 days`, plus operational execution margin, because the timelock delay is
48 hours and `resolve` excludes the exact 14-day deadline. Being ready exactly then is too
late. Batches can revert atomically; preserve failures rather than infer progress from
scheduling. Timeout eligibility itself neither submits a transaction nor releases funds.

Bind manifests, raw evidence, statistics scripts/outputs and independent review to the
exact candidate/configuration. Keep real cases distinct and exclude probes from future
rewards/reputation. No authentic probe evidence exists yet.

## 6. Offline verification and limits

From the repository root:

```text
python3 scripts/audit/verify_f13_resolver_math.py
```

The standard-library-only check verifies documented tables against exact rational binomial
calculations, outcome counts, integer bond rounding and analytical boundary cases. It
makes no network requests, chain operations or contract changes. This is mathematical/source
consistency evidence, not calibration or independent assurance; a successful exit accepts
no release gate.

Probes cover their declared distribution, not arbitrary future workloads. Recognized probes,
selective timeouts, common signer failures and procedure drift limit transfer of estimates.
Testnet tokens exercise the mechanism without establishing real-value deterrence. Actual
custody, authentic F06/F07 evidence, independent review and remaining gates stay required.
F13 is **REVALIDATED_OPEN; readiness NOT READY**.
