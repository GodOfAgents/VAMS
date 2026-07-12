# VAMS Public Testnet Deployment Evidence Register

**Status Date:** 2026-07-12
**Last verified:** 2026-07-12
**Stage:** Pre-testnet deployment evidence template
**Scope:** Polygon Amoy contracts and Cardano Pre-Prod validators

This document is the source of truth for public testnet deployment artifacts.
It does not claim mainnet deployment, production readiness, final audit status,
or completed public testnet launch.

---

## Recording Rules

- Record only verified deployment facts.
- Leave unknown fields as `Pending`; do not use placeholder addresses.
- Every deployed contract or validator must include network, chain identifier,
  transaction hash, verification status, privileged role owner, Safe/multisig,
  timelock status, and notes.
- Privileged roles must move from deployer custody to Gnosis Safe or equivalent
  multisig before public operator onboarding.
- Any changed address requires a new row or a dated note preserving the old
  evidence trail.

---

## Network Baseline

| Network | Chain Identifier | Purpose | Status |
| --- | --- | --- | --- |
| Polygon Amoy | `80002` | EVM public testnet target for Solidity contracts | Planned |
| Cardano Pre-Prod | Network magic `1` | Validator rehearsal target for Aiken scripts | Planned |

---

## Polygon Amoy Contract Evidence

| Contract | Proxy Address | Implementation Address | Deploy Tx | Verification | Role Owner | Safe / Multisig | Timelock | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `VAMSToken` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | ERC-20 governance token; max supply invariant remains $1 \times 10^9$. |
| `VAMSVesting` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Vesting schedules require deploy-time beneficiary review. |
| `VAMSStaking` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Reward solvency evidence required before launch. |
| `VAMSGovernor` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Governance wiring must point to testnet timelock. |
| `VAMSTimelockController` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Minimum delay and proposer/executor roles must be recorded. |
| `GovernorExecutor` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Cross-chain proof separation must be preserved. |
| `ComposedSettlement` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Escrow role ownership and pause path required. |
| `RegionAwareDEC` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Regional emission cap must remain <= 30%. |
| `RegionalIncentives` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Thin-liquidity price-floor parameters required. |
| `RewardDistributor` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Stablecoin/hybrid payout routes require live integration review. |
| `VAMSInsuranceFund` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Yield allocation cap must remain <= 30%. |
| `VAMSFeeCollector` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Fee cap evidence required. |
| `TransactionCompensation` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Compensation solvency evidence required. |
| `BatchSettlement` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Signature verification evidence required. |
| `VAMSSentinel` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Sentinel pause/slash authority must be Safe-controlled. |
| `SLAEnforcer` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Oracle freshness evidence required. |
| `SlashingParameters` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Parameter changes require timelock evidence. |
| `VAMSRouter` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | CLR routing parameters require deploy-time review. |
| `VAMSAgentRegistry` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Authorized wallet/session-key constraints required. |
| `VAMSHardwareRegistry` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Hardware collateralization evidence required. |
| `VAMSTrustAggregator` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Trust input weighting evidence required. |
| `VAMSUpgradeableBase` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Upgrade authority must transfer to Safe/timelock. |
| `VAMSEmergencyPausable` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Guardian list and auto-expiry evidence required. |
| `InsuranceFundProxy` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Bridge-compatible insurance claims require proof review. |

---

## Cardano Pre-Prod Validator Evidence

| Validator | Script Hash / Address | Deploy Tx | Verification | Role Owner | Safe / Multisig | Timelock | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `governor.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Must verify governance continuing-output and timelock handoff rules. |
| `timelock.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Cancel path requires at least 2 authorized DAO multisig signatures. |
| `insurance_fund.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Guardian multisig and payout cap evidence required. |
| `agent_registry.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Agent DID and CIP-68 identity evidence required. |

---

## Required Pre-Testnet Evidence

`contracts/script/DeployV2.s.sol` is a legacy integration script and is not an
approved public-testnet ceremony. It defaults to a blocked execution path
because it still contains deployer-controlled placeholder allocations and an
incomplete multisig handoff. Do not set its legacy acknowledgement
flag for a public deployment.

The approved Polygon Amoy source ceremony is
`contracts/script/DeployTestnet.s.sol`. It requires deployed governance and
treasury Safes with at least 3-of-5 thresholds plus a distinct 2-of-3 emergency
council, locks execution to chain ID `80002`, enforces a 48-hour timelock,
assigns the entire fixed supply to the treasury Safe, keeps staking rewards at
zero without granting the staking contract minter authority, and fails if the
deployer retains token or timelock roles. Reward activation is outside the
first public-testnet profile and requires a separately audited solvency design
plus a 48-hour governance action. Source validation does not replace the
on-chain evidence required below.

Before public testnet onboarding, attach or link the following evidence:

1. `forge build --sizes` and `forge test -vvv` output for the exact deploy commit.
2. Slither output for the exact deploy commit, with high findings resolved or explicitly accepted.
3. `aiken check` output for the exact Cardano validator commit.
4. Deployment transaction hashes and explorer verification URLs.
5. Role transfer transactions from deployer to Safe/multisig and timelock.
6. Safe owner list, threshold, and recovery policy.
7. Gateway live configuration evidence: Caddy config, loopback bind, DID admin, and mTLS fingerprint allowlist.
8. Mock-mode promotion scan output proving live DA, identity, TEE, bridge, Trails, Coinme, and gateway audit paths fail closed.
9. `DeployTestnet.s.sol` simulation and broadcast JSON reviewed against the deployment manifest.
10. Safe `getOwners()` and `getThreshold()` evidence for governance, treasury, and emergency councils.

---

## Deprecated Historical Addresses

Earlier V1 addresses were documented during pre-hardening work and must not be
used for public testnet or mainnet claims. If historical references are needed,
keep them in archival docs with a clear `deprecated` label and never mix them
with the active public testnet evidence table above.
