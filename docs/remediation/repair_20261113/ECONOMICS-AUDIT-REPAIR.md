# Economics audit repair — 2026-11-13

Last verified: 2026-11-13. Local engineering work; both-chain deployment
admission remains **NOT READY**. This is a repair/evidence note, not a new
blocker ledger, track acceptance or activation authorization.

## Approved scope and design

[Owner decision 4](../OWNER_DECISIONS_20261108.md) fixes the supply cap at
$1 \times 10^9$, zero emissions/rewards and no staking minter. Vesting,
buybacks/reward distribution, delegation, slashing and ordinary token voting
remain inactive; DEC floor/decay/tail remain frozen-unset. Current restricted
deployment source omits vesting and ordinary token-governor deployment;
older notes saying they are constructed are superseded by current
DeployTestnet.s.sol and DeployRestrictedTestnet.s.sol. This is source
configuration, not evidence of either chain's deployed state.

The user's November 13 request authorizes fixes and regression tests while
preserving those disablements. No future live monetary model is selected.

- **Staking principal:** one aggregate position retains the later of its
  existing deadline and the requested commitment. An active position cannot
  switch to a shorter lock type. A longer type renews the whole position;
  after expiry a new selected lock can start. Both stake and permit paths
  use this rule.
- **Rewards:** mutations crystallize rewards using the previous amount,
  tier and lock, retaining them as pending. Claim/compound consume once,
  with atomic rollback on failed mint. Fully unstaked users can claim;
  compounding cannot recreate sub-minimum unlocked principal.
- **Annual windows:** token and staking counters skip every elapsed fixed
  period once. Unused old allowances cannot be consumed through repeated
  calls at one timestamp. Supply and current-period caps are unchanged.
- **Regional budget:** all saturated shares, including exact-cap equality,
  are removed before redistribution. Sum <=10,000 BPS and each share <=3,000
  BPS. With fewer than four regions, unallocatable budget remains retained.
  Python accepts only integer caps from 500 through 3,000. Dust follows
  configured order: Python sorts IDs, Solidity uses registration order.
  Exact per-region parity requires matching order; Python float weight
  limitations remain.
- **Dormant vesting:** total default durations are cliff plus intended
  post-cliff span. Direct/batch/all release and gated revocation/refund
  require configured successful exact-32-byte GMV meeting the threshold.
  Revocation clears unvested plus vested-but-unreleased locked accounting
  before transfers. This is conservative all-or-nothing containment,
  **not** the proposed 50/50 milestone system or authenticated freshness.
  The legacy LIQUIDITY schedule is not the planned TGE airdrop.
- **Dormant collector:** collection now enforces pause/reentry guards,
  including automatic distribution. No fee/buyback/reward route was added.

These contracts are not deployed or upgraded by this work. Later deployment
requires fresh bytecode/instance qualification.

## Input-report reconciliation

The earlier audit under VAMS-economics-audit-20261113-01 and the user's
additional November 12 static report remain historical evidence. Their old
line citations are not reinterpreted against repaired source.

| Finding | Current disposition |
|---|---|
| Staking lock bypass | Repaired; real-token/restricted-staking public-path regressions added. |
| B-1 supply/inflation | Docs state accepted cap/zero emissions. No cap increase or reward activation; general mint-funded rewards remain unqualified. |
| B-2 lost rewards | Crystallization repaired; full exit, repeat claim and failed mint cases added. |
| B-3 multiplied/unbacked staking liabilities | Restricted subclass remains non-activatable at zero; funded liability/yield design remains deferred. Reward preservation is not a solvency certification. |
| B-4 accelerated vesting | Default clocks repaired; independent allocation snapshots/boundaries added. |
| B-5 GMV bypass/failure | Shared fail-closed gate on all payouts/refunds; 50/50 milestones, freshness/authority and activation remain unresolved. |
| B-6 governance | Docs distinguish ordinary Polygon votes from restricted multisig/timelock and Cardano authority; no new voting mechanism enabled. |
| B-7 fee/burn routing | Configured faucet settlement fees go to treasury; buyback/reward distributions stay inactive. Collection pause/reentry bypass repaired. |
| B-8 builder revenue | Already repaired in current RewardDistributor: exact funding and protected pending liabilities. Old unbacked-credit claim is stale. |
| M-2 emergency exit | Already repaired: both principal exits require mature 14/30-day unbonding. Crisis mode is a governed flag, not an automatic price trigger. |
| M-3 aggregate emissions | Repaired. Actual old-source vector returns 11,333 BPS, 1,333 above budget, while every individual region remains <=30%. |
| M-4 burn semantics | Dead-address transfers are not represented as reducing totalSupply; true buyback/burn remains inactive. |
| L-1 annual bursts | Token and staking period rotation repaired. |
| L-2 revoke accounting | All outstanding schedule tokens leave locked accounting on revoke. |
| M-1 DEC ensemble/cadence/domain/bounds | Authority remains inactive; future parameters frozen-unset. No one-signature controller is described as qualified ensemble safety. |
| M-5 insurance | Current source already checks the post-payout 30% cap. Vault valuation/liquidity and correlated collateral risk remain unqualified; real yield disabled. |
| M-6 governor clock | Token governance remains inactive. No wall-clock voting duration or quadratic/time-weighted implementation is asserted. |

Delegation, CHC rewards, allocated restaking security, wash-trade evidence,
hardware-floor integration, monetized fees, future insurance/yield and a
general funded staking model remain deferred. These missing mechanisms are
not silently implemented or qualified by this repair.

## Documentation

[TOKENOMICS.md](../../team/TOKENOMICS.md) records the approved faucet-only
Amoy and Cardano Pre-Prod profile, unactivated allocation plan and conditional
historical arithmetic. It removes additive inflation, guaranteed yields,
unconditional deflation, whale-proof/inherited-security certainty and
implemented dual-chain quadratic-voting claims. The full Web2-to-Web4/
Immortal Execution mission and both chains' roles remain in scope.

Strict supply deflation requires actual tokens burned > actual tokens
minted. The historical $5M example is gross break-even before costs.

## Verification

The final combined candidate passed the local checks below. These are source-
bound engineering results, not release acceptance or live economic evidence.

First package: VAMS-economics-repair-20261113-01. Old-source diagnostic:
150 methods, 122 passed/28 failed; one failure exposed a too-short new
custom-error expectation, subsequently corrected. The candidate then failed
compilation with stack depth and executed zero tests. Allocation helpers
were extracted without changing compiler, optimizer or arithmetic.

Second package: VAMS-economics-repair-20261113-02. Its 237-file manifest is:
95490af7f803df0ebce1da6de51f7fa3fa4b33c87f17142c2aed334018f77d6a.
It compiled and ran 150 focused methods: 148 passed and two new fixture
assertions failed (existing wallet balance and a getter consuming a prank).
Those fixtures were corrected with exact balance deltas and caller setup;
the production source did not change between R2 and final R3.

Final package: VAMS-economics-repair-20261113-03, 237 files, manifest
dbb9a503e6a6f289fcf82e5a0e75dcd7fa10acb69da3e0db86643ede9e9e229e.
The reviewed runner uses private network namespace, read-only source/host,
private outputs, FFI disabled, pinned Forge 1.7.1/Solc 0.8.24, two threads,
256 fuzz cases and seed 0x20261113. It verifies 2,697 existing WSL dependency
files and Gitlinks; nothing was installed or substituted from Windows
dependency worktrees. Root serializes heavy work. Timeout/cancellation
cleanup identifies only the newly spawned process group.

| Retained receipt | Actual result | Scope |
|---|---|---|
| ECONOMICS-FULL-03.json | 1,231 passed; 0 failed/skipped; 81 suites | Full Solidity suite, including all 150 focused economics methods; counts overlap and are not added |
| ECONOMICS-SIZES-03.json | Exit 0 | Build/size gate; compiler/lint warnings retained separately |
| ECONOMICS-PYTHON-03.json | 35 passed | Changed regional simulator module's complete selected pytest file |
| ECONOMICS-SLITHER-04.json | Scanner exit 0; report success; 0 High, 62 Medium, 28 Optimization | Slither 0.11.5, whole Solidity tree, --fail-high; not a zero-finding report |
| ECONOMICS-BANDIT-05.json | Exit 0; no findings, no errors/skipped files | Changed Python module, -ll -ii; 246 lines, no nosec suppressions |

R4 and R5 use exactly the R3 source archive. Separate raw streams, tool and
configuration identities, finding JSON and hashes are retained. Seven Medium
findings in changed contracts received non-author AI source review: three
deliberate whole-year rounding operations and four empty-amount guards.
This does not close the other 55 Medium findings or replace older source-bound
adjudications. No detector, exclusion or severity gate was weakened for a pass.

Runtime/creation bytes: token 11,563/15,854; staking 10,152/10,825;
restricted staking 9,864/10,521; regional DEC 7,798/8,603;
fee collector 8,551/8,808; vesting 8,896/9,483. Unchanged ComposedSettlement
is 24,401 runtime bytes, 175 bytes below the EVM runtime ceiling.

Source synchronization has its own hash-approved INTEGRATION-PLAN, retained
preimages/diff, journal and INTEGRATION-RECEIPT in the R3 evidence directory.
Canonical integration is established only by that receipt's 20-file and
237-file equality checks. Counts are not added or rerun merely because
identical bytes are copied between roots.

Working-tree documentation validation:
python -B scripts/docs/validate_docs.py --json
Exit 0, status success, errors empty. This is a documentation/source check.
Full Python/security/supply-chain release gates, Cardano native gates,
both-chain rehearsals, authentic providers/custody/privacy assurance and real
observation time are not established here. Cardano source is unchanged.

## Invariants and authority

INV-1: regional and aggregate budgets strengthened. INV-7: missing/failed
GMV reads fail closed; freshness remains unqualified. INV-8: hard cap
preserved and annual windows repaired. INV-9: accrued rewards preserved;
restricted rewards stay zero and exact-prefunded distributor backing is
retained. General staking is not certified solvent.
INV-2, INV-3–INV-6 and INV-10 enforcement are unchanged.

No live profile, role, endpoint, signer, oracle, provider, custody record,
contract instance or economic authority was activated. No deployment,
broadcast, funding, key acquisition or external provider call occurred.
No canonical readiness status or track is promoted by local test evidence.

