// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ObjectEffectV3 as O} from "../trust/ObjectEffectV3.sol";

/**
 * @title IComposedSettlement
 * @author VAMS Protocol
 * @notice Interface for multi-provider composed payment settlement.
 * @dev Handles escrow locking and per-provider claims for blueprints
 *      that span multiple hardware providers via the Resource Composer.
 *
 *      Hybrid model: single escrow lock, per-provider Merkle claim.
 *
 *      Architecture Reference: Phase 4 (Economic Layer), Sprint 10
 */
interface IComposedSettlement {
    // ═══════════════════ Enums ═══════════════════

    enum AllocationStatus {
        LOCKED,
        PARTIALLY_CLAIMED,
        FULLY_CLAIMED,
        EXPIRED,
        DISPUTED
    }

    // ═══════════════════ Structs ═══════════════════

    /// @notice A single provider's allocation within a composed request
    struct ProviderAlloc {
        address provider;        // Provider address
        uint256 amount;          // Payment amount for this provider
        bool claimed;            // Whether this provider has claimed
        uint256 claimedAt;       // Timestamp of claim (0 if unclaimed)
    }

    /// @notice Integer token amounts and the exact registry terms expected by the caller.
    struct EscrowRequestV2 {
        address[] providers;
        uint256[] amounts;
        uint256 validForSeconds;
        bytes32 blueprintHash;
        bytes32 serviceBlockId;
        bytes32 expectedTermsHash;
        bytes32[] workloadHashes;
    }

    /// @notice A composed allocation spanning multiple providers
    struct ComposedAllocation {
        bytes32 allocationId;    // Unique identifier
        address agent;           // Requesting agent
        uint256 totalAmount;     // Total escrowed amount
        uint256 providerCount;   // Number of providers in the allocation
        uint256 claimedCount;    // Providers that have successfully claimed
        bytes32 blueprintHash;   // Hash of the blueprint that was composed
        bytes32 serviceBlockId;  // Associated service block (0 if raw blueprint)
        uint256 createdAt;       // Lock timestamp
        uint256 expiresAt;       // Expiry timestamp
        AllocationStatus status; // Current status
        uint256 builderRevShareBps; // Builder revenue share in basis points
        address builderAddress;  // Builder who receives revenue share
    }

    /// @notice On-chain delivery recognition, distinct from an off-chain effect receipt.
    /// @dev Written only after action-bound verification under the current policy.
    struct EarnedDeliveryV3 {
        bytes32 outputHash;
        bytes32 replayKey;
        uint256 recordedAt;
        address feeTreasury;
        bool accepted;
    }

    event ProviderDeliveryEarned(bytes32 indexed allocationId, uint256 indexed providerIndex,
        bytes32 outputHash, bytes32 replayKey, uint256 recordedAt);

    // ═══════════════════ Events ═══════════════════

    event ComposedEscrowCreated(
        bytes32 indexed allocationId,
        address indexed agent,
        uint256 totalAmount,
        uint256 providerCount,
        uint256 expiresAt
    );

    event ProviderShareClaimed(
        bytes32 indexed allocationId,
        address indexed provider,
        uint256 payout,
        uint256 fee,
        uint256 builderShare
    );

    event ComposedEscrowRefunded(
        bytes32 indexed allocationId,
        address indexed agent,
        uint256 refundedAmount
    );

    event ComposedEscrowDisputed(
        bytes32 indexed allocationId,
        address indexed disputer
    );

    // ═══════════════════ Errors ═══════════════════

    error AllocationNotFound(bytes32 allocationId);
    error AllocationNotClaimable(bytes32 allocationId);
    error AllocationNotExpired(bytes32 allocationId);
    error ProviderAlreadyClaimed(bytes32 allocationId, uint256 index);
    error ProviderMismatch(address expected, address actual);
    error InvalidProviderIndex(uint256 index, uint256 maxIndex);
    error ArrayLengthMismatch();
    error ZeroProviders();
    error AmountMismatch(uint256 expected, uint256 actual);
    error LegacyInterfaceDisabled();
    error InvalidServiceTerms();
    error UnqualifiedServiceBlock(bytes32 blockId);
    error InvalidDeliveryProof();
    error DeliveryAlreadyEarned(bytes32 allocationId, uint256 index);
    error DeliveryNotEarned(bytes32 allocationId, uint256 index);
    /// @notice Earned payment is held by the dispute window or an open/upheld dispute.
    error DeliveryHeld(bytes32 allocationId, uint256 index);
    error NotDisputeContract();

    // ═══════════════════ Functions ═══════════════════

    /// @notice Create a composed escrow for multiple providers
    /// @param providers Array of provider addresses
    /// @param amounts Array of amounts per provider
    /// @param validForSeconds Duration before expiry
    /// @param blueprintHash Hash of the composed blueprint
    /// @param serviceBlockId Service block ID (bytes32(0) if raw)
    /// @param builderRevShareBps Builder's revenue share in BPS
    /// @param builderAddress Builder's address for revenue share
    /// @return allocationId Unique ID for the allocation
    function createComposedEscrow(
        address[] calldata providers,
        uint256[] calldata amounts,
        uint256 validForSeconds,
        bytes32 blueprintHash,
        bytes32 serviceBlockId,
        uint256 builderRevShareBps,
        address builderAddress
    ) external returns (bytes32 allocationId);

    function createComposedEscrowV2(EscrowRequestV2 calldata request) external returns (bytes32 allocationId);

    function getServiceTermsHash(bytes32 serviceBlockId) external view returns (bytes32);

    function getDeliveryContext(bytes32 allocationId, uint256 providerIndex) external view returns (bytes32);

    function claimProviderShareV2(
        bytes32 allocationId, uint256 providerIndex, bytes32 outputHash, bytes calldata proof
    ) external;

    /// @notice Recognize verified delivery without attempting token payment.
    /// @dev Pending evidence must satisfy the current policy and challenge before expiry.
    function recordEarnedDeliveryV3(bytes32 allocationId, uint256 providerIndex,
        bytes32 outputHash, bytes calldata proof) external;

    /// @notice Pay a previously recognized delivery, including after policy/expiry changes.
    /// @dev Protocol pause still blocks payout; no new proof or execution is authorized.
    function claimEarnedProviderShareV3(bytes32 allocationId, uint256 providerIndex) external;

    function getEarnedDeliveryV3(bytes32 allocationId, uint256 providerIndex)
        external view returns (EarnedDeliveryV3 memory);

    /// @notice Refund an earned row after the dispute contract upholds a dispute.
    /// @dev Callable only by the dispute contract this settlement deployed.
    function refundUpheldDispute(bytes32 allocationId, uint256 providerIndex) external;

    /// @notice Funded native admission; must finalize before provider dispatch.
    function admitObjectV3(bytes32 allocationId, uint256 providerIndex, O.Admission calldata request) external;
    /// @notice Historical authentication never grants new execution authority.
    function resolveObjectCompletionV3(bytes32 allocationId, uint256 providerIndex,
        O.ResolutionContext calldata context, bytes calldata receipt) external;
    function resolveObjectAbsenceV3(bytes32 allocationId, uint256 providerIndex,
        O.ResolutionContext calldata context, O.AbsenceEvidence calldata evidence) external;
    function refundAbsentObjectV3(bytes32 allocationId, uint256 providerIndex) external;

    /// @notice Provider claims their share of a composed allocation
    /// @param allocationId The allocation to claim from
    /// @param providerIndex Index of the provider in the allocation
    function claimProviderShare(
        bytes32 allocationId,
        uint256 providerIndex
    ) external;

    /// @notice Refund expired portions without a claim or accepted delivery; reserve earned liabilities
    /// @param allocationId The expired allocation
    function refundExpiredComposed(bytes32 allocationId) external;

    /// @notice Get a composed allocation's details
    function getComposedAllocation(bytes32 allocationId)
        external
        view
        returns (ComposedAllocation memory);

    /// @notice Get a specific provider's allocation
    function getProviderAlloc(bytes32 allocationId, uint256 providerIndex)
        external
        view
        returns (ProviderAlloc memory);

    /// @notice True only for an existing allocation whose providers have all been paid.
    /// @dev Unknown IDs, earned-but-unpaid shares and refunded portions are not fully claimed.
    function isFullyClaimed(bytes32 allocationId) external view returns (bool);
}
