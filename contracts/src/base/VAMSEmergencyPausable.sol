// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title VAMSEmergencyPausable
 * @author VAMS Protocol
 * @notice Emergency pause mechanism that bypasses timelock for critical security
 * @dev 
 * - VAMSSentinel (Primary): Autonomous on-chain anomaly detector, sub-second pause
 * - Guardian Committee (Fallback): Dormant multi-sig, only if Sentinel is compromised
 * - DAO: Must approve resume after any emergency pause
 */
abstract contract VAMSEmergencyPausable is 
    Initializable, 
    PausableUpgradeable, 
    AccessControlUpgradeable 
{
    /// @notice Role for VAMSSentinel autonomous anomaly detector (primary guardian)
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");

    /// @notice Role for Guardian Committee members (dormant fallback)
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    
    /// @notice Role for pause/unpause authority (DAO via ICB relay)
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    
    /// @notice Default emergency pause duration (48 hours)
    uint256 public constant EMERGENCY_PAUSE_DURATION = 48 hours;
    
    /// @notice Maximum pause extension per call (7 days)
    uint256 public constant MAX_PAUSE_EXTENSION = 7 days;
    
    /// @notice Timestamp when current pause expires (0 if not paused)
    uint256 public pauseExpiresAt;
    
    /// @notice Address that initiated the current pause
    address public pauseInitiator;
    
    /// @notice Reason for the current pause
    string public pauseReason;
    
    /// @notice Number of times pause has been extended
    uint256 public pauseExtensionCount;
    
    // ============ Events ============
    
    event EmergencyPauseActivated(
        address indexed guardian, 
        uint256 expiresAt, 
        string reason
    );
    event EmergencyPauseExtended(
        address indexed authority, 
        uint256 newExpiry, 
        uint256 extensionCount
    );
    event EmergencyPauseLifted(address indexed authority);
    event AutoUnpauseTriggered(uint256 timestamp);
    
    // ============ Errors ============
    
    error NotPaused();
    error AlreadyPaused();
    error PauseNotExpired(uint256 expiresAt);
    error ExtensionTooLong(uint256 requested, uint256 maximum);
    error ContractPaused();
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the pausable contract
     * @param _admin Initial admin address
     * @param _guardians Array of guardian addresses (should be 3)
     */
    function __VAMSEmergencyPausable_init(
        address _admin,
        address[] memory _guardians
    ) internal onlyInitializing {
        __Pausable_init();
        __AccessControl_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(PAUSER_ROLE, _admin);
        
        for (uint256 i = 0; i < _guardians.length; i++) {
            _grantRole(GUARDIAN_ROLE, _guardians[i]);
        }
    }
    
    // ============ Emergency Pause Functions ============
    
    /**
     * @notice Activate emergency pause (Sentinel, Guardian fallback, or Pauser)
     * @param _reason Reason for the pause
     * @dev Auto-expires after EMERGENCY_PAUSE_DURATION (48h)
     */
    function emergencyPause(string calldata _reason) external {
        if (paused()) revert AlreadyPaused();
        
        // Sentinel (primary), Guardian (fallback), or Pauser can initiate
        require(
            hasRole(SENTINEL_ROLE, msg.sender) ||
            hasRole(GUARDIAN_ROLE, msg.sender) ||
            hasRole(PAUSER_ROLE, msg.sender),
            "Not authorized to pause"
        );
        
        _pause();
        pauseExpiresAt = block.timestamp + EMERGENCY_PAUSE_DURATION;
        pauseInitiator = msg.sender;
        pauseReason = _reason;
        pauseExtensionCount = 0;
        
        emit EmergencyPauseActivated(msg.sender, pauseExpiresAt, _reason);
    }
    
    /**
     * @notice Extend the current pause (Pauser only)
     * @param _additionalSeconds Additional time to add (max 7 days)
     */
    function extendPause(uint256 _additionalSeconds) external onlyRole(PAUSER_ROLE) {
        if (!paused()) revert NotPaused();
        if (_additionalSeconds > MAX_PAUSE_EXTENSION) {
            revert ExtensionTooLong(_additionalSeconds, MAX_PAUSE_EXTENSION);
        }
        
        pauseExpiresAt += _additionalSeconds;
        pauseExtensionCount++;
        
        emit EmergencyPauseExtended(msg.sender, pauseExpiresAt, pauseExtensionCount);
    }
    
    /**
     * @notice Lift the pause manually (Pauser only)
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        if (!paused()) revert NotPaused();
        
        _unpause();
        _resetPauseState();
        
        emit EmergencyPauseLifted(msg.sender);
    }
    
    /**
     * @notice Auto-unpause after expiry (anyone can call)
     * @dev Allows permissionless unpause once timeout reached
     */
    function checkAndUnpause() external {
        if (!paused()) revert NotPaused();
        if (block.timestamp < pauseExpiresAt) {
            revert PauseNotExpired(pauseExpiresAt);
        }
        
        _unpause();
        _resetPauseState();
        
        emit AutoUnpauseTriggered(block.timestamp);
    }
    
    // ============ Internal Functions ============
    
    /**
     * @notice Reset pause state variables
     */
    function _resetPauseState() internal {
        pauseExpiresAt = 0;
        pauseInitiator = address(0);
        pauseReason = "";
        pauseExtensionCount = 0;
    }
    
    // ============ Modifiers ============
    
    /**
     * @notice Check pause with auto-expiry handling
     * @dev Automatically unpause if expired
     */
    modifier whenNotPausedOrExpired() {
        if (paused()) {
            if (block.timestamp >= pauseExpiresAt) {
                _unpause();
                _resetPauseState();
                emit AutoUnpauseTriggered(block.timestamp);
            } else {
                revert ContractPaused();
            }
        }
        _;
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Get time remaining until pause expires
     * @return uint256 Seconds remaining (0 if not paused or expired)
     */
    function pauseTimeRemaining() external view returns (uint256) {
        if (!paused() || block.timestamp >= pauseExpiresAt) {
            return 0;
        }
        return pauseExpiresAt - block.timestamp;
    }
    
    /**
     * @notice Get full pause status
     * @return isPaused Whether contract is paused
     * @return expiresAt Pause expiry timestamp
     * @return initiator Who initiated the pause
     * @return reason Reason for pause
     * @return extensions Number of extensions
     */
    function getPauseStatus() external view returns (
        bool isPaused,
        uint256 expiresAt,
        address initiator,
        string memory reason,
        uint256 extensions
    ) {
        return (
            paused(),
            pauseExpiresAt,
            pauseInitiator,
            pauseReason,
            pauseExtensionCount
        );
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
