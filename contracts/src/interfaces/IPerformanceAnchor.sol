// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IPerformanceAnchor
 * @notice Interface for the VAMS multi-DA Performance Anchor registry.
 * @dev Standalone registry mapping (DAProtocol, blobId) → reportHash.
 *      Used by Sentinel nodes to anchor performance audit reports on-chain
 *      after publishing them to a DA layer (Celestia, Near, EigenDA, etc.).
 */
interface IPerformanceAnchor {
    // ============================================================
    //                    ENUMS & STRUCTS
    // ============================================================

    /// @notice Supported DA layer protocols matching the VAMS Foundation Layer.
    enum DAProtocol {
        CELESTIA, // DAS — Public Audit Trail
        EIGEN_DA, // Restaked ETH Security
        NEAR_DA, // High-Velocity Ephemeral
        POLYGON_DAC, // Primary L3 State (DAC)
        AVAIL, // KZG Backup
        IAGON // eUTXO Storage Sovereignty
    }

    /// @notice On-chain record linking a DA blob to a verified performance report.
    struct AnchorRecord {
        DAProtocol protocol;
        bytes32 blobId;
        bytes32 reportHash;
        address provider;
        address sentinel;
        uint256 timestamp;
    }

    // ============================================================
    //                       EVENTS
    // ============================================================

    /// @notice Emitted when a Sentinel anchors a performance report.
    event PerformanceReportAnchored(
        DAProtocol indexed protocol,
        bytes32 indexed blobId,
        bytes32 reportHash,
        address indexed provider,
        address sentinel
    );

    // ============================================================
    //                       ERRORS
    // ============================================================

    /// @notice Caller is not a registered Sentinel.
    error UnauthorizedSentinel();

    /// @notice The (protocol, blobId) pair has already been anchored.
    error AnchorAlreadyExists();

    /// @notice Invalid parameters (zero address, zero hash, etc.).
    error InvalidParameters();

    // ============================================================
    //                       FUNCTIONS
    // ============================================================

    /**
     * @notice Anchor a performance report on-chain.
     * @param protocol The DA layer the blob was submitted to.
     * @param blobId A unique identifier for the blob on the DA layer.
     * @param reportHash The SHA-256 hash of the performance report.
     * @param provider The address of the hardware provider being audited.
     */
    function commit(DAProtocol protocol, bytes32 blobId, bytes32 reportHash, address provider) external;

    /**
     * @notice Retrieve an anchor record.
     * @param protocol The DA layer.
     * @param blobId The blob identifier.
     * @return record The full anchor record.
     */
    function getAnchor(DAProtocol protocol, bytes32 blobId) external view returns (AnchorRecord memory record);

    /**
     * @notice Verify that an anchor record matches the given report hash.
     * @param protocol The DA layer.
     * @param blobId The blob identifier.
     * @param reportHash The expected report hash.
     * @return matches True if the anchor's reportHash matches.
     */
    function verifyAnchor(DAProtocol protocol, bytes32 blobId, bytes32 reportHash) external view returns (bool matches);

    /**
     * @notice Get total number of anchors committed.
     */
    function totalAnchors() external view returns (uint256);

    /**
     * @notice Get number of anchors for a specific DA protocol.
     */
    function anchorsPerProtocol(DAProtocol protocol) external view returns (uint256);
}
