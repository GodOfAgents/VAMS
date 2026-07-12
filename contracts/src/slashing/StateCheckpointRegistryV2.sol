// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title StateCheckpointRegistryV2
 * @author VAMS Protocol
 * @notice Validates off-chain state checkpoints (e.g., DBOS) with optimistic fraud proofs, challenger rewards, and operator bonds.
 */
contract StateCheckpointRegistryV2 is AccessControl {
    using SafeERC20 for IERC20;

    bytes32 public constant ARBITRATOR_ROLE = keccak256("ARBITRATOR_ROLE");

    IERC20 public immutable vamsToken;

    uint256 public constant CHALLENGE_PERIOD = 7 days;
    uint256 public constant REQUIRED_BOND = 50_000e18; // 50,000 VAMS required to submit or challenge

    struct Checkpoint {
        bytes32 stateRoot;
        address operator;
        uint256 submittedAt;
        bool finalized;
        bool challenged;
        address challenger;
    }

    // stateRoot => Checkpoint
    mapping(bytes32 => Checkpoint) public checkpoints;

    event CheckpointSubmitted(bytes32 indexed stateRoot, address indexed operator, uint256 timestamp);
    event CheckpointChallenged(bytes32 indexed stateRoot, address indexed challenger, uint256 timestamp);
    event CheckpointFinalized(bytes32 indexed stateRoot, uint256 timestamp);
    event DisputeResolved(bytes32 indexed stateRoot, address indexed winner, address indexed loser, uint256 slashedAmount);

    constructor(address _admin, address _vamsToken) {
        require(_admin != address(0) && _vamsToken != address(0), "Zero address");
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        vamsToken = IERC20(_vamsToken);
    }

    /**
     * @notice Submit a new state root checkpoint with a bond
     */
    function submitCheckpoint(bytes32 _stateRoot) external {
        require(checkpoints[_stateRoot].submittedAt == 0, "Checkpoint already exists");

        // Take operator bond
        vamsToken.safeTransferFrom(msg.sender, address(this), REQUIRED_BOND);

        checkpoints[_stateRoot] = Checkpoint({
            stateRoot: _stateRoot,
            operator: msg.sender,
            submittedAt: block.timestamp,
            finalized: false,
            challenged: false,
            challenger: address(0)
        });

        emit CheckpointSubmitted(_stateRoot, msg.sender, block.timestamp);
    }

    /**
     * @notice Challenge an unfinalized checkpoint by matching the bond
     */
    function challengeCheckpoint(bytes32 _stateRoot) external {
        Checkpoint storage cp = checkpoints[_stateRoot];
        require(cp.submittedAt > 0, "Checkpoint missing");
        require(!cp.finalized, "Already finalized");
        require(!cp.challenged, "Already challenged");
        require(block.timestamp <= cp.submittedAt + CHALLENGE_PERIOD, "Challenge period over");

        // Take challenger bond
        vamsToken.safeTransferFrom(msg.sender, address(this), REQUIRED_BOND);

        cp.challenged = true;
        cp.challenger = msg.sender;

        emit CheckpointChallenged(_stateRoot, msg.sender, block.timestamp);
    }

    /**
     * @notice Finalize a checkpoint if the challenge period has passed without dispute
     */
    function finalizeCheckpoint(bytes32 _stateRoot) external {
        Checkpoint storage cp = checkpoints[_stateRoot];
        require(cp.submittedAt > 0, "Checkpoint missing");
        require(!cp.finalized, "Already finalized");
        require(!cp.challenged, "Cannot finalize challenged checkpoint");
        require(block.timestamp > cp.submittedAt + CHALLENGE_PERIOD, "Challenge period active");

        cp.finalized = true;

        // Return operator bond
        vamsToken.safeTransfer(cp.operator, REQUIRED_BOND);

        emit CheckpointFinalized(_stateRoot, block.timestamp);
    }

    /**
     * @notice Resolve a dispute via Arbitration Committee
     * @param _stateRoot The disputed checkpoint root
     * @param _operatorWins True if the operator is correct, False if the challenger is correct
     */
    function resolveDispute(bytes32 _stateRoot, bool _operatorWins) external onlyRole(ARBITRATOR_ROLE) {
        Checkpoint storage cp = checkpoints[_stateRoot];
        require(cp.submittedAt > 0, "Checkpoint missing");
        require(cp.challenged, "Checkpoint not challenged");
        require(!cp.finalized, "Already finalized"); // Disputed checkpoints don't finalize normally, but they can be marked

        // Total bond pool is REQUIRED_BOND (operator) + REQUIRED_BOND (challenger) = 2 * REQUIRED_BOND
        uint256 totalPool = REQUIRED_BOND * 2;

        if (_operatorWins) {
            // Operator was correct. Slashes challenger's bond.
            // Operator gets back their bond + the challenger's bond as a reward
            cp.finalized = true; // Still becomes a valid checkpoint
            vamsToken.safeTransfer(cp.operator, totalPool);
            emit DisputeResolved(_stateRoot, cp.operator, cp.challenger, REQUIRED_BOND);
        } else {
            // Challenger was correct (fraud proven). Slashes operator's bond.
            // Challenger gets back their bond + the operator's bond as a reward
            // Note: cp.finalized remains false forever (checkpoint is invalid)
            vamsToken.safeTransfer(cp.challenger, totalPool);
            emit DisputeResolved(_stateRoot, cp.challenger, cp.operator, REQUIRED_BOND);
        }
    }
}
