// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ISlashingOracle
 * @author VAMS Protocol
 * @notice Interface for √stake-weighted oracle voting on contested slashes
 * @dev Implements commit-reveal scheme to prevent front-running
 */
interface ISlashingOracle {
    // ============ Enums ============

    /// @notice Proposal status
    enum ProposalStatus {
        PENDING,        // Submitted, awaiting voting
        COMMIT_PHASE,   // Voters committing votes
        REVEAL_PHASE,   // Voters revealing votes
        APPROVED,       // Slash approved
        REJECTED,       // Slash rejected
        EXPIRED         // Voting window expired
    }

    // ============ Structs ============

    /// @notice Slash proposal
    struct SlashProposal {
        address proposer;           // Who proposed the slash
        address operator;           // Operator to be slashed
        uint8 offenseType;          // Type of offense
        bytes32 evidenceHash;       // Hash of evidence
        uint256 proposedAmount;     // Proposed slash amount
        uint256 createdAt;          // When proposal created
        uint256 commitDeadline;     // Deadline for commits
        uint256 revealDeadline;     // Deadline for reveals
        uint256 forStakeWeight;     // √stake voting for
        uint256 againstStakeWeight; // √stake voting against
        uint256 totalVoters;        // Number of voters
        ProposalStatus status;      // Current status
    }

    /// @notice Vote commitment
    struct VoteCommit {
        bytes32 commitment;     // keccak256(vote, salt)
        bool revealed;          // Whether revealed
        bool vote;              // Actual vote (set on reveal)
        uint256 stakeWeight;    // √stake weight
    }

    // ============ Events ============

    /// @notice Emitted when slash is proposed
    event SlashProposed(
        uint256 indexed proposalId,
        address indexed proposer,
        address indexed operator,
        uint256 proposedAmount
    );

    /// @notice Emitted when vote is committed
    event VoteCommitted(
        uint256 indexed proposalId,
        address indexed voter
    );

    /// @notice Emitted when vote is revealed
    event VoteRevealed(
        uint256 indexed proposalId,
        address indexed voter,
        bool vote,
        uint256 stakeWeight
    );

    /// @notice Emitted when proposal is finalized
    event ProposalFinalized(
        uint256 indexed proposalId,
        ProposalStatus status,
        uint256 forStake,
        uint256 againstStake
    );

    // ============ Errors ============

    /// @notice Already committed
    error AlreadyCommitted(uint256 proposalId, address voter);

    /// @notice Not in commit phase
    error NotInCommitPhase(uint256 proposalId);

    /// @notice Not in reveal phase
    error NotInRevealPhase(uint256 proposalId);

    /// @notice Invalid reveal
    error InvalidReveal(uint256 proposalId, address voter);

    /// @notice No stake
    error NoStake(address voter);

    /// @notice Proposal not found
    error ProposalNotFound(uint256 proposalId);

    /// @notice Proposal not finalized
    error ProposalNotFinalized(uint256 proposalId);

    // ============ Proposal Management ============

    /// @notice Propose a contested slash
    /// @param operator Operator to slash
    /// @param offenseType Type of offense
    /// @param evidenceHash Hash of evidence
    /// @param proposedAmount Proposed slash amount
    /// @return proposalId Proposal ID
    function proposeSlash(
        address operator,
        uint8 offenseType,
        bytes32 evidenceHash,
        uint256 proposedAmount
    ) external returns (uint256 proposalId);

    /// @notice Commit a vote
    /// @param proposalId Proposal to vote on
    /// @param commitment keccak256(abi.encodePacked(vote, salt))
    function commitVote(uint256 proposalId, bytes32 commitment) external;

    /// @notice Reveal a vote
    /// @param proposalId Proposal voted on
    /// @param vote True = approve slash, False = reject
    /// @param salt Salt used in commitment
    function revealVote(uint256 proposalId, bool vote, bytes32 salt) external;

    /// @notice Finalize proposal after reveal phase
    /// @param proposalId Proposal to finalize
    function finalizeProposal(uint256 proposalId) external;

    /// @notice Execute approved slash
    /// @param proposalId Approved proposal
    function executeSlash(uint256 proposalId) external;

    // ============ View Functions ============

    /// @notice Get proposal details
    function getProposal(uint256 proposalId) external view returns (SlashProposal memory);

    /// @notice Check if address has committed
    function hasCommitted(uint256 proposalId, address voter) external view returns (bool);

    /// @notice Check if address has revealed
    function hasRevealed(uint256 proposalId, address voter) external view returns (bool);

    /// @notice Get voter's stake weight
    function getVoterStakeWeight(address voter) external view returns (uint256);

    /// @notice Get current phase for proposal
    function getCurrentPhase(uint256 proposalId) external view returns (ProposalStatus);
}
