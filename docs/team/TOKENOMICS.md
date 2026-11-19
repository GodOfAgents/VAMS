# VAMS Tokenomics and Economic Scope

**Version:** 2.3.0  
**Updated:** 2026-11-13  
**Last verified:** 2026-11-13 (local gates and non-author AI source review; release acceptance pending)  
**Status:** Restricted-profile economic decisions recorded; testnet readiness NOT READY

## 1. Scope and status

VAMS is intended as a sovereign Web4 protocol and a migration path from Web2 to
Web4. Its intended scope includes people, organizations, applications,
services, games, IoT, infrastructure, and autonomous agents. The agent economy
is one supporting subsystem, not the limit of the project. The broader
Immortal Execution goal is continuity of authorized workloads across changing
machines and providers; it remains a design and delivery objective, not a
universal guarantee or a funding guarantee supplied by this token model.

This document records the approved restricted faucet-only testnet economic
profile for Polygon Amoy and Cardano Pre-Prod, plus a clearly separate future
allocation plan. It does not establish that either chain has a live deployment,
that a token distribution has occurred, or that economic activation is ready.
The accepted profile is recorded in
[`OWNER_DECISIONS_20261108.md`](../remediation/OWNER_DECISIONS_20261108.md)
and [`testnet-profile.json`](../audit/testnet-profile.json). Implementation
and deployment-script references below describe source configuration, not
deployed chain state.

### 1.1 Approved restricted profile

| Area | Approved restricted-profile rule |
|---|---|
| Asset policy | Faucet-only; no sale, public launch, or real-capital economics |
| Maximum supply | Fixed at $1 \times 10^9$ VAMS |
| Inflation and staking rewards | Zero emissions and zero staking rewards |
| Staking minter | No staking minter; the restricted staking contract fixes rate and budget at zero |
| Principal exits | 14-day normal unbonding; up to 30 days in crisis; no emergency exit that bypasses maturity |
| Vesting | Unactivated and unfunded in the restricted profile |
| Fee buyback, burn, and reward distribution | Not activated |
| Delegation and slashing | Formally deferred; not activated |
| Polygon governance | Token governance inactive; restricted operations use the reviewed multisig/timelock model |
| DEC parameters | Emission floor, decay schedule, and terminal rate remain frozen-unset |

The testnet profile specifies a 48-hour Polygon timelock, 3-of-5 governance
and treasury Safe thresholds, and a 2-of-3 emergency authority limited to
pause actions. The owner-approved bootstrap seats overlap; they must not be
described as separated, decentralized, or independently reviewed. Cardano
governance v2 configuration requires five unique member key hashes and a
threshold of three, using separate Cardano keys for the same five governance
seats. Applied identities, addresses, deployment state, and independent
assurance remain separate evidence requirements. This is a dual-chain
authority plan; it does not move Cardano authority to Polygon or prove that
either chain has enacted it.

The intended chain roles remain distinct: Polygon is intended for execution
and settlement roles; Cardano retains governance, identity, insurance, and
native-validator domains. This document does not assert that those roles are
deployed or qualified.

The restricted Polygon deployment source constructs
`VAMSRestrictedStaking`, whose rate and annual budget are zero, and verifies
that staking has no minter role. It does not deploy vesting or token voting;
the current core producer is `contracts/script/DeployTestnet.s.sol`, while
the full restricted Amoy producer is `contracts/script/DeployRestrictedTestnet.s.sol`.
This source configuration is not deployment evidence. The Cardano authority
configuration has its own validator and ceremony requirements.

## 2. Supply and allocation plan

The supply ceiling is $1 \times 10^9$ VAMS (`contracts/src/token/VAMSToken.sol`).
The current Polygon deployment source mints that initial supply to the
treasury Safe. This does not mean that $100{,}000{,}000$ VAMS is in circulation
or that a TGE, airdrop, liquidity provision, sale, or community distribution
has occurred. “Unlocked,” “allocated,” “held by the treasury,” and
“circulating” describe different states.

The following percentages preserve the intended allocation plan. They are
future allocation labels and vesting terms, not current balances, issued
beneficiary schedules, or authorization to transfer or release tokens. The
allocation totals 100% of the capped supply.

| Category | Share | Planned amount | Intended future terms | Status |
|---|---:|---:|---|---|
| Community and ecosystem | 50% | 500,000,000 | Sub-allocations below | Unactivated |
| ↳ Liquidity and airdrop | 10% | 100,000,000 | Intended 100% unlocked at TGE | No TGE or distribution established |
| ↳ Ecosystem grants and mining | 40% | 400,000,000 | 0-month cliff, then 60-month linear vesting | Unactivated |
| Architect | 12% | 120,000,000 | 12-month cliff, then 48-month linear vesting | Unactivated |
| Future team and advisors | 13% | 130,000,000 | 12-month cliff, 36-month time schedule; intended 50% time-based and 50% GMV-gated | Unactivated; GMV rules unresolved |
| Investors | 13% | 130,000,000 | Sub-allocations below | Unactivated |
| ↳ Early investors | 5% | 50,000,000 | 6-month cliff, then 18-month linear vesting | Unactivated |
| ↳ Regular investors | 8% | 80,000,000 | 12-month cliff, then 30-month linear vesting | Unactivated |
| DAO treasury | 12% | 120,000,000 | 6-month cliff, 48-month time schedule; intended 50% time-based and 50% GMV-gated | Unactivated; GMV rules unresolved |

For any later activation, the intended monthly amounts are approximately 6.67M
for ecosystem grants, 2.50M for Architect, 3.61M for team and advisors,
2.78M for early investors, 2.67M for regular investors, and 2.50M for the DAO
treasury. Those rates follow the intended *post-cliff* durations above. They
are not evidence of an activated allocation. The vesting source now stores
each cliffed default's total duration as cliff plus the intended linear span.
Its public payout paths share a conservative fail-closed cumulative GMV gate;
that gate still applies to the whole releasable amount and does not implement
the intended 50/50 split. Vesting remains unactivated until funding, oracle
authority and freshness, milestone and tranche accounting, and the complete
activation evidence are independently accepted.

“Community and ecosystem: 50%” is an allocation label. It does not establish
that 50% is community-held, circulating, distributed, or governed by token
holders.

## 3. Future economic mechanisms: deferred, not active

The following are design proposals or historical targets. None is enabled by
the approved faucet-only profile, and none should be presented as an earned
yield, revenue stream, security guarantee, or deployed protocol feature.

### 3.1 Fees, buyback, and distributions

Historical proposals described a 0.1–1.0% dynamic protocol fee, a 2–7%
gas-abstraction markup, a 0.05% x402 settlement fee, a 0.25% bridge fee, and
fee splits for buyback, staking, treasury, and insurance. These rates and
splits are not active economic policy. Fee collection, asset routing, provider
costs, settlement volume, swap and slippage controls, and actual token burning
need an approved and tested design before activation. The composed-settlement
source already calculates a 5-basis-point fee and sends it to the earned
delivery's pinned treasury (`ComposedSettlement.sol`). Faucet-only rehearsals
can exercise that accounting; it is not a live-revenue or buyback claim, and
the source does not route that fee into `VAMSFeeCollector`. Sending an asset to a
dead address is not proof that VAMS `totalSupply` was reduced. The current
profile does not activate buybacks, burns, or fee-funded reward distributions.

### 3.2 Emissions and DEC

The restricted profile has zero emissions. No annual inflation schedule is
approved. The former 2.5% initial rate, 0.1% DEC floor, zero-floor statement,
and 500,000-token annual terminal target do not form one consistent schedule;
the floor, decay, and tail remain unset pending a separate economic design.
The hard supply ceiling remains $1 \times 10^9$ and is not raised by this
document. Ecosystem allocation vesting, if separately activated later, is a
distribution of the capped allocation and must not be counted again as new
inflation.

### 3.3 Staking, delegation, and security

The approved restricted staking profile provides no staking rewards and has
no staking minter. Historical Silver, Gold, and Platinum tiers, APY targets,
governance multipliers, collateral rewards, and CHC composition premiums are
not guarantees or active payout terms. A displayed tier or score alone does
not prove a funded reward, a market-clearing service premium, or a validated
operator.

The 14-day normal and up-to-30-day crisis unbonding periods are retained, with
no emergency principal exit that bypasses unbonding maturity. The planned
seven-day agent-upgrade notice does not by itself give delegators time to
withdraw under those principal delays; any future upgrade protection must
provide a compatible exit window and define its interaction with stake locks.

Delegated agent staking, fee sharing, saturation curves, shared slashing, and
delegator exit protections remain deferred. `contracts/src/staking/IVAMSDelegation.sol`
is an interface marked as a future implementation, not an operational
delegation system. Slashing remains disabled for this profile.

Inherited-security or restaking language is a future design hypothesis. No
claim that VAMS currently receives allocated, slashable security from another
network, is “whale-proof,” or inherits an external network's full security is
made here. Such a design requires explicit operators, custody, economic
allocation, slashing scope, cross-chain loss handling, and independent
evidence.

### 3.4 Governance and voting

The restricted profile uses reviewed multisig/timelock authority for
restricted operations; ordinary token governance is inactive. Polygon's
`VAMSGovernor` source uses OpenZeppelin `GovernorVotes` and
`GovernorCountingSimple`; it does not implement the quadratic or time-weighted
voting described in the former proposal. Cardano has quadratic-voting source
paths, including a v2 design with distinct voter keys, but source code alone
does not establish which validator configuration is selected or deployed,
identity independence, or semantic parity with Polygon. No claim of
implemented dual-chain quadratic governance is made.

Any future token voting design must specify voting units, time and stake
weighting, checkpoints, identity and Sybil assumptions, quorum, capture
resistance, and the distinct authority of Polygon and Cardano. Quadratic
weighting by itself is not identity resistance: one identity with 10,000
units has weight 100 under square-root weighting, while 100 accepted
identities with 100 units each have aggregate weight 1,000.

### 3.5 CHC and service pricing

Capability and CHC scores may inform service matching, but a score does not by
itself establish workload quality, an enforceable price premium, reward
eligibility, or slashing authority. Any later CHC-linked economics must state
how evidence is produced and challenged, how payments are funded, and what
happens on failure or disagreement.

## 4. Conditional historical scenario arithmetic

These examples explain arithmetic used in earlier planning material. They are
not forecasts, approved rates, or an assertion that fees, emissions, or burns
are active.

Let $M$ be tokens minted, $P$ their execution price, $R$ gross fee revenue,
$b$ the share of that revenue actually available for VAMS buyback and burn,
and $C$ the monetary costs and leakage not already reflected in $b$. Strict
net supply deflation requires:

$$bR - C > MP$$

At $25{,}000{,}000$ tokens and $P=\$0.20$, the minted-token value is
$\$5{,}000{,}000$. If all gross fees are usable for a real VAMS burn and
$C=0$, $\$5{,}000{,}000$ is break-even, not strict deflation. At a 40% usable
burn share, the same issuance would require more than $\$12{,}500{,}000$ gross
revenue before costs. The calculation depends on actual issuance, execution
price, burn share, and costs; it is not an unconditional threshold.

At a proposed x402 fee of 0.05%, $1{,}000{,}000$ gross annual fee revenue
would require $2{,}000{,}000{,}000$ in annual settled value before costs. If
there were 1,000,000 settlements every day, that volume would imply about
$5.48 average value per settlement. A count of API calls or micropayments
does not establish this settlement volume; multiple calls may aggregate into
one settlement. These values are conditional arithmetic only.

## 5. Activation and evidence boundary

Any future change from this restricted profile requires an explicit approved
design, source implementation, targeted tests, exact source/configuration
bindings, and the applicable independent and operational evidence. This
document does not activate vesting, emissions, staking rewards, buybacks,
fee distributions, delegation, slashing, or token governance. It does not
claim that the remaining implementation defects have been repaired. Readiness
for restricted deployment on both Polygon Amoy and Cardano Pre-Prod remains
subject to their authoritative gates and evidence; this document is not an
acceptance record or deployment authorization.

### 5.1 Audited implementation and remaining limits

The 2026-11-13 repair preserves active aggregate staking locks across top-ups,
retains accrued rewards through position changes, rejects zero-principal
compounding, advances annual mint windows by all completed years, and preserves
regional/aggregate allocation caps. Default vesting durations include the cliff
plus the post-cliff term; the conservative cumulative GMV gate fails closed.
These repairs do not activate rewards or vesting, implement the intended 50/50
GMV split, or qualify oracle freshness and activation inputs.

The legacy ERC-8004 attestation registration entrypoint now unconditionally
reverts before external calls. A generic verifier success flag previously lacked
a qualified root/action/agent/freshness binding. The separate action-bound DCAP
path still requires authentic qualification; a quote, CHC score or source-level
fix does not establish reward eligibility, premium pricing or slashing authority.
Previously deployed immutable adapters are not changed by editing this source.

Three non-author AI source reviews examined that containment fix and all 61
residual Medium Slither identities without identifying an additional production
defect. Fresh local Solidity results were 1,242 passed across 83 suites, zero
failures/skips; the size gate passed. Slither reported 0 High, 61 Medium and 28
Optimization findings, with no new detector exclusions or suppressions. These
overlapping full-suite results must not be added to historical test totals.

Missing direct callback/lifecycle tests, authentic DCAP/custody evidence,
independent human assurance and both-chain admission requirements remain open.
Source review is not release acceptance. The approved supply cap, future
allocation labels, zero emissions/rewards, 14/30-day unbonding, inactive economic
features and frozen-unset DEC parameters remain unchanged. Details:
[non-author review and evidence](../remediation/repair_20261113/NONAUTHOR-SLITHER-REVIEW.md).
