// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "./IVAMSInsuranceFund.sol";
import "../base/VAMSUpgradeableBase.sol";

/**
 * @title VAMSInsuranceFund
 * @author VAMS Protocol
 * @notice Insurance fund for slashing protection with hybrid governance
 * @dev 
 * - Phase 1-2: Guardian 2/3 approval for claims
 * - Phase 3+: DAO timelock approval for claims
 * - No auto-approval to prevent mass drainage attacks
 * - Coverage tiers based on stake amount
 */
contract VAMSInsuranceFund is 
    Initializable, 
    AccessControlUpgradeable,
    ReentrancyGuardUpgradeable,
    IVAMSInsuranceFund 
{
    using SafeERC20 for IERC20;
    
    // ============ Constants ============
    
    /// @notice Guardian role for claim approval (Phase 1-2)
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    
    /// @notice Slasher role (can deposit slashed funds)
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");
    
    /// @notice Claim review window (7 days)
    uint256 public constant CLAIM_WINDOW = 7 days;
    
    /// @notice Required guardian approvals (2 of 3)
    uint8 public constant APPROVAL_THRESHOLD = 2;
    
    /// @notice Maximum payout per claim (50% of fund)
    uint256 public constant MAX_PAYOUT_BPS = 5000;
    
    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10000;
    
    /// @notice Stake threshold for Agent tier (10,000 VAMS)
    uint256 public constant AGENT_TIER_STAKE = 10_000 * 1e18;
    
    /// @notice Stake threshold for Operator tier (100,000 VAMS)
    uint256 public constant OPERATOR_TIER_STAKE = 100_000 * 1e18;
    
    // ============ State ============
    
    /// @notice VAMS token
    IERC20 public vamsToken;
    
    /// @notice Staking contract (for coverage tier lookup)
    address public stakingContract;
    
    /// @notice Timelock controller (for Phase 3+ governance)
    address public timelockController;
    
    /// @notice Current governance phase (mirrors VAMSUpgradeableBase)
    uint8 public governancePhase;
    
    /// @notice Total claims counter
    uint256 public totalClaims;
    
    /// @notice Claims mapping
    mapping(bytes32 claimId => Claim claim) private _claims;
    
    /// @notice Guardian approvals per claim
    mapping(bytes32 claimId => mapping(address guardian => bool approved)) private _approvals;
    
    /// @notice Claims by claimant
    mapping(address claimant => bytes32[] claimIds) private _claimantClaims;
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the insurance fund
     * @param _admin Admin address
     * @param _vamsToken VAMS token address
     * @param _stakingContract Staking contract for tier lookup
     * @param _guardians Guardian addresses (should be 3)
     */
    function initialize(
        address _admin,
        address _vamsToken,
        address _stakingContract,
        address[] memory _guardians
    ) public initializer {
        if (_admin == address(0) || _vamsToken == address(0)) revert ZeroAddress();
        
        __AccessControl_init();
        __ReentrancyGuard_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        
        for (uint256 i = 0; i < _guardians.length; i++) {
            _grantRole(GUARDIAN_ROLE, _guardians[i]);
        }
        
        vamsToken = IERC20(_vamsToken);
        stakingContract = _stakingContract;
        governancePhase = 1;
    }
    
    // ============ Deposit Functions ============
    
    /// @inheritdoc IVAMSInsuranceFund
    function deposit(uint256 amount) external override nonReentrant {
        if (amount == 0) revert ZeroAmount();
        
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        
        emit Deposited(msg.sender, amount);
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function receiveSlashedFunds(uint256 amount) external override onlyRole(SLASHER_ROLE) {
        if (amount == 0) revert ZeroAmount();
        
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        
        emit SlashingReceived(msg.sender, amount);
    }
    
    // ============ Claim Functions ============
    
    /// @inheritdoc IVAMSInsuranceFund
    function submitClaim(
        bytes32 agentId,
        uint256 amount,
        string calldata reason
    ) external override nonReentrant returns (bytes32 claimId) {
        if (amount == 0) revert ZeroAmount();
        
        // Check coverage
        CoverageTier tier = getCoverageTier(msg.sender);
        if (tier == CoverageTier.NONE) revert NoCoverage(msg.sender);
        
        // Check fund has sufficient balance
        uint256 maxPayout = (totalFundBalance() * MAX_PAYOUT_BPS) / BPS_DENOMINATOR;
        if (amount > maxPayout) {
            revert InsufficientFunds(amount, maxPayout);
        }
        
        // Generate claim ID
        claimId = keccak256(abi.encodePacked(
            msg.sender,
            agentId,
            amount,
            block.timestamp,
            totalClaims
        ));
        
        // Create claim
        _claims[claimId] = Claim({
            agentId: agentId,
            claimant: msg.sender,
            amount: amount,
            submittedAt: block.timestamp,
            resolvedAt: 0,
            status: ClaimStatus.PENDING,
            reason: reason,
            approvalCount: 0
        });
        
        _claimantClaims[msg.sender].push(claimId);
        totalClaims++;
        
        emit ClaimSubmitted(claimId, msg.sender, amount);
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function approveClaim(bytes32 claimId) external override nonReentrant {
        Claim storage claim = _claims[claimId];
        
        if (claim.claimant == address(0)) revert ClaimNotFound(claimId);
        if (claim.status != ClaimStatus.PENDING) revert ClaimAlreadyResolved(claimId);
        if (block.timestamp > claim.submittedAt + CLAIM_WINDOW) {
            revert ClaimWindowExpired(claimId);
        }
        
        // Hybrid governance check
        if (governancePhase <= 2) {
            // Phase 1-2: Guardian approval
            if (!hasRole(GUARDIAN_ROLE, msg.sender)) {
                revert AccessControlUnauthorizedAccount(msg.sender, GUARDIAN_ROLE);
            }
            if (_approvals[claimId][msg.sender]) {
                revert AlreadyApproved(claimId, msg.sender);
            }
            
            _approvals[claimId][msg.sender] = true;
            claim.approvalCount++;
            
            emit ClaimApproved(claimId, msg.sender);
            
            // Check threshold
            if (claim.approvalCount >= APPROVAL_THRESHOLD) {
                claim.status = ClaimStatus.APPROVED;
                claim.resolvedAt = block.timestamp;
            }
        } else {
            // Phase 3+: Must come from timelock
            if (msg.sender != timelockController) {
                revert AccessControlUnauthorizedAccount(msg.sender, DEFAULT_ADMIN_ROLE);
            }
            
            claim.status = ClaimStatus.APPROVED;
            claim.resolvedAt = block.timestamp;
            
            emit ClaimApproved(claimId, msg.sender);
        }
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function rejectClaim(bytes32 claimId, string calldata reason) external override {
        Claim storage claim = _claims[claimId];
        
        if (claim.claimant == address(0)) revert ClaimNotFound(claimId);
        if (claim.status != ClaimStatus.PENDING) revert ClaimAlreadyResolved(claimId);
        
        // Same governance check as approve
        if (governancePhase <= 2) {
            if (!hasRole(GUARDIAN_ROLE, msg.sender)) {
                revert AccessControlUnauthorizedAccount(msg.sender, GUARDIAN_ROLE);
            }
        } else {
            if (msg.sender != timelockController) {
                revert AccessControlUnauthorizedAccount(msg.sender, DEFAULT_ADMIN_ROLE);
            }
        }
        
        claim.status = ClaimStatus.REJECTED;
        claim.resolvedAt = block.timestamp;
        
        emit ClaimRejected(claimId, msg.sender, reason);
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function executePayout(bytes32 claimId) external override nonReentrant {
        Claim storage claim = _claims[claimId];
        
        if (claim.claimant == address(0)) revert ClaimNotFound(claimId);
        if (claim.status != ClaimStatus.APPROVED) revert ClaimAlreadyResolved(claimId);
        
        uint256 amount = claim.amount;
        if (amount > totalFundBalance()) {
            revert InsufficientFunds(amount, totalFundBalance());
        }
        
        claim.status = ClaimStatus.PAID;
        
        vamsToken.safeTransfer(claim.claimant, amount);
        
        emit ClaimPaid(claimId, claim.claimant, amount);
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Set the timelock controller for Phase 3+ governance
     * @param _timelockController Timelock address
     */
    function setTimelockController(address _timelockController) external onlyRole(DEFAULT_ADMIN_ROLE) {
        timelockController = _timelockController;
    }
    
    /**
     * @notice Advance governance phase
     * @param newPhase New governance phase (1-4)
     */
    function setGovernancePhase(uint8 newPhase) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newPhase > governancePhase && newPhase <= 4, "Invalid phase");
        governancePhase = newPhase;
    }
    
    /**
     * @notice Update staking contract reference
     * @param _stakingContract New staking contract
     */
    function setStakingContract(address _stakingContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        stakingContract = _stakingContract;
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc IVAMSInsuranceFund
    function getClaim(bytes32 claimId) external view override returns (Claim memory) {
        return _claims[claimId];
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function getCoverageTier(address account) public view override returns (CoverageTier) {
        if (stakingContract == address(0)) {
            return CoverageTier.NONE;
        }
        
        // Query staking contract for stake amount
        // Note: This assumes staking contract has getStakeInfo that returns stake amount
        // Simplified check - in production, would call staking contract
        // For now, return AGENT tier if caller has any VAMS balance
        uint256 balance = vamsToken.balanceOf(account);
        
        if (balance >= OPERATOR_TIER_STAKE) {
            return CoverageTier.OPERATOR;
        } else if (balance >= AGENT_TIER_STAKE) {
            return CoverageTier.AGENT;
        }
        
        return CoverageTier.NONE;
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function totalFundBalance() public view override returns (uint256) {
        return vamsToken.balanceOf(address(this));
    }
    
    /// @inheritdoc IVAMSInsuranceFund
    function hasApproved(bytes32 claimId, address guardian) external view override returns (bool) {
        return _approvals[claimId][guardian];
    }
    
    /**
     * @notice Get all claims for a claimant
     * @param claimant Claimant address
     * @return Array of claim IDs
     */
    function getClaimsByClaimant(address claimant) external view returns (bytes32[] memory) {
        return _claimantClaims[claimant];
    }
    
    /**
     * @notice Check if claim window is still open
     * @param claimId Claim ID
     * @return True if window is open
     */
    function isClaimWindowOpen(bytes32 claimId) external view returns (bool) {
        Claim storage claim = _claims[claimId];
        return claim.claimant != address(0) && 
               block.timestamp <= claim.submittedAt + CLAIM_WINDOW;
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
