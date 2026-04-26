// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../utils/BaseTest.sol";
import "../../src/slashing/SlashingOracle.sol";
import "../../src/slashing/ISlashingOracle.sol";
import "../../src/slashing/VAMSSlasher.sol";
import "../../src/staking/VAMSStaking.sol";
import "../../src/staking/IVAMSStaking.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/**
 * @title SlashingOracleTest
 * @notice Comprehensive unit tests for SlashingOracle commit-reveal voting
 */
contract SlashingOracleTest is BaseTest {
    SlashingOracle public oracle;
    SlashingOracle public oracleImpl;
    VAMSSlasher public vamsSlasher;
    VAMSStaking public staking;
    
    // Test voters
    address public voter1;
    address public voter2;
    address public voter3;
    address public voter4;
    
    // Test data
    address public operatorToSlash;
    bytes32 public testEvidenceHash = keccak256("test_evidence");
    uint256 public testSlashAmount = 1000 ether;
    
    // Constants
    uint256 constant MIN_STAKE = 50_000 ether;
    uint256 constant PROPOSAL_STAKE = 10_000 ether;
    
    // Events
    event SlashProposed(uint256 indexed proposalId, address indexed proposer, address indexed operator, uint256 proposedAmount);
    event VoteCommitted(uint256 indexed proposalId, address indexed voter);
    event VoteRevealed(uint256 indexed proposalId, address indexed voter, bool vote, uint256 stakeWeight);
    event ProposalFinalized(uint256 indexed proposalId, ISlashingOracle.ProposalStatus status, uint256 forStake, uint256 againstStake);
    
    function setUp() public override {
        super.setUp();
        
        // Create voter addresses
        voter1 = makeAddr("voter1");
        voter2 = makeAddr("voter2");
        voter3 = makeAddr("voter3");
        voter4 = makeAddr("voter4");
        operatorToSlash = makeAddr("operatorToSlash");
        
        // Deploy staking contract
        staking = _deployStaking();
        
        // Deploy slasher (mock for testing)
        vamsSlasher = _deploySlasher();
        
        // Deploy oracle
        oracleImpl = new SlashingOracle();
        
        bytes memory initData = abi.encodeWithSelector(
            SlashingOracle.initialize.selector,
            admin,
            address(vamsSlasher),
            address(staking)
        );
        
        ERC1967Proxy proxy = new ERC1967Proxy(address(oracleImpl), initData);
        oracle = SlashingOracle(address(proxy));
        
        vm.label(address(oracle), "SlashingOracle");
        
        // Fund and stake voters (all must be >= MIN_STAKE)
        _setupVoter(voter1, MIN_STAKE);
        _setupVoter(voter2, MIN_STAKE * 5);
        _setupVoter(voter3, MIN_STAKE * 10);
        _setupVoter(voter4, MIN_STAKE * 50);
        
        // Fund admin for proposals
        _setupVoter(admin, MIN_STAKE);
        
        // IMPORTANT: Advance time past MIN_STAKE_AGE (7 days) so staking is valid for voting
        // This is required after HIGH-2 security fix for flash loan attack prevention
        vm.warp(block.timestamp + 8 days);
    }
    
    // ============ Initialization Tests ============
    
    function test_Initialization() public view {
        assertEq(address(oracle.slasher()), address(vamsSlasher));
        assertEq(address(oracle.staking()), address(staking));
        assertTrue(oracle.hasRole(oracle.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.PROPOSER_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.EXECUTOR_ROLE(), admin));
    }
    
    function test_Constants() public view {
        assertEq(oracle.COMMIT_DURATION(), 24 hours);
        assertEq(oracle.REVEAL_DURATION(), 24 hours);
        assertEq(oracle.MIN_STAKE_TO_VOTE(), 1000 ether);
        assertEq(oracle.MIN_PARTICIPATION_BPS(), 500); // 5%
        assertEq(oracle.APPROVAL_THRESHOLD_BPS(), 6000); // 60%
        assertEq(oracle.PROPOSAL_STAKE(), 10_000 ether);
    }
    
    // ============ Proposal Tests ============
    
    function test_ProposeSlash_Success() public {
        vm.prank(admin);
        uint256 proposalId = oracle.proposeSlash(
            operatorToSlash,
            1, // offense type
            testEvidenceHash,
            testSlashAmount
        );
        
        assertEq(proposalId, 1);
        
        ISlashingOracle.SlashProposal memory proposal = oracle.getProposal(proposalId);
        assertEq(proposal.proposer, admin);
        assertEq(proposal.operator, operatorToSlash);
        assertEq(proposal.evidenceHash, testEvidenceHash);
        assertEq(proposal.proposedAmount, testSlashAmount);
        assertEq(uint256(proposal.status), uint256(ISlashingOracle.ProposalStatus.COMMIT_PHASE));
    }
    
    function test_ProposeSlash_Revert_NotProposer() public {
        vm.expectRevert();
        vm.prank(user1);
        oracle.proposeSlash(operatorToSlash, 1, testEvidenceHash, testSlashAmount);
    }
    
    function test_ProposeSlash_Revert_InsufficientStake() public {
        // Grant user1 PROPOSER_ROLE but they have no stake
        bytes32 proposerRole = oracle.PROPOSER_ROLE();
        vm.prank(admin);
        oracle.grantRole(proposerRole, user1);
        
        // Ensure role was granted
        assertTrue(oracle.hasRole(proposerRole, user1));
        
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.NoStake.selector, user1));
        vm.prank(user1);
        oracle.proposeSlash(operatorToSlash, 1, testEvidenceHash, testSlashAmount);
    }
    
    function test_ProposeSlash_EmitsEvent() public {
        vm.expectEmit(true, true, true, true);
        emit SlashProposed(1, admin, operatorToSlash, testSlashAmount);
        
        vm.prank(admin);
        oracle.proposeSlash(operatorToSlash, 1, testEvidenceHash, testSlashAmount);
    }
    
    // ============ Commit Phase Tests ============
    
    function test_CommitVote_Success() public {
        uint256 proposalId = _createProposal();
        
        bytes32 commitment = _createCommitment(true, bytes32(uint256(1)));
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, commitment);
        
        assertTrue(oracle.hasCommitted(proposalId, voter1));
        assertFalse(oracle.hasRevealed(proposalId, voter1));
    }
    
    function test_CommitVote_MultipleVoters() public {
        uint256 proposalId = _createProposal();
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, bytes32(uint256(1))));
        
        vm.prank(voter2);
        oracle.commitVote(proposalId, _createCommitment(false, bytes32(uint256(2))));
        
        vm.prank(voter3);
        oracle.commitVote(proposalId, _createCommitment(true, bytes32(uint256(3))));
        
        assertTrue(oracle.hasCommitted(proposalId, voter1));
        assertTrue(oracle.hasCommitted(proposalId, voter2));
        assertTrue(oracle.hasCommitted(proposalId, voter3));
    }
    
    function test_CommitVote_Revert_AlreadyCommitted() public {
        uint256 proposalId = _createProposal();
        
        bytes32 commitment1 = _createCommitment(true, bytes32(uint256(1)));
        bytes32 commitment2 = _createCommitment(false, bytes32(uint256(2)));
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, commitment1);
        
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.AlreadyCommitted.selector, proposalId, voter1));
        vm.prank(voter1);
        oracle.commitVote(proposalId, commitment2);
    }
    
    function test_CommitVote_Revert_AfterCommitPhase() public {
        uint256 proposalId = _createProposal();
        
        // Warp past commit deadline
        vm.warp(block.timestamp + 25 hours);
        
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.NotInCommitPhase.selector, proposalId));
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, bytes32(uint256(1))));
    }
    
    function test_CommitVote_Revert_InsufficientStake() public {
        uint256 proposalId = _createProposal();
        
        // user1 has no stake
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.NoStake.selector, user1));
        vm.prank(user1);
        oracle.commitVote(proposalId, _createCommitment(true, bytes32(uint256(1))));
    }
    
    function test_CommitVote_Revert_StakeTooNew() public {
        // Create a new voter with fresh stake BEFORE proposal
        address newVoter = makeAddr("newVoter");
        token.mint(newVoter, MIN_STAKE * 5);
        vm.startPrank(newVoter);
        token.approve(address(staking), MIN_STAKE * 5);
        staking.stake(MIN_STAKE * 5, IVAMSStaking.LockPeriod.ThirtyDays);
        vm.stopPrank();
        
        // Create proposal now (newVoter's stake is still too new)
        uint256 proposalId = _createProposal();
        
        // Try to vote immediately (stake is too new)
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.StakeTooNew.selector, newVoter, 7 days));
        vm.prank(newVoter);
        oracle.commitVote(proposalId, _createCommitment(true, bytes32(uint256(1))));
        
        // After waiting 7 days, create new proposal and voting should work
        vm.warp(block.timestamp + 7 days + 1);
        
        uint256 proposalId2 = _createProposal();
        
        vm.prank(newVoter);
        oracle.commitVote(proposalId2, _createCommitment(true, bytes32(uint256(1))));
        assertTrue(oracle.hasCommitted(proposalId2, newVoter));
    }
    
    function test_CommitVote_EmitsEvent() public {
        uint256 proposalId = _createProposal();
        
        vm.expectEmit(true, true, true, true);
        emit VoteCommitted(proposalId, voter1);
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, bytes32(uint256(1))));
    }
    
    // ============ Reveal Phase Tests ============
    
    function test_RevealVote_Success() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt = bytes32(uint256(12345));
        bool vote = true;
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(vote, salt));
        
        // Advance to reveal phase
        vm.warp(block.timestamp + 25 hours);
        
        vm.prank(voter1);
        oracle.revealVote(proposalId, vote, salt);
        
        assertTrue(oracle.hasRevealed(proposalId, voter1));
        
        ISlashingOracle.SlashProposal memory proposal = oracle.getProposal(proposalId);
        assertGt(proposal.forStakeWeight, 0);
        assertEq(proposal.totalVoters, 1);
    }
    
    function test_RevealVote_Both_ForAndAgainst() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt1 = bytes32(uint256(1));
        bytes32 salt2 = bytes32(uint256(2));
        
        // Commit votes
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, salt1));
        
        vm.prank(voter2);
        oracle.commitVote(proposalId, _createCommitment(false, salt2));
        
        // Reveal phase
        vm.warp(block.timestamp + 25 hours);
        
        vm.prank(voter1);
        oracle.revealVote(proposalId, true, salt1);
        
        vm.prank(voter2);
        oracle.revealVote(proposalId, false, salt2);
        
        ISlashingOracle.SlashProposal memory proposal = oracle.getProposal(proposalId);
        assertGt(proposal.forStakeWeight, 0);
        assertGt(proposal.againstStakeWeight, 0);
        assertEq(proposal.totalVoters, 2);
    }
    
    function test_RevealVote_Revert_InvalidCommitment() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt = bytes32(uint256(12345));
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, salt));
        
        vm.warp(block.timestamp + 25 hours);
        
        // Reveal with wrong vote
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.InvalidReveal.selector, proposalId, voter1));
        vm.prank(voter1);
        oracle.revealVote(proposalId, false, salt);
    }
    
    function test_RevealVote_Revert_InvalidSalt() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt = bytes32(uint256(12345));
        bytes32 wrongSalt = bytes32(uint256(99999));
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, salt));
        
        vm.warp(block.timestamp + 25 hours);
        
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.InvalidReveal.selector, proposalId, voter1));
        vm.prank(voter1);
        oracle.revealVote(proposalId, true, wrongSalt);
    }
    
    function test_RevealVote_Revert_BeforeRevealPhase() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt = bytes32(uint256(12345));
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, salt));
        
        // Still in commit phase
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.NotInRevealPhase.selector, proposalId));
        vm.prank(voter1);
        oracle.revealVote(proposalId, true, salt);
    }
    
    function test_RevealVote_Revert_AfterRevealPhase() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt = bytes32(uint256(12345));
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, _createCommitment(true, salt));
        
        // Warp past reveal deadline
        vm.warp(block.timestamp + 49 hours);
        
        vm.expectRevert(abi.encodeWithSelector(ISlashingOracle.NotInRevealPhase.selector, proposalId));
        vm.prank(voter1);
        oracle.revealVote(proposalId, true, salt);
    }

    function test_FinalizeProposal_Approved() public {
        uint256 proposalId = _createProposal();
        
        // Commit phase
        address[4] memory voters = [voter1, voter2, voter3, voter4];
        bytes32[4] memory salts;
        
        for(uint i=0; i<4; i++) {
            salts[i] = bytes32(uint256(i + 1));
            vm.prank(voters[i]);
            oracle.commitVote(proposalId, _createCommitment(true, salts[i]));
        }
        
        // Reveal phase
        vm.warp(block.timestamp + 25 hours);
        
        for(uint i=0; i<4; i++) {
            vm.prank(voters[i]);
            oracle.revealVote(proposalId, true, salts[i]);
        }
        
        // Finalize
        vm.warp(block.timestamp + 49 hours);
        oracle.finalizeProposal(proposalId);
        
        ISlashingOracle.SlashProposal memory proposal = oracle.getProposal(proposalId);
        assertEq(uint256(proposal.status), uint256(ISlashingOracle.ProposalStatus.APPROVED));
    }
    
    function test_FinalizeProposal_Rejected() public {
        uint256 proposalId = _createProposal();
        
        // Commit phase
        address[4] memory voters = [voter1, voter2, voter3, voter4];
        bytes32[4] memory salts;
        
        for(uint i=0; i<4; i++) {
            salts[i] = bytes32(uint256(i + 1));
            vm.prank(voters[i]);
            oracle.commitVote(proposalId, _createCommitment(false, salts[i]));
        }
        
        // Reveal phase
        vm.warp(block.timestamp + 25 hours);
        
        for(uint i=0; i<4; i++) {
            vm.prank(voters[i]);
            oracle.revealVote(proposalId, false, salts[i]);
        }
        
        // Finalize
        vm.warp(block.timestamp + 49 hours);
        oracle.finalizeProposal(proposalId);
        
        ISlashingOracle.SlashProposal memory proposal = oracle.getProposal(proposalId);
        assertEq(uint256(proposal.status), uint256(ISlashingOracle.ProposalStatus.REJECTED));
    }
    
    function test_FinalizeProposal_Expired_NoParticipation() public {
        uint256 proposalId = _createProposal();
        
        // No one votes
        
        vm.warp(block.timestamp + 49 hours);
        oracle.finalizeProposal(proposalId);
        
        ISlashingOracle.SlashProposal memory proposal = oracle.getProposal(proposalId);
        assertEq(uint256(proposal.status), uint256(ISlashingOracle.ProposalStatus.EXPIRED));
    }
    
    function test_FinalizeProposal_Revert_BeforeDeadline() public {
        uint256 proposalId = _createProposal();
        
        vm.warp(block.timestamp + 24 hours);
        
        vm.expectRevert("Reveal phase not ended");
        oracle.finalizeProposal(proposalId);
    }
    
    // ============ Sqrt Stake Weight Tests ============
    
    function test_GetVoterStakeWeight() public view {
        // Voter4 has 50,000 VAMS staked
        uint256 weight = oracle.getVoterStakeWeight(voter4);
        
        // sqrt(50000 ether) ≈ 223606797749978969 wei (√50000 in 18 decimals)
        assertGt(weight, 0);
    }
    
    function test_StakeWeight_SquareRoot() public view {
        // voter1 has 50,000, voter4 has 2,500,000
        // weight ratio should be sqrt(2500000)/sqrt(50000) ≈ 7.07 (not 50x)
        
        uint256 weight1 = oracle.getVoterStakeWeight(voter1);
        uint256 weight4 = oracle.getVoterStakeWeight(voter4);
        
        // With sqrt weighting, 50x stake should give ~7.07x voting power
        uint256 actualRatio = (weight4 * 100) / weight1;
        
        // Allow some tolerance due to integer math
        assertGt(actualRatio, 680);
        assertLt(actualRatio, 730);
    }
    
    // ============ View Function Tests ============
    
    function test_GetCurrentPhase() public {
        uint256 proposalId = _createProposal();
        
        assertEq(uint256(oracle.getCurrentPhase(proposalId)), uint256(ISlashingOracle.ProposalStatus.COMMIT_PHASE));
        
        vm.warp(block.timestamp + 25 hours);
        assertEq(uint256(oracle.getCurrentPhase(proposalId)), uint256(ISlashingOracle.ProposalStatus.REVEAL_PHASE));
    }
    
    function test_GetVoteCommit() public {
        uint256 proposalId = _createProposal();
        
        bytes32 salt = bytes32(uint256(12345));
        bytes32 commitment = _createCommitment(true, salt);
        
        vm.prank(voter1);
        oracle.commitVote(proposalId, commitment);
        
        ISlashingOracle.VoteCommit memory commit = oracle.getVoteCommit(proposalId, voter1);
        assertEq(commit.commitment, commitment);
        assertFalse(commit.revealed);
    }
    
    // ============ Pausability Tests ============
    
    function test_Pause_BlocksProposals() public {
        vm.prank(admin);
        oracle.pause();
        
        vm.expectRevert();
        vm.prank(admin);
        oracle.proposeSlash(operatorToSlash, 1, testEvidenceHash, testSlashAmount);
    }
    
    function test_Unpause_AllowsProposals() public {
        vm.prank(admin);
        oracle.pause();
        
        vm.prank(admin);
        oracle.unpause();
        
        vm.prank(admin);
        uint256 proposalId = oracle.proposeSlash(operatorToSlash, 1, testEvidenceHash, testSlashAmount);
        
        assertEq(proposalId, 1);
    }
    
    // ============ Helper Functions ============
    
    function _deployStaking() internal returns (VAMSStaking) {
        // VAMSStaking uses a constructor, not initialize
        VAMSStaking _staking = new VAMSStaking(
            address(token),  // staking token
            address(token),  // reward token (same)
            11574074074,     // reward per second (~1 token per day)
            admin            // admin
        );
        
        vm.label(address(_staking), "VAMSStaking");
        
        // Fund staking contract for rewards
        token.mint(address(_staking), 100_000_000 ether);
        
        return _staking;
    }
    
    function _deploySlasher() internal returns (VAMSSlasher) {
        address insuranceFund = makeAddr("insuranceFund");
        
        VAMSSlasher slasherImpl = new VAMSSlasher();
        bytes memory initData = abi.encodeWithSelector(
            VAMSSlasher.initialize.selector,
            admin,
            insuranceFund,
            address(token)
        );
        
        ERC1967Proxy proxy = new ERC1967Proxy(address(slasherImpl), initData);
        VAMSSlasher _slasher = VAMSSlasher(address(proxy));
        
        vm.label(address(_slasher), "VAMSSlasher");
        
        return _slasher;
    }
    
    function _setupVoter(address voter, uint256 stakeAmount) internal {
        // Fund voter
        token.mint(voter, stakeAmount);
        
        // Approve and stake
        vm.startPrank(voter);
        token.approve(address(staking), stakeAmount);
        staking.stake(stakeAmount, IVAMSStaking.LockPeriod.ThirtyDays);
        vm.stopPrank();
    }
    
    function _createProposal() internal returns (uint256) {
        vm.prank(admin);
        return oracle.proposeSlash(operatorToSlash, 1, testEvidenceHash, testSlashAmount);
    }
    
    function _createCommitment(bool vote, bytes32 salt) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(vote, salt));
    }
    
    function _commitAndReveal(uint256 proposalId, address voter, bool vote, bytes32 salt) internal {
        // Commit
        vm.prank(voter);
        oracle.commitVote(proposalId, _createCommitment(vote, salt));
    }
}
