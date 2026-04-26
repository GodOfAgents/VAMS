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
