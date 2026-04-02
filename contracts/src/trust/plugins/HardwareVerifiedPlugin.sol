// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../../interfaces/IVAMSProofPlugin.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @title HardwareVerifiedPlugin
 * @notice Plugs into VAMSTrustAggregator. Evaluates signatures from the Sentinel Network
 *         to attach hardware verification weight to an agent's trust score.
 */
contract HardwareVerifiedPlugin is IVAMSProofPlugin {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    address public immutable slaEnforcer;
    uint256 public immutable weightBps;
    uint256 public constant MIN_SCORE_THRESHOLD = 7500; // 75% SLA

    constructor(address _slaEnforcer, uint256 _weightBps) {
        require(_slaEnforcer != address(0), "Enforcer address zero");
        slaEnforcer = _slaEnforcer;
        weightBps = _weightBps;
    }

    function proofType() external pure returns (bytes32) {
        return keccak256("HARDWARE_VERIFIED");
    }

    /**
     * @notice Verify hardware health proof
     * @param proofData Encoded (bytes32 nodeId, uint256 currentScore, bytes signature)
     */
    function verify(
        bytes32, /* serviceHash */
        bytes32, /* deliveryHash */
        bytes calldata proofData
    ) external view returns (bool) {
        if (proofData.length == 0) return false;

        (bytes32 nodeId, uint256 currentScore, bytes memory sig) = abi.decode(proofData, (bytes32, uint256, bytes));

        // If the node is struggling, we instantly reject its proof weight
        if (currentScore < MIN_SCORE_THRESHOLD) {
            return false;
        }

        bytes32 digest = keccak256(abi.encode(nodeId, currentScore)).toEthSignedMessageHash();
        address signer = digest.recover(sig);

        // Check if the signer is a registered Sentinel in the SLAEnforcer
        (bool success, bytes memory data) = slaEnforcer.staticcall(
            abi.encodeWithSignature("isSentinel(address)", signer)
        );
        
        if (success && data.length > 0) {
            bool isRegistered = abi.decode(data, (bool));
            return isRegistered;
        }

        return false;
    }

    function trustWeight() external view returns (uint256) {
        return weightBps;
    }

    function name() external pure returns (string memory) {
        return "Sentinel Hardware Verification";
    }
}
