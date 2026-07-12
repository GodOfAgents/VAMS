// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {VAMSToken} from "../src/token/VAMSToken.sol";
import {VAMSStaking} from "../src/staking/VAMSStaking.sol";
import {VAMSVesting} from "../src/vesting/VAMSVesting.sol";
import {VAMSGovernor} from "../src/governance/VAMSGovernor.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";
import {VAMSSentinel} from "../src/sentinel/VAMSSentinel.sol";

interface ISafeLike {
    function getOwners() external view returns (address[] memory);
    function getThreshold() external view returns (uint256);
}

contract DeployTestnet is Script {
    uint256 internal constant POLYGON_AMOY_CHAIN_ID = 80_002;
    uint256 internal constant GOVERNANCE_DELAY = 48 hours;

    error InvalidChain(uint256 actual, uint256 expected);
    error InvalidSafe(address candidate, uint256 owners, uint256 threshold);
    error SharedAuthority(address first, address second);
    error DeployerRetainedRole(address target, bytes32 role);

    uint256 private deployerPrivateKey;
    address private deployer;
    address private governanceSafe;
    address private treasurySafe;
    address private emergencyCouncil;

    VAMSTimelockController private timelock;
    VAMSToken private token;
    VAMSStaking private staking;
    VAMSVesting private vesting;
    VAMSGovernor private governor;
    VAMSSentinel private sentinel;

    function run() external {
        if (block.chainid != POLYGON_AMOY_CHAIN_ID) {
            revert InvalidChain(block.chainid, POLYGON_AMOY_CHAIN_ID);
        }

        deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        deployer = vm.addr(deployerPrivateKey);
        governanceSafe = vm.envAddress("VAMS_GOVERNANCE_SAFE");
        treasurySafe = vm.envAddress("VAMS_TREASURY_SAFE");
        emergencyCouncil = vm.envAddress("VAMS_EMERGENCY_COUNCIL");

        _requireSafe(governanceSafe, 5, 3);
        _requireSafe(treasurySafe, 5, 3);
        _requireSafe(emergencyCouncil, 3, 2);
        _requireDistinctAuthorities(governanceSafe, treasurySafe, emergencyCouncil);

        vm.startBroadcast(deployerPrivateKey);
        _deployContracts();
        _configureRoles();
        vm.stopBroadcast();

        _verifyPostconditions();
        _logDeployment();
    }

    function _deployContracts() private {
        address[] memory noProposers = new address[](0);
        address[] memory openExecutors = new address[](1);
        openExecutors[0] = address(0);
        timelock = new VAMSTimelockController(
            GOVERNANCE_DELAY,
            noProposers,
            openExecutors,
            deployer
        );
        token = new VAMSToken(deployer, treasurySafe);
        staking = new VAMSStaking(
            address(token),
            address(token),
            0,
            address(timelock)
        );
        vesting = new VAMSVesting(address(token), address(timelock));
        governor = new VAMSGovernor(token, timelock);
        sentinel = new VAMSSentinel(
            address(timelock),
            address(token),
            address(timelock),
            emergencyCouncil
        );
    }

    function _configureRoles() private {
        timelock.grantRole(timelock.PROPOSER_ROLE(), address(governor));
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

    function _verifyPostconditions() private view {
        _requireNoRole(
            address(token),
            token.hasRole(token.DEFAULT_ADMIN_ROLE(), deployer),
            token.DEFAULT_ADMIN_ROLE()
        );
        _requireNoRole(
            address(token),
            token.hasRole(token.MINTER_ROLE(), deployer),
            token.MINTER_ROLE()
        );
        _requireNoRole(
            address(token),
            token.hasRole(token.PAUSER_ROLE(), deployer),
            token.PAUSER_ROLE()
        );
        _requireNoRole(
            address(token),
            token.hasRole(token.MINTER_ROLE(), address(staking)),
            token.MINTER_ROLE()
        );
        _requireNoRole(
            address(timelock),
            timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), deployer),
            timelock.DEFAULT_ADMIN_ROLE()
        );
        require(timelock.getMinDelay() >= GOVERNANCE_DELAY, "Timelock below 48 hours");
        require(token.totalSupply() == token.MAX_SUPPLY(), "Supply invariant failed");
        require(token.balanceOf(treasurySafe) == token.MAX_SUPPLY(), "Treasury allocation failed");
        require(staking.rewardPerSecond() == 0, "Testnet staking rewards must be disabled");
    }

    function _logDeployment() private view {
        console.log("VAMS Polygon Amoy deployment complete");
        console.log("Token:", address(token));
        console.log("Timelock:", address(timelock));
        console.log("Governor:", address(governor));
        console.log("Staking:", address(staking));
        console.log("Vesting:", address(vesting));
        console.log("Sentinel:", address(sentinel));
        console.log("Governance Safe:", governanceSafe);
        console.log("Treasury Safe:", treasurySafe);
        console.log("Emergency Council:", emergencyCouncil);
    }

    function _requireSafe(
        address candidate,
        uint256 minimumOwners,
        uint256 minimumThreshold
    ) private view {
        if (candidate.code.length == 0) revert InvalidSafe(candidate, 0, 0);
        try ISafeLike(candidate).getOwners() returns (address[] memory owners) {
            try ISafeLike(candidate).getThreshold() returns (uint256 threshold) {
                if (owners.length < minimumOwners || threshold < minimumThreshold) {
                    revert InvalidSafe(candidate, owners.length, threshold);
                }
            } catch {
                revert InvalidSafe(candidate, owners.length, 0);
            }
        } catch {
            revert InvalidSafe(candidate, 0, 0);
        }
    }

    function _requireNoRole(
        address target,
        bool retained,
        bytes32 role
    ) private pure {
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
}
