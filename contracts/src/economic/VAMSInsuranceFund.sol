// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
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
    ReentrancyGuard,
    PausableUpgradeable,
    IVAMSInsuranceFund
{
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Guardian role for claim approval (Phase 1-2)
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    /// @notice Slasher role (can deposit slashed funds)
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");

    /// @notice INTG01: Role for VAMSSentinel autonomous emergency pause
    bytes32 public constant SENTINEL_ROLE = keccak256("SENTINEL_ROLE");

    /// @notice Role for Yield Manager (OMS Yield Vaults)
    bytes32 public constant YIELD_MANAGER_ROLE = keccak256("YIELD_MANAGER_ROLE");

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

    /// @notice Total capital deployed to yield vaults
    uint256 public totalDeployedBalance;

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
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _admin, address _vamsToken, address _stakingContract, address[] memory _guardians)
        public
        initializer
    {
        if (_admin == address(0) || _vamsToken == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();

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

    // ============ Yield Functions (Phase 4) ============

    event YieldDeployed(address indexed vault, uint256 amount);
    event YieldWithdrawn(address indexed vault, uint256 amount);

    /**
     * @notice Deploy capital to a yield vault (max 30% of total fund)
     * @param vault Yield vault address
     * @param amount Amount to deploy
     */
    function deployToYield(address vault, uint256 amount)
        external
        onlyRole(YIELD_MANAGER_ROLE)
        nonReentrant
        whenNotPaused
    {
        if (vault == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        uint256 currentFundBalance = totalFundBalance();
        uint256 maxDeployable = (currentFundBalance * 3000) / BPS_DENOMINATOR; // 30%

        if (totalDeployedBalance + amount > maxDeployable) {
            revert("VAMSInsuranceFund: Max yield allocation exceeded");
        }

        totalDeployedBalance += amount;
        vamsToken.safeTransfer(vault, amount);

        emit YieldDeployed(vault, amount);
    }

    /**
     * @notice Withdraw capital from a yield vault
     * @param vault Yield vault address
     * @param amount Amount to withdraw
     */
    function withdrawFromYield(address vault, uint256 amount) external onlyRole(YIELD_MANAGER_ROLE) nonReentrant {
        if (vault == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        if (amount > totalDeployedBalance) {
            revert("VAMSInsuranceFund: Insufficient deployed balance");
        }

        totalDeployedBalance -= amount;
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);

        emit YieldWithdrawn(vault, amount);
    }

    // ============ Claim Functions ============

    /// @inheritdoc IVAMSInsuranceFund
    function submitClaim(bytes32 agentId, uint256 amount, string calldata reason)
        external
        override
        nonReentrant
        returns (bytes32 claimId)
    {
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
        claimId = keccak256(abi.encodePacked(msg.sender, agentId, amount, block.timestamp, totalClaims));

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

        // AUDIT FIX ECON02: Query actual staked amount from staking contract
        // instead of raw balanceOf to prevent flash-loan tier manipulation.
        uint256 stakedAmount = _getStakedAmount(account);

        if (stakedAmount >= OPERATOR_TIER_STAKE) {
            return CoverageTier.OPERATOR;
        } else if (stakedAmount >= AGENT_TIER_STAKE) {
            return CoverageTier.AGENT;
        }

        return CoverageTier.NONE;
    }

    /**
     * @dev Query the staking contract for locked stake amount
     * @param account The account to query
     * @return The staked amount (0 if call fails)
     */
    function _getStakedAmount(address account) internal view returns (uint256) {
        // Call staking contract's getStakeInfo to get locked stake
        // Uses staticcall to safely handle interface mismatches
        (bool success, bytes memory data) =
            stakingContract.staticcall(abi.encodeWithSignature("getStakeInfo(address)", account));
        if (!success || data.length < 32) return 0;

        // getStakeInfo returns a StakeInfo struct, first field is amount
        return abi.decode(data, (uint256));
    }

    /// @inheritdoc IVAMSInsuranceFund
    function totalFundBalance() public view override returns (uint256) {
        return vamsToken.balanceOf(address(this)) + totalDeployedBalance;
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
        return claim.claimant != address(0) && block.timestamp <= claim.submittedAt + CLAIM_WINDOW;
    }

    // ============ Emergency Pause — INTG01 ============

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

    /// @notice Guardian fallback pause
    function pause() external onlyRole(GUARDIAN_ROLE) {
        _pause();
    }

    /// @notice Unpause (admin or sentinel)
    function unpause() external {
        require(
            hasRole(DEFAULT_ADMIN_ROLE, msg.sender) || hasRole(SENTINEL_ROLE, msg.sender),
            "VAMSInsuranceFund: not authorized"
        );
        _unpause();
    }

    // ============ Storage Gap ============

    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
