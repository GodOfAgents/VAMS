// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "../interfaces/IPerformanceAnchor.sol";
import "../interfaces/ISLAEnforcer.sol";

/**
 * @title PerformanceAnchor
 * @notice Standalone on-chain registry anchoring multi-DA performance audit data.
 * @dev Maps (DAProtocol, blobId) → AnchorRecord for verifiable audit trails.
 *
 *      Design Decisions:
 *      - STANDALONE registry, NOT integrated into SLAEnforcer (separation of concerns).
 *      - Sentinel-only ACL via cross-reference to SLAEnforcer.isSentinel().
 *      - Supports all 6 DA protocols from the VAMS Foundation Layer.
 *      - Exposes verifyAnchor() for composability with SLAEnforcer and TrustAggregator.
 */
contract PerformanceAnchor is
    Initializable,
    AccessControlUpgradeable,
    ReentrancyGuardUpgradeable,
    IPerformanceAnchor
{
    // ============================================================
    //                        ROLES
    // ============================================================

    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    // ============================================================
    //                        STATE
    // ============================================================

    /// @notice Reference to the SLAEnforcer for Sentinel authorization checks.
    ISLAEnforcer public slaEnforcer;

    /// @notice Primary state: (protocol, blobId) → AnchorRecord
    mapping(DAProtocol => mapping(bytes32 => AnchorRecord)) private _anchors;

    /// @notice Statistics: total anchors committed
    uint256 private _totalAnchors;

    /// @notice Statistics: anchors per DA protocol
    mapping(DAProtocol => uint256) private _protocolCounts;

    /// @notice Statistics: anchors per provider
    mapping(address => uint256) public anchorsPerProvider;

    /// @dev Storage gap for future upgrades
    uint256[44] private __gap;

    // ============================================================
    //                     INITIALIZER
    // ============================================================

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    /// @notice Initialize the PerformanceAnchor contract.
    /// @param _admin Address with admin rights to upgrade and manage configuration.
    /// @param _slaEnforcer Address of the SLAEnforcer contract for Sentinel ACL.
    function initialize(
        address _admin,
        address _slaEnforcer
    ) public initializer {
        __AccessControl_init();
        __ReentrancyGuard_init();

        require(_admin != address(0), "Admin address zero");
        require(_slaEnforcer != address(0), "SLAEnforcer address zero");

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(ADMIN_ROLE, _admin);

        slaEnforcer = ISLAEnforcer(_slaEnforcer);
    }

    // ============================================================
    //                     MODIFIERS
    // ============================================================

    /// @dev Verifies msg.sender is a registered Sentinel in SLAEnforcer.
    modifier onlySentinel() {
        (bool success, bytes memory data) = address(slaEnforcer).staticcall(
            abi.encodeWithSignature("isSentinel(address)", msg.sender)
        );
        if (!success || data.length == 0) revert UnauthorizedSentinel();
        bool isRegistered = abi.decode(data, (bool));
        if (!isRegistered) revert UnauthorizedSentinel();
        _;
    }

    // ============================================================
    //                     CORE FUNCTIONS
    // ============================================================

    /// @inheritdoc IPerformanceAnchor
    function commit(
        DAProtocol protocol,
        bytes32 blobId,
        bytes32 reportHash,
        address provider
    ) external nonReentrant onlySentinel {
        // Validate inputs
        if (blobId == bytes32(0) || reportHash == bytes32(0)) revert InvalidParameters();
        if (provider == address(0)) revert InvalidParameters();

        // Check for duplicates
        if (_anchors[protocol][blobId].timestamp != 0) revert AnchorAlreadyExists();

        // Store anchor
        _anchors[protocol][blobId] = AnchorRecord({
            protocol: protocol,
            blobId: blobId,
            reportHash: reportHash,
            provider: provider,
            sentinel: msg.sender,
            timestamp: block.timestamp
        });

        // Update statistics
        _totalAnchors++;
        _protocolCounts[protocol]++;
        anchorsPerProvider[provider]++;

        emit PerformanceReportAnchored(
            protocol,
            blobId,
            reportHash,
            provider,
            msg.sender
        );
    }

    // ============================================================
    //                     VIEW FUNCTIONS
    // ============================================================

    /// @inheritdoc IPerformanceAnchor
    function getAnchor(
        DAProtocol protocol,
        bytes32 blobId
    ) external view returns (AnchorRecord memory record) {
        return _anchors[protocol][blobId];
    }

    /// @inheritdoc IPerformanceAnchor
    function verifyAnchor(
        DAProtocol protocol,
        bytes32 blobId,
        bytes32 reportHash
    ) external view returns (bool matches) {
        AnchorRecord storage record = _anchors[protocol][blobId];
        if (record.timestamp == 0) return false;
        return record.reportHash == reportHash;
    }

    /// @inheritdoc IPerformanceAnchor
    function totalAnchors() external view returns (uint256) {
        return _totalAnchors;
    }

    /// @inheritdoc IPerformanceAnchor
    function anchorsPerProtocol(DAProtocol protocol) external view returns (uint256) {
        return _protocolCounts[protocol];
    }

    // ============================================================
    //                     ADMIN FUNCTIONS
    // ============================================================

    /// @notice Update the SLAEnforcer reference (e.g., after upgrade).
    /// @param _newEnforcer The new SLAEnforcer address.
    function setSLAEnforcer(address _newEnforcer) external onlyRole(ADMIN_ROLE) {
        require(_newEnforcer != address(0), "SLAEnforcer address zero");
        slaEnforcer = ISLAEnforcer(_newEnforcer);
    }
}
