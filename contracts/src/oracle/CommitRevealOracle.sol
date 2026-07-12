// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "./OracleRegistry.sol";

/**
 * @title CommitRevealOracle
 * @author VAMS Protocol
 * @notice 2-phase commit-and-reveal scheme for agent data provisioning
 */
contract CommitRevealOracle is AccessControl {
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");

    IOracleRegistry public immutable registry;
    bytes32 public immutable staleFallbackValue;
    IOracleRegistry.Category public category;

    struct Request {
        uint256 id;
        uint256 expectedResolvesAt;
        bool resolved;
        bytes32 finalValue;
    }

    struct Commit {
        bytes32 commitHash;
        uint256 committedAt;
        bool revealed;
    }

    uint256 public nextRequestId = 1;

    // request ID => Request
    mapping(uint256 => Request) public requests;
    // request ID => oracle => Commit
    mapping(uint256 => mapping(address => Commit)) public commits;
    // request ID => array of revealed values (for quorum)
    mapping(uint256 => bytes32[]) public revealedValues;
    // request ID => value => count
    mapping(uint256 => mapping(bytes32 => uint256)) public valueCounts;
    // request ID => oracle => revealed value
    mapping(uint256 => mapping(address => bytes32)) public oracleReveals;

    uint256 public constant COMMIT_PHASE_DURATION = 1 hours;
    uint256 public constant REVEAL_PHASE_DURATION = 1 hours;

    // ============ Custom Errors ============
    error ZeroAddress();
    error NotAuthorizedOracle();
    error RequestDoesNotExist();
    error RequestAlreadyResolved();
    error CommitPhaseOver();
    error CommitPhaseNotOver();
    error RevealPhaseOver();
    error AlreadyCommitted();
    error DidNotCommit();
    error AlreadyRevealed();
    error HashMismatch();
    error RequestNotStale();

    event RequestCreated(uint256 indexed requestId, uint256 expectedResolvesAt);
    event Committed(uint256 indexed requestId, address indexed oracle);
    event Revealed(uint256 indexed requestId, address indexed oracle, bytes32 value);
    event RequestResolved(uint256 indexed requestId, bytes32 finalValue);
    event StaleRequestResolved(uint256 indexed requestId, bytes32 fallbackValue);

    constructor(
        address _admin,
        address _registry,
        IOracleRegistry.Category _category,
        bytes32 _staleFallbackValue
    ) {
        if (_admin == address(0) || _registry == address(0)) revert ZeroAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);

        registry = IOracleRegistry(_registry);
        category = _category;
        staleFallbackValue = _staleFallbackValue;
    }

    /**
     * @notice Create a new request for data
     */
    function createRequest() external returns (uint256) {
        uint256 id = nextRequestId++;
        requests[id] = Request({
            id: id,
            expectedResolvesAt: block.timestamp + COMMIT_PHASE_DURATION + REVEAL_PHASE_DURATION,
            resolved: false,
            finalValue: bytes32(0)
        });

        emit RequestCreated(id, requests[id].expectedResolvesAt);
        return id;
    }

    /**
     * @notice Commit a hidden value
     * @param requestId The ID of the request
     * @param commitHash keccak256(abi.encodePacked(value, salt))
     */
    function commit(uint256 requestId, bytes32 commitHash) external {
        if (!registry.isAuthorizedOracle(msg.sender, category)) revert NotAuthorizedOracle();
        
        Request storage req = requests[requestId];
        if (req.id == 0) revert RequestDoesNotExist();
        if (req.resolved) revert RequestAlreadyResolved();
        if (block.timestamp > req.expectedResolvesAt - REVEAL_PHASE_DURATION) revert CommitPhaseOver();
        if (commits[requestId][msg.sender].committedAt != 0) revert AlreadyCommitted();

        commits[requestId][msg.sender] = Commit({
            commitHash: commitHash,
            committedAt: block.timestamp,
            revealed: false
        });

        emit Committed(requestId, msg.sender);
    }

    /**
     * @notice Reveal the hidden value
     * @param requestId The ID of the request
     * @param value The actual value
     * @param salt The salt used for the commit
     */
    function reveal(uint256 requestId, bytes32 value, bytes32 salt) external {
        Request storage req = requests[requestId];
        if (req.id == 0) revert RequestDoesNotExist();
        if (req.resolved) revert RequestAlreadyResolved();

        uint256 commitEnd = req.expectedResolvesAt - REVEAL_PHASE_DURATION;
        if (block.timestamp <= commitEnd) revert CommitPhaseNotOver();
        if (block.timestamp > req.expectedResolvesAt) revert RevealPhaseOver();

        Commit storage c = commits[requestId][msg.sender];
        if (c.committedAt == 0) revert DidNotCommit();
        if (c.revealed) revert AlreadyRevealed();

        bytes32 expectedHash = keccak256(abi.encodePacked(value, salt));
        if (expectedHash != c.commitHash) revert HashMismatch();

        c.revealed = true;
        revealedValues[requestId].push(value);
        valueCounts[requestId][value]++;
        oracleReveals[requestId][msg.sender] = value;

        emit Revealed(requestId, msg.sender, value);

        _tryResolve(requestId);
    }

    /**
     * @notice Try to resolve the value if quorum is reached
     */
    function _tryResolve(uint256 requestId) internal {
        IOracleRegistry.CategoryConfig memory config = registry.getCategoryConfig(category);
        uint256 totalReveals = revealedValues[requestId].length;

        if (totalReveals < config.minParticipants) {
            return;
        }

        // Check if any value has enough votes to pass the consensus threshold
        uint256 requiredVotes = (totalReveals * config.consensusThreshold + 9999) / 10000;
        if (requiredVotes == 0) requiredVotes = 1;

        for (uint256 i = 0; i < totalReveals; i++) {
            bytes32 val = revealedValues[requestId][i];
            if (valueCounts[requestId][val] >= requiredVotes) {
                requests[requestId].resolved = true;
                requests[requestId].finalValue = val;
                emit RequestResolved(requestId, val);
                return;
            }
        }
    }

    /**
     * @notice Get the resolved value of a request
     */
    function getResult(uint256 requestId) external view returns (bool resolved, bytes32 value) {
        Request storage req = requests[requestId];
        return (req.resolved, req.finalValue);
    }

    /**
     * @notice Resolve an expired request to the configured fail-closed fallback.
     * @dev Permissionless because blockchains cannot execute deadline transitions
     *      automatically. The fixed fallback prevents caller-selected stale values.
     */
    function resolveStaleRequest(uint256 requestId) external {
        Request storage req = requests[requestId];
        if (req.id == 0) revert RequestDoesNotExist();
        if (req.resolved) revert RequestAlreadyResolved();
        if (block.timestamp <= req.expectedResolvesAt) revert RequestNotStale();

        req.resolved = true;
        req.finalValue = staleFallbackValue;
        emit StaleRequestResolved(requestId, staleFallbackValue);
        emit RequestResolved(requestId, staleFallbackValue);
    }
}
