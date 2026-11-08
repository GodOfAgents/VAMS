// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Stateless, action-bound delivery verification boundary.
/// @dev Implementations must enforce authentic evidence and current policy.
interface IComposedDeliveryVerifier {
    struct ExpectedDelivery {
        bytes32 context;
        address provider;
        bytes32 workloadHash;
        uint256 amount;
        bytes32 nonce;
        uint256 issuedAt;
        uint256 expiresAt;
        bytes32 policyRoot;
        uint256 policyVersion;
        uint256 authorityEpoch;
        bytes32 intentId;
    }

    function challengePolicy(address provider, bytes32 workloadHash, uint256 amount)
        external view returns (bytes32 root, uint256 version, uint256 epoch);
    function authorizeEscrow(address initiator, address[] calldata providers,
        bytes32[] calldata workloadHashes, uint256 totalAmount, uint256 validity)
        external view returns (bool);

    function verifyDelivery(
        ExpectedDelivery calldata expected,
        bytes32 outputHash,
        bytes calldata proof
    ) external view returns (bool valid, bytes32 replayKey);
}
