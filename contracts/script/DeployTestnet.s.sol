// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {VAMSToken} from "../src/token/VAMSToken.sol";
import {VAMSStaking} from "../src/staking/VAMSStaking.sol";
import {VAMSRestrictedStaking} from "../src/staking/VAMSRestrictedStaking.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";
import {VAMSSentinel} from "../src/sentinel/VAMSSentinel.sol";
import {AuthorityIdentityValidator} from "./utils/AuthorityIdentityValidator.sol";

/// @notice Historical core-only producer; full service admission uses DeployRestrictedTestnet.
contract DeployTestnet is Script, AuthorityIdentityValidator {
    uint256 internal constant POLYGON_AMOY_CHAIN_ID = 80_002;
    uint256 internal constant GOVERNANCE_DELAY = 48 hours;

    error InvalidChain(uint256 actual, uint256 expected);
    error SharedAuthority(address first, address second);
    error DeployerRetainedRole(address target, bytes32 role);

    uint256 internal deployerPrivateKey;
    address internal deployer;
    address internal governanceSafe;
    address internal treasurySafe;
    address internal emergencyCouncil;

    VAMSTimelockController internal timelock;
    VAMSToken internal token;
    VAMSStaking internal staking;
    VAMSSentinel internal sentinel;

    function run() external virtual {
        _requireAmoy();

        deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        deployer = vm.addr(deployerPrivateKey);
        governanceSafe = vm.envAddress("VAMS_GOVERNANCE_SAFE");
        treasurySafe = vm.envAddress("VAMS_TREASURY_SAFE");
        emergencyCouncil = vm.envAddress("VAMS_EMERGENCY_COUNCIL");
        SafeIdentity memory safeIdentity = SafeIdentity({
            proxyRuntimeCodeHash: vm.envBytes32("VAMS_SAFE_PROXY_RUNTIME_CODE_HASH"),
            singleton: vm.envAddress("VAMS_SAFE_SINGLETON"),
            singletonRuntimeCodeHash: vm.envBytes32("VAMS_SAFE_SINGLETON_RUNTIME_CODE_HASH")
        });

        _validateAuthorityIdentities(governanceSafe, treasurySafe, emergencyCouncil, safeIdentity);

        vm.startBroadcast(deployerPrivateKey);
        _deployContracts();
        _configureRoles();
        vm.stopBroadcast();

        _verifyPostconditions(safeIdentity);
        _logDeployment(safeIdentity);
    }

    /// @notice Local full-stack rehearsal that never reads or broadcasts a private key.
    function rehearse(
        address governanceAuthority,
        address treasuryAuthority,
        address emergencyAuthority,
        SafeIdentity calldata safeIdentity
    ) external virtual {
        _requireAmoy();
        deployer = address(this);
        governanceSafe = governanceAuthority;
        treasurySafe = treasuryAuthority;
        emergencyCouncil = emergencyAuthority;
        _validateAuthorityIdentities(governanceSafe, treasurySafe, emergencyCouncil, safeIdentity);
        _deployContracts();
        _configureRoles();
        _verifyPostconditions(safeIdentity);
    }

    /// @notice Read-only ceremony preflight for exact Safe instance identities.
    function validateAuthorityIdentities(
        address governanceAuthority,
        address treasuryAuthority,
        address emergencyAuthority,
        SafeIdentity calldata safeIdentity
    ) external view {
        _validateAuthorityIdentities(governanceAuthority, treasuryAuthority, emergencyAuthority, safeIdentity);
    }

    /// @notice Read-only identity check for the exact VAMS timelock runtime.
    function validateTimelockIdentity(address candidate) external view {
        _requireKnownVAMSTimelockRuntime(candidate);
    }

    function _deployContracts() internal {
        address[] memory noProposers = new address[](0);
        address[] memory openExecutors = new address[](1);
        openExecutors[0] = address(0);
        timelock = new VAMSTimelockController(GOVERNANCE_DELAY, noProposers, openExecutors, deployer);
        token = new VAMSToken(deployer, treasurySafe);
        staking = new VAMSRestrictedStaking(address(token), address(timelock));
        // Vesting and token voting are not deployed in this restricted profile.
        sentinel = new VAMSSentinel(address(timelock), address(token), address(timelock), emergencyCouncil);
    }

    function _configureRoles() internal {
        timelock.grantRole(timelock.PROPOSER_ROLE(), governanceSafe);
        timelock.grantRole(timelock.CANCELLER_ROLE(), governanceSafe);

        token.grantRole(token.DEFAULT_ADMIN_ROLE(), address(timelock));
        token.grantRole(token.PAUSER_ROLE(), address(timelock));
        token.removeExemptAddress(deployer);
        token.revokeRole(token.MINTER_ROLE(), deployer);
        token.revokeRole(token.PAUSER_ROLE(), deployer);
        token.renounceRole(token.DEFAULT_ADMIN_ROLE(), deployer);

        timelock.renounceRole(timelock.DEFAULT_ADMIN_ROLE(), deployer);
    }

    function _verifyPostconditions(SafeIdentity memory safeIdentity) internal view {
        _validateAuthorityIdentities(governanceSafe, treasurySafe, emergencyCouncil, safeIdentity);
        _requireKnownVAMSTimelockRuntime(address(timelock));
        _requireNoRole(address(token), token.hasRole(token.DEFAULT_ADMIN_ROLE(), deployer), token.DEFAULT_ADMIN_ROLE());
        _requireNoRole(address(token), token.hasRole(token.MINTER_ROLE(), deployer), token.MINTER_ROLE());
        _requireNoRole(address(token), token.hasRole(token.PAUSER_ROLE(), deployer), token.PAUSER_ROLE());
        _requireNoRole(address(token), token.hasRole(token.MINTER_ROLE(), address(staking)), token.MINTER_ROLE());
        _requireNoRole(
            address(timelock), timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), deployer), timelock.DEFAULT_ADMIN_ROLE()
        );
        require(timelock.getMinDelay() >= GOVERNANCE_DELAY, "Timelock below 48 hours");
        require(timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), address(timelock)), "Timelock self-admin missing");
        require(timelock.hasRole(timelock.PROPOSER_ROLE(), governanceSafe), "Governance proposer missing");
        require(timelock.hasRole(timelock.CANCELLER_ROLE(), governanceSafe), "Governance canceller missing");
        require(timelock.hasRole(timelock.EXECUTOR_ROLE(), address(0)), "Open executor missing");
        require(token.totalSupply() == token.MAX_SUPPLY(), "Supply invariant failed");
        require(token.balanceOf(treasurySafe) == token.MAX_SUPPLY(), "Treasury allocation failed");
        require(staking.rewardPerSecond() == 0, "Testnet staking rewards must be disabled");
        require(staking.annualEmissionBudget() == 0, "Testnet emission budget must be zero");
        require(!VAMSRestrictedStaking(address(staking)).rewardsEnabled(), "Restricted reward guard missing");
    }

    function _logDeployment(SafeIdentity memory safeIdentity) internal view {
        console.log("VAMS Polygon Amoy deployment complete");
        console.log("Token:", address(token));
        console.log("Timelock:", address(timelock));
        console.log("Staking:", address(staking));
        console.log("Sentinel:", address(sentinel));
        console.log("Governance Safe:", governanceSafe);
        console.log("Treasury Safe:", treasurySafe);
        console.log("Emergency Council:", emergencyCouncil);
        console.log("Safe Singleton:", safeIdentity.singleton);
        console.log("Safe proxy runtime code hash:");
        console.logBytes32(safeIdentity.proxyRuntimeCodeHash);
        console.log("Safe singleton runtime code hash:");
        console.logBytes32(safeIdentity.singletonRuntimeCodeHash);
        console.log("Timelock runtime code hash:");
        console.logBytes32(address(timelock).codehash);
    }

    function _requireNoRole(address target, bool retained, bytes32 role) private pure {
        if (retained) revert DeployerRetainedRole(target, role);
    }

    function _requireDistinctAuthorities(
        address governanceAuthority,
        address treasuryAuthority,
        address emergencyAuthority
    ) private pure {
        if (governanceAuthority == treasuryAuthority) {
            revert SharedAuthority(governanceAuthority, treasuryAuthority);
        }
        if (governanceAuthority == emergencyAuthority) {
            revert SharedAuthority(governanceAuthority, emergencyAuthority);
        }
        if (treasuryAuthority == emergencyAuthority) {
            revert SharedAuthority(treasuryAuthority, emergencyAuthority);
        }
    }

    function _validateAuthorityIdentities(
        address governanceAuthority,
        address treasuryAuthority,
        address emergencyAuthority,
        SafeIdentity memory safeIdentity
    ) internal view {
        _requireSafe(governanceAuthority, 5, 3, safeIdentity);
        _requireSafe(treasuryAuthority, 5, 3, safeIdentity);
        _requireSafe(emergencyAuthority, 3, 2, safeIdentity);
        _requireDistinctAuthorities(governanceAuthority, treasuryAuthority, emergencyAuthority);
    }

    function _requireAmoy() internal view {
        if (block.chainid != POLYGON_AMOY_CHAIN_ID) {
            revert InvalidChain(block.chainid, POLYGON_AMOY_CHAIN_ID);
        }
    }
}
