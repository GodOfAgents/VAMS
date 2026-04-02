// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IProviderBondRegistry
 * @author VAMS Protocol
 * @notice Interface for provider bonding and accountability
 * @dev Providers must bond $VAMS to guarantee settlement and accept requests
 * 
 * Architecture Reference: ARCHITECTURE_v0-3-0.md §20.2.3
 * 
 * Bond Requirements:
 * - Minimum bond: 10,000 $VAMS
 * - Coverage ratio: Bond must cover 10x max single request value
 * - Pending settlements cannot exceed bond amount
 * 
 * Slashing Conditions:
 * - Non-delivery of service after escrow lock
 * - Service quality disputes (proven via evidence)
 * - Settlement failures attributable to provider
 */
interface IProviderBondRegistry {
    // ============ Structs ============
    
    /**
     * @notice Provider bond information
     * @param bondedAmount Total bonded $VAMS
     * @param maxRequestValue Maximum single request value provider can accept
     * @param pendingSettlements Sum of in-flight request values
     * @param activeRequests Count of active requests
     * @param registeredAt Registration timestamp
     * @param totalEarned Lifetime earnings
     * @param totalSlashed Lifetime slashed amount
     * @param isActive Whether provider is accepting requests
     * @param withdrawalUnlockTime Time when withdrawal is unlocked (0 if none pending)
     * @param pendingWithdrawal Amount pending withdrawal
     */
    struct ProviderBond {
        uint256 bondedAmount;
        uint256 maxRequestValue;
        uint256 pendingSettlements;
        uint256 activeRequests;
        uint256 registeredAt;
        uint256 totalEarned;
        uint256 totalSlashed;
        bool isActive;
        uint256 withdrawalUnlockTime;
        uint256 pendingWithdrawal;
        uint256 hardwareCollateralLocked; // Append for Sprint 4 collateralization
    }
    
    /**
     * @notice Active request tracking
     * @param value Request value
     * @param startedAt When request was accepted
     * @param provider Provider handling the request
     */
    struct ActiveRequest {
        uint256 value;
        uint256 startedAt;
        address provider;
    }
    
    // ============ Events ============
    
    event ProviderRegistered(
        address indexed provider, 
        uint256 bondAmount, 
        uint256 maxRequestValue
    );
    event BondIncreased(
        address indexed provider, 
        uint256 additionalAmount, 
        uint256 newTotal
    );
    event WithdrawalRequested(
        address indexed provider,
        uint256 amount,
        uint256 unlockTime
    );
    event WithdrawalExecuted(
        address indexed provider,
        uint256 amount
    );
    event WithdrawalCancelled(address indexed provider);
    event ProviderSlashed(
        address indexed provider, 
        uint256 amount, 
        bytes32 indexed escrowId, 
        string reason
    );
    event ProviderCompensated(
        address indexed provider, 
        uint256 amount, 
        bytes32 indexed escrowId
    );
    event ProviderDeactivated(address indexed provider, string reason);
    event ProviderReactivated(address indexed provider);
    event RequestAccepted(
        address indexed provider, 
        bytes32 indexed escrowId, 
        uint256 value
    );
    event RequestCompleted(
        address indexed provider, 
        bytes32 indexed escrowId
    );
    event MaxRequestValueUpdated(
        address indexed provider,
        uint256 oldValue,
        uint256 newValue
    );
    
    // ============ Errors ============
    
    /// @notice Bond amount is below minimum
    error BondTooLow(uint256 provided, uint256 minimum);
    
    /// @notice Coverage ratio not met (bond < maxRequest * ratio)
    error CoverageRatioNotMet(uint256 bond, uint256 maxRequest, uint256 requiredRatio);
    
    /// @notice Provider is not active
    error ProviderNotActive(address provider);
    
    /// @notice Provider not found in registry
    error ProviderNotFound(address provider);
    
    /// @notice Request value exceeds provider's max
    error RequestValueTooHigh(uint256 requested, uint256 maximum);
    
    /// @notice Pending settlements would exceed bond
    error InsufficientBondCoverage(uint256 pending, uint256 bond);
    
    /// @notice Provider already registered
    error ProviderAlreadyRegistered(address provider);
    
    /// @notice Caller not authorized for this operation
    error UnauthorizedCaller();
    
    /// @notice Withdrawal still locked
    error WithdrawalLocked(uint256 unlockTime);
    
    /// @notice No pending withdrawal to execute
    error NoPendingWithdrawal();
    
    /// @notice Cannot withdraw - active requests exist
    error ActiveRequestsExist(uint256 count);
    
    /// @notice Zero address provided
    error ZeroAddress();
    
    /// @notice Zero amount provided
    error ZeroAmount();
    
    /// @notice Escrow not found or already completed
    error EscrowNotFound(bytes32 escrowId);
    
    /// @notice Slash amount exceeds bond
    error SlashExceedsBond(uint256 slash, uint256 bond);
    
    // ============ Constants View ============
    
    /// @notice Minimum bond requirement (10,000 $VAMS)
    function MIN_BOND() external view returns (uint256);
    
    /// @notice Bond must cover this multiple of max request value
    function BOND_COVERAGE_RATIO() external view returns (uint256);
    
    /// @notice Delay before withdrawal can be executed
    function WITHDRAWAL_DELAY() external view returns (uint256);
    
    // ============ View Functions ============
    
    /**
     * @notice Get provider bond details
     * @param provider Provider address
     * @return ProviderBond struct with all details
     */
    function getBond(address provider) external view returns (ProviderBond memory);
    
    /**
     * @notice Check if provider can accept a request of given value
     * @param provider Provider address
     * @param requestValue Value of the request
     * @return canAccept True if provider can accept
     * @return reason Human-readable reason if cannot accept
     */
    function canAcceptRequest(address provider, uint256 requestValue) 
        external view returns (bool canAccept, string memory reason);
    
    /**
     * @notice Get active request details
     * @param escrowId Escrow identifier
     * @return ActiveRequest struct
     */
    function getActiveRequest(bytes32 escrowId) 
        external view returns (ActiveRequest memory);
    
    /**
     * @notice Check if provider is registered
     * @param provider Provider address
     * @return True if provider is in registry
     */
    function isRegistered(address provider) external view returns (bool);
    
    /**
     * @notice Calculate available bond (total - pending)
     * @param provider Provider address
     * @return Available bond amount
     */
    function getAvailableBond(address provider) external view returns (uint256);
    
    /**
     * @notice Get total value locked in provider bonds
     * @return Total bonded amount across all providers
     */
    function totalBonded() external view returns (uint256);
    
    // ============ Provider Functions ============
    
    /**
     * @notice Register as a provider with initial bond
     * @param bondAmount Amount of $VAMS to bond
     * @param maxRequestValue Maximum single request value
     */
    function registerProvider(uint256 bondAmount, uint256 maxRequestValue) external;
    
    /**
     * @notice Increase bond amount
     * @param additionalAmount Additional $VAMS to bond
     */
    function increaseBond(uint256 additionalAmount) external;
    
    /**
     * @notice Update maximum request value
     * @dev Must still satisfy coverage ratio
     * @param newMaxRequestValue New maximum request value
     */
    function updateMaxRequestValue(uint256 newMaxRequestValue) external;
    
    /**
     * @notice Request bond withdrawal (subject to delay)
     * @param amount Amount to withdraw
     */
    function requestWithdrawal(uint256 amount) external;
    
    /**
     * @notice Cancel pending withdrawal
     */
    function cancelWithdrawal() external;
    
    /**
     * @notice Execute pending withdrawal after delay
     */
    function executeWithdrawal() external;
    
    /**
     * @notice Deactivate provider (stop accepting new requests)
     */
    function deactivate() external;
    
    /**
     * @notice Reactivate provider
     */
    function reactivate() external;
    
    /**
     * @notice Lock hardware collateral for a commitment
     */
    function lockHardwareCollateral(address provider, uint256 amount) external;
    
    /**
     * @notice Unlock hardware collateral when a commitment ends
     */
    function unlockHardwareCollateral(address provider, uint256 amount) external;

    // ============ Settlement Functions (Authorized Only) ============
    
    /**
     * @notice Mark a request as accepted (increases pending)
     * @dev Only callable by authorized escrow contracts
     * @param provider Provider address
     * @param escrowId Escrow identifier
     * @param value Request value
     */
    function acceptRequest(address provider, bytes32 escrowId, uint256 value) external;
    
    /**
     * @notice Mark a request as completed (decreases pending)
     * @dev Only callable by authorized escrow contracts
     * @param provider Provider address
     * @param escrowId Escrow identifier
     */
    function completeRequest(address provider, bytes32 escrowId) external;
    
    /**
     * @notice Slash provider for failure
     * @dev Only callable by authorized slashing contracts
     * @param provider Provider address
     * @param amount Amount to slash
     * @param escrowId Failed escrow identifier
     * @param reason Slash reason
     */
    function slashProvider(
        address provider,
        uint256 amount,
        bytes32 escrowId,
        string calldata reason
    ) external;
    
    /**
     * @notice Compensate provider for settlement failure (not their fault)
     * @dev Only callable by authorized contracts
     * @param provider Provider address
     * @param amount Compensation amount
     * @param escrowId Failed escrow identifier
     */
    function compensateProvider(
        address provider,
        uint256 amount,
        bytes32 escrowId
    ) external;
}
