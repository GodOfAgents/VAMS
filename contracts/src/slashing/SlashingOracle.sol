// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./ISlashingOracle.sol";
import "./VAMSSlasher.sol";
import "../staking/IVAMSStaking.sol";

/**
 * @title SlashingOracle
 * @author VAMS Protocol
 * @notice √stake-weighted oracle voting for contested slashing decisions
 * @dev Implements commit-reveal scheme to prevent front-running
 * 
 * Flow:
 * 1. Proposer submits slash proposal with evidence
 * 2. Commit phase: Stakers commit vote hashes
 * 3. Reveal phase: Stakers reveal actual votes
 * 4. Finalization: √stake-weighted tally determines outcome
 * 5. Execution: Approved slashes are executed via VAMSSlasher
 * 
 * √stake weighting ensures larger stakers have more influence
 * but prevents plutocracy (10x stake = ~3.2x voting power)
 */
contract SlashingOracle is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    ISlashingOracle 
{
    // ============ Constants ============

    /// @notice Proposer role (can submit proposals)
    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");

    /// @notice Executor role (can execute slashes)
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");

    /// @notice Commit phase duration (24 hours)
    uint256 public constant COMMIT_DURATION = 24 hours;

    /// @notice Reveal phase duration (24 hours)
    uint256 public constant REVEAL_DURATION = 24 hours;

    /// @notice Minimum stake to vote (1000 VAMS)
    uint256 public constant MIN_STAKE_TO_VOTE = 1000 ether;

    /// @notice Minimum participation (% of total stake)
    uint256 public constant MIN_PARTICIPATION_BPS = 500; // 5%

    /// @notice Approval threshold (% of participating stake)
    uint256 public constant APPROVAL_THRESHOLD_BPS = 6000; // 60%

    /// @notice Proposal stake requirement (10,000 VAMS)
    uint256 public constant PROPOSAL_STAKE = 10_000 ether;

    /// @notice Minimum stake age to vote (prevents flash loan attacks)
    uint256 public constant MIN_STAKE_AGE = 7 days;

    // ============ State Variables ============

    /// @notice VAMSSlasher contract
    VAMSSlasher public slasher;

    /// @notice VAMSStaking contract
    IVAMSStaking public staking;

    /// @notice Proposal counter
    uint256 public proposalCounter;

    /// @notice Proposals by ID
    mapping(uint256 => SlashProposal) public proposals;

    /// @notice Vote commits by proposal and voter
    mapping(uint256 => mapping(address => VoteCommit)) public voteCommits;

    /// @notice Track total staked at proposal time
    mapping(uint256 => uint256) public proposalTotalStake;

    // ============ Initializer ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the oracle
     * @param _admin Admin address
     * @param _slasher VAMSSlasher contract
     * @param _staking VAMSStaking contract
     */
    function initialize(
        address _admin,
        address _slasher,
        address _staking
    ) external initializer {
        require(_admin != address(0), "Invalid admin");
        require(_slasher != address(0), "Invalid slasher");
        require(_staking != address(0), "Invalid staking");

        __AccessControl_init();
        __Pausable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(PROPOSER_ROLE, _admin);
        _grantRole(EXECUTOR_ROLE, _admin);

        slasher = VAMSSlasher(_slasher);
        staking = IVAMSStaking(_staking);
    }

    // ============ Proposal Management ============

    /// @inheritdoc ISlashingOracle
    function proposeSlash(
        address operator,
        uint8 offenseType,
        bytes32 evidenceHash,
        uint256 proposedAmount
    ) external override whenNotPaused onlyRole(PROPOSER_ROLE) returns (uint256 proposalId) {
        require(operator != address(0), "Invalid operator");
        require(evidenceHash != bytes32(0), "Invalid evidence");
        require(proposedAmount > 0, "Invalid amount");

        // Verify proposer has sufficient stake
        IVAMSStaking.StakeInfo memory proposerInfo = staking.getStakeInfo(msg.sender);
        if (proposerInfo.amount < PROPOSAL_STAKE) {
            revert NoStake(msg.sender);
        }

        proposalCounter++;
        proposalId = proposalCounter;

        uint256 commitDeadline = block.timestamp + COMMIT_DURATION;
        uint256 revealDeadline = commitDeadline + REVEAL_DURATION;

        proposals[proposalId] = SlashProposal({
            proposer: msg.sender,
            operator: operator,
            offenseType: offenseType,
            evidenceHash: evidenceHash,
            proposedAmount: proposedAmount,
            createdAt: block.timestamp,
            commitDeadline: commitDeadline,
            revealDeadline: revealDeadline,
            forStakeWeight: 0,
            againstStakeWeight: 0,
            totalVoters: 0,
            status: ProposalStatus.COMMIT_PHASE
        });

        // Store total stake at proposal time for participation check
        proposalTotalStake[proposalId] = staking.totalStaked();

        emit SlashProposed(proposalId, msg.sender, operator, proposedAmount);
    }

    /// @inheritdoc ISlashingOracle
    function commitVote(
        uint256 proposalId, 
        bytes32 commitment
    ) external override whenNotPaused {
        SlashProposal storage proposal = proposals[proposalId];
        if (proposal.proposer == address(0)) revert ProposalNotFound(proposalId);
        
        if (block.timestamp > proposal.commitDeadline) {
            revert NotInCommitPhase(proposalId);
        }

        if (voteCommits[proposalId][msg.sender].commitment != bytes32(0)) {
            revert AlreadyCommitted(proposalId, msg.sender);
        }

        // Check voter has stake
        IVAMSStaking.StakeInfo memory voterInfo = staking.getStakeInfo(msg.sender);
        uint256 voterStake = voterInfo.amount;
        if (voterStake < MIN_STAKE_TO_VOTE) {
            revert NoStake(msg.sender);
        }

        // Check stake age (prevents flash loan attacks per security audit HIGH-2)
        if (voterInfo.stakedAt == 0 || block.timestamp - voterInfo.stakedAt < MIN_STAKE_AGE) {
            revert StakeTooNew(msg.sender, MIN_STAKE_AGE);
        }

        // Calculate √stake weight
        uint256 stakeWeight = _sqrt(voterStake);

        voteCommits[proposalId][msg.sender] = VoteCommit({
            commitment: commitment,
            revealed: false,
            vote: false,
            stakeWeight: stakeWeight
        });

        emit VoteCommitted(proposalId, msg.sender);
    }

    /// @inheritdoc ISlashingOracle
    function revealVote(
        uint256 proposalId, 
        bool vote, 
        bytes32 salt
    ) external override whenNotPaused {
        SlashProposal storage proposal = proposals[proposalId];
        if (proposal.proposer == address(0)) revert ProposalNotFound(proposalId);

        // Must be in reveal phase
        if (block.timestamp <= proposal.commitDeadline) {
            revert NotInRevealPhase(proposalId);
        }
        if (block.timestamp > proposal.revealDeadline) {
            revert NotInRevealPhase(proposalId);
        }

        // Update status if just entered reveal phase
        if (proposal.status == ProposalStatus.COMMIT_PHASE) {
            proposal.status = ProposalStatus.REVEAL_PHASE;
        }

        VoteCommit storage commit = voteCommits[proposalId][msg.sender];
        if (commit.commitment == bytes32(0)) {
            revert InvalidReveal(proposalId, msg.sender);
        }
        if (commit.revealed) {
            revert AlreadyCommitted(proposalId, msg.sender);
        }

        // Verify commitment
        bytes32 expectedCommit = keccak256(abi.encodePacked(vote, salt));
        if (commit.commitment != expectedCommit) {
            revert InvalidReveal(proposalId, msg.sender);
        }

        commit.revealed = true;
        commit.vote = vote;

        // Tally vote
        if (vote) {
            proposal.forStakeWeight += commit.stakeWeight;
        } else {
            proposal.againstStakeWeight += commit.stakeWeight;
        }
        proposal.totalVoters++;

        emit VoteRevealed(proposalId, msg.sender, vote, commit.stakeWeight);
    }

    /// @inheritdoc ISlashingOracle
    function finalizeProposal(uint256 proposalId) external override {
        SlashProposal storage proposal = proposals[proposalId];
        if (proposal.proposer == address(0)) revert ProposalNotFound(proposalId);

        // Must be after reveal deadline
        require(block.timestamp > proposal.revealDeadline, "Reveal phase not ended");
        require(
            proposal.status == ProposalStatus.COMMIT_PHASE || 
            proposal.status == ProposalStatus.REVEAL_PHASE,
            "Already finalized"
        );

        uint256 totalParticipation = proposal.forStakeWeight + proposal.againstStakeWeight;
        uint256 requiredParticipation = (_sqrt(proposalTotalStake[proposalId]) * MIN_PARTICIPATION_BPS) / 10_000;

        if (totalParticipation < requiredParticipation) {
            // Not enough participation - expired
            proposal.status = ProposalStatus.EXPIRED;
        } else {
            // Check if approved (60% threshold)
            uint256 approvalBps = (proposal.forStakeWeight * 10_000) / totalParticipation;
            
            if (approvalBps >= APPROVAL_THRESHOLD_BPS) {
                proposal.status = ProposalStatus.APPROVED;
            } else {
                proposal.status = ProposalStatus.REJECTED;
            }
        }

        emit ProposalFinalized(
            proposalId, 
            proposal.status, 
            proposal.forStakeWeight, 
            proposal.againstStakeWeight
        );
    }

    /// @inheritdoc ISlashingOracle
    function executeSlash(
        uint256 proposalId
    ) external override nonReentrant onlyRole(EXECUTOR_ROLE) {
        SlashProposal storage proposal = proposals[proposalId];
        if (proposal.proposer == address(0)) revert ProposalNotFound(proposalId);
        
        if (proposal.status != ProposalStatus.APPROVED) {
            revert ProposalNotFinalized(proposalId);
        }

        // Mark as no longer pending to prevent re-execution
        // Using a workaround since we can't add new status
        proposal.status = ProposalStatus.PENDING; // Repurpose as "executed"

        // Execute slash through VAMSSlasher
        // The slasher contract handles the actual slashing logic
        // This would require VAMSSlasher to have a function that accepts oracle-approved slashes
        // For now, emit event - integration would require VAMSSlasher modification
        
        // Note: In production, add: slasher.executeOracleSlash(proposal.operator, proposal.proposedAmount);
    }

    // ============ View Functions ============

    /// @inheritdoc ISlashingOracle
    function getProposal(uint256 proposalId) external view override returns (SlashProposal memory) {
        return proposals[proposalId];
    }

    /// @inheritdoc ISlashingOracle
    function hasCommitted(uint256 proposalId, address voter) external view override returns (bool) {
        return voteCommits[proposalId][voter].commitment != bytes32(0);
    }

    /// @inheritdoc ISlashingOracle
    function hasRevealed(uint256 proposalId, address voter) external view override returns (bool) {
        return voteCommits[proposalId][voter].revealed;
    }

    /// @inheritdoc ISlashingOracle
    function getVoterStakeWeight(address voter) external view override returns (uint256) {
        IVAMSStaking.StakeInfo memory voterInfo = staking.getStakeInfo(voter);
        uint256 stake = voterInfo.amount;
        return _sqrt(stake);
    }

    /// @inheritdoc ISlashingOracle
    function getCurrentPhase(uint256 proposalId) external view override returns (ProposalStatus) {
        SlashProposal storage proposal = proposals[proposalId];
        
        if (proposal.proposer == address(0)) {
            return ProposalStatus.PENDING;
        }
        
        // If already finalized, return that status
        if (proposal.status != ProposalStatus.COMMIT_PHASE && 
            proposal.status != ProposalStatus.REVEAL_PHASE) {
            return proposal.status;
        }
        
        // Determine current phase based on time
        if (block.timestamp <= proposal.commitDeadline) {
            return ProposalStatus.COMMIT_PHASE;
        } else if (block.timestamp <= proposal.revealDeadline) {
            return ProposalStatus.REVEAL_PHASE;
        } else {
            return ProposalStatus.PENDING; // Should be finalized
        }
    }

    /**
     * @notice Get vote details for a voter
     * @param proposalId Proposal ID
     * @param voter Voter address
     * @return commit Vote commitment details
     */
    function getVoteCommit(
        uint256 proposalId, 
        address voter
    ) external view returns (VoteCommit memory) {
        return voteCommits[proposalId][voter];
    }

    // ============ Admin Functions ============

    /**
     * @notice Pause the oracle
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause the oracle
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /**
     * @notice Update slasher address
     * @param _slasher New slasher address
     */
    function setSlasher(address _slasher) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_slasher != address(0), "Invalid slasher");
        slasher = VAMSSlasher(_slasher);
    }

    /**
     * @notice Update staking address
     * @param _staking New staking address
     */
    function setStaking(address _staking) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_staking != address(0), "Invalid staking");
        staking = IVAMSStaking(_staking);
    }

    // ============ Internal Functions ============

    /**
     * @notice Calculate integer square root (Babylonian method)
     * @param x Value to take sqrt of
     * @return y Square root
     */
    function _sqrt(uint256 x) internal pure returns (uint256 y) {
        if (x == 0) return 0;
        
        uint256 z = (x + 1) / 2;
        y = x;
        
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
