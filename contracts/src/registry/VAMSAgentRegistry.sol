// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title VAMSAgentRegistry
 * @author VAMS Protocol
 * @notice On-chain registry for AI agents with fraud-proof challenge window
 * @dev Implements §20.8 of VAMS Architecture - Agent Registration with 7-day finality
 * 
 * Features:
 * - Agent registration with stake requirement
 * - 7-day challenge window for fraud-proofs
 * - Merkle root submission for state commitments
 * - Slashing integration for detected fraud
 * - TEE attestation support
 */
contract VAMSAgentRegistry is 
    Initializable, 
    AccessControlUpgradeable,
    ReentrancyGuardUpgradeable,
    PausableUpgradeable
{
    // ============ Constants ============
    
    /// @notice Challenge window duration (7 days per §20.8)
    uint256 public constant CHALLENGE_WINDOW = 7 days;
    
    /// @notice Minimum stake required to register an agent
    uint256 public constant MIN_REGISTRATION_STAKE = 1000 ether; // 1000 VAMS
    
    /// @notice Minimum stake for challengers
    uint256 public constant MIN_CHALLENGER_STAKE = 100 ether;
    
    /// @notice Fraction of agent stake awarded to successful challenger (50%)
    uint256 public constant CHALLENGER_REWARD_BPS = 5000;
    
    /// @notice BPS denominator
    uint256 public constant BPS_DENOMINATOR = 10000;
    
    // ============ Roles ============
    
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant CHALLENGER_ROLE = keccak256("CHALLENGER_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    
    // ============ Enums ============
    
    enum AgentStatus {
        PENDING,      // In challenge window
        ACTIVE,       // Challenge window passed, operational
        CHALLENGED,   // Under active challenge
        SLASHED,      // Fraud proven, stake slashed
        DEREGISTERED  // Voluntarily exited
    }
    
    enum ChallengeStatus {
        OPEN,      // Challenge submitted, awaiting resolution
        PROVEN,    // Fraud proven, agent slashed
        REJECTED,  // Challenge invalid, challenger slashed
        EXPIRED    // Challenge window closed without resolution
    }
    
    // ============ Structs ============
    
    struct Agent {
        address owner;              // Controller address
        bytes32 publicKeyHash;      // Hash of agent's public key
        bytes32 teeAttestation;     // TEE attestation hash (optional)
        uint256 stake;              // Staked VAMS tokens
        uint256 registeredAt;       // Registration timestamp
        uint256 finalizedAt;        // When challenge window ends
        AgentStatus status;         // Current status
        bytes32 latestMerkleRoot;   // Latest state commitment
        uint256 lastHeartbeat;      // Last heartbeat timestamp
        string metadata;            // IPFS/Arweave URI for metadata
    }
    
    struct Challenge {
        address challenger;         // Who submitted the challenge
        bytes32 agentId;           // Agent being challenged
        bytes32 fraudProofHash;    // Hash of fraud proof data
        uint256 submittedAt;       // When challenge was submitted
        uint256 challengerStake;   // Stake by challenger
        ChallengeStatus status;    // Current status
        string evidence;           // IPFS URI for evidence
    }
    
    struct MerkleSubmission {
        bytes32 merkleRoot;        // Root of agent state tree
        uint256 blockNumber;       // Block when submitted
        uint256 timestamp;         // Submission timestamp
    }
    
    // ============ State ============
    
    /// @notice Agent records by ID (keccak256 of public key)
    mapping(bytes32 => Agent) public agents;
    
    /// @notice Challenge records by ID
    mapping(bytes32 => Challenge) public challenges;
    
    /// @notice Agent ID => list of Merkle submissions
    mapping(bytes32 => MerkleSubmission[]) public merkleHistory;
    
    /// @notice Owner => list of agent IDs
    mapping(address => bytes32[]) public ownerAgents;
    
    /// @notice Total registered agents
    uint256 public totalAgents;
    
    /// @notice Total active challenges
    uint256 public totalChallenges;
    
    /// @notice VAMS token address (for staking)
    address public vamsToken;
    
    /// @notice Slasher contract address
    address public slasher;
    
    // ============ Events ============
    
    event AgentRegistered(
        bytes32 indexed agentId,
        address indexed owner,
        uint256 stake,
        uint256 finalizedAt
    );
    
    event AgentFinalized(bytes32 indexed agentId, uint256 timestamp);
    
    event AgentDeregistered(bytes32 indexed agentId, address indexed owner);
    
    event MerkleRootSubmitted(
        bytes32 indexed agentId,
        bytes32 merkleRoot,
        uint256 blockNumber
    );
    
    event HeartbeatReceived(bytes32 indexed agentId, uint256 timestamp);
    
    event ChallengeSubmitted(
        bytes32 indexed challengeId,
        bytes32 indexed agentId,
        address indexed challenger,
        uint256 stake
    );
    
    event ChallengeResolved(
        bytes32 indexed challengeId,
        ChallengeStatus status,
        uint256 slashAmount
    );
    
    event TEEAttestationUpdated(bytes32 indexed agentId, bytes32 attestation);
    
    // ============ Errors ============
    
    error AgentNotFound();
    error AgentAlreadyExists();
    error AgentNotActive();
    error AgentStillPending();
    error InsufficientStake(uint256 required, uint256 provided);
    error ChallengeWindowNotExpired(uint256 expiresAt);
    error ChallengeNotFound();
    error ChallengeAlreadyResolved();
    error NotAgentOwner();
    error InvalidProof();
    error ZeroAddress();
    
    // ============ Initializer ============
    
    function initialize(
        address _admin,
        address _vamsToken,
        address _slasher
    ) public initializer {
        if (_admin == address(0) || _vamsToken == address(0)) revert ZeroAddress();
        
        __AccessControl_init();
        __ReentrancyGuard_init();
        __Pausable_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        _grantRole(GUARDIAN_ROLE, _admin);
        
        vamsToken = _vamsToken;
        slasher = _slasher;
    }
    
    // ============ Agent Registration ============
    
    /**
     * @notice Register a new AI agent
     * @param _publicKeyHash Hash of agent's ECDSA public key
     * @param _stake Amount of VAMS to stake
     * @param _metadata IPFS/Arweave URI for agent metadata
     * @return agentId The unique agent identifier
     */
    function registerAgent(
        bytes32 _publicKeyHash,
        uint256 _stake,
        string calldata _metadata
    ) external nonReentrant whenNotPaused returns (bytes32 agentId) {
        if (_stake < MIN_REGISTRATION_STAKE) {
            revert InsufficientStake(MIN_REGISTRATION_STAKE, _stake);
        }
        
        agentId = keccak256(abi.encodePacked(_publicKeyHash, msg.sender, block.timestamp));
        
        if (agents[agentId].owner != address(0)) {
            revert AgentAlreadyExists();
        }
        
        // Transfer stake from user to this contract
        IERC20(vamsToken).transferFrom(msg.sender, address(this), _stake);
        
        agents[agentId] = Agent({
            owner: msg.sender,
            publicKeyHash: _publicKeyHash,
            teeAttestation: bytes32(0),
            stake: _stake,
            registeredAt: block.timestamp,
            finalizedAt: block.timestamp + CHALLENGE_WINDOW,
            status: AgentStatus.PENDING,
            latestMerkleRoot: bytes32(0),
            lastHeartbeat: block.timestamp,
            metadata: _metadata
        });
        
        ownerAgents[msg.sender].push(agentId);
        totalAgents++;
        
        emit AgentRegistered(agentId, msg.sender, _stake, block.timestamp + CHALLENGE_WINDOW);
        
        return agentId;
    }
    
    /**
     * @notice Finalize agent registration after challenge window
     * @param _agentId Agent to finalize
     */
    function finalizeAgent(bytes32 _agentId) external {
        Agent storage agent = agents[_agentId];
        
        if (agent.owner == address(0)) revert AgentNotFound();
        if (agent.status != AgentStatus.PENDING) revert AgentNotActive();
        if (block.timestamp < agent.finalizedAt) {
            revert ChallengeWindowNotExpired(agent.finalizedAt);
        }
        
        agent.status = AgentStatus.ACTIVE;
        
        emit AgentFinalized(_agentId, block.timestamp);
    }
    
    /**
     * @notice Deregister an agent and withdraw stake
     * @param _agentId Agent to deregister
     */
    function deregisterAgent(bytes32 _agentId) external nonReentrant {
        Agent storage agent = agents[_agentId];
        
        if (agent.owner != msg.sender) revert NotAgentOwner();
        if (agent.status == AgentStatus.CHALLENGED) {
            revert AgentStillPending();
        }
        
        uint256 stakeToReturn = agent.stake;
        agent.status = AgentStatus.DEREGISTERED;
        agent.stake = 0;
        
        // Return stake to owner
        IERC20(vamsToken).transfer(msg.sender, stakeToReturn);
        
        emit AgentDeregistered(_agentId, msg.sender);
    }
    
    // ============ State Commitments ============
    
    /**
     * @notice Submit Merkle root of agent state
     * @param _agentId Agent ID
     * @param _merkleRoot Merkle root of current state
     */
    function submitMerkleRoot(
        bytes32 _agentId,
        bytes32 _merkleRoot
    ) external {
        Agent storage agent = agents[_agentId];
        
        if (agent.owner != msg.sender) revert NotAgentOwner();
        if (agent.status != AgentStatus.ACTIVE && agent.status != AgentStatus.PENDING) {
            revert AgentNotActive();
        }
        
        agent.latestMerkleRoot = _merkleRoot;
        agent.lastHeartbeat = block.timestamp;
        
        merkleHistory[_agentId].push(MerkleSubmission({
            merkleRoot: _merkleRoot,
            blockNumber: block.number,
            timestamp: block.timestamp
        }));
        
        emit MerkleRootSubmitted(_agentId, _merkleRoot, block.number);
        emit HeartbeatReceived(_agentId, block.timestamp);
    }
    
    /**
     * @notice Update TEE attestation for an agent
     * @param _agentId Agent ID
     * @param _attestation TEE attestation hash
     */
    function updateTEEAttestation(
        bytes32 _agentId,
        bytes32 _attestation
    ) external {
        Agent storage agent = agents[_agentId];
        
        if (agent.owner != msg.sender) revert NotAgentOwner();
        
        agent.teeAttestation = _attestation;
        
        emit TEEAttestationUpdated(_agentId, _attestation);
    }
    
    // ============ Challenge System ============
    
    /**
     * @notice Submit a fraud-proof challenge against an agent
     * @param _agentId Agent to challenge
     * @param _fraudProofHash Hash of the fraud proof
     * @param _evidence IPFS URI containing evidence
     * @return challengeId The unique challenge identifier
     */
    function submitChallenge(
        bytes32 _agentId,
        bytes32 _fraudProofHash,
        uint256 _stake,
        string calldata _evidence
    ) external nonReentrant whenNotPaused returns (bytes32 challengeId) {
        if (_stake < MIN_CHALLENGER_STAKE) {
            revert InsufficientStake(MIN_CHALLENGER_STAKE, _stake);
        }
        
        Agent storage agent = agents[_agentId];
        if (agent.owner == address(0)) revert AgentNotFound();
        if (agent.status == AgentStatus.SLASHED || agent.status == AgentStatus.DEREGISTERED) {
            revert AgentNotActive();
        }
        
        challengeId = keccak256(abi.encodePacked(_agentId, msg.sender, block.timestamp));
        
        // Transfer challenger stake
        IERC20(vamsToken).transferFrom(msg.sender, address(this), _stake);
        
        challenges[challengeId] = Challenge({
            challenger: msg.sender,
            agentId: _agentId,
            fraudProofHash: _fraudProofHash,
            submittedAt: block.timestamp,
            challengerStake: _stake,
            status: ChallengeStatus.OPEN,
            evidence: _evidence
        });
        
        agent.status = AgentStatus.CHALLENGED;
        totalChallenges++;
        
        emit ChallengeSubmitted(challengeId, _agentId, msg.sender, _stake);
        
        return challengeId;
    }
    
    /**
     * @notice Resolve a challenge (guardian or automated)
     * @param _challengeId Challenge to resolve
     * @param _fraudProven Whether fraud was proven
     */
    function resolveChallenge(
        bytes32 _challengeId,
        bool _fraudProven,
        bytes calldata /* _proof */
    ) external onlyRole(GUARDIAN_ROLE) nonReentrant {
        Challenge storage challenge = challenges[_challengeId];
        
        if (challenge.challenger == address(0)) revert ChallengeNotFound();
        if (challenge.status != ChallengeStatus.OPEN) revert ChallengeAlreadyResolved();
        
        Agent storage agent = agents[challenge.agentId];
        uint256 slashAmount = 0;
        
        if (_fraudProven) {
            // Fraud proven: slash agent, reward challenger
            challenge.status = ChallengeStatus.PROVEN;
            agent.status = AgentStatus.SLASHED;
            
            slashAmount = (agent.stake * CHALLENGER_REWARD_BPS) / BPS_DENOMINATOR;
            
            // Transfer reward to challenger: 50% of slashed stake
            IERC20(vamsToken).transfer(challenge.challenger, slashAmount);
            
            // Return challenger's original stake
            IERC20(vamsToken).transfer(challenge.challenger, challenge.challengerStake);
            
            // Remaining 50% stays in contract (effectively burned or sent to insurance in future)
            // agent.stake was total, so we reduce it
            agent.stake -= slashAmount;
            
        } else {
            // Challenge rejected: slash challenger
            challenge.status = ChallengeStatus.REJECTED;
            agent.status = AgentStatus.ACTIVE;
            
            // Challenger loses stake (stays in contract)
            slashAmount = challenge.challengerStake;
            challenge.challengerStake = 0;
            
            // Note: In a real implementation we might burn this or send to insurance
        }
        
        emit ChallengeResolved(_challengeId, challenge.status, slashAmount);
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Get agent details
     */
    function getAgent(bytes32 _agentId) external view returns (
        address owner,
        bytes32 publicKeyHash,
        uint256 stake,
        AgentStatus status,
        uint256 registeredAt,
        uint256 finalizedAt,
        bytes32 latestMerkleRoot
    ) {
        Agent storage agent = agents[_agentId];
        return (
            agent.owner,
            agent.publicKeyHash,
            agent.stake,
            agent.status,
            agent.registeredAt,
            agent.finalizedAt,
            agent.latestMerkleRoot
        );
    }
    
    /**
     * @notice Check if agent is active and operational
     */
    function isAgentActive(bytes32 _agentId) external view returns (bool) {
        Agent storage agent = agents[_agentId];
        return agent.status == AgentStatus.ACTIVE && agent.stake >= MIN_REGISTRATION_STAKE;
    }
    
    /**
     * @notice Check if agent's challenge window has expired
     */
    function isChallengeWindowExpired(bytes32 _agentId) external view returns (bool) {
        return block.timestamp >= agents[_agentId].finalizedAt;
    }
    
    /**
     * @notice Get agents owned by an address
     */
    function getAgentsByOwner(address _owner) external view returns (bytes32[] memory) {
        return ownerAgents[_owner];
    }
    
    /**
     * @notice Get Merkle history for an agent
     */
    function getMerkleHistory(bytes32 _agentId) external view returns (MerkleSubmission[] memory) {
        return merkleHistory[_agentId];
    }
    
    /**
     * @notice Get remaining time in challenge window
     */
    function getChallengeWindowRemaining(bytes32 _agentId) external view returns (uint256) {
        Agent storage agent = agents[_agentId];
        if (block.timestamp >= agent.finalizedAt) return 0;
        return agent.finalizedAt - block.timestamp;
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Update slasher contract address
     */
    function setSlasher(address _slasher) external onlyRole(DEFAULT_ADMIN_ROLE) {
        slasher = _slasher;
    }
    
    /**
     * @notice Emergency pause
     */
    function pause() external onlyRole(GUARDIAN_ROLE) {
        _pause();
    }
    
    /**
     * @notice Unpause
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}
