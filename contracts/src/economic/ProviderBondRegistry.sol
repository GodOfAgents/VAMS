// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {IProviderBondRegistry} from "./IProviderBondRegistry.sol";

/**
 * @title ProviderBondRegistry
 * @author VAMS Protocol
 * @notice Manages provider bonds for x402 settlement accountability
 * @dev Implements bonding, slashing, and withdrawal per ARCHITECTURE_v0-3-0.md §20.2.3
 * 
 * Security Model:
 * - Minimum 10,000 $VAMS bond to register
 * - Bond must cover 10x the max single request value
 * - 7-day withdrawal delay to allow dispute resolution
 * - Slashed funds split between burn and insurance fund
 * 
 * Integration:
 * - Escrow manager calls acceptRequest/completeRequest
 * - Slasher contract calls slashProvider
 * - Insurance fund receives 50% of slashed amounts
 */
contract ProviderBondRegistry is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    IProviderBondRegistry 
{
    using SafeERC20 for IERC20;
    
    // ============ Constants ============
    
    /// @notice Minimum bond requirement: 10,000 $VAMS
    uint256 public constant MIN_BOND = 10_000e18;
    
    /// @notice Bond must cover this multiple of max request value
    uint256 public constant BOND_COVERAGE_RATIO = 10;
    
    /// @notice Withdrawal delay: 7 days
    uint256 public constant WITHDRAWAL_DELAY = 7 days;
    
    /// @notice Percentage of slashed funds sent to insurance (50%)
    uint256 public constant SLASH_TO_INSURANCE_BPS = 5000;
    
    /// @notice Basis points denominator
    uint256 private constant BPS_DENOMINATOR = 10000;
    
    /// @notice Role for escrow contracts that can manage requests
    bytes32 public constant ESCROW_ROLE = keccak256("ESCROW_ROLE");

    /// @notice Role for slashing operations
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");

    /// @notice Role for protocol administration
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    /// @notice Role for hardware commitments locking up bonds
    bytes32 public constant HARDWARE_COMMITMENT_ROLE = keccak256("HARDWARE_COMMITMENT_ROLE");

    /// @notice Role for emergency pause
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    /// @notice INTG01: Role for VAMSSentinel autonomous emergency pause
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");
    
    // ============ Storage ============
    
    /// @notice VAMS token contract
    IERC20 public vamsToken;
    
    /// @notice Insurance fund address (receives slash portion)
    address public insuranceFund;
    
    /// @notice Provider bonds
    mapping(address => ProviderBond) private _bonds;
    
    /// @notice Active requests by escrow ID
    mapping(bytes32 => ActiveRequest) private _activeRequests;
    
    /// @notice Provider's active escrow IDs
    mapping(address => bytes32[]) private _providerEscrows;
    
    /// @notice Total value bonded across all providers
    uint256 public totalBonded;
    
    /// @notice Total value slashed lifetime
    uint256 public totalSlashed;
    
    /// @notice Count of registered providers
    uint256 public providerCount;
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the provider bond registry
     * @param admin Protocol admin address
     * @param _vamsToken VAMS token contract
     * @param _insuranceFund Insurance fund address
     */
    function initialize(
        address admin,
        address _vamsToken,
        address _insuranceFund
    ) external initializer {
        if (admin == address(0)) revert ZeroAddress();
        if (_vamsToken == address(0)) revert ZeroAddress();
        if (_insuranceFund == address(0)) revert ZeroAddress();
        
        __AccessControl_init();
        __Pausable_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        
        vamsToken = IERC20(_vamsToken);
        insuranceFund = _insuranceFund;
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc IProviderBondRegistry
    function getBond(address provider) 
        external 
        view 
        override 
        returns (ProviderBond memory) 
    {
        return _bonds[provider];
    }
    
    /// @inheritdoc IProviderBondRegistry
    function canAcceptRequest(address provider, uint256 requestValue) 
        external 
        view 
        override 
        returns (bool canAccept, string memory reason) 
    {
        ProviderBond storage bond = _bonds[provider];
        
        if (bond.registeredAt == 0) {
            return (false, "Provider not registered");
        }
        
        if (!bond.isActive) {
            return (false, "Provider not active");
        }
        
        if (requestValue > bond.maxRequestValue) {
            return (false, "Request value exceeds provider maximum");
        }
        
        if (bond.pendingSettlements + requestValue > bond.bondedAmount) {
            return (false, "Insufficient bond coverage for pending + new request");
        }
        
        return (true, "");
    }
    
    /// @inheritdoc IProviderBondRegistry
    function getActiveRequest(bytes32 escrowId) 
        external 
        view 
        override 
        returns (ActiveRequest memory) 
    {
        return _activeRequests[escrowId];
    }
    
    /// @inheritdoc IProviderBondRegistry
    function isRegistered(address provider) external view override returns (bool) {
        return _bonds[provider].registeredAt > 0;
    }
    
    /// @inheritdoc IProviderBondRegistry
    function getAvailableBond(address provider) 
        external 
        view 
        override 
        returns (uint256) 
    {
        ProviderBond storage bond = _bonds[provider];
        if (bond.bondedAmount <= bond.pendingSettlements) {
            return 0;
        }
        return bond.bondedAmount - bond.pendingSettlements;
    }
    
    // ============ Provider Functions ============
    
    /// @inheritdoc IProviderBondRegistry
    function registerProvider(
        uint256 bondAmount, 
        uint256 maxRequestValue
    ) external override nonReentrant whenNotPaused {
        if (_bonds[msg.sender].registeredAt > 0) {
            revert ProviderAlreadyRegistered(msg.sender);
        }
        
        if (bondAmount < MIN_BOND) {
            revert BondTooLow(bondAmount, MIN_BOND);
        }
        
        if (bondAmount < maxRequestValue * BOND_COVERAGE_RATIO) {
            revert CoverageRatioNotMet(bondAmount, maxRequestValue, BOND_COVERAGE_RATIO);
        }
        
        // Transfer bond from provider
        vamsToken.safeTransferFrom(msg.sender, address(this), bondAmount);
        
        // Create provider record
        _bonds[msg.sender] = ProviderBond({
            bondedAmount: bondAmount,
            maxRequestValue: maxRequestValue,
            pendingSettlements: 0,
            activeRequests: 0,
            registeredAt: block.timestamp,
            totalEarned: 0,
            totalSlashed: 0,
            isActive: true,
            withdrawalUnlockTime: 0,
            pendingWithdrawal: 0,
            hardwareCollateralLocked: 0
        });
        
        totalBonded += bondAmount;
        providerCount++;
        
        emit ProviderRegistered(msg.sender, bondAmount, maxRequestValue);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function increaseBond(uint256 additionalAmount) 
        external 
        override 
        nonReentrant 
        whenNotPaused 
    {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(msg.sender);
        }
        
        if (additionalAmount == 0) {
            revert ZeroAmount();
        }
        
        vamsToken.safeTransferFrom(msg.sender, address(this), additionalAmount);
        
        bond.bondedAmount += additionalAmount;
        totalBonded += additionalAmount;
        
        emit BondIncreased(msg.sender, additionalAmount, bond.bondedAmount);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function updateMaxRequestValue(uint256 newMaxRequestValue) 
        external 
        override 
        whenNotPaused 
    {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(msg.sender);
        }
        
        // Ensure coverage ratio is still met
        if (bond.bondedAmount < newMaxRequestValue * BOND_COVERAGE_RATIO) {
            revert CoverageRatioNotMet(
                bond.bondedAmount, 
                newMaxRequestValue, 
                BOND_COVERAGE_RATIO
            );
        }
        
        uint256 oldValue = bond.maxRequestValue;
        bond.maxRequestValue = newMaxRequestValue;
        
        emit MaxRequestValueUpdated(msg.sender, oldValue, newMaxRequestValue);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function requestWithdrawal(uint256 amount) 
        external 
        override 
        whenNotPaused 
    {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(msg.sender);
        }
        
        if (amount == 0) {
            revert ZeroAmount();
        }
        
        // Cannot withdraw if there are active requests
        if (bond.activeRequests > 0) {
            revert ActiveRequestsExist(bond.activeRequests);
        }
        
        // Check remaining bond would still meet minimum
        uint256 remainingBond = bond.bondedAmount - amount;
        if (remainingBond > 0 && remainingBond < MIN_BOND) {
            revert BondTooLow(remainingBond, MIN_BOND);
        }
        
        // Check coverage ratio would still be met
        if (remainingBond > 0 && remainingBond < bond.maxRequestValue * BOND_COVERAGE_RATIO) {
            revert CoverageRatioNotMet(
                remainingBond, 
                bond.maxRequestValue, 
                BOND_COVERAGE_RATIO
            );
        }

        // Hardware Commitment check
        if (remainingBond < bond.hardwareCollateralLocked) {
            revert("Withdrawal cuts into locked hardware collateral");
        }
        
        bond.pendingWithdrawal = amount;
        bond.withdrawalUnlockTime = block.timestamp + WITHDRAWAL_DELAY;
        
        emit WithdrawalRequested(msg.sender, amount, bond.withdrawalUnlockTime);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function cancelWithdrawal() external override {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.pendingWithdrawal == 0) {
            revert NoPendingWithdrawal();
        }
        
        bond.pendingWithdrawal = 0;
        bond.withdrawalUnlockTime = 0;
        
        emit WithdrawalCancelled(msg.sender);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function executeWithdrawal() external override nonReentrant {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.pendingWithdrawal == 0) {
            revert NoPendingWithdrawal();
        }
        
        if (block.timestamp < bond.withdrawalUnlockTime) {
            revert WithdrawalLocked(bond.withdrawalUnlockTime);
        }
        
        // Re-check no active requests
        if (bond.activeRequests > 0) {
            revert ActiveRequestsExist(bond.activeRequests);
        }
        
        uint256 amount = bond.pendingWithdrawal;
        bond.bondedAmount -= amount;
        bond.pendingWithdrawal = 0;
        bond.withdrawalUnlockTime = 0;
        totalBonded -= amount;
        
        // If fully withdrawn, deactivate
        if (bond.bondedAmount == 0) {
            bond.isActive = false;
        }
        
        vamsToken.safeTransfer(msg.sender, amount);
        
        emit WithdrawalExecuted(msg.sender, amount);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function deactivate() external override {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(msg.sender);
        }
        
        bond.isActive = false;
        
        emit ProviderDeactivated(msg.sender, "Self-deactivated");
    }
    
    /// @inheritdoc IProviderBondRegistry
    function reactivate() external override whenNotPaused {
        ProviderBond storage bond = _bonds[msg.sender];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(msg.sender);
        }
        
        // Ensure still meets minimum bond
        if (bond.bondedAmount < MIN_BOND) {
            revert BondTooLow(bond.bondedAmount, MIN_BOND);
        }
        
        bond.isActive = true;
        
        emit ProviderReactivated(msg.sender);
    }
    
    // ============ Settlement Functions ============
    
    /// @inheritdoc IProviderBondRegistry
    function acceptRequest(
        address provider, 
        bytes32 escrowId, 
        uint256 value
    ) external override onlyRole(ESCROW_ROLE) whenNotPaused {
        ProviderBond storage bond = _bonds[provider];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(provider);
        }
        
        if (!bond.isActive) {
            revert ProviderNotActive(provider);
        }
        
        if (value > bond.maxRequestValue) {
            revert RequestValueTooHigh(value, bond.maxRequestValue);
        }
        
        if (bond.pendingSettlements + value > bond.bondedAmount) {
            revert InsufficientBondCoverage(bond.pendingSettlements + value, bond.bondedAmount);
        }
        
        // Track active request
        _activeRequests[escrowId] = ActiveRequest({
            value: value,
            startedAt: block.timestamp,
            provider: provider
        });
        
        _providerEscrows[provider].push(escrowId);
        
        bond.pendingSettlements += value;
        bond.activeRequests++;
        
        emit RequestAccepted(provider, escrowId, value);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function completeRequest(
        address provider, 
        bytes32 escrowId
    ) external override onlyRole(ESCROW_ROLE) {
        ActiveRequest storage request = _activeRequests[escrowId];
        
        if (request.provider == address(0)) {
            revert EscrowNotFound(escrowId);
        }
        
        if (request.provider != provider) {
            revert UnauthorizedCaller();
        }
        
        ProviderBond storage bond = _bonds[provider];
        
        // Update provider state
        bond.pendingSettlements -= request.value;
        bond.activeRequests--;
        bond.totalEarned += request.value;
        
        // Clear request
        delete _activeRequests[escrowId];
        
        emit RequestCompleted(provider, escrowId);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function slashProvider(
        address provider,
        uint256 amount,
        bytes32 escrowId,
        string calldata reason
    ) external override onlyRole(SLASHER_ROLE) nonReentrant {
        ProviderBond storage bond = _bonds[provider];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(provider);
        }
        
        // Cap slash to available bond
        uint256 slashAmount = amount > bond.bondedAmount ? bond.bondedAmount : amount;
        
        bond.bondedAmount -= slashAmount;
        bond.totalSlashed += slashAmount;
        totalBonded -= slashAmount;
        totalSlashed += slashAmount;
        
        // Split: 50% to insurance, 50% burned
        uint256 toInsurance = (slashAmount * SLASH_TO_INSURANCE_BPS) / BPS_DENOMINATOR;
        uint256 toBurn = slashAmount - toInsurance;
        
        // Send to insurance fund
        if (toInsurance > 0 && insuranceFund != address(0)) {
            vamsToken.safeTransfer(insuranceFund, toInsurance);
        }
        
        // Burn portion (send to dead address)
        if (toBurn > 0) {
            vamsToken.safeTransfer(address(0xdead), toBurn);
        }
        
        // Deactivate if bond falls below minimum
        if (bond.bondedAmount < MIN_BOND) {
            bond.isActive = false;
            emit ProviderDeactivated(provider, "Bond below minimum after slash");
        }
        
        emit ProviderSlashed(provider, slashAmount, escrowId, reason);
    }
    
    /// @inheritdoc IProviderBondRegistry
    function compensateProvider(
        address provider,
        uint256 amount,
        bytes32 escrowId
    ) external override onlyRole(ESCROW_ROLE) nonReentrant {
        // Compensation comes from insurance fund, sent directly to provider
        // This is called when settlement fails due to agent/network issues
        
        ProviderBond storage bond = _bonds[provider];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(provider);
        }
        
        bond.totalEarned += amount;
        
        emit ProviderCompensated(provider, amount, escrowId);
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Update insurance fund address
     * @param _insuranceFund New insurance fund address
     */
    function setInsuranceFund(address _insuranceFund) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        insuranceFund = _insuranceFund;
    }
    
    /**
     * @notice INTG01: Sentinel-callable emergency pause (implements IPausableTarget)
     * @param reason Human-readable reason for the pause
     */
    function emergencyPause(string calldata reason) external onlyRole(SENTINEL_ROLE) {
        emit EmergencyPauseActivated(msg.sender, reason);
        _pause();
    }

    /// @dev Emitted when Sentinel triggers an emergency pause
    event EmergencyPauseActivated(address indexed sentinel, string reason);

    /**
     * @notice Pause the registry
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause the registry (PAUSER_ROLE or SENTINEL_ROLE)
     */
    function unpause() external {
        require(
            hasRole(PAUSER_ROLE, msg.sender) || hasRole(SENTINEL_ROLE, msg.sender),
            "ProviderBondRegistry: not authorized"
        );
        _unpause();
    }
    
    /**
     * @notice Force deactivate a provider (emergency)
     * @param provider Provider address
     * @param reason Reason for deactivation
     */
    function forceDeactivate(address provider, string calldata reason) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        ProviderBond storage bond = _bonds[provider];
        
        if (bond.registeredAt == 0) {
            revert ProviderNotFound(provider);
        }
        
        bond.isActive = false;
        
        emit ProviderDeactivated(provider, reason);
    }
    
    /**
     * @notice Lock hardware collateral for a commitment
     */
    function lockHardwareCollateral(address provider, uint256 amount) external onlyRole(HARDWARE_COMMITMENT_ROLE) {
        ProviderBond storage bond = _bonds[provider];
        if (bond.registeredAt == 0) revert ProviderNotFound(provider);
        
        bond.hardwareCollateralLocked += amount;
        require(bond.hardwareCollateralLocked <= bond.bondedAmount, "Lock exceeds bond");
    }
    
    /**
     * @notice Unlock hardware collateral when a commitment ends
     */
    function unlockHardwareCollateral(address provider, uint256 amount) external onlyRole(HARDWARE_COMMITMENT_ROLE) {
        ProviderBond storage bond = _bonds[provider];
        if (bond.registeredAt == 0) revert ProviderNotFound(provider);
        require(amount <= bond.hardwareCollateralLocked, "Unlock exceeds locked");
        
        bond.hardwareCollateralLocked -= amount;
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
