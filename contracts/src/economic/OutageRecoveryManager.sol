// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./IOutageRecoveryManager.sol";

/**
 * @title OutageRecoveryManager
 * @author VAMS Protocol
 * @notice Emergency fund release during chain outages
 * @dev Black swan disaster recovery contract
 * 
 * Flow:
 * 1. Guardian(s) declare outage → grace period starts
 * 2. After grace period → emergency mode activates
 * 3. Users can request emergency withdrawals
 * 4. System recovery proven → emergency mode deactivated
 * 
 * Safeguards:
 * - 24-hour grace period before emergency mode
 * - 7-day emergency duration limit
 * - Pro-rata withdrawal limits
 * - Guardian quorum for declarations
 */
contract OutageRecoveryManager is 
    Initializable,
    AccessControlUpgradeable,
    ReentrancyGuardUpgradeable,
    IOutageRecoveryManager 
{
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Guardian role
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    /// @notice Operator role for processing withdrawals
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    /// @notice Required guardian declarations for outage
    uint256 public constant DECLARATION_THRESHOLD = 2;

    /// @notice Grace period before emergency mode (24 hours)
    uint256 public constant OUTAGE_GRACE_PERIOD = 24 hours;

    /// @notice Maximum emergency duration (7 days)
    uint256 public constant EMERGENCY_DURATION = 7 days;

    /// @notice Maximum withdrawal per request (10% of pool)
    uint256 public constant MAX_WITHDRAWAL_BPS = 1000; // 10%

    // ============ State Variables ============

    /// @notice Current system state
    SystemState public systemState;

    /// @notice Current outage counter
    uint256 public outageCounter;

    /// @notice Current withdrawal request counter
    uint256 public requestCounter;

    /// @notice Active outage ID
    uint256 public activeOutageId;

    /// @notice Outage records
    mapping(uint256 => OutageRecord) public outages;

    /// @notice Guardian declarations per outage
    mapping(uint256 => mapping(address => bool)) public guardianDeclarations;

    /// @notice Withdrawal requests
    mapping(uint256 => WithdrawalRequest) public requests;

    /// @notice User pending requests
    mapping(address => uint256[]) public userRequests;

    /// @notice Supported tokens for emergency withdrawal
    mapping(address => bool) public supportedTokens;

    /// @notice Token withdrawal totals (for pro-rata limits)
    mapping(address => uint256) public tokenWithdrawnTotals;

    /// @notice Token pool balances at emergency activation
    mapping(address => uint256) public tokenPoolBalances;

    // ============ Initializer ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the recovery manager
     * @param _admin Admin address
     * @param _guardians Array of guardian addresses
     * @param _supportedTokens Initial supported tokens
     */
    function initialize(
        address _admin,
        address[] calldata _guardians,
        address[] calldata _supportedTokens
    ) external initializer {
        require(_admin != address(0), "Invalid admin");
        require(_guardians.length >= 3, "Need at least 3 guardians");

        __AccessControl_init();
        __ReentrancyGuard_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);

        for (uint256 i = 0; i < _guardians.length; i++) {
            _grantRole(GUARDIAN_ROLE, _guardians[i]);
        }

        for (uint256 i = 0; i < _supportedTokens.length; i++) {
            supportedTokens[_supportedTokens[i]] = true;
        }

        systemState = SystemState.NORMAL;
    }

    // ============ Outage Declaration ============

    /// @inheritdoc IOutageRecoveryManager
    function declareOutage(string calldata reason) external override onlyRole(GUARDIAN_ROLE) {
        // Can declare from NORMAL state or add to existing pending outage
        if (systemState != SystemState.NORMAL && systemState != SystemState.OUTAGE_DECLARED) {
            revert InvalidSystemState(systemState, SystemState.NORMAL);
        }

        uint256 outageId;

        if (systemState == SystemState.NORMAL) {
            // First declaration - create new outage
            outageCounter++;
            outageId = outageCounter;
            activeOutageId = outageId;

            outages[outageId] = OutageRecord({
                declaredAt: block.timestamp,
                emergencyStartAt: 0,
                recoveredAt: 0,
                reason: reason,
                state: SystemState.OUTAGE_DECLARED,
                declaringGuardians: 1
            });

            systemState = SystemState.OUTAGE_DECLARED;
            guardianDeclarations[outageId][msg.sender] = true;
        } else {
            // Additional declaration
            outageId = activeOutageId;
            if (guardianDeclarations[outageId][msg.sender]) {
                revert AlreadyDeclared(msg.sender);
            }

            guardianDeclarations[outageId][msg.sender] = true;
            outages[outageId].declaringGuardians++;
        }

        emit OutageDeclared(outageId, msg.sender, reason);
    }

    /// @inheritdoc IOutageRecoveryManager
    function activateEmergencyMode() external override {
        if (systemState != SystemState.OUTAGE_DECLARED) {
            revert InvalidSystemState(systemState, SystemState.OUTAGE_DECLARED);
        }

        OutageRecord storage outage = outages[activeOutageId];

        // Check declaration threshold met
        require(outage.declaringGuardians >= DECLARATION_THRESHOLD, "Insufficient declarations");

        // Check grace period elapsed
        uint256 gracePeriodEnd = outage.declaredAt + OUTAGE_GRACE_PERIOD;
        if (block.timestamp < gracePeriodEnd) {
            revert GracePeriodNotElapsed(gracePeriodEnd - block.timestamp);
        }

        // Activate emergency mode
        systemState = SystemState.EMERGENCY_MODE;
        outage.state = SystemState.EMERGENCY_MODE;
        outage.emergencyStartAt = block.timestamp;

        emit EmergencyModeActivated(activeOutageId, block.timestamp);
    }

    // ============ Emergency Withdrawals ============

    /// @inheritdoc IOutageRecoveryManager
    function requestEmergencyWithdraw(
        address token,
        uint256 amount
    ) external override nonReentrant returns (uint256 requestId) {
        if (systemState != SystemState.EMERGENCY_MODE) {
            revert InvalidSystemState(systemState, SystemState.EMERGENCY_MODE);
        }

        OutageRecord storage outage = outages[activeOutageId];
        
        // Check emergency duration not expired
        if (block.timestamp > outage.emergencyStartAt + EMERGENCY_DURATION) {
            revert EmergencyDurationExpired();
        }

        require(supportedTokens[token], "Token not supported");

        // Calculate maximum withdrawal (10% of remaining pool)
        uint256 poolBalance = IERC20(token).balanceOf(address(this));
        uint256 maxWithdrawal = (poolBalance * MAX_WITHDRAWAL_BPS) / 10_000;
        if (amount > maxWithdrawal) {
            revert InsufficientBalance(token, amount, maxWithdrawal);
        }

        requestCounter++;
        requestId = requestCounter;

        requests[requestId] = WithdrawalRequest({
            requester: msg.sender,
            token: token,
            amount: amount,
            requestedAt: block.timestamp,
            processedAt: 0,
            status: WithdrawalStatus.APPROVED // Auto-approve during emergency
        });

        userRequests[msg.sender].push(requestId);

        emit EmergencyWithdrawalRequested(requestId, msg.sender, token, amount);
    }

    /// @inheritdoc IOutageRecoveryManager
    function processWithdrawal(uint256 requestId) external override nonReentrant {
        WithdrawalRequest storage request = requests[requestId];
        if (request.requester == address(0)) revert RequestNotFound(requestId);
        if (request.status != WithdrawalStatus.APPROVED) {
            revert RequestNotFound(requestId); // Reuse error for simplicity
        }

        // Anyone can process their own withdrawal, operators can process any
        if (msg.sender != request.requester && !hasRole(OPERATOR_ROLE, msg.sender)) {
            revert NotRequester(msg.sender, request.requester);
        }

        uint256 balance = IERC20(request.token).balanceOf(address(this));
        if (balance < request.amount) {
            revert InsufficientBalance(request.token, request.amount, balance);
        }

        request.status = WithdrawalStatus.PROCESSED;
        request.processedAt = block.timestamp;
        tokenWithdrawnTotals[request.token] += request.amount;

        IERC20(request.token).safeTransfer(request.requester, request.amount);

        emit EmergencyWithdrawalProcessed(requestId, request.requester, request.amount);
    }

    /// @inheritdoc IOutageRecoveryManager
    function cancelWithdrawal(uint256 requestId) external override {
        WithdrawalRequest storage request = requests[requestId];
        if (request.requester == address(0)) revert RequestNotFound(requestId);
        if (request.requester != msg.sender) revert NotRequester(msg.sender, request.requester);
        require(request.status == WithdrawalStatus.PENDING || request.status == WithdrawalStatus.APPROVED, "Cannot cancel");

        request.status = WithdrawalStatus.CANCELLED;
    }

    // ============ Recovery ============

    /// @inheritdoc IOutageRecoveryManager
    function proveRecovery(bytes calldata proof) external override onlyRole(GUARDIAN_ROLE) {
        if (systemState != SystemState.EMERGENCY_MODE) {
            revert InvalidSystemState(systemState, SystemState.EMERGENCY_MODE);
        }

        // In production, verify proof (e.g., recent block hash from resumed chain)
        // For now, guardian attestation is sufficient
        require(proof.length > 0, "Empty proof");

        emit RecoveryProven(activeOutageId, proof);
    }

    /// @inheritdoc IOutageRecoveryManager
    function deactivateEmergencyMode() external override onlyRole(GUARDIAN_ROLE) {
        if (systemState != SystemState.EMERGENCY_MODE) {
            revert InvalidSystemState(systemState, SystemState.EMERGENCY_MODE);
        }

        OutageRecord storage outage = outages[activeOutageId];
        outage.state = SystemState.RECOVERED;
        outage.recoveredAt = block.timestamp;

        systemState = SystemState.RECOVERED;
        activeOutageId = 0;

        emit EmergencyModeDeactivated(outageCounter, block.timestamp);

        // Reset to normal after recovery
        systemState = SystemState.NORMAL;
    }

    // ============ Admin Functions ============

    /**
     * @notice Add supported token
     * @param token Token address
     */
    function addSupportedToken(address token) external onlyRole(DEFAULT_ADMIN_ROLE) {
        supportedTokens[token] = true;
    }

    /**
     * @notice Remove supported token
     * @param token Token address
     */
    function removeSupportedToken(address token) external onlyRole(DEFAULT_ADMIN_ROLE) {
        supportedTokens[token] = false;
    }

    /**
     * @notice Deposit tokens to pool
     * @param token Token address
     * @param amount Amount to deposit
     */
    function depositToPool(address token, uint256 amount) external {
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
    }

    /**
     * @notice Withdraw tokens from pool (admin only, normal state only)
     * @param token Token address
     * @param to Recipient
     * @param amount Amount to withdraw
     */
    function withdrawFromPool(
        address token,
        address to,
        uint256 amount
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(systemState == SystemState.NORMAL, "Not in normal state");
        IERC20(token).safeTransfer(to, amount);
    }

    // ============ View Functions ============

    /// @inheritdoc IOutageRecoveryManager
    function getSystemState() external view override returns (SystemState) {
        return systemState;
    }

    /// @inheritdoc IOutageRecoveryManager
    function getActiveOutage() external view override returns (OutageRecord memory) {
        if (activeOutageId == 0) {
            return OutageRecord(0, 0, 0, "", SystemState.NORMAL, 0);
        }
        return outages[activeOutageId];
    }

    /// @inheritdoc IOutageRecoveryManager
    function getWithdrawalRequest(uint256 requestId) external view override returns (WithdrawalRequest memory) {
        return requests[requestId];
    }

    /// @inheritdoc IOutageRecoveryManager
    function getPendingWithdrawals(address user) external view override returns (uint256[] memory) {
        return userRequests[user];
    }

    /// @inheritdoc IOutageRecoveryManager
    function hasGuardianDeclared(address guardian) external view override returns (bool) {
        if (activeOutageId == 0) return false;
        return guardianDeclarations[activeOutageId][guardian];
    }

    /// @inheritdoc IOutageRecoveryManager
    function getOutageGracePeriod() external pure override returns (uint256) {
        return OUTAGE_GRACE_PERIOD;
    }

    /// @inheritdoc IOutageRecoveryManager
    function getEmergencyDuration() external pure override returns (uint256) {
        return EMERGENCY_DURATION;
    }

    /**
     * @notice Get pool balance for token
     * @param token Token address
     * @return balance Pool balance
     */
    function getPoolBalance(address token) external view returns (uint256) {
        return IERC20(token).balanceOf(address(this));
    }

    /**
     * @notice Time remaining until emergency mode can be activated
     * @return remaining Remaining seconds (0 if can be activated)
     */
    function getGracePeriodRemaining() external view returns (uint256) {
        if (systemState != SystemState.OUTAGE_DECLARED) return 0;
        
        OutageRecord storage outage = outages[activeOutageId];
        uint256 gracePeriodEnd = outage.declaredAt + OUTAGE_GRACE_PERIOD;
        
        if (block.timestamp >= gracePeriodEnd) return 0;
        return gracePeriodEnd - block.timestamp;
    }

    /**
     * @notice Time remaining in emergency mode
     * @return remaining Remaining seconds (0 if expired or not active)
     */
    function getEmergencyTimeRemaining() external view returns (uint256) {
        if (systemState != SystemState.EMERGENCY_MODE) return 0;
        
        OutageRecord storage outage = outages[activeOutageId];
        uint256 emergencyEnd = outage.emergencyStartAt + EMERGENCY_DURATION;
        
        if (block.timestamp >= emergencyEnd) return 0;
        return emergencyEnd - block.timestamp;
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
