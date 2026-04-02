// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

/**
 * @title OutputHashProofPlugin
 * @notice Proof plugin for simple output hash commitment verification.
 * @dev Verifies that a provider's signed output hash matches the delivery hash.
 *      This is the lowest-trust proof type — no execution guarantee, only commitment.
 *      Useful as a baseline attestation for providers that don't support TEE or ZK.
 */
contract OutputHashProofPlugin is IVAMSProofPlugin {

    /// @notice Registered provider addresses
    mapping(address => bool) public registeredProviders;

    /// @notice Contract admin
    address public immutable admin;

    /// @notice Output hash proof structure
    struct OutputHashAttestation {
        bytes32 outputHash;   // Hash of the service output
        bytes signature;      // Provider's signature over (serviceHash, outputHash)
        address provider;     // Claimed provider address
    }

    event ProviderRegistered(address indexed provider);
    event ProviderRevoked(address indexed provider);

    modifier onlyAdmin() {
        require(msg.sender == admin, "OutputHashProofPlugin: not admin");
        _;
    }

    constructor(address _admin) {
        admin = _admin;
    }

    // ============================================================
    //                  IVAMSProofPlugin
    // ============================================================

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("OUTPUT_HASH"));
    }

    function verify(
        bytes32 serviceHash,
        bytes32 deliveryHash,
        bytes calldata proofData
    ) external view override returns (bool valid) {
        if (proofData.length == 0) return false;

        OutputHashAttestation memory attestation = abi.decode(proofData, (OutputHashAttestation));

        // 1. Verify the output hash matches the delivery hash
        if (attestation.outputHash != deliveryHash) return false;

        // 2. Verify the provider is registered
        if (!registeredProviders[attestation.provider]) return false;

        // 3. Verify the signature
        bytes32 messageHash = keccak256(
            abi.encodePacked(
                "\x19Ethereum Signed Message:\n64",
                serviceHash,
                attestation.outputHash
            )
        );

        address signer = _recoverSigner(messageHash, attestation.signature);
        if (signer != attestation.provider) return false;

        return true;
    }

    function trustWeight() external pure override returns (uint256) {
        return 1000; // 10% — lowest trust (no execution guarantee)
    }

    function name() external pure override returns (string memory) {
        return "Output Hash Commitment";
    }

    // ============================================================
    //                  INTERNAL
    // ============================================================

    function _recoverSigner(bytes32 hash, bytes memory sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }

        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);

        return ecrecover(hash, v, r, s);
    }

    // ============================================================
    //                  ADMIN FUNCTIONS
    // ============================================================

    function registerProvider(address provider) external onlyAdmin {
        registeredProviders[provider] = true;
        emit ProviderRegistered(provider);
    }

    function revokeProvider(address provider) external onlyAdmin {
        registeredProviders[provider] = false;
        emit ProviderRevoked(provider);
    }
}
