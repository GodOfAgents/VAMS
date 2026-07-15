// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";

/**
 * @title EmergencyLockdown (Fixed)
 * @author VAMS Protocol
 * @notice EMERGENCY: Atomic lockdown script for compromised deployer wallet
 */

interface IAccessControlPausable {
    function revokeRole(bytes32 role, address account) external;
    function pause() external;
    function hasRole(bytes32 role, address account) external view returns (bool);
}

contract EmergencyLockdown is Script {
    // ============ Deployed Contract Addresses (Polygon Amoy) ============

    address VAMS_TOKEN;
    address TIMELOCK;
    // address STAKING; // Skipped - Unauthorized
    // address VESTING; // Skipped - Unauthorized
    address AGENT_REGISTRY;
    address X402_ESCROW;
    // address NONCE_REGISTRY; // Skipped - Unauthorized
    address PROVIDER_BOND;

    // ============ Role Hashes ============

    bytes32 constant DEFAULT_ADMIN_ROLE = 0x00;
    bytes32 constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    // bytes32 constant EMISSION_ADMIN_ROLE    = keccak256("EMISSION_ADMIN_ROLE");
    // bytes32 constant VESTING_ADMIN_ROLE_ACTUAL = keccak256("VESTING_ADMIN_ROLE");
    bytes32 constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    bytes32 constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    // bytes32 constant SETTLER_ROLE           = keccak256("SETTLER_ROLE");
    bytes32 constant ESCROW_ROLE = keccak256("ESCROW_ROLE");
    bytes32 constant SLASHER_ROLE = keccak256("SLASHER_ROLE");

    // Timelock-specific roles
    bytes32 constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
    bytes32 constant CANCELLER_ROLE = keccak256("CANCELLER_ROLE");

    function run() external {
        VAMS_TOKEN = vm.envAddress("VAMS_TOKEN");
        TIMELOCK = vm.envAddress("TIMELOCK");
        AGENT_REGISTRY = vm.envAddress("AGENT_REGISTRY");
        X402_ESCROW = vm.envAddress("X402_ESCROW");
        PROVIDER_BOND = vm.envAddress("PROVIDER_BOND");

        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast();

        address compromised = msg.sender;
        console.log("==============================================");
        console.log("  VAMS EMERGENCY LOCKDOWN (RETRY)");
        console.log("  Compromised wallet:", compromised);
        console.log("==============================================");

        // ============================================================
        // STEP 1: PAUSE CONTRACTS (Token, Registry, Escrow, Bond Only)
        // ============================================================
        console.log("");
        console.log("[STEP 1] Pausing contracts...");

        // 1a. VAMSToken
        _safePause(VAMS_TOKEN, "VAMSToken");

        // 1c. Agent Registry
        _safePause(AGENT_REGISTRY, "AgentRegistry");

        // 1d. X402 Escrow
        _safePause(X402_ESCROW, "X402Escrow");

        // 1f. Provider Bond Registry
        _safePause(PROVIDER_BOND, "ProviderBond");

        console.log("[STEP 1] Selected contracts paused.");

        // ============================================================
        // STEP 2: REVOKE ROLES (Token, Timelock, Registry, Escrow, Bond)
        // ============================================================
        console.log("");
        console.log("[STEP 2] Revoking roles...");

        // 2a. VAMSToken roles
        _safeRevoke(VAMS_TOKEN, PAUSER_ROLE, compromised, "VAMSToken.PAUSER_ROLE");
        // Minter not held
        _safeRevoke(VAMS_TOKEN, DEFAULT_ADMIN_ROLE, compromised, "VAMSToken.DEFAULT_ADMIN_ROLE");

        // 2b. Timelock roles
        _safeRevoke(TIMELOCK, PROPOSER_ROLE, compromised, "Timelock.PROPOSER_ROLE");
        // Executor not held
        _safeRevoke(TIMELOCK, CANCELLER_ROLE, compromised, "Timelock.CANCELLER_ROLE");
        _safeRevoke(TIMELOCK, DEFAULT_ADMIN_ROLE, compromised, "Timelock.DEFAULT_ADMIN_ROLE");

        // 2e. Agent Registry roles
        _safeRevoke(AGENT_REGISTRY, GUARDIAN_ROLE, compromised, "Registry.GUARDIAN_ROLE");
        _safeRevoke(AGENT_REGISTRY, DEFAULT_ADMIN_ROLE, compromised, "Registry.DEFAULT_ADMIN_ROLE");

        // 2f. X402 Escrow roles
        _safeRevoke(X402_ESCROW, ADMIN_ROLE, compromised, "Escrow.ADMIN_ROLE");
        _safeRevoke(X402_ESCROW, PAUSER_ROLE, compromised, "Escrow.PAUSER_ROLE");
        _safeRevoke(X402_ESCROW, DEFAULT_ADMIN_ROLE, compromised, "Escrow.DEFAULT_ADMIN_ROLE");

        // 2h. Provider Bond Registry roles
        _safeRevoke(PROVIDER_BOND, ADMIN_ROLE, compromised, "Bond.ADMIN_ROLE");
        _safeRevoke(PROVIDER_BOND, PAUSER_ROLE, compromised, "Bond.PAUSER_ROLE");
        // Escrow/Slasher not held
        _safeRevoke(PROVIDER_BOND, DEFAULT_ADMIN_ROLE, compromised, "Bond.DEFAULT_ADMIN_ROLE");

        console.log("[STEP 2] Roles revoked.");

        vm.stopBroadcast();
    }

    function _safePause(address target, string memory name) internal {
        // Direct call without try/catch to ensure we don't mask simulation errors
        // But only calling on contracts we CONFIRMED we have access to
        IAccessControlPausable(target).pause();
        console.log("  [OK] Paused:", name);
    }

    function _safeRevoke(address target, bytes32 role, address account, string memory label) internal {
        // Only revoke if we have the role (AccessControl check)
        // We know we are admin, so we can revoke ourselves
        IAccessControlPausable(target).revokeRole(role, account);
        console.log("  [REVOKED]", label);
    }
}
