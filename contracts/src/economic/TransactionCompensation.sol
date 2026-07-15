// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./ITransactionCompensation.sol";

/**
 * @title TransactionCompensation
 * @author VAMS Protocol
 * @notice Handles compensation claims for failed transactions during outages
 * @dev Disaster recovery contract for black swan events
 *
 * Key features:
 * - Guardian-controlled incident declaration
 * - Time-bounded claim window
 * - Multi-signature claim approval
 * - Insurance fund integration
 * - Tiered compensation limits
 */
contract TransactionCompensation is
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    ITransactionCompensation
{
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Guardian role for incident/claim management
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    /// @notice Processor role for claim payouts
    bytes32 public constant PROCESSOR_ROLE = keccak256("PROCESSOR_ROLE");

    /// @notice Required guardian approvals
    uint256 public constant APPROVAL_THRESHOLD = 2;

    /// @notice Maximum claim window (30 days)
    uint256 public constant MAX_CLAIM_WINDOW = 30 days;

    /// @notice Default claim window (14 days)
    uint256 public constant DEFAULT_CLAIM_WINDOW = 14 days;

    /// @notice Maximum compensation per claim (100,000 VAMS)
    uint256 public constant MAX_CLAIM_AMOUNT = 100_000 ether;

    // ============ State Variables ============

    /// @notice VAMS token for compensation payouts
    IERC20 public vamsToken;

    /// @notice Insurance fund address (source of compensation funds)
    address public insuranceFund;

    /// @notice Current incident counter
    uint256 public incidentCounter;

    /// @notice Current claim counter
    uint256 public claimCounter;

    /// @notice Active incident ID (0 if none)
    uint256 public activeIncidentId;

    /// @notice Total compensation paid out
    uint256 public totalCompensationPaid;

    /// @notice Incidents by ID
    mapping(uint256 => Incident) public incidents;

    /// @notice Claims by ID
    mapping(uint256 => Claim) private claims;

    /// @notice Transaction hash to claim ID mapping (prevent duplicates)
    mapping(bytes32 => uint256) public txToClaim;

    /// @notice Guardian votes per claim
    mapping(uint256 => mapping(address => bool)) public guardianVotes;

    /// @notice Claims by claimant
    mapping(address => uint256[]) public claimantClaims;

    /// @notice Pending claim IDs
    uint256[] public pendingClaimIds;

    // ============ Events ============

    /// @notice Emitted when compensation pool is funded
    /// @dev AUDIT FIX: C02 — Added to track pool funding by admin
    event PoolFunded(address indexed funder, uint256 amount);

    // ============ Initializer ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the compensation contract
     * @param _admin Admin address
     * @param _guardians Array of guardian addresses
     * @param _vamsToken VAMS token address
     * @param _insuranceFund Insurance fund address
     */
    function initialize(address _admin, address[] calldata _guardians, address _vamsToken, address _insuranceFund)
        external
        initializer
    {
        require(_admin != address(0), "Invalid admin");
        require(_vamsToken != address(0), "Invalid token");
        require(_insuranceFund != address(0), "Invalid insurance fund");
        require(_guardians.length >= 3, "Need at least 3 guardians");

        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(PROCESSOR_ROLE, _admin);

        for (uint256 i = 0; i < _guardians.length; i++) {
            _grantRole(GUARDIAN_ROLE, _guardians[i]);
        }

        vamsToken = IERC20(_vamsToken);
        insuranceFund = _insuranceFund;
    }

    // ============ Incident Management ============

    /// @inheritdoc ITransactionCompensation
    function declareIncident(string calldata description, uint256 claimWindowDays)
        external
        override
        onlyRole(GUARDIAN_ROLE)
        returns (uint256 incidentId)
    {
        require(activeIncidentId == 0, "Incident already active");
        require(claimWindowDays > 0 && claimWindowDays <= 30, "Invalid claim window");

        incidentCounter++;
        incidentId = incidentCounter;

        uint256 claimDeadline = block.timestamp + (claimWindowDays * 1 days);

        incidents[incidentId] = Incident({
            declaredAt: block.timestamp,
            resolvedAt: 0,
            claimDeadline: claimDeadline,
            description: description,
            active: true
        });

        activeIncidentId = incidentId;

        emit IncidentDeclared(incidentId, description, claimDeadline);
    }

    /// @inheritdoc ITransactionCompensation
    function resolveIncident(uint256 incidentId) external override onlyRole(GUARDIAN_ROLE) {
        Incident storage incident = incidents[incidentId];
        require(incident.active, "Incident not active");

        incident.active = false;
        incident.resolvedAt = block.timestamp;

        if (activeIncidentId == incidentId) {
            activeIncidentId = 0;
        }

        emit IncidentResolved(incidentId, block.timestamp);
    }

    // ============ Claim Management ============

    /// @inheritdoc ITransactionCompensation
    function submitClaim(bytes32 txHash, TransactionType txType, uint256 amount, string calldata evidence)
        external
        override
        whenNotPaused
        returns (uint256 claimId)
    {
        if (activeIncidentId == 0) revert NoActiveIncident();

        Incident storage incident = incidents[activeIncidentId];
        if (block.timestamp > incident.claimDeadline) revert ClaimDeadlinePassed();
        if (txToClaim[txHash] != 0) revert ClaimAlreadyExists(txHash);
        if (amount == 0 || amount > MAX_CLAIM_AMOUNT) revert AmountExceedsMaximum(amount, MAX_CLAIM_AMOUNT);
        if (bytes(evidence).length == 0) revert InvalidEvidence();

        claimCounter++;
        claimId = claimCounter;

        claims[claimId] = Claim({
            claimant: msg.sender,
            txHash: txHash,
            txType: txType,
            amount: amount,
            submittedAt: block.timestamp,
            processedAt: 0,
            status: ClaimStatus.PENDING,
            approvals: 0,
            rejections: 0,
            evidence: evidence,
            resolution: ""
        });

        txToClaim[txHash] = claimId;
        claimantClaims[msg.sender].push(claimId);
        pendingClaimIds.push(claimId);

        emit ClaimSubmitted(claimId, msg.sender, txHash, amount);
    }

    /// @inheritdoc ITransactionCompensation
    function approveClaim(uint256 claimId) external override onlyRole(GUARDIAN_ROLE) {
        Claim storage claim = claims[claimId];
        if (claim.claimant == address(0)) revert ClaimNotFound(claimId);
        if (claim.status != ClaimStatus.PENDING) revert ClaimNotPending(claimId);
        if (guardianVotes[claimId][msg.sender]) revert AlreadyVoted(claimId, msg.sender);

        guardianVotes[claimId][msg.sender] = true;
        claim.approvals++;

        emit ClaimVoted(claimId, msg.sender, true);

        // Check if threshold met
        if (claim.approvals >= APPROVAL_THRESHOLD) {
            claim.status = ClaimStatus.APPROVED;
            emit ClaimFinalized(claimId, ClaimStatus.APPROVED, claim.amount);
        }
    }

    /// @inheritdoc ITransactionCompensation
    function rejectClaim(uint256 claimId, string calldata reason) external override onlyRole(GUARDIAN_ROLE) {
        Claim storage claim = claims[claimId];
        if (claim.claimant == address(0)) revert ClaimNotFound(claimId);
        if (claim.status != ClaimStatus.PENDING) revert ClaimNotPending(claimId);
        if (guardianVotes[claimId][msg.sender]) revert AlreadyVoted(claimId, msg.sender);

        guardianVotes[claimId][msg.sender] = true;
        claim.rejections++;

        emit ClaimVoted(claimId, msg.sender, false);

        // Reject if 2+ rejections (assuming 3 guardians)
        if (claim.rejections >= APPROVAL_THRESHOLD) {
            claim.status = ClaimStatus.REJECTED;
            claim.resolution = reason;
            claim.processedAt = block.timestamp;
            emit ClaimFinalized(claimId, ClaimStatus.REJECTED, 0);
        }
    }

    /// @inheritdoc ITransactionCompensation
    function processClaim(uint256 claimId) external override nonReentrant onlyRole(PROCESSOR_ROLE) {
        _processClaim(claimId);
    }

    /// @inheritdoc ITransactionCompensation
    function batchProcessClaims(uint256[] calldata claimIds) external override nonReentrant onlyRole(PROCESSOR_ROLE) {
        for (uint256 i = 0; i < claimIds.length; i++) {
            _processClaim(claimIds[i]);
        }
    }

    /**
     * @notice Internal claim processing
     */
    function _processClaim(uint256 claimId) internal {
        Claim storage claim = claims[claimId];
        if (claim.claimant == address(0)) revert ClaimNotFound(claimId);
        require(claim.status == ClaimStatus.APPROVED, "Claim not approved");

        uint256 balance = vamsToken.balanceOf(address(this));
        if (balance < claim.amount) revert InsufficientFunds(claim.amount, balance);

        claim.status = ClaimStatus.PAID;
        claim.processedAt = block.timestamp;
        totalCompensationPaid += claim.amount;

        vamsToken.safeTransfer(claim.claimant, claim.amount);

        emit CompensationPaid(claimId, claim.claimant, claim.amount);
        emit ClaimFinalized(claimId, ClaimStatus.PAID, claim.amount);
    }

    // ============ Admin Functions ============

    /**
     * @notice Fund the compensation pool
     * @param amount Amount to fund
     * @dev AUDIT FIX: C02 — Changed from safeTransferFrom(insuranceFund) to
     * safeTransferFrom(msg.sender) to prevent unauthorized insurance fund drainage.
     * The caller must provide and approve the tokens themselves.
     */
    function fundPool(uint256 amount) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(amount > 0, "Zero amount");
        vamsToken.safeTransferFrom(msg.sender, address(this), amount);
        emit PoolFunded(msg.sender, amount);
    }

    /**
     * @notice Return unused funds to insurance
     * @param amount Amount to return
     */
    function returnToInsurance(uint256 amount) external onlyRole(DEFAULT_ADMIN_ROLE) {
        vamsToken.safeTransfer(insuranceFund, amount);
    }

    /**
     * @notice Expire old pending claims
     * @param claimId Claim to expire
     */
    function expireClaim(uint256 claimId) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Claim storage claim = claims[claimId];
        require(claim.status == ClaimStatus.PENDING, "Not pending");

        // Only expire if incident claim window has passed
        uint256 incidentId = activeIncidentId > 0 ? activeIncidentId : incidentCounter;
        require(block.timestamp > incidents[incidentId].claimDeadline + 7 days, "Window not expired");

        claim.status = ClaimStatus.EXPIRED;
        claim.processedAt = block.timestamp;
        emit ClaimFinalized(claimId, ClaimStatus.EXPIRED, 0);
    }

    /**
     * @notice Pause claims
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause claims
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ============ View Functions ============

    /// @inheritdoc ITransactionCompensation
    function getClaim(uint256 claimId) external view override returns (Claim memory) {
        return claims[claimId];
    }

    /// @inheritdoc ITransactionCompensation
    function getActiveIncident() external view override returns (Incident memory) {
        if (activeIncidentId == 0) {
            return Incident(0, 0, 0, "", false);
        }
        return incidents[activeIncidentId];
    }

    /// @inheritdoc ITransactionCompensation
    function getIncident(uint256 incidentId) external view override returns (Incident memory) {
        return incidents[incidentId];
    }

    /// @inheritdoc ITransactionCompensation
    function hasClaimForTx(bytes32 txHash) external view override returns (bool) {
        return txToClaim[txHash] != 0;
    }

    /// @inheritdoc ITransactionCompensation
    function getClaimsByClaimant(address claimant) external view override returns (uint256[] memory) {
        return claimantClaims[claimant];
    }

    /// @inheritdoc ITransactionCompensation
    function getPendingClaimsCount() external view override returns (uint256 count) {
        uint256 pendingCount = pendingClaimIds.length;
        for (uint256 i = 0; i < pendingCount; i++) {
            if (claims[pendingClaimIds[i]].status == ClaimStatus.PENDING) {
                count++;
            }
        }
    }

    /// @inheritdoc ITransactionCompensation
    function getTotalCompensationPaid() external view override returns (uint256) {
        return totalCompensationPaid;
    }

    /// @inheritdoc ITransactionCompensation
    function getApprovalThreshold() external pure override returns (uint256) {
        return APPROVAL_THRESHOLD;
    }

    /**
     * @notice Get pool balance
     * @return balance Available compensation funds
     */
    function getPoolBalance() external view returns (uint256) {
        return vamsToken.balanceOf(address(this));
    }

    // ============ Storage Gap ============

    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
