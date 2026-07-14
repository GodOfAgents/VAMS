// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";

/// @title VAMSProgramRegistry
/// @notice Immutable-identity registry for deterministic VIR-Core programs.
contract VAMSProgramRegistry is VDSOCanaryAccess {
    bytes32 public constant REGISTRAR_ROLE = keccak256("VDSO_PROGRAM_REGISTRAR_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("VDSO_PROGRAM_GUARDIAN_ROLE");
    bytes public constant PROGRAM_DOMAIN = "VAMS:PROGRAM:v1";
    uint16 public constant SUPPORTED_VIR_VERSION = 1;
    bytes32 public constant VIR_V1_HOST_FUNCTION_SET_HASH =
        0x926aa059fa0db9477ba813b969d5c1dcf92fbcdbf7e00d6ceeec13ceef33e860;
    bytes32 public constant VIR_V1_GAS_SCHEDULE_HASH =
        0xea7983ef0e10911d248e354efebafd3b05a479e50ba5f0cfa46890f74034f773;
    bytes32 public constant VIR_V1_ARITHMETIC_POLICY_HASH =
        0xe6231804a0697191feee14abb9b5806f393a2725a10c0fc92f0159ee79c893a5;

    struct ProgramConfig {
        bytes32 bytecodeHash;
        bytes32 hostFunctionSetHash;
        bytes32 gasScheduleHash;
        bytes32 arithmeticPolicyHash;
        bytes32 verifierId;
        uint16 virVersion;
        bool active;
    }

    mapping(bytes32 programId => ProgramConfig config) private _programs;

    event ProgramRegistered(bytes32 indexed programId, bytes32 indexed verifierId, uint16 virVersion);
    event ProgramDeactivated(bytes32 indexed programId, bytes32 indexed reasonHash);

    error InvalidProgram();
    error ProgramAlreadyRegistered(bytes32 programId);
    error ProgramNotActive(bytes32 programId);
    error UnsupportedVIRVersion(uint16 supplied);
    error UnsupportedPolicyCommitment(bytes32 hostFunctionSet, bytes32 gasSchedule, bytes32 arithmeticPolicy);

    constructor(address admin, address pauser, address guardian) VDSOCanaryAccess(admin, pauser) {
        if (guardian == address(0)) revert InvalidAddress();
        _grantRole(REGISTRAR_ROLE, admin);
        _grantRole(GUARDIAN_ROLE, guardian);
    }

    function computeProgramId(
        uint16 virVersion,
        bytes32 bytecodeHash,
        bytes32 hostFunctionSetHash,
        bytes32 gasScheduleHash,
        bytes32 arithmeticPolicyHash
    ) public pure returns (bytes32) {
        // abi.encodePacked(uint16) is the two-byte big-endian wire encoding.
        return keccak256(
            abi.encodePacked(
                PROGRAM_DOMAIN, virVersion, bytecodeHash, hostFunctionSetHash, gasScheduleHash, arithmeticPolicyHash
            )
        );
    }

    function registerProgram(
        uint16 virVersion,
        bytes32 bytecodeHash,
        bytes32 hostFunctionSetHash,
        bytes32 gasScheduleHash,
        bytes32 arithmeticPolicyHash,
        bytes32 verifierId
    ) external onlyRole(REGISTRAR_ROLE) whenNotPaused returns (bytes32 programId) {
        if (bytecodeHash == bytes32(0) || verifierId == bytes32(0)) revert InvalidProgram();
        if (virVersion != SUPPORTED_VIR_VERSION) revert UnsupportedVIRVersion(virVersion);
        if (
            hostFunctionSetHash != VIR_V1_HOST_FUNCTION_SET_HASH || gasScheduleHash != VIR_V1_GAS_SCHEDULE_HASH
                || arithmeticPolicyHash != VIR_V1_ARITHMETIC_POLICY_HASH
        ) revert UnsupportedPolicyCommitment(hostFunctionSetHash, gasScheduleHash, arithmeticPolicyHash);

        programId =
            computeProgramId(virVersion, bytecodeHash, hostFunctionSetHash, gasScheduleHash, arithmeticPolicyHash);
        if (_programs[programId].virVersion != 0) revert ProgramAlreadyRegistered(programId);

        _programs[programId] = ProgramConfig({
            bytecodeHash: bytecodeHash,
            hostFunctionSetHash: hostFunctionSetHash,
            gasScheduleHash: gasScheduleHash,
            arithmeticPolicyHash: arithmeticPolicyHash,
            verifierId: verifierId,
            virVersion: virVersion,
            active: true
        });
        emit ProgramRegistered(programId, verifierId, virVersion);
    }

    function deactivateProgram(bytes32 programId, bytes32 reasonHash) external onlyRole(GUARDIAN_ROLE) {
        ProgramConfig storage config = _programs[programId];
        if (!config.active) revert ProgramNotActive(programId);
        if (reasonHash == bytes32(0)) revert InvalidProgram();
        config.active = false;
        emit ProgramDeactivated(programId, reasonHash);
    }

    function isProgramActive(bytes32 programId, bytes32 verifierId) external view returns (bool) {
        ProgramConfig memory config = _programs[programId];
        return !paused() && config.active && config.verifierId == verifierId;
    }

    function getProgram(bytes32 programId) external view returns (ProgramConfig memory) {
        return _programs[programId];
    }
}
