# VAMS Security: Role & Key Management

This document outlines the operational security procedures, roles, and administrative key architecture for the Verifiable and Agentic Modular Stack (VAMS). 

Following the v1.0.0-icn architectural upgrade, VAMS has migrated to a robust `VAMSUpgradeableBase` architecture to strictly segment operational permissions across our modular framework. Single-key administration has been deprecated.

## 1. Access Control Roles

VAMS core contracts leverage OpenZeppelin's `AccessControlUpgradeable`. The following roles govern all operational state changes and upgrades.

### `DEFAULT_ADMIN_ROLE` (Master Role)
- **Permissions**: Can grant or revoke all other roles. Acts as the `RoleAdmin` for `UPGRADER_ROLE`, `GOVERNANCE_ROLE`, and `EMERGENCY_ROLE`.
- **Holder**: Held exclusively by the VAMS Master Multisig (Phase 2) or the DAO Timelock (Phase 3). Never held by a simple Externally Owned Account (EOA) in mainnet.

### `UPGRADER_ROLE` (Contract Upgrades)
- **Permissions**: Authorized to execute UUPS logic upgrades (via `upgradeToAndCall`) and manage structural changes, specifically the VAMS Trust Aggregator plugin configurations (`registerProofPlugin`, `deregisterProofPlugin`).
- **Holder**: Initially the Developer Operations key, eventually transferring to the DAO Timelock.

### `GOVERNANCE_ROLE` (Protocol Parameters)
- **Permissions**: Responsible for updating business rules and bounds without touching contract logic, including managing dynamic validation bounds, base rates, and demand curves in `VAMSValidatorManager`.
- **Holder**: The VAMS Governance multisig or an automated timelock governor.

### `EMERGENCY_ROLE` (Circuit Breaking)
- **Permissions**: Can trigger emergency pauses (`pause()`) and freeze pricing structures (`emergencyFreeze()`) during abnormal network conditions or detected exploit attempts.
- **Holder**: Dedicated multisig composed of DevSecOps team members and trusted community guardians.

---

## 2. Key Segregation Best Practices

**Crucial Warning**: Using a single deployment key to manage all roles is strictly forbidden under mainnet VAMS protocol policy. If one key is compromised, the entire protocol stack is at risk.

You must set up distinct keys (hardware wallets or Multi-Party Computation wallets via Safe) for each role:

1. **The Admin Key (Cold Storage)**: Should never be loaded into a script or hot wallet. Only used to grant/revoke roles or transfer authority.
2. **The Upgrader Key (Warm Storage)**: Used infrequently during scheduled maintenance windows for logic upgrades.
3. **The Governance Key (Timelocked)**: Represents the collective voting consensus of the VAMS DAO.
4. **The Emergency Key (Hot/Warm Storage)**: Requires fast access capabilities by the DevSecOps team to halt malicious activities rapidly.

---

## 3. Governance Phases

VAMS uses a 4-phase rollout plan for progressively decentralizing these keys via `VAMSUpgradeableBase`:

1. **Phase 1 (Deployer EOA)**: Restricted to testnets. A single deployer holds all roles for bootstrapping.
2. **Phase 2 (Team Multisig)**: Recommended for early mainnet. Uses `transferToMultisig()` to migrate `DEFAULT_ADMIN_ROLE` and `UPGRADER_ROLE` securely to a 3-of-5 Safe multisig.
3. **Phase 3 (DAO Governance)**: Uses `transferToDAO()` to shift authority to an on-chain Timelock controller governed by `$VAMS` token quadratic voting. 
4. **Phase 4 (Immutable)**: Optional final phase. Invoking `renounceUpgradeability()` permanently deletes the `UPGRADER_ROLE`, sealing the protocol logic forever.

---

## 4. v0.6.0 Additions — OMS Integration Roles

### `YIELD_MANAGER_ROLE` (Insurance Fund Yield)
- **Permissions**: Can call `deployToYield(address vault, uint256 amount)` and
  `withdrawFromYield(address vault, uint256 amount)` on `VAMSInsuranceFund.sol`.
  Deployment is mathematically capped at ≤30% of `totalFundBalance()` — the cap is enforced
  by a Solidity `require`, not by this role alone.
- **Holder**: Initially the `GOVERNANCE_ROLE` multisig; intended to transfer to an automated
  `YieldManager` smart contract once audited.
- **Note**: This role does **not** grant access to insurance claim processing or fund withdrawals.

---

## 5. OMS API Key Rotation Procedure

Two environment variables are introduced in v0.6.0 for the OMS Compliance and RPC integrations:

| Variable | Purpose | Rotation Frequency |
|---|---|---|
| `OMS_API_KEY` | Authentication for `OMSIdentityVerifier` API calls | Every 90 days |
| `OMS_IDENTITY_API` | Base URL for OMS Identity endpoint | Only on provider migration |
| `OMS_POLYGON_RPC_PRIMARY` | Primary enterprise RPC for Polygon-ecosystem chains | As needed |
| `OMS_POLYGON_RPC_SECONDARY` | Fallback enterprise RPC | As needed |

**Rotation Steps (OMS_API_KEY):**
1. Provision a new API key from the OMS Console (polygon.technology/oms)
2. Update the key in your secrets manager (AWS Secrets Manager / HashiCorp Vault)
3. Perform a rolling restart of Neuron services — old key remains valid during transition
4. Revoke the old key in the OMS Console after confirming all services are running the new key
5. Update `docs/role-management-keys.md` with the rotation date

> [!CAUTION]
> Never commit `OMS_API_KEY` or `OMS_IDENTITY_API` to version control. Load exclusively from
> environment variables or a secrets manager. `oms_identity.py` fails closed outside
> mock mode when `OMS_API_KEY` is unset.

---

## 6. Session Key Expiry Policy

Session keys created by `SessionKeyManager` in `neuron/sdk/sequence_wallet.py` carry the
following expiry rules:

| TrustTier | Default Validity | Maximum Validity | Can Re-issue Without Root? |
|---|---|---|---|
| BRONZE | 24h | 48h | Yes (up to 3 consecutive) |
| SILVER | 24h | 72h | Yes (up to 5 consecutive) |
| GOLD | 24h | 7 days | Yes, with governance approval |
| PLATINUM | 24h | 30 days | Yes, with governance approval |

**Expiry enforcement:** Session keys are validated on-chain by the Sequence ERC-4337
`EntryPoint`. An expired key causes the `UserOperation` to be rejected at the paymaster stage —
no on-chain state is mutated on rejection.

**Key invalidation (emergency):** A compromised session key can be revoked by calling
`VAMSAgentRegistry.setAuthorizedWallet(agentId, address(0))`, which clears the authorized wallet
and immediately invalidates all associated session operations.
