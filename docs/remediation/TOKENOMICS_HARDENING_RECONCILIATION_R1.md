# Tokenomics hardening reconciliation R1

Date: 2026-10-08. Evidence level: current-source inspection only.
Status: specification reconciliation and executable acceptance PENDING.

## Scope and existing coverage

This record adds the gaps identified in the complete [tokenomics specification](../team/TOKENOMICS.md) to the hardening pipeline. It is initial source-backed triage, not an exhaustive economic audit, a repair, an independently accepted implementation or deployment evidence. No Solidity, Aiken or economic simulation ran for this record.

The [mission](MISSION.md) remains a restricted faucet-only Polygon Amoy plus Cardano Pre-Prod testnet. Public launch, TGE, real capital and mainnet are outside scope. TOKENOMICS.md is a pre-launch specification, not implementation evidence; this record does not amend its parameters.

The [control matrix](../audit/control-matrix.json) already covers supply/emissions/solvency (T17), fees/settlement/insurance/yield (T18), linked actors and market abuse (T19), concentration (T20), governance (T21) and regional fairness (T22). T17-T20 and T22 are partial; T21 is blocked. Reuse G2/G4 and relevant M4/M6/M7 integration controls. Broad suite counts do not resolve the clause-level gaps below.

The [testnet profile](../audit/testnet-profile.json) disables staking rewards, real fiat and real yield capital. [DeployTestnet.s.sol](../../contracts/script/DeployTestnet.s.sol) constructs zero-rate staking, revokes the deployer minter and checks that staking has no minter role. These are source restrictions, not deployed observations. They do not automatically exclude vesting, fee or governance paths.

Every enabled path requires a frozen interpretation, public-boundary tests, source-bound evidence and separate review. A future feature may be deferred or disabled for this restricted profile only through a reviewed scope disposition and executable containment. A missing test is not an exclusion; PENDING never becomes PASS through reclassification.

## Gap and acceptance matrix

TR identifiers are local reconciliation rows, not new F-ledger dispositions. All executable verification is PENDING. Priorities describe potential impact if the path is enabled; they do not assert deployed exposure or reproduced loss.

| Row / priority | Specification and current source | Gap | Required decision and public evidence | Existing track |
| --- | --- | --- | --- | --- |
| TR-01 / High if enabled | TOKENOMICS sections 4-5: team/treasury 50% time, 50% GMV. [VAMSVesting.sol](../../contracts/src/vesting/VAMSVesting.sol), release entrypoints, lines 196-269. | `batchRelease` and `releaseAll` omit GMV checks. Individual `release` bypasses the gate for an unset oracle/zero threshold or failed/short oracle response, and does not implement separate 50% tranches. | Freeze milestones, units, oracle authority/freshness and tranche semantics. Test all three release entrypoints with met/unmet, absent, reverting, short, malformed and stale GMV evidence; check balances and locked/released accounting. Invalid GMV must not unlock the gated portion. | T17/T18/T21; G2/G4 |
| TR-02 / High economic mismatch | TOKENOMICS sections 4-5/Appendix A: linear vesting after cliff. [VAMSVesting.sol](../../contracts/src/vesting/VAMSVesting.sol), constants and `_vestedAmount`, lines 43-58 and 479-506. | Default duration is an end measured from schedule start, with the cliff subtracted from the linear span. Completion is founder M48 vs M60, team M36 vs M48, early investor M18 vs M24, regular investor M30 vs M42, foundation M48 vs treasury M54 in the specification. | Freeze start/cliff/post-cliff clocks and foundation-to-treasury mapping. Test each cliff and completion boundary, independent monthly amounts, rounding, repeated release and conservation. Code months are 30-day units, not automatically calendar months. | T17/T21; G2/G4 |
| TR-03 / High if enabled | TOKENOMICS section 8.2: 14-day unbonding, up to 30 days in crisis. [VAMSStaking.sol](../../contracts/src/staking/VAMSStaking.sol), lines 246-301. | Normal withdrawal checks `unbondingEnd`; public `emergencyWithdraw` checks only `lockedUntil` and returns active plus unbonding principal without that deadline. | Freeze any emergency exception explicitly. Test active/pending stake through both exits, expired stake locks, 14/30-day boundaries, crisis changes and principal conservation. A stake lock is not an unbonding clock. | T17/T19/T21; G2/G4 |
| TR-04 / Blocking specification decision | TOKENOMICS sections 1/7/Appendix A discuss inflation and about $1.05 \times 10^9$ supply. [VAMSToken.sol](../../contracts/src/token/VAMSToken.sol), lines 50-53 and 144-170, enforces $1 \times 10^9$; [RegionAwareDEC.sol](../../contracts/src/economic/RegionAwareDEC.sol), lines 360-365, transfers prefunded tokens. | Additional supply conflicts with INV-8; distributing rewards from the existing grants pool is not additional supply. The specification mixes those models. | Owner must reconcile redistribution versus burn-headroom minting or separately review a design amendment. Do not silently raise INV-8. Test allocation/cap boundaries, burns/remints, funded rewards and annual-window/catch-up behavior after multi-year inactivity. | T17/T21; INV-8/INV-9; G2/G4 |
| TR-05 / Material timing/authority gap | TOKENOMICS section 3.1: 100% buyback/burn until M60, then 40/30/20/10. [VAMSFeeCollector.sol](../../contracts/src/economic/VAMSFeeCollector.sol), lines 235-285. | Administrative phase/custom-split changes do not enforce that clock or a one-way transition. | Freeze phase origin, terminal-emission dependency and override authority. Test early/at/late changes, reversal, unauthorized/custom bypass and conservation. Overrides require explicit reviewed semantics. | T18/T21; G2/G4 |
| TR-06 / Material burn-semantics gap | TOKENOMICS section 3.1 promises automated VAMS buyback/burn. [VAMSFeeCollector.sol](../../contracts/src/economic/VAMSFeeCollector.sol), lines 203-229. | Fee-token transfer to `BURN_ADDRESS` is not a VAMS buyback or ERC-20 burn reducing `totalSupply`. | Freeze supported assets and buyback/burn mechanism or an explicit exclusion. Measure acquired VAMS, actual supply reduction, failures, rounding and conservation. Dead-address balances and revenue/price projections do not prove deflation. | T17/T18; INV-8; G2 |
| TR-07 / High before reward activation | TOKENOMICS section 3.1 assigns 30% mature fees to rewards. [VAMSFeeCollector.sol](../../contracts/src/economic/VAMSFeeCollector.sol), lines 219-220; [VAMSStaking.sol](../../contracts/src/staking/VAMSStaking.sol), `claimRewards` and accrual/mint paths. | A transfer to staking does not establish fee-funded claimability. The claim path mints; funding, reservations and accrued liabilities need a coherent model. | Keep zero rewards/no staking minter pending separate INV-9 design. Test collector-to-staking integration, funded/accrued/claimed/pending balances, insufficiency, failed mint/transfer and retries. Recipient balances or mint mocks are insufficient. | T17/T18; INV-9; G2 |
| TR-08 / Unimplemented or deferred | TOKENOMICS section 2: per-agent delegation, fee sharing, shared slashing, saturation and seven-day upgrade/exit protection. [IVAMSDelegation.sol](../../contracts/src/staking/IVAMSDelegation.sol), line 12, is a future stub. | An interface is not implementation. Seven-day exit protection conflicts with 14/30-day unbonding unless explicitly reconciled; generic timelocks do not prove withdrawal before upgrade. | Select a reviewed profile disposition; before enablement freeze delegation/slashing and upgrade/exit semantics. Test actual entrypoints, linked actors, saturation, authorization and fee/principal conservation. | T17-T21; G2/G4 |
| TR-09 / Overstated implementation claim | TOKENOMICS sections 1/7 claim quadratic/time-weighted dual-chain governance. [VAMSGovernor.sol](../../contracts/src/governance/VAMSGovernor.sol), lines 14-117. | Solidity inherits ordinary GovernorVotes/CountingSimple without a quadratic/time-weighted override. That does not establish the claimed square-root-of-staked-token model or Cardano parity. | Freeze voting units, weights, checkpoints, identity/Sybil assumptions and restricted-profile governance. Test independent vote vectors, stake/time boundaries, quorum/capture and both-chain semantics where enabled. Preserve multisig/timelock controls. | T20/T21; G2/G4 |
| TR-10 / Unresolved specification/evidence | TOKENOMICS sections 3.1/6/7: 0.1% floor, DAO 0% floor, decay, 500K/year terminal, fee movement and ensemble fallback. [DynamicEmissionController.sol](../../contracts/src/governance/DynamicEmissionController.sol), lines 23-35. | Floors/terminal rules need reconciliation; rate/change constants alone do not prove decay or three-model divergence safety. Model count is not signature-quorum evidence. | Freeze units, reward source, floor/decay/terminal rules and observational versus authoritative outputs. Test epochs, cumulative budgets, divergence, invalid/stale inputs, fallback and alerts; retain regional <=30%, supply and solvency limits. | T17/T19/T22 and M6; INV-1/INV-8/INV-9; G2 |

## Remaining clause coverage

This is not complete TOKENOMICS coverage. Map allocation and claimed 10% TGE circulation, grants/vesting funding, protocol/gas/x402/bridge fee rates, tier eligibility/APY/governance weights, collateralized probation/shared slashing, CHC yield premiums/challenge authority and inherited-security/restaking claims. APY and demand/price examples remain targets or assumptions, not guaranteed yield or network proof. TGE exclusions do not establish an observed initial distribution.

Use the chain:

`requirement -> owner-approved interpretation -> exact implementation -> public regression -> source-bound evidence/review -> enabled / enforced-disabled / reviewed-deferred disposition`

Assign the existing track owner and missing prerequisite. This update assigns no activation disposition or PASS credit. Independently derived expected values and mutation sensitivity are required; helper constants, generic totals, synthetic campaigns and event-only assertions do not substitute for enabled contract behavior.

## Dependency-ordered follow-up (proposal only)

1. Freeze the supply, vesting/GMV, emergency-unbonding, fee-phase/burn, funding and governance interpretations and explicit restricted-profile dispositions with owner and independent review.
2. In separately authorized narrow slices, reproduce/remediate TR-01 through TR-03 for enabled paths, or prove their approved disabled boundary. Do not change production from this documentation request.
3. Qualify fee/reward/emission integration and remaining enabled clauses, then run existing economic/invariant/governance gates against the exact integrated tree.
4. Carry accepted evidence into M7 and separately authorized rehearsal/observation. No TGE, deployment or reward activation follows.

This work can progress independently of the F04 runner blocker, without waiving it. The rejected F04 R5 result is not superseded; D1/D2/D3 receive no new execution credit. F05/M3, M5, historical M2 and history/security/network/governance blockers are not closed or replaced.

## Invariant and mock-mode impact

| ID | Documentation-only impact |
| --- | --- |
| INV-1 | Enforcement unchanged; emission qualification must preserve regional <=30%. |
| INV-2 | Enforcement unchanged; prior narrow payout-cap acceptance does not prove vault liveness. |
| INV-3 | Session expiry untouched. |
| INV-4 | Contract allowlists untouched. |
| INV-5 | OMS fail-closed behavior untouched. |
| INV-6 | Root-EOA TEE binding untouched. |
| INV-7 | Oracle enforcement untouched; GMV freshness/failure needs separate TR-01 rules. |
| INV-8 | Absolute $1 \times 10^9$ cap unchanged; supply reconciliation remains pending. |
| INV-9 | No reward activation or new acceptance; zero-rate/no-minter profile retained. |
| INV-10 | Bridge proof/payload separation untouched; fee design is not proof substitution. |

Mock behavior and M1 containment are unchanged. Synthetic projections/local doubles cannot become live economic, identity, DA, provider or bridge proof. Finding/milestone dispositions are unchanged. Readiness remains NOT READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

## Source identity and limitations

Canonical HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`.
Branch: `testnet/remediation-20260907`.
Before-edit expanded porcelain-v1 status: 3,392 entries, SHA-256
`7b54fde08f974e60203182f746fd4aa0438507e34a321c81c1ee43e2e1a8f21f`.
Recursive submodules: 14 entries, SHA-256
`343f414115be335d8fd6dfcfe4abef99d85e92553efe396043f3c38aaffe1d2d`.
HEAD alone does not bind dirty source. Inspected file hashes follow.

| File | SHA-256 |
| --- | --- |
| docs/team/TOKENOMICS.md | `81578c75fc1bca5ee883c00f1f7dbdb535ad8ce237435ee7cf114b0d4994fa45` |
| docs/audit/control-matrix.json | `28b9146bb2ace970c19441ab4cd8ee4f91937d56acf4f178b3639f5b4f493cf4` |
| docs/audit/testnet-profile.json | `67136081adf06054b9385db7fe94987744529ed5a5f221ffb6ada0f5057153db` |
| docs/audit/INVARIANT_CONTROL_INDEX.md | `315236c492566c0aa0cc14182ef8e3b35e50ff81dace57e86f8466115e0b5348` |
| docs/remediation/FINDINGS.json | `b62253b4b0c7d88355e04eeff3f51c06d6e15c462f083a7224e99f3a6b44dc35` |
| contracts/src/vesting/VAMSVesting.sol | `223ca7e8d6bd165d74172b22928ab76c37882221480a570d838ef05b71896bb8` |
| contracts/src/staking/VAMSStaking.sol | `543e5183d7c0c1ca65f6b9d20063fdbb6127c248115120bc5ef41859b049f950` |
| contracts/src/economic/VAMSFeeCollector.sol | `e646a9da0a15961178708ca1bf8713c1b408d429eca351a7192d7eb1b0bf88a2` |
| contracts/src/token/VAMSToken.sol | `df9e5d7bd893a617359c68638766858fa2eb6883fe7458820d0c9d079f4ddc17` |
| contracts/src/governance/DynamicEmissionController.sol | `2fad3dcefe4b168401e139084d1f99d668462019823746879aaa280a75ec9fb7` |
| contracts/src/economic/RegionAwareDEC.sol | `cb8191c3782754d7774bd682e1d5799520240bb7f5d3c4cd46bafa2e7254ec86` |
| contracts/src/staking/IVAMSDelegation.sol | `3279451ee2aca7cfed33a72295e25c07dd85eb12a9f832b1d985fad02b8e069a` |
| contracts/src/governance/VAMSGovernor.sol | `0eaf7fb0ec6cab0b0c79f82113134438cc309e0ea8510e7b2762304a2eb8cfb9` |
| contracts/script/DeployTestnet.s.sol | `542d6aed8e5fb1cccc08ef8ceed6361ae7aa715bb181dfa65894c203b2c15cf9` |
| cardano/aiken.lock | `7c69f0a484d3b42862dc0ab0773cf6b3edf72709c921b2ad3648a0753af8cafc` |
| cardano/plutus.json | `718845f253ebdfb9f1d565e34511534f6b565cf1dd898402b67109180dff6492` |

Documentation/link/JSON validation establishes structure and continuity only. Solidity, Aiken, simulator, economic-campaign and live-network checks are NOT_RUN for this documentation slice. No historical evidence verdict is rewritten; no independent economic acceptance is claimed.
