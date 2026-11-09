// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IComposedSettlement} from "./IComposedSettlement.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {IServiceBlockRegistry} from "../interfaces/IServiceBlockRegistry.sol";
import {IComposedDeliveryVerifier} from "./IComposedDeliveryVerifier.sol";
import {IProviderBondRegistry} from "./IProviderBondRegistry.sol";
import {IComposedObjectVerifierV3} from "./IComposedObjectVerifierV3.sol";
import {ActionContextV1} from "../trust/ActionContextV1.sol";
import {GovernedObjectGrantV1 as G} from "../trust/GovernedObjectGrantV1.sol";
import {EffectReceiptV3 as R} from "../trust/EffectReceiptV3.sol";
import {ObjectEffectV3 as O} from "../trust/ObjectEffectV3.sol";
import {DeliveryDisputeV1} from "./DeliveryDisputeV1.sol";

/**
 * @title ComposedSettlement
 * @author VAMS Protocol
 * @notice Multi-provider payment settlement for composed blueprints.
 * @dev Implements a hybrid escrow model:
 *      - Single lock from the agent for the total amount
 *      - Per-provider independent claims (no dependency between providers)
 *      - Builder revenue share deducted from each provider's claim
 *      - Protocol fee (5 bps) deducted on claim
 *      - Unclaimed portions refundable after expiry
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 10
 *
 *      // TODO [v1.1]: Refactor to UUPS upgradeable pattern (L-02 accepted risk)
 */
contract ComposedSettlement is
    IComposedSettlement,
    AccessControl,
    ReentrancyGuard,
    Pausable
{
    using SafeERC20 for IERC20;

    // ═══════════════════ Constants ═══════════════════

    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");

    /// @notice Settlement fee: 0.05% (5 basis points)
    uint256 public constant SETTLEMENT_FEE_BPS = 5;

    /// @notice BPS denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;
    uint256 public constant MAX_BUILDER_BPS = 5_000;

    /// @notice Minimum validity: 5 minutes
    uint256 public constant MIN_VALIDITY = 5 minutes;

    /// @notice Maximum validity: 48 hours (slightly more than X402 for composed)
    uint256 public constant MAX_VALIDITY = 48 hours;

    /// @notice Maximum providers per composed allocation
    uint256 public constant MAX_PROVIDERS = 20;

    // ═══════════════════ Storage ═══════════════════

    /// @notice VAMS token
    IERC20 public immutable vamsToken;
    IServiceBlockRegistry public immutable serviceBlockRegistry;
    IComposedDeliveryVerifier public immutable deliveryVerifier;
    /// @notice Dispute window for earned deliveries (owner decision 10), deployed and bound here.
    DeliveryDisputeV1 public immutable disputes;
    mapping(bytes32 => bytes32) public allocationTermsHash;
    mapping(bytes32 => bytes32) public allocationManifestHash;
    mapping(bytes32 => uint256) public allocationManifestVersion;
    mapping(bytes32 => mapping(uint256 => bytes32)) public deliveredOutputHash;
    mapping(bytes32 => mapping(uint256 => bytes32)) public expectedWorkloadHash;
    mapping(bytes32 => bool) public consumedDeliveryNonces;
    /// @notice Registry and stable per-provider request identities are pinned at admission.
    mapping(bytes32 => IProviderBondRegistry) public allocationBondRegistry;
    mapping(bytes32 => mapping(uint256 => bytes32)) public bondRequestIds;
    mapping(bytes32 => mapping(uint256 => IComposedDeliveryVerifier.ExpectedDelivery)) private _deliveryChallenges;
    uint256 private _challengeCount;
    event DeliveryChallengeIssued(bytes32 indexed allocationId, uint256 indexed providerIndex, bytes32 nonce);
    event BoundDeliveryAccepted(bytes32 indexed allocationId, uint256 indexed providerIndex,
        bytes32 context, bytes32 outputHash);

    /// @notice Provider bond registry for validation
    IProviderBondRegistry public bondRegistry;

    /// @notice Fee treasury
    address public treasury;

    /// @notice Allocation counter
    uint256 public allocationCount;

    /// @notice Total escrowed value
    uint256 public totalEscrowed;

    /// @notice Total fees collected
    uint256 public totalFeesCollected;

    /// @notice Total builder revenue distributed
    uint256 public totalBuilderRevenue;

    /// @notice Allocations by ID
    mapping(bytes32 => ComposedAllocation) private _allocations;

    /// @notice Provider allocations within a composed allocation
    /// allocationId => providerIndex => ProviderAlloc
    mapping(bytes32 => mapping(uint256 => ProviderAlloc)) private _providerAllocs;

    /// @notice Agent's allocation IDs
    mapping(address => bytes32[]) private _agentAllocations;

    /// @notice Verified ZK proofs for provider claims (allocationId => providerIndex => isVerified)
    mapping(bytes32 => mapping(uint256 => bool)) public verifiedProviderProofs;

    /// @notice Earned liabilities survive current-policy changes and escrow expiry.
    mapping(bytes32 => mapping(uint256 => EarnedDeliveryV3)) private _earnedDeliveries;

    enum ObjectResolutionV3 { NONE, RESERVED, COMPLETED, ABSENT }
    struct ObjectObligationV3 {
        bytes32 proposalDigest;
        bytes32 admissionDigest;
        bytes32 operationId;
        bytes32 grantDigest;
        bytes32 authorityIssuer;
        bytes32 providerIssuer;
        uint256 costUnits;
        address feeTreasury;
        uint256 admittedAt;
        ObjectResolutionV3 resolution;
        bytes32 attemptId;
        bytes32 previousAttempt;
    }
    struct ObjectOperationV3 {
        ObjectResolutionV3 resolution;
        uint256 authorityEpoch;
        uint256 fencingToken;
        bytes32 logicalWork;
        bytes32 headAttempt;
        bytes32 policyRoot;
        uint256 policyVersion;
    }
    mapping(bytes32 => mapping(uint256 => ObjectObligationV3)) private _objectObligations;
    mapping(bytes32 => ObjectOperationV3) public objectOperationsV3;
    struct ObjectAttemptLocationV3 { bytes32 allocationId; uint256 providerIndex; }
    mapping(bytes32 => ObjectAttemptLocationV3) public objectAttemptsV3;
    /// @notice Governed non-token cost units, including pending and completed effects.
    mapping(bytes32 => uint256) public objectGrantUsedV3;
    mapping(bytes32 => mapping(uint256 => bool)) public refundedProviderShareV3;
    event ObjectFundsReservedV3(bytes32 indexed allocationId, uint256 indexed index,
        bytes32 indexed operationId, bytes32 proposalDigest, bytes32 admissionDigest);
    event ObjectFundsResolvedV3(bytes32 indexed allocationId, uint256 indexed index,
        ObjectResolutionV3 resolution, bytes32 receiptDigest);

    // ═══════════════════ Constructor ═══════════════════

    /// @notice Initialize the ComposedSettlement contract
    /// @param admin Admin address
    /// @param _vamsToken VAMS ERC-20 token address
    /// @param _bondRegistry Provider bond registry address
    /// @param _treasury Protocol treasury address
    constructor(
        address admin,
        address _vamsToken,
        address _bondRegistry,
        address _treasury,
        address _serviceBlockRegistry,
        address _deliveryVerifier,
        address _disputeResolver
    ) {
        require(admin != address(0), "Zero admin");
        require(_vamsToken != address(0), "Zero token");
        require(_bondRegistry != address(0), "Zero bondRegistry");
        require(_bondRegistry.code.length > 0, "Invalid bond registry");
        require(_treasury != address(0), "Zero treasury");
        require(_serviceBlockRegistry.code.length > 0, "Invalid service registry");
        require(_deliveryVerifier.code.length > 0, "Invalid delivery verifier");
        serviceBlockRegistry = IServiceBlockRegistry(_serviceBlockRegistry);
        deliveryVerifier = IComposedDeliveryVerifier(_deliveryVerifier);
        // The resolver must be the governance timelock in deployment (decision 10).
        disputes = new DeliveryDisputeV1(address(this), _disputeResolver, _vamsToken);

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);

        vamsToken = IERC20(_vamsToken);
        bondRegistry = IProviderBondRegistry(_bondRegistry);
        treasury = _treasury;
    }

    // ═══════════════════ Core Functions ═══════════════════

    /// @dev The historical unbound ABI cannot create allocations.
    function createComposedEscrow(address[] calldata, uint256[] calldata, uint256,
        bytes32, bytes32, uint256, address) external pure override returns (bytes32) {
        revert LegacyInterfaceDisabled();
    }

    /// @inheritdoc IComposedSettlement
    function createComposedEscrowV2(EscrowRequestV2 calldata request)
        external override nonReentrant whenNotPaused returns (bytes32 allocationId) {
        IProviderBondRegistry selectedBondRegistry = bondRegistry;
        IServiceBlockRegistry.ServiceBlock memory block_;
        if (request.serviceBlockId != bytes32(0)) block_ = _qualifiedBlock(request.serviceBlockId);
        bytes32 termsHash = request.serviceBlockId == bytes32(0) ? bytes32(0) : _termsHash(block_);
        if (request.expectedTermsHash != termsHash) revert InvalidServiceTerms();
        // Validations
        if (request.providers.length == 0) revert ZeroProviders();
        if (request.providers.length != request.amounts.length) revert ArrayLengthMismatch();
        if (request.providers.length != request.workloadHashes.length) revert ArrayLengthMismatch();
        if (request.providers.length > MAX_PROVIDERS) revert InvalidProviderIndex(request.providers.length, MAX_PROVIDERS);
        require(request.validForSeconds >= MIN_VALIDITY && request.validForSeconds <= MAX_VALIDITY, "Invalid validity");

        // Calculate total
        uint256 totalAmount = 0;
        for (uint256 i = 0; i < request.amounts.length; i++) {
            require(request.amounts[i] > 0, "Zero amount for provider");
            require(request.workloadHashes[i] != bytes32(0), "Missing workload commitment");
            totalAmount += request.amounts[i];
        }

        // Validate all request.providers are bonded
        for (uint256 i = 0; i < request.providers.length; i++) {
            require(request.providers[i] != address(0), "Zero provider address");
            (bool canAccept, string memory reason) = selectedBondRegistry.canAcceptRequest(request.providers[i], request.amounts[i]);
            require(canAccept, reason);
        }

        // The direct contract route applies current policy before accepting funds.
        try deliveryVerifier.authorizeEscrow(msg.sender, request.providers, request.workloadHashes,
            totalAmount, request.validForSeconds) returns (bool allowed) {
            if (!allowed) revert InvalidDeliveryProof();
        } catch { revert InvalidDeliveryProof(); }

        // Generate allocation ID
        allocationId = keccak256(abi.encodePacked(
            msg.sender,
            block.timestamp,
            allocationCount,
            request.blueprintHash
        ));

        // Transfer total from agent
        uint256 balanceBefore = vamsToken.balanceOf(address(this));
        vamsToken.safeTransferFrom(msg.sender, address(this), totalAmount);
        uint256 balanceAfter = vamsToken.balanceOf(address(this));
        if (balanceAfter < balanceBefore || balanceAfter - balanceBefore != totalAmount) {
            revert AmountMismatch(totalAmount, balanceAfter >= balanceBefore ? balanceAfter - balanceBefore : 0);
        }
        allocationTermsHash[allocationId] = termsHash;
        allocationManifestHash[allocationId] = block_.manifestHash;
        allocationManifestVersion[allocationId] = block_.manifestVersion;
        allocationBondRegistry[allocationId] = selectedBondRegistry;

        // Create allocation
        uint256 expiresAt = block.timestamp + request.validForSeconds;

        _allocations[allocationId] = ComposedAllocation({
            allocationId: allocationId,
            agent: msg.sender,
            totalAmount: totalAmount,
            providerCount: request.providers.length,
            claimedCount: 0,
            blueprintHash: request.blueprintHash,
            serviceBlockId: request.serviceBlockId,
            createdAt: block.timestamp,
            expiresAt: expiresAt,
            status: AllocationStatus.LOCKED,
            builderRevShareBps: block_.revenueShareBps,
            builderAddress: block_.builder
        });

        // Create per-provider allocations
        for (uint256 i = 0; i < request.providers.length; i++) {
            bytes32 requestId = keccak256(abi.encode(
                "VAMS:COMPOSED-BOND-REQUEST:v1", block.chainid, address(this), allocationId, i));
            bondRequestIds[allocationId][i] = requestId;
            selectedBondRegistry.acceptRequest(request.providers[i], requestId, request.amounts[i]);
            expectedWorkloadHash[allocationId][i] = request.workloadHashes[i];
            _providerAllocs[allocationId][i] = ProviderAlloc({
                provider: request.providers[i],
                amount: request.amounts[i],
                claimed: false,
                claimedAt: 0
            });
        }

        // Track
        _agentAllocations[msg.sender].push(allocationId);
        allocationCount++;
        totalEscrowed += totalAmount;

        emit ComposedEscrowCreated(allocationId, msg.sender, totalAmount, request.providers.length, expiresAt);

        return allocationId;
    }

    /// @inheritdoc IComposedSettlement
    function claimProviderShare(bytes32, uint256) external pure override {
        revert LegacyInterfaceDisabled();
    }

    /// @dev Atomic verify-and-pay cannot coexist with the dispute window.
    function claimProviderShareV2(bytes32, uint256, bytes32, bytes calldata) external pure override {
        revert LegacyInterfaceDisabled();
    }

    /// @inheritdoc IComposedSettlement
    function recordEarnedDeliveryV3(bytes32 allocationId, uint256 providerIndex,
        bytes32 outputHash, bytes calldata proof) external override nonReentrant whenNotPaused {
        _recordEarnedDelivery(allocationId, providerIndex, outputHash, proof);
    }

    /// @inheritdoc IComposedSettlement
    function claimEarnedProviderShareV3(bytes32 allocationId, uint256 providerIndex)
        external override nonReentrant whenNotPaused {
        _payEarnedDelivery(allocationId, providerIndex);
    }

    function _recordEarnedDelivery(bytes32 allocationId, uint256 providerIndex,
        bytes32 outputHash, bytes calldata proof) private {
        ComposedAllocation storage alloc = _allocations[allocationId];
        if (alloc.agent == address(0)) revert AllocationNotFound(allocationId);

        // Must be in claimable state
        if (alloc.status == AllocationStatus.EXPIRED || alloc.status == AllocationStatus.DISPUTED) {
            revert AllocationNotClaimable(allocationId);
        }

        // Check expiry
        require(block.timestamp <= alloc.expiresAt, "Allocation expired");

        // Validate index
        if (providerIndex >= alloc.providerCount) {
            revert InvalidProviderIndex(providerIndex, alloc.providerCount);
        }
        // An admitted object has its own retained signature/terminal-resolution path.
        if (_objectObligations[allocationId][providerIndex].resolution != ObjectResolutionV3.NONE ||
            refundedProviderShareV3[allocationId][providerIndex]) revert InvalidDeliveryProof();

        ProviderAlloc storage pAlloc = _providerAllocs[allocationId][providerIndex];

        // Check not already claimed
        if (pAlloc.claimed) revert ProviderAlreadyClaimed(allocationId, providerIndex);

        // Must be the correct provider
        if (msg.sender != pAlloc.provider) {
            revert ProviderMismatch(pAlloc.provider, msg.sender);
        }

        if (_earnedDeliveries[allocationId][providerIndex].accepted) {
            revert DeliveryAlreadyEarned(allocationId, providerIndex);
        }

        // A pending proof can become earned only while current policy and its exact
        // challenge accept. A historical Boolean or administrative role cannot do so.
        bytes32 context = getDeliveryContext(allocationId, providerIndex);
        if (outputHash == bytes32(0) || proof.length == 0 || proof.length > 65_536) revert InvalidDeliveryProof();
        IComposedDeliveryVerifier.ExpectedDelivery memory expected = _deliveryChallenges[allocationId][providerIndex];
        if (expected.nonce == 0 || block.timestamp >= expected.expiresAt) revert InvalidDeliveryProof();
        bytes32 acceptedReplayKey;
        try deliveryVerifier.verifyDelivery(expected, outputHash, proof)
            returns (bool valid, bytes32 replayKey) {
            if (!valid || replayKey == 0 || consumedDeliveryNonces[replayKey]) revert InvalidDeliveryProof();
            consumedDeliveryNonces[replayKey] = true;
            acceptedReplayKey = replayKey;
        } catch { revert InvalidDeliveryProof(); }

        _earnedDeliveries[allocationId][providerIndex] = EarnedDeliveryV3(
            outputHash, acceptedReplayKey, block.timestamp, treasury, true);
        verifiedProviderProofs[allocationId][providerIndex] = true; // Historical result only.
        deliveredOutputHash[allocationId][providerIndex] = outputHash;
        // Delivery, rather than a later token retry, completes this exact reservation.
        _completeBondReservation(allocationId, providerIndex);
        emit BoundDeliveryAccepted(allocationId, providerIndex, context, outputHash);
        emit ProviderDeliveryEarned(allocationId, providerIndex, outputHash, acceptedReplayKey, block.timestamp);
    }

    function _payEarnedDelivery(bytes32 allocationId, uint256 providerIndex) private {
        ComposedAllocation storage alloc = _allocations[allocationId];
        if (alloc.agent == address(0)) revert AllocationNotFound(allocationId);
        if (providerIndex >= alloc.providerCount) revert InvalidProviderIndex(providerIndex, alloc.providerCount);
        if (alloc.status == AllocationStatus.DISPUTED) revert AllocationNotClaimable(allocationId);
        ProviderAlloc storage pAlloc = _providerAllocs[allocationId][providerIndex];
        if (msg.sender != pAlloc.provider) revert ProviderMismatch(pAlloc.provider, msg.sender);
        if (pAlloc.claimed) revert ProviderAlreadyClaimed(allocationId, providerIndex);
        EarnedDeliveryV3 storage earned = _earnedDeliveries[allocationId][providerIndex];
        if (!earned.accepted) revert DeliveryNotEarned(allocationId, providerIndex);
        if (refundedProviderShareV3[allocationId][providerIndex] ||
            !disputes.releasable(allocationId, providerIndex, earned.recordedAt)) {
            revert DeliveryHeld(allocationId, providerIndex);
        }

        // Calculate fees with full precision, preserving floor rounding.
        uint256 protocolFee = Math.mulDiv(pAlloc.amount, SETTLEMENT_FEE_BPS, BPS_DENOMINATOR);
        uint256 builderShare = 0;

        if (alloc.builderRevShareBps > 0 && alloc.builderAddress != address(0)) {
            builderShare = Math.mulDiv(pAlloc.amount, alloc.builderRevShareBps, BPS_DENOMINATOR);
        }

        uint256 providerPayout = pAlloc.amount - protocolFee - builderShare;

        // Update state
        pAlloc.claimed = true;
        pAlloc.claimedAt = block.timestamp;
        alloc.claimedCount++;

        totalEscrowed -= pAlloc.amount;
        totalFeesCollected += protocolFee;
        totalBuilderRevenue += builderShare;

        // Update allocation status
        if (alloc.claimedCount == alloc.providerCount) {
            alloc.status = AllocationStatus.FULLY_CLAIMED;
        } else if (alloc.status != AllocationStatus.EXPIRED) {
            alloc.status = AllocationStatus.PARTIALLY_CLAIMED;
        }

        // Recipients and fee terms were fixed when delivery became earned.
        if (protocolFee > 0) {
            vamsToken.safeTransfer(earned.feeTreasury, protocolFee);
        }

        // Transfer: builder share → builder
        if (builderShare > 0) {
            vamsToken.safeTransfer(alloc.builderAddress, builderShare);
        }

        // Transfer: payout → provider
        vamsToken.safeTransfer(pAlloc.provider, providerPayout);

        emit ProviderShareClaimed(allocationId, pAlloc.provider, providerPayout, protocolFee, builderShare);
    }

    /// @inheritdoc IComposedSettlement
    function refundExpiredComposed(bytes32 allocationId) external override nonReentrant {
        ComposedAllocation storage alloc = _allocations[allocationId];
        if (alloc.agent == address(0)) revert AllocationNotFound(allocationId);

        // Must be expired
        if (block.timestamp <= alloc.expiresAt) {
            revert AllocationNotExpired(allocationId);
        }

        // Only agent can request refund
        require(msg.sender == alloc.agent, "Not the agent");

        // Must not be fully claimed or already expired-refunded
        require(
            alloc.status == AllocationStatus.LOCKED ||
            alloc.status == AllocationStatus.PARTIALLY_CLAIMED ||
            alloc.status == AllocationStatus.EXPIRED,
            "Cannot refund in current status"
        );

        // Calculate unclaimed amount
        uint256 refundAmount = 0;
        for (uint256 i = 0; i < alloc.providerCount; i++) {
            if (!_providerAllocs[allocationId][i].claimed && !_earnedDeliveries[allocationId][i].accepted &&
                !refundedProviderShareV3[allocationId][i] &&
                _objectObligations[allocationId][i].resolution != ObjectResolutionV3.RESERVED) {
                refundAmount += _providerAllocs[allocationId][i].amount;
                refundedProviderShareV3[allocationId][i] = true;
                if (_objectObligations[allocationId][i].resolution == ObjectResolutionV3.NONE) {
                    _cancelBondReservation(allocationId, i);
                }
            }
        }

        // Update state
        require(refundAmount > 0 || alloc.status != AllocationStatus.EXPIRED, "Nothing refundable");
        alloc.status = AllocationStatus.EXPIRED;
        totalEscrowed -= refundAmount;

        // Refund agent
        if (refundAmount > 0) {
            vamsToken.safeTransfer(alloc.agent, refundAmount);
        }

        emit ComposedEscrowRefunded(allocationId, alloc.agent, refundAmount);
    }

    /// @inheritdoc IComposedSettlement
    function refundUpheldDispute(bytes32 allocationId, uint256 index) external override nonReentrant {
        if (msg.sender != address(disputes)) revert NotDisputeContract();
        ProviderAlloc storage p = _providerAllocs[allocationId][index];
        if (!_earnedDeliveries[allocationId][index].accepted || p.claimed ||
            refundedProviderShareV3[allocationId][index]) revert DeliveryHeld(allocationId, index);
        refundedProviderShareV3[allocationId][index] = true;
        address agent = _allocations[allocationId].agent;
        totalEscrowed -= p.amount;
        vamsToken.safeTransfer(agent, p.amount);
        emit ComposedEscrowRefunded(allocationId, agent, p.amount);
    }

    /// @notice Reserve a funded row before dispatch. Expiry cannot release this obligation.
    /// @dev This EVM payment route binds providerId to the existing provider payee address.
    ///      It does not redefine generic V3 provider identities or establish chain finality.
    function admitObjectV3(bytes32 allocationId,uint256 index,O.Admission calldata)
        external nonReentrant whenNotPaused {
        getDeliveryContext(allocationId,index);
        ComposedAllocation storage a=_allocations[allocationId];
        ProviderAlloc storage p=_providerAllocs[allocationId][index];
        require(msg.sender==a.agent,"Not the agent");
        require((a.status==AllocationStatus.LOCKED || a.status==AllocationStatus.PARTIALLY_CLAIMED) &&
            block.timestamp<a.expiresAt && !p.claimed && !refundedProviderShareV3[allocationId][index] &&
            !_earnedDeliveries[allocationId][index].accepted &&
            _objectObligations[allocationId][index].resolution==ObjectResolutionV3.NONE,"Row unavailable");
        require(msg.data.length<=8192,"Unbounded object invocation");
        O.ExpectedRow memory row=O.ExpectedRow(allocationId,index,a.agent,p.provider,
            expectedWorkloadHash[allocationId][index],p.amount,a.expiresAt);
        (bool valid,O.AdmissionFacts memory f)=IComposedObjectVerifierV3(address(deliveryVerifier))
            .verifyObjectAdmissionV3(msg.data,row);
        if (!valid || f.grantDigest==0) revert InvalidDeliveryProof();
        _reserveObjectAttemptV3(allocationId,index,f);
    }

    function _reserveObjectAttemptV3(bytes32 allocationId,uint256 index,O.AdmissionFacts memory f) private {
        ObjectOperationV3 storage previous=objectOperationsV3[f.operationId];
        require(previous.resolution==ObjectResolutionV3.NONE ||
            (previous.resolution==ObjectResolutionV3.ABSENT && f.authorityEpoch>previous.authorityEpoch &&
             f.fencingToken>previous.fencingToken),"Operation already reserved or completed");
        require(f.policyVersion>=previous.policyVersion &&
            (previous.policyRoot==0 || f.policyRoot==previous.policyRoot ||
             f.policyVersion>previous.policyVersion),"Policy generation regressed");
        require(previous.logicalWork==0 || previous.logicalWork==f.logicalWork,"Logical work changed");
        require(objectGrantUsedV3[f.grantDigest]<=f.grantBudget &&
            f.costUnits<=f.grantBudget-objectGrantUsedV3[f.grantDigest],"Grant budget exhausted");
        objectGrantUsedV3[f.grantDigest]+=f.costUnits;
        bytes32 attempt=O.attemptId(f,allocationId,index,block.chainid,address(this));
        bytes32 predecessor=previous.headAttempt;
        objectOperationsV3[f.operationId]=ObjectOperationV3(ObjectResolutionV3.RESERVED,f.authorityEpoch,f.fencingToken,
            f.logicalWork,attempt,f.policyRoot,f.policyVersion);
        require(objectAttemptsV3[attempt].allocationId==0,"Attempt already exists");
        objectAttemptsV3[attempt]=ObjectAttemptLocationV3(allocationId,index);
        _objectObligations[allocationId][index]=ObjectObligationV3(f.proposalDigest,f.admissionDigest,f.operationId,
            f.grantDigest,f.authorityIssuer,f.providerIssuer,f.costUnits,treasury,block.timestamp,ObjectResolutionV3.RESERVED,
            attempt,predecessor);
        emit ObjectFundsReservedV3(allocationId,index,f.operationId,f.proposalDigest,f.admissionDigest);
    }

    /// @notice Authenticate a retained completion after expiry/revocation without new dispatch authority.
    /// @dev Anyone may relay; only the original provider can claim the fixed original payment.
    function resolveObjectCompletionV3(bytes32 allocationId, uint256 index,
        O.ResolutionContext calldata, bytes calldata)
        external nonReentrant {
        getDeliveryContext(allocationId,index);
        ObjectObligationV3 storage o = _objectObligations[allocationId][index];
        require(o.resolution == ObjectResolutionV3.RESERVED && msg.data.length <= 8192, "No pending object");
        (bool valid,bytes32 receiptHash,bytes32 outputHash) = IComposedObjectVerifierV3(address(deliveryVerifier))
            .verifyObjectCompletionV3(msg.data,_expectedObjectTerminalV3(allocationId,index,o));
        if (!valid) revert InvalidDeliveryProof();
        o.resolution = ObjectResolutionV3.COMPLETED;
        objectOperationsV3[o.operationId].resolution = ObjectResolutionV3.COMPLETED;
        _earnedDeliveries[allocationId][index] = EarnedDeliveryV3(outputHash,
            receiptHash,block.timestamp,o.feeTreasury,true);
        deliveredOutputHash[allocationId][index] = outputHash;
        // This is an authenticated provider receipt, not a ZK/TEE proof Boolean.
        _completeBondReservation(allocationId,index);
        emit ObjectFundsResolvedV3(allocationId,index,ObjectResolutionV3.COMPLETED,receiptHash);
        emit ProviderDeliveryEarned(allocationId,index,outputHash,receiptHash,block.timestamp);
    }

    /// @notice Only a newer authority-signed fence plus provider acknowledgement and absence can release funds.
    function resolveObjectAbsenceV3(bytes32 allocationId, uint256 index,
        O.ResolutionContext calldata, O.AbsenceEvidence calldata evidence)
        external nonReentrant {
        getDeliveryContext(allocationId,index);
        ObjectObligationV3 storage o = _objectObligations[allocationId][index];
        require(o.resolution == ObjectResolutionV3.RESERVED && msg.data.length <= 8192, "No pending object");
        (bool valid,bytes32 receiptHash) = IComposedObjectVerifierV3(address(deliveryVerifier))
            .verifyObjectAbsenceV3(msg.data,_expectedObjectTerminalV3(allocationId,index,o));
        if (!valid) revert InvalidDeliveryProof();
        o.resolution = ObjectResolutionV3.ABSENT;
        ObjectOperationV3 storage operation=objectOperationsV3[o.operationId];
        operation.resolution=ObjectResolutionV3.ABSENT;
        operation.authorityEpoch=evidence.fence.authorityEpoch;operation.fencingToken=evidence.fence.fencingToken;
        operation.policyRoot=evidence.fence.policyRoot;operation.policyVersion=evidence.fence.policyVersion;
        objectGrantUsedV3[o.grantDigest] -= o.costUnits;
        _cancelBondReservation(allocationId,index);
        emit ObjectFundsResolvedV3(allocationId,index,ObjectResolutionV3.ABSENT,receiptHash);
    }

    /// @notice Exact principal refund after authenticated absence, including before allocation expiry.
    function refundAbsentObjectV3(bytes32 allocationId, uint256 index) external nonReentrant {
        getDeliveryContext(allocationId,index);
        ComposedAllocation storage a = _allocations[allocationId];
        require(msg.sender == a.agent, "Not the agent");
        require(_objectObligations[allocationId][index].resolution == ObjectResolutionV3.ABSENT &&
            !refundedProviderShareV3[allocationId][index], "No refundable absence");
        refundedProviderShareV3[allocationId][index] = true;
        uint256 amount = _providerAllocs[allocationId][index].amount;
        totalEscrowed -= amount;
        vamsToken.safeTransfer(a.agent,amount);
        emit ComposedEscrowRefunded(allocationId,a.agent,amount);
    }

    function getObjectObligationV3(bytes32 allocationId, uint256 index)
        external view returns (ObjectObligationV3 memory) {
        getDeliveryContext(allocationId,index);
        return _objectObligations[allocationId][index];
    }

    function _expectedObjectTerminalV3(bytes32 id,uint256 index,ObjectObligationV3 storage o)
        private view returns (O.ExpectedTerminal memory) {
        return O.ExpectedTerminal(id,index,o.proposalDigest,o.admissionDigest,
            o.authorityIssuer,o.providerIssuer,o.admittedAt);
    }

    /// @inheritdoc IComposedSettlement
    function getEarnedDeliveryV3(bytes32 allocationId, uint256 providerIndex)
        external view override returns (EarnedDeliveryV3 memory) {
        getDeliveryContext(allocationId, providerIndex);
        return _earnedDeliveries[allocationId][providerIndex];
    }

    function _completeBondReservation(bytes32 allocationId, uint256 index) private {
        allocationBondRegistry[allocationId].completeRequest(
            _providerAllocs[allocationId][index].provider, bondRequestIds[allocationId][index]);
    }

    function _cancelBondReservation(bytes32 allocationId, uint256 index) private {
        allocationBondRegistry[allocationId].cancelRequest(
            _providerAllocs[allocationId][index].provider, bondRequestIds[allocationId][index]);
    }

    // ═══════════════════ View Functions ═══════════════════

    /// @inheritdoc IComposedSettlement
    function getComposedAllocation(bytes32 allocationId)
        external
        view
        override
        returns (ComposedAllocation memory)
    {
        return _allocations[allocationId];
    }

    /// @inheritdoc IComposedSettlement
    function getProviderAlloc(bytes32 allocationId, uint256 providerIndex)
        external
        view
        override
        returns (ProviderAlloc memory)
    {
        require(providerIndex < _allocations[allocationId].providerCount, "Index OOB");
        return _providerAllocs[allocationId][providerIndex];
    }

    /// @inheritdoc IComposedSettlement
    function isFullyClaimed(bytes32 allocationId) external view override returns (bool) {
        ComposedAllocation storage alloc = _allocations[allocationId];
        return alloc.agent != address(0) && alloc.claimedCount == alloc.providerCount;
    }

    /// @notice Get all allocation IDs for an agent
    /// @param agent The agent address
    /// @return Array of allocation IDs
    function getAgentAllocations(address agent) external view returns (bytes32[] memory) {
        return _agentAllocations[agent];
    }

    // ═══════════════════ Admin ═══════════════════

    /// @notice Update the protocol treasury
    /// @param _treasury New treasury address
    function setTreasury(address _treasury) external onlyRole(ADMIN_ROLE) {
        require(_treasury != address(0), "Zero treasury");
        treasury = _treasury;
    }

    /// @notice Update the bond registry reference
    /// @param _bondRegistry New bond registry address
    function setBondRegistry(address _bondRegistry) external onlyRole(ADMIN_ROLE) {
        require(_bondRegistry.code.length > 0, "Invalid bond registry");
        bondRegistry = IProviderBondRegistry(_bondRegistry);
    }

    /// @notice Pause all composed escrows
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /// @notice Unpause composed escrows
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    /// @dev A privileged role is not delivery evidence. Compatibility ABI rejects.
    function verifyProviderProof(bytes32, uint256) external pure {
        revert LegacyInterfaceDisabled();
    }

    function _qualifiedBlock(bytes32 id) internal view returns (IServiceBlockRegistry.ServiceBlock memory b) {
        b = serviceBlockRegistry.getServiceBlock(id);
        if (b.blockId != id || b.builder == address(0) || !b.isActive || !b.isVerified ||
            b.isQuarantined || b.manifestHash == bytes32(0) || b.manifestVersion == 0) {
            revert UnqualifiedServiceBlock(id);
        }
        if (b.revenueShareBps > MAX_BUILDER_BPS || b.revenueShareBps + SETTLEMENT_FEE_BPS > BPS_DENOMINATOR) {
            revert InvalidServiceTerms();
        }
    }

    function _termsHash(IServiceBlockRegistry.ServiceBlock memory b) internal view returns (bytes32) {
        return keccak256(abi.encode(block.chainid, address(serviceBlockRegistry), b.blockId,
            b.builder, b.revenueShareBps, b.manifestHash, b.manifestVersion,
            b.resourceRequirementsHash, b.capabilityRoot, b.permissionsBitmap, b.manifestSigner));
    }

    function getServiceTermsHash(bytes32 id) external view override returns (bytes32) {
        return id == bytes32(0) ? bytes32(0) : _termsHash(_qualifiedBlock(id));
    }

    function getDeliveryContext(bytes32 allocationId, uint256 providerIndex)
        public view override returns (bytes32) {
        ComposedAllocation storage a = _allocations[allocationId];
        if (a.agent == address(0)) revert AllocationNotFound(allocationId);
        if (providerIndex >= a.providerCount) revert InvalidProviderIndex(providerIndex, a.providerCount);
        ProviderAlloc storage p = _providerAllocs[allocationId][providerIndex];
        bytes32 allocationDigest = keccak256(abi.encode(allocationId, a.agent, a.blueprintHash,
            a.serviceBlockId, allocationTermsHash[allocationId], a.expiresAt));
        return keccak256(abi.encode(block.chainid, address(this), allocationDigest,
            providerIndex, p.provider, address(vamsToken), p.amount,
            expectedWorkloadHash[allocationId][providerIndex]));
    }

    /// @notice Obtain a current on-chain challenge before collecting evidence.
    /// @dev New challenges replace old pending approvals; policy scope is latched.
    function issueDeliveryChallenge(bytes32 allocationId, uint256 providerIndex)
        external nonReentrant whenNotPaused returns (bytes32 nonce) {
        bytes32 context = getDeliveryContext(allocationId, providerIndex);
        ProviderAlloc storage p = _providerAllocs[allocationId][providerIndex];
        ComposedAllocation storage a = _allocations[allocationId];
        if (msg.sender != p.provider) revert ProviderMismatch(p.provider, msg.sender);
        if (p.claimed) revert ProviderAlreadyClaimed(allocationId, providerIndex);
        if (_objectObligations[allocationId][providerIndex].resolution != ObjectResolutionV3.NONE ||
            refundedProviderShareV3[allocationId][providerIndex]) revert InvalidDeliveryProof();
        if (_earnedDeliveries[allocationId][providerIndex].accepted) {
            revert DeliveryAlreadyEarned(allocationId, providerIndex);
        }
        require(block.timestamp < a.expiresAt, "Allocation expired");
        (bytes32 root, uint256 version, uint256 epoch) = deliveryVerifier.challengePolicy(
            p.provider, expectedWorkloadHash[allocationId][providerIndex], p.amount);
        if (root == 0 || version == 0 || epoch == 0) revert InvalidDeliveryProof();
        nonce = sha256(abi.encode(block.chainid, address(this), context, ++_challengeCount,
            block.prevrandao, block.number, root, version, epoch));
        uint256 expiry = block.timestamp + 10 minutes;
        if (expiry > a.expiresAt) expiry = a.expiresAt;
        _deliveryChallenges[allocationId][providerIndex] = IComposedDeliveryVerifier.ExpectedDelivery(
            context, p.provider, expectedWorkloadHash[allocationId][providerIndex], p.amount,
            nonce, block.timestamp, expiry, root, version, epoch, allocationId);
        emit DeliveryChallengeIssued(allocationId, providerIndex, nonce);
    }

    function getExpectedDelivery(bytes32 allocationId, uint256 providerIndex)
        external view returns (IComposedDeliveryVerifier.ExpectedDelivery memory) {
        getDeliveryContext(allocationId, providerIndex);
        return _deliveryChallenges[allocationId][providerIndex];
    }
}
