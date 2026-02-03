// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IOutageRecoveryManager
 * @author VAMS Protocol
 * @notice Interface for emergency fund release during chain outages
 * @dev Allows controlled fund recovery when main chain is halted
 */
interface IOutageRecoveryManager {
    // ============ Enums ============

    /// @notice System operational state
    enum SystemState {
        NORMAL,             // Normal operation
        OUTAGE_DECLARED,    // Outage declared, grace period active
        EMERGENCY_MODE,     // Emergency mode activated
        RECOVERED           // System recovered, emergency mode deactivated
    }

    /// @notice Withdrawal request status
    enum WithdrawalStatus {
        PENDING,    // Submitted, awaiting approval
        APPROVED,   // Approved for withdrawal
        PROCESSED,  // Withdrawal processed
        CANCELLED   // Request cancelled
    }

    // ============ Structs ============

    /// @notice Outage declaration details
    struct OutageRecord {
        uint256 declaredAt;         // When outage was declared
        uint256 emergencyStartAt;   // When emergency mode activated
        uint256 recoveredAt;        // When system recovered
        string reason;              // Outage reason
        SystemState state;          // Current state
        uint256 declaringGuardians; // Number of guardians who declared
    }

    /// @notice Emergency withdrawal request
    struct WithdrawalRequest {
        address requester;          // Who requested
        address token;              // Token to withdraw
        uint256 amount;             // Amount requested
        uint256 requestedAt;        // When requested
        uint256 processedAt;        // When processed
        WithdrawalStatus status;    // Current status
    }

    // ============ Events ============

    /// @notice Emitted when guardian declares outage
    event OutageDeclared(
        uint256 indexed outageId,
        address indexed guardian,
        string reason
    );

    /// @notice Emitted when emergency mode is activated
    event EmergencyModeActivated(uint256 indexed outageId, uint256 activatedAt);

    /// @notice Emitted when emergency withdrawal is requested
    event EmergencyWithdrawalRequested(
        uint256 indexed requestId,
        address indexed requester,
        address token,
        uint256 amount
    );

    /// @notice Emitted when withdrawal is processed
    event EmergencyWithdrawalProcessed(
        uint256 indexed requestId,
        address indexed requester,
        uint256 amount
    );

    /// @notice Emitted when system recovery is proven
    event RecoveryProven(uint256 indexed outageId, bytes proof);

    /// @notice Emitted when emergency mode is deactivated
    event EmergencyModeDeactivated(uint256 indexed outageId, uint256 deactivatedAt);

    // ============ Errors ============

    /// @notice Thrown when system not in expected state
    error InvalidSystemState(SystemState current, SystemState expected);

    /// @notice Thrown when grace period not elapsed
    error GracePeriodNotElapsed(uint256 remainingTime);

    /// @notice Thrown when already declared by guardian
    error AlreadyDeclared(address guardian);

    /// @notice Thrown when request not found
    error RequestNotFound(uint256 requestId);

    /// @notice Thrown when not requester
    error NotRequester(address caller, address requester);

    /// @notice Thrown when insufficient balance
    error InsufficientBalance(address token, uint256 requested, uint256 available);

    /// @notice Thrown when emergency duration expired
    error EmergencyDurationExpired();

    // ============ Outage Declaration ============

    /// @notice Guardian declares an outage
    /// @param reason Outage reason
    function declareOutage(string calldata reason) external;

    /// @notice Activate emergency mode after grace period
    function activateEmergencyMode() external;

    // ============ Emergency Withdrawals ============

    /// @notice Request emergency withdrawal
    /// @param token Token to withdraw
    /// @param amount Amount to withdraw
    /// @return requestId Request ID
    function requestEmergencyWithdraw(
        address token,
        uint256 amount
    ) external returns (uint256 requestId);

    /// @notice Process approved withdrawal
    /// @param requestId Request to process
    function processWithdrawal(uint256 requestId) external;

    /// @notice Cancel withdrawal request
    /// @param requestId Request to cancel
    function cancelWithdrawal(uint256 requestId) external;

    // ============ Recovery ============

    /// @notice Submit proof of system recovery
    /// @param proof Recovery proof (e.g., block hash from resumed chain)
    function proveRecovery(bytes calldata proof) external;

    /// @notice Deactivate emergency mode (guardian quorum)
    function deactivateEmergencyMode() external;

    // ============ View Functions ============

    /// @notice Get current system state
    /// @return state Current system state
    function getSystemState() external view returns (SystemState state);

    /// @notice Get active outage record
    /// @return record Active outage record
    function getActiveOutage() external view returns (OutageRecord memory record);

    /// @notice Get withdrawal request
    /// @param requestId Request ID
    /// @return request Withdrawal request
    function getWithdrawalRequest(uint256 requestId) external view returns (WithdrawalRequest memory request);

    /// @notice Get pending withdrawals for user
    /// @param user User address
    /// @return requestIds Array of request IDs
    function getPendingWithdrawals(address user) external view returns (uint256[] memory requestIds);

    /// @notice Check if guardian has declared outage
    /// @param guardian Guardian address
    /// @return declared Whether guardian has declared
    function hasGuardianDeclared(address guardian) external view returns (bool declared);

    /// @notice Get outage grace period
    /// @return period Grace period in seconds
    function getOutageGracePeriod() external view returns (uint256 period);

    /// @notice Get emergency duration
    /// @return duration Emergency duration in seconds
    function getEmergencyDuration() external view returns (uint256 duration);
}
