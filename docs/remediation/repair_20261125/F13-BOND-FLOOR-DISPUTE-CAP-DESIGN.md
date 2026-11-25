# F13 dispute bond floor and per-agent dispute cap: design (2026-11-25)

Status: **APPROVED (owner decision 10b, 2026-11-25: Q1-Q4 as recommended) and implemented in the WSL
working tree, uncommitted; not independently reviewed.** Implementation evidence:
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

## 3. Owner decisions needed

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q1 | `MIN_BOND` value | (a) 1 VAMS; (b) another constant; (c) a deployment-time value tied to the policy `maxActionBudget` (needs a settlement constructor change); (d) no floor | **(a) 1 VAMS for the restricted testnet**, explicitly revisited before any real-value deployment. Testnet VAMS has no market value, so on Amoy the floor exercises the mechanism; it cannot demonstrate economic deterrence |
| Q2 | `MAX_OPEN_DISPUTES_PER_AGENT` | 5; 20; per allocation instead of per agent | **20**, equal to `MAX_PROVIDERS`, so an honest agent can always dispute every row of one bad allocation. 5 would block that case |
| Q3 | Release the count on all three outcomes | yes / only on resolver decisions | **Yes.** Timeouts must release it, or a silent resolver permanently locks an agent out |
| Q4 | Scope of the cap | agent / provider / both | **Agent only.** Providers cannot open disputes |

## 4. Effects and trade-offs

- An honest agent disputing a row smaller than about $B_{min}/1.05$ posts more bond than the row is
  worth. Expected value stays positive only if the resolver is accurate and responsive:
  $(1-q)(1-\delta)A > [q + (1-q)\delta]\,B_{min}$. Disputes on very small rows become rare; this is
  the intended price of protecting resolver capacity.
- Ring capacity becomes at most $N \times$ (admitted initiators the ring controls), with each dispute
  costing at least $B_{min}$ of locked capital for up to 14 days. With recycling, the floor adds
  capital lock rather than loss; the cap is what bounds volume.
- No change to outcomes, deadlines, recipients, conservation or decision 10a.

## 5. Feasibility (throwaway prototype with placeholder values, `prototype/`)

| Item | Measured |
|---|---|
| `DeliveryDisputeV1` runtime | 4,857 B -> 5,192 B (+335 B; limit 24,576 B) |
| `ComposedSettlement` runtime | 24,401 B, unchanged (175 B margin kept) |
| `ComposedSettlement` initcode | 31,163 B -> 31,499 B (+336 B; limit 49,152 B), because it deploys the dispute contract in its constructor |
| Existing dispute suites | 2 failures, both tests that pin a 1-unit bond (`test_parametersMatchOwnerDecision10`, `test_dustRowDisputeNeedsOnlyOneUnitBond`). They would be updated deliberately; everything else passed |

The settlement's runtime metadata hash changes because its source imports the dispute contract.
Nothing is deployed, so no manifest or pinned code hash needs regeneration yet.

## 6. Acceptance tests (to write at implementation)

1. `bondFor` equals the floor below the crossover row, the proportional bond above it, and is exact at
   the crossover; fuzz across row sizes.
2. Dust row: the bond is `MIN_BOND`, and a short bond transfer reverts with `BondTransferMismatch`.
3. Cap: the N-th open dispute succeeds and the (N+1)-th reverts; after any of uphold, reject or
   timeout, one more dispute succeeds.
4. Invariant fuzz: `openDisputeCount[a]` equals the number of OPEN disputes whose agent is `a`, across
   random sequences of open, resolve and finalize over several agents; balances still equal
   `totalEscrowed` and `totalBondsHeld`.
5. Different agents are independent: one agent at the cap does not block another.
6. Governance path: a timelock-executed resolution releases the count.
7. Size gate: `ComposedSettlement` runtime unchanged; `DeliveryDisputeV1` growth recorded.
8. Slither with the anchored CI filter: no new High.

## 7. Invariants and limits

- INV-9 adjacent: escrow and bonds stay separately backed; bonds still leave exactly once. INV-1 to
  INV-8 and INV-10 untouched.
- A cap cannot stop a ring that controls many admitted initiators; admission review remains the
  primary control. In any open-admission profile this design is insufficient on its own.
- Neither change measures or improves resolver accuracy; see `F13-RESOLVER-ACCURACY-PLAN.md`.
- Independent review is required before acceptance.
