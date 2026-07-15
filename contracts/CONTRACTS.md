# VAMS Public Testnet Deployment Evidence Register

**Status Date:** 2026-07-14
**Last verified:** 2026-07-14
**Stage:** Pre-testnet deployment evidence template
**Scope:** Polygon Amoy contracts, an empty paused VDSO suite, and Cardano
Pre-Prod validators

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

## Polygon Amoy VDSO Canary Evidence

The VDSO suite is deployment-eligible only as an empty, non-authoritative,
non-value-bearing canary with public `VDSO_MODE=off`. No public Gateway VDSO
route may be mounted. All seven EVM modules must be paused at deployment, with
`PAUSER_ROLE` held only by the distinct 2-of-3 emergency Safe and no deployer
privilege remaining. Guardian/quarantine and recovery authority must use two
additional, mutually distinct 2-of-3 Safe proxies; no privileged authority may
be an EOA. Each authority Safe must have nonce zero and no enabled module,
transaction guard, module guard, or fallback handler at the deployment
snapshot. This current-state check is not proof that no hash was preapproved:
the ceremony must also pin an audited Safe release and provide complete setup
and `ApproveHash` event history. Every field remains `Pending` until a chain-ID
`80002` rehearsal or deployment produces exact-commit evidence.

| Module | Address | Deploy Tx | Runtime Code Hash | Explorer Verification | Authority | Empty / Inactive Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `VAMSObjectStore` | Pending | Pending | Pending | Pending | Pending | Pending | No state domain or writer may be active. |
| `VAMSReservationManager` | Pending | Pending | Pending | Pending | Pending | Pending | No reservation or recovery verifier may be active. |
| `VAMSAdapterRegistry` | Pending | Pending | Pending | Pending | Pending | Pending | Registry must be empty; Avail, EigenDA, and current Celestia/Near VDSO routes remain excluded. |
| `VAMSProgramRegistry` | Pending | Pending | Pending | Pending | Pending | Pending | Registry must contain no active program. |
| `VAMSProofRouter` | Pending | Pending | Pending | Pending | Pending | Pending | No proof or recovery verifier may be configured. |
| `VAMSCapabilityRouter` | Pending | Pending | Pending | Pending | Pending | Pending | No execution capability may be activated. |
| `VAMSExecutionKernel` | Pending | Pending | Pending | Pending | Pending | Pending | No execution route may be active. |

---

## Cardano Pre-Prod Validator Evidence

| Validator | Script Hash / Address | Deploy Tx | Verification | Role Owner | Safe / Multisig | Timelock | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `governor.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Schema-v2 source preserves proposal authentication assets and emits one exact Cardano-local timelock intent; applied-parameter and transaction evidence pending. |
| `timelock.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Source restricts execution to configured local targets and requires emergency threshold cancellation; bridge execution is disabled. Applied evidence pending. |
| `insurance_fund.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Source binds the canonical fund asset, claim commitments, approvals, and exact payout transitions; cross-chain deposits are disabled. Applied evidence pending. |
| `agent_registry.ak` | Pending | Pending | Pending | Pending | Pending | Pending | Source preserves the full agent authentication asset class and exact value; owner deregistration burns/refunds and slashing is disabled. Applied evidence pending. |

Auxiliary creation controls are not persistent validators. Record the applied
`agent_nft.ak`, `proposal_nft.ak`, and `fund_nft.ak` one-shot policy IDs,
parameter manifests, seed UTxOs, and bootstrap/registration transactions in
the Cardano deployment evidence bundle. Never count them as additional
persistent validators. Unapplied Aiken blueprint/template hashes are not
deployment script hashes.

`cardano/lib/vams/vdso.ak` is conformance-only library evidence. It is not a
validator entrypoint and must never be entered in this register as a deployed
Cardano VDSO validator.

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
10. Safe release/runtime allowlist, `getOwners()`, `getThreshold()`, zero nonce,
    extension-free storage, setup transaction, and complete `ApproveHash`
    history evidence for every authority Safe.
11. VDSO runtime code hashes plus empty registry/domain/program/verifier counts,
    `paused() == true`, pause-authority transfer, and zero deployer privileges
    for all seven modules.
12. A public profile proving `VDSO_MODE=off`; private shadow evidence is kept in
    a separately signed `vdso-shadow-report.json` and cannot authorize public or
    value-bearing VDSO operation.

---

## Deprecated Historical Addresses

Earlier V1 addresses were documented during pre-hardening work and must not be
used for public testnet or mainnet claims. If historical references are needed,
keep them in archival docs with a clear `deprecated` label and never mix them
with the active public testnet evidence table above.
