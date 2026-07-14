// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VDSOCanaryAccess} from "./VDSOCanaryAccess.sol";
import {IVAMSProofVerifier} from "./interfaces/IVAMSProofVerifier.sol";

/// @title VAMSProofRouter
/// @notice Fail-closed proof routing with optional independent-verifier agreement.
contract VAMSProofRouter is VDSOCanaryAccess {
    bytes32 public constant CONFIG_ROLE = keccak256("VDSO_PROOF_CONFIG_ROLE");
    bytes32 public constant KERNEL_ROLE = keccak256("VDSO_PROOF_KERNEL_ROLE");

    struct VerifierSet {
        address primary;
        address secondary;
        bytes32 primaryCodeHash;
        bytes32 secondaryCodeHash;
        bool requireAgreement;
        bool active;
    }

    mapping(bytes32 verifierId => VerifierSet verifierSet) private _verifiers;
    mapping(bytes32 receiptId => bool consumed) public receiptUsed;

    event VerifierConfigured(
        bytes32 indexed verifierId, address indexed primary, address indexed secondary, bool requireAgreement
    );
    event VerifierDisabled(bytes32 indexed verifierId);
    event ProofAccepted(bytes32 indexed receiptId, bytes32 indexed verifierId, bytes32 indexed transitionHash);

    error InvalidVerifier();
    error UnsupportedVerifier(bytes32 verifierId);
    error InvalidProof(bytes32 verifierId);
    error ProofDisagreement(bytes32 verifierId);
    error ReceiptReplay(bytes32 receiptId);
    error VerifierAlreadyConfigured(bytes32 verifierId);
    error VerifierCodeChanged(bytes32 verifierId, address verifier, bytes32 expected, bytes32 actual);

    constructor(address admin, address pauser) VDSOCanaryAccess(admin, pauser) {
        _grantRole(CONFIG_ROLE, admin);
    }

    function configureVerifier(bytes32 verifierId, address primary, address secondary, bool requireAgreement)
        external
        onlyRole(CONFIG_ROLE)
        whenNotPaused
    {
        if (verifierId == bytes32(0) || primary.code.length == 0) revert InvalidVerifier();
        if (requireAgreement && (secondary.code.length == 0 || primary == secondary)) revert InvalidVerifier();
        if (!requireAgreement && secondary != address(0)) revert InvalidVerifier();
        if (_verifiers[verifierId].primary != address(0)) revert VerifierAlreadyConfigured(verifierId);

        _verifiers[verifierId] = VerifierSet({
            primary: primary,
            secondary: secondary,
            primaryCodeHash: primary.codehash,
            secondaryCodeHash: secondary.codehash,
            requireAgreement: requireAgreement,
            active: true
        });
        emit VerifierConfigured(verifierId, primary, secondary, requireAgreement);
    }

    function disableVerifier(bytes32 verifierId) external onlyRole(CONFIG_ROLE) {
        VerifierSet storage verifierSet = _verifiers[verifierId];
        if (!verifierSet.active) revert UnsupportedVerifier(verifierId);
        verifierSet.active = false;
        emit VerifierDisabled(verifierId);
    }

    function verifyAndRecord(
        bytes32 receiptId,
        bytes32 verifierId,
        bytes32 programId,
        bytes32 transitionHash,
        bytes calldata primaryProof,
        bytes calldata secondaryProof
    ) external onlyRole(KERNEL_ROLE) whenNotPaused returns (bool) {
        if (receiptId == bytes32(0) || receiptUsed[receiptId]) {
            revert ReceiptReplay(receiptId);
        }

        VerifierSet memory verifierSet = _verifiers[verifierId];
        if (!verifierSet.active) revert UnsupportedVerifier(verifierId);
        _requirePinnedCode(verifierId, verifierSet.primary, verifierSet.primaryCodeHash);
        if (verifierSet.requireAgreement) {
            _requirePinnedCode(verifierId, verifierSet.secondary, verifierSet.secondaryCodeHash);
        }

        bool primaryValid = _safeVerify(verifierSet.primary, programId, transitionHash, primaryProof);
        if (verifierSet.requireAgreement) {
            bool secondaryValid = _safeVerify(verifierSet.secondary, programId, transitionHash, secondaryProof);
            if (primaryValid != secondaryValid) revert ProofDisagreement(verifierId);
            if (!primaryValid) revert InvalidProof(verifierId);
        } else if (!primaryValid) {
            revert InvalidProof(verifierId);
        }

        receiptUsed[receiptId] = true;
        emit ProofAccepted(receiptId, verifierId, transitionHash);
        return true;
    }

    function getVerifier(bytes32 verifierId) external view returns (VerifierSet memory) {
        return _verifiers[verifierId];
    }

    function _safeVerify(address verifier, bytes32 programId, bytes32 transitionHash, bytes calldata proof)
        private
        view
        returns (bool)
    {
        try IVAMSProofVerifier(verifier).verify(programId, transitionHash, proof) returns (bool valid) {
            return valid;
        } catch {
            return false;
        }
    }

    function _requirePinnedCode(bytes32 verifierId, address verifier, bytes32 expectedCodeHash) private view {
        bytes32 actualCodeHash = verifier.codehash;
        if (actualCodeHash != expectedCodeHash) {
            revert VerifierCodeChanged(verifierId, verifier, expectedCodeHash, actualCodeHash);
        }
    }
}
