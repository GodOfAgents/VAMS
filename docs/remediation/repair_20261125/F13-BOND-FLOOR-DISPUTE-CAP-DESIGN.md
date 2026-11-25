# F13 dispute bond floor and per-agent dispute cap: design (2026-11-25)

Status: **APPROVED (owner decision 10b, 2026-11-25: Q1-Q4 as recommended), implemented and committed
locally as `b631f67`; bounded non-author AI source review is recorded, while independent release
assurance and acceptance remain pending.** Implementation evidence:
`.tmp-history-tests/f13-floor-cap-20261125-01/`. F13 stays REVALIDATED_OPEN; readiness NOT READY
(13 open findings, 0/36 tracks). Decisions 10 and 10a are unchanged by this document.

Inputs: `.tmp-history-tests/f13-bond-economics-20261125-01/ANALYSIS.md` (findings 3 and 5, options
O1 and O3); source at `remediation/phase1` `f91a933`.

## 1. Problem

- **Dust rows.** Rows only need `amount > 0` (`ComposedSettlement.sol:222`), and the bond is
  `ceil(5% * row)`, so a 1-unit row is disputed for a 1-unit bond. The bond prices nothing there.
- **Resolver-capacity exhaustion.** A commonly controlled agent-provider ring recycles its bonds and
  pays only the 5 bps fee per dispute (0 on uphold). It can open many disputes, each needing a Safe
  decision through the 48-hour timelock. Honest disputes that time out lose their bond (decision 10a).
- Bounded today only by the admission gate (governance-admitted initiators and provider routes).

## 2. Mechanism

Both changes live entirely in `DeliveryDisputeV1`. `ComposedSettlement` source does not change.

**O1 Bond floor.**

$$B = \max\left(\left\lceil \frac{500 \cdot A}{10\,000} \right\rceil,\ B_{min}\right)$$

`MIN_BOND` is a `constant` in VAMS base units, like the decision-10 constants. Rows above
$B_{min}/0.05$ are unaffected.

**O3 Per-agent open-dispute cap.** `openDisputeCount[agent]` counts OPEN disputes for the allocation's
agent. `openDispute` reverts `TooManyOpenDisputes(agent, cap)` when the count has reached
`MAX_OPEN_DISPUTES_PER_AGENT`. Every terminal outcome (uphold, reject, timeout) decrements it in
`_releaseBond`, the single exit path. The cap is per agent, never global: a global cap would let
one actor block every honest agent.

## 3. Approved owner decisions (10b)

Q1-Q4 were approved as recorded in decision 10b. The options below are retained
as design history; the final column records the approved selection, not a pending vote.

| # | Decision | Historical options | Approved selection |
|---|---|---|---|
| Q1 | `MIN_BOND` value | (a) 1 VAMS; (b) another constant; (c) a deployment-time value tied to the policy `maxActionBudget` (needs a settlement constructor change); (d) no floor | **(a) 1 VAMS for the restricted testnet**, explicitly revisited before any real-value deployment. Testnet VAMS has no market value, so on Amoy the floor exercises the mechanism; it cannot demonstrate economic deterrence |
| Q2 | `MAX_OPEN_DISPUTES_PER_AGENT` | 5; 20; per allocation instead of per agent | **20**, equal to `MAX_PROVIDERS`, covering every row of one 20-row allocation when the agent starts with no other open disputes. 5 would block that case |
| Q3 | Release the count on all three outcomes | yes / only on resolver decisions | **Yes.** Timeouts must release it, or a silent resolver permanently locks an agent out |
| Q4 | Scope of the cap | agent / provider / both | **Agent only.** Provider status alone grants no ability to open a dispute; a provider that is also the allocation agent acts in that agent role |

## 4. Effects and trade-offs

This section supersedes the pre-floor analysis's use of a universal $B/A=0.05$.
Compute $B$ in integer token base units with section 2's formula and set $b_{eff}=B/A$.
With the approved 1-VAMS floor, the crossover is **20 VAMS**; above it the rounded
proportional bond applies. A positive row **below 1 VAMS**, not $B_{min}/1.05$, needs
a bond greater than its principal. Rounding applies at the crossover plus one base unit.

Use separate timeout rates $q_M$ and $q_H$ for meritless and meritorious complaints.
$\varepsilon$ and $\delta$ are error rates **among decided cases** in those classes.
Let $C\geq0$ be incremental gas/capital cost in principal units. Relative to not disputing:

$$EV_M=(1-q_M)\varepsilon(A+B)-B-C,$$
$$EV_H=p_H A-(1-p_H)B-C,\qquad p_H=(1-q_H)(1-\delta).$$

Meritless filing is profitable only if $\varepsilon>(B+C)/[(1-q_M)(A+B)]$ for $q_M<1$;
when $q_M=1$, its expected value is $-B-C$. Honest filing has positive monetary expected
value only if $p_H>(B+C)/(A+B)$. Equality is break-even. When $C\geq A$, even certain
success cannot yield positive $EV_H$ under this model.

The table uses exact base-unit bonds and $C=0$. Its last column assumes illustrative
$q_H=0.20$, $\delta=0.10$, losing 28% of the bond on average. None are measured rates or
acceptance limits.

<!-- BEGIN F13 FLOOR TABLE -->
| Row A (VAMS) | Bond B (VAMS) | Effective B/A | Honest success needed (strictly above) | Expected honest bond loss / row |
|---|---|---|---|---|
| 0.1 | 1 | 10 | 90.9091% | 280.0000% |
| 1 | 1 | 1 | 50.0000% | 28.0000% |
| 5 | 1 | 1/5 | 16.6667% | 5.6000% |
| 20 | 1 | 1/20 | 4.7619% | 1.4000% |
| 100 | 5 | 1/20 | 4.7619% | 1.4000% |
<!-- END F13 FLOOR TABLE -->

For a 0.1-VAMS row, expected bond loss in that example is **0.28 VAMS (280% of the row)**
and $EV_H=0.72(0.1)-0.28=-0.208$ VAMS before costs. For a one-base-unit row ($A=1$,
$B=10^{18}$ in base units), positive honest $EV_H$ requires
$p_H>10^{18}/(10^{18}+1)$, a failure probability below $1/(10^{18}+1)$ before costs.
Do not round this to an achievable 100% estimate or use the proportional regime's
4.7619% abuse threshold for this row.

The floor increases dust collateral and can make honest small-row disputes uneconomic;
it does not establish a minimum service charge or prove that small disputes will be rare.
Commonly controlled agent/provider pairs still recycle the bond. Simple annualized delay
compensation does not establish universal extortion resistance or price external gains.

For one dispute contract, $K$ admitted ring-controlled agents can hold at most $20K$ OPEN
disputes concurrently. This is neither a global service-rate bound nor Sybil resistance.
Resolved slots can be reused and identities multiply the cap. The 14-day deadline makes
timeout finalization eligible; it does not submit a transaction, release collateral, or
guarantee provider payment while paused. Failed transactions can prolong actual lock time.
Admission and funded operator execution remain necessary controls.

Decision 10b adds the bond floor and per-agent cap and changes `bondFor` as
described in section 2. This mathematics/coverage correction changes none of
those approved parameters or the outcome, deadline, recipient and conservation
semantics of decisions 10/10a.
The [measurement plan](F13-RESOLVER-ACCURACY-PLAN.md) fixes rate definitions and stage order.
Reproduce the tables with `python3 scripts/audit/verify_f13_resolver_math.py`.

## 5. Feasibility (throwaway prototype with placeholder values, `prototype/`)

| Item | Measured |
|---|---|
| `DeliveryDisputeV1` runtime | 4,857 B -> 5,192 B (+335 B; limit 24,576 B) |
| `ComposedSettlement` runtime | 24,401 B, unchanged (175 B margin kept) |
| `ComposedSettlement` initcode | 31,163 B -> 31,499 B (+336 B; limit 49,152 B), because it deploys the dispute contract in its constructor |
| Existing dispute suites | 2 failures, both tests that pin a 1-unit bond (`test_parametersMatchOwnerDecision10`, `test_dustRowDisputeNeedsOnlyOneUnitBond`). They would be updated deliberately; everything else passed |

The settlement's runtime metadata hash changes because its source imports the dispute contract.
Nothing is deployed, so no manifest or pinned code hash needs regeneration yet.

## 6. Acceptance criteria and source coverage

The table preserves the original criteria and distinguishes source coverage from
execution and operational acceptance. All dispute tests use a noncryptographic
evidence backend. Token fault injection below is local negative testing, not
qualification of another live token or proof provider. Exact runs and their
source identities are recorded separately in the local review/scan record.

| Criterion | Source coverage | Remaining limits |
|---|---|---|
| 1. Floor, rounded proportional bond and exact crossover; fuzz row sizes | `DeliveryDisputeFloorCapTest.test_bondFloorCrossoverIsExact`, `testFuzz_bondIsFloorOrRoundedUpProportional` | Fuzz domain is `1..1e30`; it is not full-uint256 verification. The deployed token supply remains a separate bound. |
| 2. Dust floor and short received transfer fail closed | `DeliveryDisputeEconomicsTest.test_dustRowDisputePostsTheBondFloor`; `DeliveryDisputeFloorCapTest.test_smallRowPostsTheFloorAndShortAllowanceReverts`, `test_shortReceivedBondRollsBackDisputeAndCount` | Allowance failure and short receipt are distinct tests. Token fault injection is synthetic. |
| 3. N succeeds, N+1 fails; reuse after uphold, reject and timeout | `DeliveryDisputeFloorCapTest.test_twentyFirstOpenDisputeRevertsUntilEachOutcomeReleasesASlot`, `test_upholdRejectAndTimeoutEachReleaseOneSlot` | Reuse after timeout uses newly earned work; old rows' dispute windows remain expired. |
| 4. Per-agent OPEN-entry and balance invariants over mixed operations | `DeliveryDisputeFloorCapTest.testFuzz_openCountEqualsOpenDisputesPerAgent` enumerates stored entries while interleaving fresh opens and outcomes across two agents, including opens after timeout warps | Bounded traces of 4-14 opens, not exhaustive state-space, maximum-cap fuzz or Sybil-resistance evidence. Deterministic tests cover the cap boundary. |
| 5. One agent at the cap does not block another | `DeliveryDisputeFloorCapTest.test_oneAgentAtTheCapDoesNotBlockAnother` | Per-address isolation does not bound a multi-identity ring. |
| 6. Timelock-executed resolution releases the slot | `DeliveryDisputeGovernancePathTest.test_upholdThroughScheduledOperationRefundsAgentAndBond`; reject/deadline paths in that suite; unit count tests for all outcomes | Safe threshold and real custody are unmodelled. All-outcome transfer rollback is exercised separately by `test_outgoingBondFailurePreservesStateAndSlotUntilRetry` and `test_refundTransferFailureRollsBackSettlementAndDispute`. |
| 7. Runtime/initcode size limits and recorded growth | `forge build --sizes --offline`; exact input identities, retained output locator and SHA-256 are in [the local review/scan record](F13-LOCAL-SCAN-REVIEW.md) | Prototype figures in section 5 are historical; source-bound local output is not deployment qualification. |
| 8. Anchored Slither filter, no new High | CI severity flags on the exact source, with report retained separately | Exit 0 does not dispose of the existing Medium/Optimization results or replace independent assurance. |

The callback-failure tests enter the actual settlement refund path and inject
token failures; wrong-row timelock failure and unauthorized direct callback
tests alone do not establish that rollback coverage. No criterion above is a
claim that authentic proof, custody, closed-canary or release gates have passed.

## 7. Invariants and limits

- INV-9 adjacent: escrow and bonds stay separately backed; bonds still leave exactly once. INV-1 to
  INV-8 and INV-10 untouched.
- A cap cannot stop a ring that controls many admitted initiators; admission review remains the
  primary control. In any open-admission profile this design is insufficient on its own.
- Neither change measures or improves resolver accuracy; see `F13-RESOLVER-ACCURACY-PLAN.md`.
- Independent review is required before acceptance.
