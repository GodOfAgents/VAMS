// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {VDSOTypes} from "../src/vdso/VDSOTypes.sol";
import {VAMSObjectStore} from "../src/vdso/VAMSObjectStore.sol";
import {VAMSReservationManager} from "../src/vdso/VAMSReservationManager.sol";
import {VAMSAdapterRegistry} from "../src/vdso/VAMSAdapterRegistry.sol";
import {VAMSProgramRegistry} from "../src/vdso/VAMSProgramRegistry.sol";
import {VAMSProofRouter} from "../src/vdso/VAMSProofRouter.sol";
import {VAMSCapabilityRouter} from "../src/vdso/VAMSCapabilityRouter.sol";
import {VAMSExecutionKernel} from "../src/vdso/VAMSExecutionKernel.sol";
import {AuthorityIdentityValidator} from "./utils/AuthorityIdentityValidator.sol";

interface IVDSOTimelockLike {
    function getMinDelay() external view returns (uint256);

    function hasRole(bytes32 role, address account) external view returns (bool);

    function PROPOSER_ROLE() external view returns (bytes32);

    function CANCELLER_ROLE() external view returns (bytes32);

    function EXECUTOR_ROLE() external view returns (bytes32);
}

interface IVDSOAccessLike {
    function DEFAULT_ADMIN_ROLE() external view returns (bytes32);

    function PAUSER_ROLE() external view returns (bytes32);

    function hasRole(bytes32 role, address account) external view returns (bool);

    function paused() external view returns (bool);

    function pause() external;

    function grantRole(bytes32 role, address account) external;

    function revokeRole(bytes32 role, address account) external;

    function renounceRole(bytes32 role, address account) external;
}

/// @title DeployVDSOCanary
/// @notice Fail-closed Polygon Amoy deployment rehearsal for empty VDSO canary modules.
/// @dev This script performs no adapter, verifier, program, or domain activation.
contract DeployVDSOCanary is Script, AuthorityIdentityValidator {
    uint256 public constant POLYGON_AMOY_CHAIN_ID = 80_002;
    uint256 public constant MINIMUM_TIMELOCK_DELAY = 48 hours;

    struct Authorities {
        address governanceSafe;
        address timelock;
        address pauseCouncil;
        address guardian;
        address recoveryAuthority;
    }

    error InvalidChain(uint256 actual, uint256 expected);
    error InvalidTimelock(address candidate, uint256 delay);
    error TimelockGovernanceMissing(address timelock, address governanceSafe);
    error TimelockExecutorMissing(address timelock, address governanceSafe);
    error SharedAuthority(address first, address second);
    error RoleInvariantFailed(address target, bytes32 role, address account, bool expected);
    error PauseInvariantFailed(address target, bool expected);
    error WiringInvariantFailed(address target, address expected);
    error CanaryNotEmpty(address target);

    VAMSObjectStore public objectStore;
    VAMSReservationManager public reservationManager;
    VAMSAdapterRegistry public adapterRegistry;
    VAMSProgramRegistry public programRegistry;
    VAMSProofRouter public proofRouter;
    VAMSCapabilityRouter public capabilityRouter;
    VAMSExecutionKernel public kernel;

    /// @notice Broadcast entrypoint. All authorities and the key must be supplied externally.
    function run() external {
        _requireAmoy();
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deploymentActor = vm.addr(deployerPrivateKey);
        Authorities memory authorities = Authorities({
            governanceSafe: vm.envAddress("VAMS_VDSO_GOVERNANCE_SAFE"),
            timelock: vm.envAddress("VAMS_VDSO_TIMELOCK"),
            pauseCouncil: vm.envAddress("VAMS_VDSO_PAUSE_COUNCIL"),
            guardian: vm.envAddress("VAMS_VDSO_GUARDIAN"),
            recoveryAuthority: vm.envAddress("VAMS_VDSO_RECOVERY_AUTHORITY")
        });
        SafeIdentity memory safeIdentity = SafeIdentity({
            proxyRuntimeCodeHash: vm.envBytes32("VAMS_VDSO_SAFE_PROXY_RUNTIME_CODE_HASH"),
            singleton: vm.envAddress("VAMS_VDSO_SAFE_SINGLETON"),
            singletonRuntimeCodeHash: vm.envBytes32("VAMS_VDSO_SAFE_SINGLETON_RUNTIME_CODE_HASH")
        });
        _validateAuthorities(authorities, safeIdentity);

        vm.startBroadcast(deployerPrivateKey);
        _deployAndConfigure(deploymentActor, authorities);
        vm.stopBroadcast();

        _verifyPostconditions(deploymentActor, authorities, safeIdentity);
        _logDeployment(authorities, safeIdentity);
    }

    /// @notice Local rehearsal path that never reads or uses a private key.
    /// @dev Unit tests call this on an Amoy-chain-id forkless EVM.
    function rehearse(Authorities calldata authorities, SafeIdentity calldata safeIdentity) external {
        _requireAmoy();
        _validateAuthorities(authorities, safeIdentity);
        _deployAndConfigure(address(this), authorities);
        _verifyPostconditions(address(this), authorities, safeIdentity);
    }

    function _deployAndConfigure(address deploymentActor, Authorities memory authorities) private {
        objectStore = new VAMSObjectStore(deploymentActor, authorities.pauseCouncil);
        reservationManager = new VAMSReservationManager(
            deploymentActor, authorities.pauseCouncil, authorities.recoveryAuthority, address(0)
        );
        adapterRegistry = new VAMSAdapterRegistry(deploymentActor, authorities.pauseCouncil, authorities.guardian);
        programRegistry = new VAMSProgramRegistry(deploymentActor, authorities.pauseCouncil, authorities.guardian);
        proofRouter = new VAMSProofRouter(deploymentActor, authorities.pauseCouncil);
        capabilityRouter = new VAMSCapabilityRouter(deploymentActor, authorities.pauseCouncil, address(adapterRegistry));
        kernel = new VAMSExecutionKernel(
            deploymentActor,
            authorities.pauseCouncil,
            address(objectStore),
            address(reservationManager),
            address(adapterRegistry),
            address(programRegistry),
            address(proofRouter),
            address(capabilityRouter)
        );

        // Every module starts fail-closed. The deployer receives pause
        // authority only long enough to perform this setup step; the role is
        // then removed, leaving the distinct 2-of-3 council as the sole
        // configured emergency-stop authority on all seven modules.
        address[7] memory modules = _modules();
        for (uint256 i = 0; i < modules.length; ++i) {
            _pauseAndRemoveDeployer(modules[i], deploymentActor);
        }

        objectStore.grantRole(objectStore.KERNEL_ROLE(), address(kernel));
        reservationManager.grantRole(reservationManager.KERNEL_ROLE(), address(kernel));
        proofRouter.grantRole(proofRouter.KERNEL_ROLE(), address(kernel));

        objectStore.grantRole(objectStore.AUTHORITY_ADMIN_ROLE(), authorities.timelock);
        adapterRegistry.grantRole(adapterRegistry.REGISTRAR_ROLE(), authorities.timelock);
        programRegistry.grantRole(programRegistry.REGISTRAR_ROLE(), authorities.timelock);
        proofRouter.grantRole(proofRouter.CONFIG_ROLE(), authorities.timelock);
        kernel.grantRole(kernel.EXECUTOR_ROLE(), authorities.timelock);

        objectStore.revokeRole(objectStore.AUTHORITY_ADMIN_ROLE(), deploymentActor);
        adapterRegistry.revokeRole(adapterRegistry.REGISTRAR_ROLE(), deploymentActor);
        programRegistry.revokeRole(programRegistry.REGISTRAR_ROLE(), deploymentActor);
        proofRouter.revokeRole(proofRouter.CONFIG_ROLE(), deploymentActor);
        kernel.revokeRole(kernel.EXECUTOR_ROLE(), deploymentActor);

        _handoffDefaultAdmin(address(objectStore), deploymentActor, authorities.timelock);
        _handoffDefaultAdmin(address(reservationManager), deploymentActor, authorities.timelock);
        _handoffDefaultAdmin(address(adapterRegistry), deploymentActor, authorities.timelock);
        _handoffDefaultAdmin(address(programRegistry), deploymentActor, authorities.timelock);
        _handoffDefaultAdmin(address(proofRouter), deploymentActor, authorities.timelock);
        _handoffDefaultAdmin(address(capabilityRouter), deploymentActor, authorities.timelock);
        _handoffDefaultAdmin(address(kernel), deploymentActor, authorities.timelock);
    }

    function _handoffDefaultAdmin(address target, address deploymentActor, address timelock) private {
        bytes32 adminRole = IVDSOAccessLike(target).DEFAULT_ADMIN_ROLE();
        IVDSOAccessLike(target).grantRole(adminRole, timelock);
        IVDSOAccessLike(target).renounceRole(adminRole, deploymentActor);
    }

    function _pauseAndRemoveDeployer(address target, address deploymentActor) private {
        bytes32 pauserRole = IVDSOAccessLike(target).PAUSER_ROLE();
        IVDSOAccessLike(target).grantRole(pauserRole, deploymentActor);
        IVDSOAccessLike(target).pause();
        IVDSOAccessLike(target).revokeRole(pauserRole, deploymentActor);
    }

    function _modules() private view returns (address[7] memory modules) {
        modules = [
            address(objectStore),
            address(reservationManager),
            address(adapterRegistry),
            address(programRegistry),
            address(proofRouter),
            address(capabilityRouter),
            address(kernel)
        ];
    }

    function _validateAuthorities(Authorities memory authorities, SafeIdentity memory safeIdentity) private view {
        _requireSafe(authorities.governanceSafe, 5, 3, safeIdentity);
        _requireSafe(authorities.pauseCouncil, 3, 2, safeIdentity);
        _requireSafe(authorities.guardian, 3, 2, safeIdentity);
        _requireSafe(authorities.recoveryAuthority, 3, 2, safeIdentity);
        _requireTimelock(authorities.timelock, authorities.governanceSafe);

        address[5] memory allAuthorities = [
            authorities.governanceSafe,
            authorities.timelock,
            authorities.pauseCouncil,
            authorities.guardian,
            authorities.recoveryAuthority
        ];
        for (uint256 i = 0; i < allAuthorities.length; ++i) {
            for (uint256 j = i + 1; j < allAuthorities.length; ++j) {
                if (allAuthorities[i] == allAuthorities[j]) {
                    revert SharedAuthority(allAuthorities[i], allAuthorities[j]);
                }
            }
        }
    }

    function _requireTimelock(address candidate, address governanceSafe) private view {
        _requireKnownVAMSTimelockRuntime(candidate);
        uint256 delay;
        try IVDSOTimelockLike(candidate).getMinDelay() returns (uint256 configuredDelay) {
            delay = configuredDelay;
        } catch {
            revert InvalidTimelock(candidate, 0);
        }
        if (delay < MINIMUM_TIMELOCK_DELAY) revert InvalidTimelock(candidate, delay);

        bytes32 proposerRole;
        bytes32 cancellerRole;
        bytes32 executorRole;
        try IVDSOTimelockLike(candidate).PROPOSER_ROLE() returns (bytes32 role) {
            proposerRole = role;
        } catch {
            revert TimelockGovernanceMissing(candidate, governanceSafe);
        }
        try IVDSOTimelockLike(candidate).CANCELLER_ROLE() returns (bytes32 role) {
            cancellerRole = role;
        } catch {
            revert TimelockGovernanceMissing(candidate, governanceSafe);
        }
        try IVDSOTimelockLike(candidate).EXECUTOR_ROLE() returns (bytes32 role) {
            executorRole = role;
        } catch {
            revert TimelockExecutorMissing(candidate, governanceSafe);
        }
        if (
            !IVDSOTimelockLike(candidate).hasRole(proposerRole, governanceSafe)
                || !IVDSOTimelockLike(candidate).hasRole(cancellerRole, governanceSafe)
        ) revert TimelockGovernanceMissing(candidate, governanceSafe);
        if (
            !IVDSOTimelockLike(candidate).hasRole(executorRole, governanceSafe)
                && !IVDSOTimelockLike(candidate).hasRole(executorRole, address(0))
        ) revert TimelockExecutorMissing(candidate, governanceSafe);
    }

    function _verifyPostconditions(
        address deploymentActor,
        Authorities memory authorities,
        SafeIdentity memory safeIdentity
    ) private view {
        _validateAuthorities(authorities, safeIdentity);
        address[7] memory modules = _modules();
        for (uint256 i = 0; i < modules.length; ++i) {
            _requireRole(modules[i], bytes32(0), authorities.timelock, true);
            _requireRole(modules[i], bytes32(0), deploymentActor, false);
            _requireRole(modules[i], IVDSOAccessLike(modules[i]).PAUSER_ROLE(), authorities.pauseCouncil, true);
            _requireRole(modules[i], IVDSOAccessLike(modules[i]).PAUSER_ROLE(), deploymentActor, false);
            _requireRole(modules[i], IVDSOAccessLike(modules[i]).PAUSER_ROLE(), authorities.timelock, false);
            _requireRole(modules[i], IVDSOAccessLike(modules[i]).PAUSER_ROLE(), authorities.governanceSafe, false);
            _requireRole(modules[i], IVDSOAccessLike(modules[i]).PAUSER_ROLE(), authorities.guardian, false);
            _requireRole(modules[i], IVDSOAccessLike(modules[i]).PAUSER_ROLE(), authorities.recoveryAuthority, false);
            _requireRole(modules[i], bytes32(0), authorities.pauseCouncil, false);
            _requireRole(modules[i], bytes32(0), authorities.governanceSafe, false);
            _requireRole(modules[i], bytes32(0), authorities.guardian, false);
            _requireRole(modules[i], bytes32(0), authorities.recoveryAuthority, false);
            _requirePaused(modules[i], true);
        }

        _requireRole(address(objectStore), objectStore.KERNEL_ROLE(), address(kernel), true);
        _requireRole(address(objectStore), objectStore.AUTHORITY_ADMIN_ROLE(), authorities.timelock, true);
        _requireRole(address(reservationManager), reservationManager.KERNEL_ROLE(), address(kernel), true);
        _requireRole(
            address(reservationManager), reservationManager.RECOVERY_ROLE(), authorities.recoveryAuthority, true
        );
        _requireRole(address(proofRouter), proofRouter.KERNEL_ROLE(), address(kernel), true);
        _requireRole(address(proofRouter), proofRouter.CONFIG_ROLE(), authorities.timelock, true);
        _requireRole(address(adapterRegistry), adapterRegistry.REGISTRAR_ROLE(), authorities.timelock, true);
        _requireRole(address(adapterRegistry), adapterRegistry.GUARDIAN_ROLE(), authorities.guardian, true);
        _requireRole(address(programRegistry), programRegistry.REGISTRAR_ROLE(), authorities.timelock, true);
        _requireRole(address(programRegistry), programRegistry.GUARDIAN_ROLE(), authorities.guardian, true);
        _requireRole(address(kernel), kernel.EXECUTOR_ROLE(), authorities.timelock, true);
        if (address(reservationManager.recoveryVerifier()) != address(0)) {
            revert WiringInvariantFailed(address(reservationManager.recoveryVerifier()), address(0));
        }

        _requireRole(address(objectStore), objectStore.AUTHORITY_ADMIN_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(objectStore), objectStore.KERNEL_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(reservationManager), reservationManager.KERNEL_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(reservationManager), reservationManager.RECOVERY_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(adapterRegistry), adapterRegistry.REGISTRAR_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(adapterRegistry), adapterRegistry.GUARDIAN_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(programRegistry), programRegistry.REGISTRAR_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(programRegistry), programRegistry.GUARDIAN_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(proofRouter), proofRouter.CONFIG_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(proofRouter), proofRouter.KERNEL_ROLE(), authorities.pauseCouncil, false);
        _requireRole(address(kernel), kernel.EXECUTOR_ROLE(), authorities.pauseCouncil, false);

        _requireRole(address(objectStore), objectStore.AUTHORITY_ADMIN_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(reservationManager), reservationManager.RECOVERY_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(adapterRegistry), adapterRegistry.REGISTRAR_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(adapterRegistry), adapterRegistry.GUARDIAN_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(programRegistry), programRegistry.REGISTRAR_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(programRegistry), programRegistry.GUARDIAN_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(proofRouter), proofRouter.CONFIG_ROLE(), authorities.governanceSafe, false);
        _requireRole(address(kernel), kernel.EXECUTOR_ROLE(), authorities.governanceSafe, false);

        _requireRole(address(objectStore), objectStore.AUTHORITY_ADMIN_ROLE(), authorities.guardian, false);
        _requireRole(address(reservationManager), reservationManager.RECOVERY_ROLE(), authorities.guardian, false);
        _requireRole(address(adapterRegistry), adapterRegistry.REGISTRAR_ROLE(), authorities.guardian, false);
        _requireRole(address(programRegistry), programRegistry.REGISTRAR_ROLE(), authorities.guardian, false);
        _requireRole(address(proofRouter), proofRouter.CONFIG_ROLE(), authorities.guardian, false);
        _requireRole(address(kernel), kernel.EXECUTOR_ROLE(), authorities.guardian, false);

        _requireRole(address(objectStore), objectStore.AUTHORITY_ADMIN_ROLE(), authorities.recoveryAuthority, false);
        _requireRole(address(adapterRegistry), adapterRegistry.REGISTRAR_ROLE(), authorities.recoveryAuthority, false);
        _requireRole(address(adapterRegistry), adapterRegistry.GUARDIAN_ROLE(), authorities.recoveryAuthority, false);
        _requireRole(address(programRegistry), programRegistry.REGISTRAR_ROLE(), authorities.recoveryAuthority, false);
        _requireRole(address(programRegistry), programRegistry.GUARDIAN_ROLE(), authorities.recoveryAuthority, false);
        _requireRole(address(proofRouter), proofRouter.CONFIG_ROLE(), authorities.recoveryAuthority, false);
        _requireRole(address(kernel), kernel.EXECUTOR_ROLE(), authorities.recoveryAuthority, false);

        _requireRole(address(objectStore), objectStore.AUTHORITY_ADMIN_ROLE(), deploymentActor, false);
        _requireRole(address(adapterRegistry), adapterRegistry.REGISTRAR_ROLE(), deploymentActor, false);
        _requireRole(address(programRegistry), programRegistry.REGISTRAR_ROLE(), deploymentActor, false);
        _requireRole(address(proofRouter), proofRouter.CONFIG_ROLE(), deploymentActor, false);
        _requireRole(address(kernel), kernel.EXECUTOR_ROLE(), deploymentActor, false);

        if (address(capabilityRouter.adapterRegistry()) != address(adapterRegistry)) {
            revert WiringInvariantFailed(address(capabilityRouter.adapterRegistry()), address(adapterRegistry));
        }
        if (
            address(kernel.objectStore()) != address(objectStore)
                || address(kernel.reservationManager()) != address(reservationManager)
                || address(kernel.adapterRegistry()) != address(adapterRegistry)
                || address(kernel.programRegistry()) != address(programRegistry)
                || address(kernel.proofRouter()) != address(proofRouter)
                || address(kernel.capabilityRouter()) != address(capabilityRouter)
        ) revert WiringInvariantFailed(address(kernel), address(0));

        _requireEmptyAndInactive();
    }

    function _requireEmptyAndInactive() private view {
        bytes32 sentinel = keccak256("VDSO_CANARY_EMPTY_SENTINEL");

        VAMSObjectStore.DomainAuthority memory authority = objectStore.getDomainAuthority(sentinel);
        VAMSObjectStore.ObjectHeader memory objectHeader = objectStore.getObject(sentinel);
        if (
            authority.host != VDSOTypes.Host.NONE || authority.writer != address(0) || authority.epoch != 0
                || authority.enabled || objectHeader.domainId != bytes32(0) || objectHeader.stateRoot != bytes32(0)
                || objectHeader.evidenceRoot != bytes32(0) || objectHeader.version != 0 || objectHeader.updatedAt != 0
        ) revert CanaryNotEmpty(address(objectStore));

        VAMSReservationManager.Reservation memory reservation = reservationManager.getReservation(sentinel);
        if (
            reservation.objectId != bytes32(0) || reservation.holder != address(0)
                || reservation.status != VDSOTypes.ReservationStatus.NONE
                || reservationManager.activeReservation(sentinel) != bytes32(0)
                || reservationManager.lastFencingToken(sentinel) != 0 || reservationManager.reservationIdUsed(sentinel)
                || address(reservationManager.recoveryVerifier()) != address(0)
        ) revert CanaryNotEmpty(address(reservationManager));

        VAMSAdapterRegistry.AdapterConfig memory adapter = adapterRegistry.getAdapter(sentinel);
        if (
            adapter.adapter != address(0) || adapter.status != VDSOTypes.AdapterStatus.NONE || adapter.version != 0
                || adapter.capabilityMask != 0
        ) revert CanaryNotEmpty(address(adapterRegistry));

        VAMSProgramRegistry.ProgramConfig memory program = programRegistry.getProgram(sentinel);
        if (program.active || program.bytecodeHash != bytes32(0) || program.verifierId != bytes32(0)) {
            revert CanaryNotEmpty(address(programRegistry));
        }

        VAMSProofRouter.VerifierSet memory verifier = proofRouter.getVerifier(sentinel);
        if (
            verifier.active || verifier.primary != address(0) || verifier.secondary != address(0)
                || proofRouter.receiptUsed(sentinel)
        ) revert CanaryNotEmpty(address(proofRouter));

        // The capability router has no mutable activation registry of its own;
        // its only route source is the empty adapter registry checked above.
        if (address(capabilityRouter.adapterRegistry()) != address(adapterRegistry)) {
            revert CanaryNotEmpty(address(capabilityRouter));
        }

        if (kernel.executionUsed(sentinel) || kernel.executionAdapter(sentinel) != bytes32(0)) {
            revert CanaryNotEmpty(address(kernel));
        }
    }

    function _requireRole(address target, bytes32 role, address account, bool expected) private view {
        bool actual = IVDSOAccessLike(target).hasRole(role, account);
        if (actual != expected) revert RoleInvariantFailed(target, role, account, expected);
    }

    function _requirePaused(address target, bool expected) private view {
        bool actual = IVDSOAccessLike(target).paused();
        if (actual != expected) revert PauseInvariantFailed(target, expected);
    }

    function _requireAmoy() private view {
        if (block.chainid != POLYGON_AMOY_CHAIN_ID) {
            revert InvalidChain(block.chainid, POLYGON_AMOY_CHAIN_ID);
        }
    }

    function _logDeployment(Authorities memory authorities, SafeIdentity memory safeIdentity) private view {
        console.log("VDSO Polygon Amoy canary rehearsal complete");
        console.log("Object store:", address(objectStore));
        console.log("Reservation manager:", address(reservationManager));
        console.log("Adapter registry:", address(adapterRegistry));
        console.log("Program registry:", address(programRegistry));
        console.log("Proof router:", address(proofRouter));
        console.log("Capability router:", address(capabilityRouter));
        console.log("Execution kernel:", address(kernel));
        console.log("Governance Safe:", authorities.governanceSafe);
        console.log("Existing timelock:", authorities.timelock);
        console.log("Pause council:", authorities.pauseCouncil);
        console.log("Guardian:", authorities.guardian);
        console.log("Recovery authority:", authorities.recoveryAuthority);
        console.log("Safe Singleton:", safeIdentity.singleton);
        console.log("Safe proxy runtime code hash:");
        console.logBytes32(safeIdentity.proxyRuntimeCodeHash);
        console.log("Safe singleton runtime code hash:");
        console.logBytes32(safeIdentity.singletonRuntimeCodeHash);
        console.log("Timelock runtime code hash:");
        console.logBytes32(authorities.timelock.codehash);
    }
}
