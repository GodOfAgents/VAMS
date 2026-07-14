// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {DeployTestnet} from "../../script/DeployTestnet.s.sol";
import {AuthorityIdentityValidator} from "../../script/utils/AuthorityIdentityValidator.sol";
import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";
import {
    KnownSafeProxyFixture,
    KnownSafeSingletonFixture,
    ShapeOnlySafeFixture,
    ShapeOnlyTimelockFixture
} from "../helpers/AuthorityIdentityFixtures.sol";

contract DeployTestnetAuthorityTest is Test {
    uint256 private constant AMOY_CHAIN_ID = 80_002;

    DeployTestnet private deployer;
    KnownSafeSingletonFixture private safeSingleton;
    KnownSafeProxyFixture private governanceSafe;
    KnownSafeProxyFixture private treasurySafe;
    KnownSafeProxyFixture private pauseCouncil;

    function setUp() public {
        deployer = new DeployTestnet();
        safeSingleton = new KnownSafeSingletonFixture();
        governanceSafe = new KnownSafeProxyFixture(address(safeSingleton), 5, 3, 0x1000);
        treasurySafe = new KnownSafeProxyFixture(address(safeSingleton), 5, 3, 0x2000);
        pauseCouncil = new KnownSafeProxyFixture(address(safeSingleton), 3, 2, 0x3000);
    }

    function testAcceptsPinnedDistinctSafeAuthorities() public view {
        deployer.validateAuthorityIdentities(
            address(governanceSafe), address(treasurySafe), address(pauseCouncil), _safeIdentity()
        );
    }

    function testRehearsalDeploysAndRemovesDeployerPrivileges() public {
        vm.chainId(AMOY_CHAIN_ID);
        deployer.rehearse(address(governanceSafe), address(treasurySafe), address(pauseCouncil), _safeIdentity());
    }

    function testRejectsSafeInterfaceShapeImpersonator() public {
        ShapeOnlySafeFixture impersonator = new ShapeOnlySafeFixture(address(safeSingleton), 5, 3);
        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.SafeProxyRuntimeMismatch.selector,
                address(impersonator),
                address(impersonator).codehash,
                address(governanceSafe).codehash
            )
        );
        deployer.validateAuthorityIdentities(
            address(impersonator), address(treasurySafe), address(pauseCouncil), _safeIdentity()
        );
    }

    function testRejectsUnexpectedSafeSingleton() public {
        KnownSafeSingletonFixture unexpectedSingleton = new KnownSafeSingletonFixture();
        KnownSafeProxyFixture unexpectedProxy = new KnownSafeProxyFixture(address(unexpectedSingleton), 5, 3, 0x4000);
        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.SafeSingletonMismatch.selector,
                address(unexpectedProxy),
                address(unexpectedSingleton),
                address(safeSingleton)
            )
        );
        deployer.validateAuthorityIdentities(
            address(unexpectedProxy), address(treasurySafe), address(pauseCouncil), _safeIdentity()
        );
    }

    function testRejectsUnexpectedSafeSingletonRuntime() public {
        AuthorityIdentityValidator.SafeIdentity memory identity = _safeIdentity();
        bytes32 actual = identity.singletonRuntimeCodeHash;
        identity.singletonRuntimeCodeHash = bytes32(uint256(actual) ^ 1);
        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.SafeSingletonRuntimeMismatch.selector,
                address(safeSingleton),
                actual,
                identity.singletonRuntimeCodeHash
            )
        );
        deployer.validateAuthorityIdentities(
            address(governanceSafe), address(treasurySafe), address(pauseCouncil), identity
        );
    }

    function testRejectsNonExactGovernanceThreshold() public {
        KnownSafeProxyFixture fourOfFive = new KnownSafeProxyFixture(address(safeSingleton), 5, 4, 0x5000);
        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.InvalidSafe.selector, address(fourOfFive), uint256(5), uint256(4)
            )
        );
        deployer.validateAuthorityIdentities(
            address(fourOfFive), address(treasurySafe), address(pauseCouncil), _safeIdentity()
        );
    }

    function testRejectsSharedAuthority() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                DeployTestnet.SharedAuthority.selector, address(governanceSafe), address(governanceSafe)
            )
        );
        deployer.validateAuthorityIdentities(
            address(governanceSafe), address(governanceSafe), address(pauseCouncil), _safeIdentity()
        );
    }

    function testAcceptsExactVAMSTimelockRuntime() public {
        address[] memory proposers = new address[](1);
        proposers[0] = address(governanceSafe);
        address[] memory executors = new address[](1);
        executors[0] = address(0);
        VAMSTimelockController timelock = new VAMSTimelockController(48 hours, proposers, executors, address(0));

        deployer.validateTimelockIdentity(address(timelock));
        assertEq(address(timelock).codehash, deployer.expectedVAMSTimelockRuntimeCodeHash());
    }

    function testRejectsTimelockInterfaceShapeImpersonator() public {
        ShapeOnlyTimelockFixture impersonator = new ShapeOnlyTimelockFixture(48 hours, address(governanceSafe), true);
        bytes32 expectedRuntime = deployer.expectedVAMSTimelockRuntimeCodeHash();
        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.TimelockRuntimeMismatch.selector,
                address(impersonator),
                address(impersonator).codehash,
                expectedRuntime
            )
        );
        deployer.validateTimelockIdentity(address(impersonator));
    }

    function _safeIdentity() private view returns (AuthorityIdentityValidator.SafeIdentity memory) {
        return AuthorityIdentityValidator.SafeIdentity({
            proxyRuntimeCodeHash: address(governanceSafe).codehash,
            singleton: address(safeSingleton),
            singletonRuntimeCodeHash: address(safeSingleton).codehash
        });
    }
}
