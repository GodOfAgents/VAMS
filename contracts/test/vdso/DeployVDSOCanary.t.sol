// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {DeployVDSOCanary} from "../../script/DeployVDSOCanary.s.sol";
import {AuthorityIdentityValidator} from "../../script/utils/AuthorityIdentityValidator.sol";
import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";
import {VDSOTypes} from "../../src/vdso/VDSOTypes.sol";
import {VAMSObjectStore} from "../../src/vdso/VAMSObjectStore.sol";
import {VAMSReservationManager} from "../../src/vdso/VAMSReservationManager.sol";
import {VAMSAdapterRegistry} from "../../src/vdso/VAMSAdapterRegistry.sol";
import {VAMSProgramRegistry} from "../../src/vdso/VAMSProgramRegistry.sol";
import {VAMSProofRouter} from "../../src/vdso/VAMSProofRouter.sol";
import {VAMSCapabilityRouter} from "../../src/vdso/VAMSCapabilityRouter.sol";
import {VAMSExecutionKernel} from "../../src/vdso/VAMSExecutionKernel.sol";
import {
    KnownSafeProxyFixture,
    KnownSafeSingletonFixture,
    ShapeOnlySafeFixture,
    ShapeOnlyTimelockFixture
} from "../helpers/AuthorityIdentityFixtures.sol";

contract MockVDSOAuthority {}

contract DeployVDSOCanaryTest is Test {
    uint256 private constant AMOY_CHAIN_ID = 80_002;
    bytes32 private constant REHEARSAL_ID = keccak256("REHEARSAL");

    DeployVDSOCanary private deployer;
    KnownSafeSingletonFixture private safeSingleton;
    KnownSafeProxyFixture private governanceSafe;
    KnownSafeProxyFixture private pauseCouncil;
    MockVDSOAuthority private guardian;
    MockVDSOAuthority private recoveryAuthority;
    VAMSTimelockController private timelock;

    function setUp() public {
        vm.chainId(AMOY_CHAIN_ID);
        deployer = new DeployVDSOCanary();
        safeSingleton = new KnownSafeSingletonFixture();
        governanceSafe = new KnownSafeProxyFixture(address(safeSingleton), 5, 3, 0x1000);
        pauseCouncil = new KnownSafeProxyFixture(address(safeSingleton), 3, 2, 0x2000);
        guardian = new MockVDSOAuthority();
        recoveryAuthority = new MockVDSOAuthority();

        address[] memory proposers = new address[](1);
        proposers[0] = address(governanceSafe);
        address[] memory executors = new address[](1);
        executors[0] = address(0);
        timelock = new VAMSTimelockController(48 hours, proposers, executors, address(0));
    }

    function testRehearsalDeploysEmptyCanaryAndHandsOffRoles() public {
        DeployVDSOCanary.Authorities memory authorities = _authorities(address(timelock));
        deployer.rehearse(authorities, _safeIdentity());

        VAMSObjectStore objectStore = deployer.objectStore();
        VAMSReservationManager reservationManager = deployer.reservationManager();
        VAMSAdapterRegistry adapterRegistry = deployer.adapterRegistry();
        VAMSProgramRegistry programRegistry = deployer.programRegistry();
        VAMSProofRouter proofRouter = deployer.proofRouter();
        VAMSCapabilityRouter capabilityRouter = deployer.capabilityRouter();
        VAMSExecutionKernel kernel = deployer.kernel();

        assertTrue(objectStore.hasRole(objectStore.DEFAULT_ADMIN_ROLE(), address(timelock)));
        assertFalse(objectStore.hasRole(objectStore.DEFAULT_ADMIN_ROLE(), address(deployer)));
        assertTrue(objectStore.hasRole(objectStore.KERNEL_ROLE(), address(kernel)));
        assertTrue(reservationManager.hasRole(reservationManager.KERNEL_ROLE(), address(kernel)));
        assertEq(address(reservationManager.recoveryVerifier()), address(0));
        assertTrue(proofRouter.hasRole(proofRouter.KERNEL_ROLE(), address(kernel)));

        assertTrue(objectStore.hasRole(objectStore.AUTHORITY_ADMIN_ROLE(), address(timelock)));
        assertTrue(adapterRegistry.hasRole(adapterRegistry.REGISTRAR_ROLE(), address(timelock)));
        assertTrue(programRegistry.hasRole(programRegistry.REGISTRAR_ROLE(), address(timelock)));
        assertTrue(proofRouter.hasRole(proofRouter.CONFIG_ROLE(), address(timelock)));
        assertTrue(kernel.hasRole(kernel.EXECUTOR_ROLE(), address(timelock)));

        assertFalse(objectStore.hasRole(objectStore.PAUSER_ROLE(), address(pauseCouncil)));
        assertFalse(reservationManager.hasRole(reservationManager.PAUSER_ROLE(), address(pauseCouncil)));
        assertFalse(adapterRegistry.hasRole(adapterRegistry.PAUSER_ROLE(), address(pauseCouncil)));
        assertFalse(programRegistry.hasRole(programRegistry.PAUSER_ROLE(), address(pauseCouncil)));
        assertFalse(proofRouter.hasRole(proofRouter.PAUSER_ROLE(), address(pauseCouncil)));
        assertFalse(capabilityRouter.hasRole(capabilityRouter.PAUSER_ROLE(), address(pauseCouncil)));
        assertTrue(kernel.hasRole(kernel.PAUSER_ROLE(), address(pauseCouncil)));
        assertFalse(objectStore.hasRole(objectStore.AUTHORITY_ADMIN_ROLE(), address(pauseCouncil)));
        assertTrue(adapterRegistry.hasRole(adapterRegistry.GUARDIAN_ROLE(), address(guardian)));
        assertFalse(adapterRegistry.hasRole(adapterRegistry.REGISTRAR_ROLE(), address(guardian)));
        assertTrue(reservationManager.hasRole(reservationManager.RECOVERY_ROLE(), address(recoveryAuthority)));
        assertFalse(reservationManager.hasRole(reservationManager.KERNEL_ROLE(), address(recoveryAuthority)));

        assertEq(address(capabilityRouter.adapterRegistry()), address(adapterRegistry));
        assertEq(address(kernel.objectStore()), address(objectStore));
        assertEq(address(kernel.reservationManager()), address(reservationManager));
        assertEq(address(kernel.adapterRegistry()), address(adapterRegistry));
        assertEq(address(kernel.programRegistry()), address(programRegistry));
        assertEq(address(kernel.proofRouter()), address(proofRouter));
        assertEq(address(kernel.capabilityRouter()), address(capabilityRouter));

        VAMSObjectStore.DomainAuthority memory authority = objectStore.getDomainAuthority(REHEARSAL_ID);
        VAMSAdapterRegistry.AdapterConfig memory adapter = adapterRegistry.getAdapter(REHEARSAL_ID);
        VAMSProgramRegistry.ProgramConfig memory program = programRegistry.getProgram(REHEARSAL_ID);
        VAMSProofRouter.VerifierSet memory verifier = proofRouter.getVerifier(REHEARSAL_ID);
        assertFalse(authority.enabled);
        assertEq(authority.epoch, 0);
        assertEq(uint8(adapter.status), uint8(VDSOTypes.AdapterStatus.NONE));
        assertFalse(program.active);
        assertFalse(verifier.active);
    }

    function testRehearsalRejectsNonAmoyChain() public {
        vm.chainId(1);
        vm.expectRevert(abi.encodeWithSelector(DeployVDSOCanary.InvalidChain.selector, 1, AMOY_CHAIN_ID));
        deployer.rehearse(_authorities(address(timelock)), _safeIdentity());
    }

    function testRehearsalRejectsMissingAuthorities() public {
        DeployVDSOCanary.Authorities memory empty;
        vm.expectRevert(abi.encodeWithSelector(AuthorityIdentityValidator.InvalidSafe.selector, address(0), 0, 0));
        deployer.rehearse(empty, _safeIdentity());
    }

    function testRehearsalRejectsShortTimelock() public {
        vm.store(address(timelock), bytes32(uint256(2)), bytes32(uint256(48 hours - 1)));
        vm.expectRevert(
            abi.encodeWithSelector(DeployVDSOCanary.InvalidTimelock.selector, address(timelock), uint256(48 hours - 1))
        );
        deployer.rehearse(_authorities(address(timelock)), _safeIdentity());
    }

    function testRehearsalRejectsTimelockWithoutExecutor() public {
        address[] memory proposers = new address[](1);
        proposers[0] = address(governanceSafe);
        address[] memory noExecutors = new address[](0);
        VAMSTimelockController noExecutorTimelock =
            new VAMSTimelockController(48 hours, proposers, noExecutors, address(0));
        vm.expectRevert(
            abi.encodeWithSelector(
                DeployVDSOCanary.TimelockExecutorMissing.selector, address(noExecutorTimelock), address(governanceSafe)
            )
        );
        deployer.rehearse(_authorities(address(noExecutorTimelock)), _safeIdentity());
    }

    function testRehearsalRejectsUnexpectedSafeThreshold() public {
        KnownSafeProxyFixture weakGovernanceSafe = new KnownSafeProxyFixture(address(safeSingleton), 5, 2, 0x3000);
        address[] memory proposers = new address[](1);
        proposers[0] = address(weakGovernanceSafe);
        address[] memory executors = new address[](1);
        executors[0] = address(0);
        VAMSTimelockController weakTimelock = new VAMSTimelockController(48 hours, proposers, executors, address(0));

        DeployVDSOCanary.Authorities memory authorities = _authorities(address(weakTimelock));
        authorities.governanceSafe = address(weakGovernanceSafe);
        vm.expectRevert(
            abi.encodeWithSelector(AuthorityIdentityValidator.InvalidSafe.selector, address(weakGovernanceSafe), 5, 2)
        );
        deployer.rehearse(authorities, _safeIdentity());
    }

    function testRehearsalRejectsSharedAuthority() public {
        DeployVDSOCanary.Authorities memory authorities = _authorities(address(timelock));
        authorities.recoveryAuthority = address(guardian);
        vm.expectRevert(
            abi.encodeWithSelector(DeployVDSOCanary.SharedAuthority.selector, address(guardian), address(guardian))
        );
        deployer.rehearse(authorities, _safeIdentity());
    }

    function testRehearsalRejectsSafeInterfaceShapeImpersonator() public {
        ShapeOnlySafeFixture impersonator = new ShapeOnlySafeFixture(address(safeSingleton), 5, 3);
        DeployVDSOCanary.Authorities memory authorities = _authorities(address(timelock));
        authorities.governanceSafe = address(impersonator);

        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.SafeProxyRuntimeMismatch.selector,
                address(impersonator),
                address(impersonator).codehash,
                address(governanceSafe).codehash
            )
        );
        deployer.rehearse(authorities, _safeIdentity());
    }

    function testRehearsalRejectsUnexpectedSafeSingleton() public {
        KnownSafeSingletonFixture unexpectedSingleton = new KnownSafeSingletonFixture();
        KnownSafeProxyFixture unexpectedProxy = new KnownSafeProxyFixture(address(unexpectedSingleton), 5, 3, 0x4000);
        DeployVDSOCanary.Authorities memory authorities = _authorities(address(timelock));
        authorities.governanceSafe = address(unexpectedProxy);

        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityIdentityValidator.SafeSingletonMismatch.selector,
                address(unexpectedProxy),
                address(unexpectedSingleton),
                address(safeSingleton)
            )
        );
        deployer.rehearse(authorities, _safeIdentity());
    }

    function testRehearsalRejectsTimelockInterfaceShapeImpersonator() public {
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
        deployer.rehearse(_authorities(address(impersonator)), _safeIdentity());
    }

    function _authorities(address timelockAddress) private view returns (DeployVDSOCanary.Authorities memory) {
        return DeployVDSOCanary.Authorities({
            governanceSafe: address(governanceSafe),
            timelock: timelockAddress,
            pauseCouncil: address(pauseCouncil),
            guardian: address(guardian),
            recoveryAuthority: address(recoveryAuthority)
        });
    }

    function _safeIdentity() private view returns (AuthorityIdentityValidator.SafeIdentity memory) {
        return AuthorityIdentityValidator.SafeIdentity({
            proxyRuntimeCodeHash: address(governanceSafe).codehash,
            singleton: address(safeSingleton),
            singletonRuntimeCodeHash: address(safeSingleton).codehash
        });
    }
}
