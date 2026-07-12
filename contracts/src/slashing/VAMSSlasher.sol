// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "./SlashingParameters.sol";

/**
 * @title VAMSSlasher
 * @author VAMS Protocol
 * @notice Handles slashing calculations and execution for operators/providers
 * @dev Uses SlashingParameters library for all constants
 */
contract VAMSSlasher is 
    Initializable, 
    AccessControlUpgradeable,
    ReentrancyGuard
{
    using SlashingParameters for *;
    using SafeERC20 for IERC20;
    
    // ============ Roles ============
    
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");
    bytes32 public constant JAIL_MANAGER_ROLE = keccak256("JAIL_MANAGER_ROLE");
    
    // ============ Enums ============
    
    enum OffenseType {
        LIVENESS_MINOR,
        LIVENESS_MEDIUM,
        EQUIVOCATION,
        MALICIOUS_INPUT,
        SLA_CAPACITY,
        SLA_OFFLINE,
        SLA_FRAUD
    }
    
    enum OperatorStatus {
        ACTIVE,
        JAILED,
        TOMBSTONED
    }
    
    // ============ Structs ============
    
    struct OperatorRecord {
        uint256 stake;
        OperatorStatus status;
        uint256 jailedUntil;
        uint256 livenessOffenses;
        uint256 equivocationOffenses;
        uint256 totalSlashed;
    }
    
    struct SlashResult {
        uint256 slashAmount;
        uint256 jailDuration;
        uint256 victimCompensation;
        uint256 burnAmount;
        bool tombstone;
    }
    
    // ============ State ============
    
    /// @notice Operator records by address
    mapping(address => OperatorRecord) public operators;
    
    /// @notice Total amount slashed across all operators
    uint256 public totalSlashed;
    
    /// @notice Burn address
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;
    
    /// @notice Insurance fund address
    address public insuranceFund;
    
    /// @notice Token used for staking
    address public vamsToken;
    
    // ============ Events ============
    
    event OperatorSlashed(
        address indexed operator,
        OffenseType indexed offense,
        uint256 slashAmount,
        uint256 jailDuration
    );
    event OperatorJailed(address indexed operator, uint256 until);
    event OperatorUnjailed(address indexed operator);
    event OperatorTombstoned(address indexed operator, string reason);
    event VictimCompensated(address indexed victim, uint256 amount);
    event TokensBurned(uint256 amount);
    
    // ============ Errors ============
    
    error OperatorNotFound();
    error OperatorAlreadyTombstoned();
    error OperatorStillJailed(uint256 jailedUntil);
    error InsufficientStake(uint256 required, uint256 actual);
    error InvalidEquivocationProof();
    error InvalidMaliciousEvidence();
    
    // ============ Initializer ============
    
    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }
    
    function initialize(
        address _admin,
        address _insuranceFund,
        address _vamsToken
    ) public initializer {
        __AccessControl_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(SLASHER_ROLE, _admin);
        _grantRole(JAIL_MANAGER_ROLE, _admin);
        
        insuranceFund = _insuranceFund;
        vamsToken = _vamsToken;
    }
    
    // ============ Operator Management ============
    
    /**
     * @notice Register an operator with stake
     */
    function registerOperator(address _operator, uint256 _stake) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_stake < SlashingParameters.MIN_OPERATOR_STAKE) {
            revert InsufficientStake(SlashingParameters.MIN_OPERATOR_STAKE, _stake);
        }
        
        IERC20(vamsToken).safeTransferFrom(msg.sender, address(this), _stake);
        
        operators[_operator] = OperatorRecord({
            stake: _stake,
            status: OperatorStatus.ACTIVE,
            jailedUntil: 0,
            livenessOffenses: 0,
            equivocationOffenses: 0,
            totalSlashed: 0
        });
    }

    /**
     * @notice Withdraw operator stake
     */
    function withdrawStake(address _operator) external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        OperatorRecord storage op = operators[_operator];
        
        if (op.status == OperatorStatus.TOMBSTONED) revert OperatorAlreadyTombstoned();
        if (op.status == OperatorStatus.JAILED && block.timestamp < op.jailedUntil) revert OperatorStillJailed(op.jailedUntil);
        
        uint256 amount = op.stake;
        if (amount == 0) revert OperatorNotFound();
        
        op.stake = 0;
        op.status = OperatorStatus.TOMBSTONED; // Effectively deregistered
        
        IERC20(vamsToken).safeTransfer(_operator, amount);
    }
    
    // ============ Slashing Functions ============
    
    /**
     * @notice Slash for liveness failure (missed heartbeats)
     * @param _operator Operator address
     * @param _missedBlocks Number of missed blocks/heartbeats
     */
    function slashLiveness(
        address _operator,
        uint256 _missedBlocks
    ) external onlyRole(SLASHER_ROLE) nonReentrant returns (SlashResult memory result) {
        OperatorRecord storage op = operators[_operator];
        _validateOperator(op);
        
        result = _calculateLivenessSlash(op.stake, _missedBlocks, op.livenessOffenses);
        
        if (result.slashAmount > 0) {
            _executeSlash(_operator, op, result);
            op.livenessOffenses++;
            
            emit OperatorSlashed(_operator, 
                _missedBlocks >= SlashingParameters.SLASH_LIVENESS_THRESHOLD_MED 
                    ? OffenseType.LIVENESS_MEDIUM 
                    : OffenseType.LIVENESS_MINOR,
                result.slashAmount,
                result.jailDuration
            );
        }
    }
    
    /**
     * @notice Slash for equivocation (double-signing)
     * @param _operator Operator address
     * @param _proof Cryptographic proof of double-sign
     */
    function slashEquivocation(
        address _operator,
        bytes calldata _proof
    ) external onlyRole(SLASHER_ROLE) nonReentrant returns (SlashResult memory result) {
        OperatorRecord storage op = operators[_operator];
        _validateOperator(op);
        
        // Verify proof cryptographically
        if (!_verifyEquivocationProof(_operator, _proof)) {
            revert InvalidEquivocationProof();
        }
        
        result = _calculateEquivocationSlash(op.stake, op.equivocationOffenses);
        
        _executeSlash(_operator, op, result);
        op.equivocationOffenses++;
        
        if (result.tombstone) {
            op.status = OperatorStatus.TOMBSTONED;
            emit OperatorTombstoned(_operator, "Equivocation: 3 strikes");
        }
        
        emit OperatorSlashed(_operator, OffenseType.EQUIVOCATION, result.slashAmount, result.jailDuration);
    }
    
    /**
     * @notice Slash for malicious input
     * @param _operator Operator address
     * @param _victim Victim address (receives compensation)
     * @param _evidence Evidence of malicious behavior
     */
    function slashMalicious(
        address _operator,
        address _victim,
        bytes calldata _evidence
    ) external onlyRole(SLASHER_ROLE) nonReentrant returns (SlashResult memory result) {
        OperatorRecord storage op = operators[_operator];
        _validateOperator(op);
        
        // Validate evidence
        if (!_validateMaliciousEvidence(_operator, _victim, _evidence)) {
            revert InvalidMaliciousEvidence();
        }
        
        result = _calculateMaliciousSlash(op.stake, _victim);
        
        _executeSlash(_operator, op, result);
        
        // Compensate victim
        if (result.victimCompensation > 0 && _victim != address(0)) {
            // Transfer compensation (assumes this contract holds slashed tokens)
            IERC20(vamsToken).safeTransfer(_victim, result.victimCompensation);
            emit VictimCompensated(_victim, result.victimCompensation);
        }
        
        // Always tombstone for malicious
        op.status = OperatorStatus.TOMBSTONED;
        emit OperatorTombstoned(_operator, "Malicious input");
        emit OperatorSlashed(_operator, OffenseType.MALICIOUS_INPUT, result.slashAmount, 0);
    }
    
    /**
     * @notice Slash for SLA violation reported by Sentinel network
     * @param _operator Operator address
     * @param _offenseType The specific SLA offense
     * @param _customBps Optional custom slash bps if overriding standard penalty
     */
    function slashSLA(
        address _operator,
        OffenseType _offenseType,
        uint256 _customBps
    ) external onlyRole(SLASHER_ROLE) nonReentrant returns (SlashResult memory result) {
        OperatorRecord storage op = operators[_operator];
        _validateOperator(op);
        
        uint256 penaltyBps = _customBps;
        if (penaltyBps == 0) {
            if (_offenseType == OffenseType.SLA_CAPACITY) penaltyBps = SlashingParameters.SLA_CAPACITY_PENALTY_BPS;
            else if (_offenseType == OffenseType.SLA_OFFLINE) penaltyBps = SlashingParameters.SLA_OFFLINE_PENALTY_BPS;
            else if (_offenseType == OffenseType.SLA_FRAUD) penaltyBps = SlashingParameters.SLA_FRAUD_PENALTY_BPS;
        }

        result.slashAmount = (op.stake * penaltyBps) / SlashingParameters.BPS_DENOMINATOR;
        result.burnAmount = result.slashAmount; // SLA penalties are burned
        result.jailDuration = 1 days; // default jail for SLA
        
        if (_offenseType == OffenseType.SLA_FRAUD) {
            result.tombstone = true;
            result.jailDuration = type(uint256).max;
        }

        _executeSlash(_operator, op, result);
        
        if (result.tombstone) {
            op.status = OperatorStatus.TOMBSTONED;
            emit OperatorTombstoned(_operator, "SLA Fraud");
        }
        
        emit OperatorSlashed(_operator, _offenseType, result.slashAmount, result.jailDuration);
    }
    
    // ============ Jail Management ============
    
    /**
     * @notice Unjail an operator after jail period
     */
    function unjail(address _operator) external onlyRole(JAIL_MANAGER_ROLE) {
        OperatorRecord storage op = operators[_operator];
        
        if (op.status == OperatorStatus.TOMBSTONED) revert OperatorAlreadyTombstoned();
        if (block.timestamp < op.jailedUntil) revert OperatorStillJailed(op.jailedUntil);
        
        op.status = OperatorStatus.ACTIVE;
        op.jailedUntil = 0;
        
        emit OperatorUnjailed(_operator);
    }
    
    // ============ Internal: Calculation Functions ============
    
    function _calculateLivenessSlash(
        uint256 _stake,
        uint256 _missedBlocks,
        uint256 _priorOffenses
    ) internal pure returns (SlashResult memory result) {
        uint256 penaltyBps;
        
        if (_missedBlocks >= SlashingParameters.SLASH_LIVENESS_THRESHOLD_MED) {
            penaltyBps = SlashingParameters.SLASH_LIVENESS_PENALTY_MED_BPS;
            result.jailDuration = SlashingParameters.SLASH_LIVENESS_JAIL_MED;
        } else if (_missedBlocks >= SlashingParameters.SLASH_LIVENESS_THRESHOLD_LOW) {
            penaltyBps = SlashingParameters.SLASH_LIVENESS_PENALTY_LOW_BPS;
            result.jailDuration = SlashingParameters.SLASH_LIVENESS_JAIL_LOW;
        } else {
            return result; // No slash
        }
        
        // Escalation: 1.5^n capped at 5x (Max 10 iterations to prevent gas DoS)
        uint256 multiplier = SlashingParameters.BPS_DENOMINATOR;
        uint256 maxIters = _priorOffenses > 10 ? 10 : _priorOffenses;
        for (uint256 i = 0; i < maxIters; i++) {
            multiplier = (multiplier * SlashingParameters.SLASH_REPEAT_MULTIPLIER_BPS) / SlashingParameters.BPS_DENOMINATOR;
            if (multiplier >= SlashingParameters.SLASH_MAX_MULTIPLIER_BPS) {
                multiplier = SlashingParameters.SLASH_MAX_MULTIPLIER_BPS;
                break;
            }
        }
        
        result.slashAmount = (_stake * penaltyBps * multiplier) / (SlashingParameters.BPS_DENOMINATOR * SlashingParameters.BPS_DENOMINATOR);
        result.burnAmount = result.slashAmount; // 100% burned for liveness
    }
    
    function _calculateEquivocationSlash(
        uint256 _stake,
        uint256 _priorEquivocations
    ) internal pure returns (SlashResult memory result) {
        uint256 offenseCount = _priorEquivocations + 1;
        
        if (offenseCount >= SlashingParameters.SLASH_EQUIVOCATION_TOMBSTONE_COUNT) {
            // Tombstone: slash 100%
            result.slashAmount = _stake;
            result.jailDuration = type(uint256).max;
            result.tombstone = true;
        } else {
            // Progressive: 5% × offense count
            uint256 penaltyBps = SlashingParameters.SLASH_EQUIVOCATION_PENALTY_BPS * offenseCount;
            result.slashAmount = (_stake * penaltyBps) / SlashingParameters.BPS_DENOMINATOR;
            result.jailDuration = SlashingParameters.SLASH_EQUIVOCATION_JAIL;
        }
        
        result.burnAmount = result.slashAmount / 2; // 50% burned
        result.victimCompensation = result.slashAmount - result.burnAmount; // 50% to insurance
    }
    
    function _calculateMaliciousSlash(
        uint256 _stake,
        address _victim
    ) internal pure returns (SlashResult memory result) {
        result.slashAmount = (_stake * SlashingParameters.SLASH_MALICIOUS_PENALTY_BPS) / SlashingParameters.BPS_DENOMINATOR;
        result.tombstone = true;
        
        if (_victim != address(0)) {
            result.victimCompensation = (result.slashAmount * SlashingParameters.SLASH_MALICIOUS_VICTIM_SHARE_BPS) / SlashingParameters.BPS_DENOMINATOR;
        }
        
        result.burnAmount = result.slashAmount - result.victimCompensation;
    }
    
    // ============ Internal: Execution ============
    
    function _validateOperator(OperatorRecord storage _op) internal view {
        if (_op.stake == 0) revert OperatorNotFound();
        if (_op.status == OperatorStatus.TOMBSTONED) revert OperatorAlreadyTombstoned();
    }
    
    function _executeSlash(
        address _operator,
        OperatorRecord storage _op,
        SlashResult memory _result
    ) internal {
        // Reduce stake
        _op.stake -= _result.slashAmount;
        _op.totalSlashed += _result.slashAmount;
        totalSlashed += _result.slashAmount;
        
        // Jail if applicable
        if (_result.jailDuration > 0 && _result.jailDuration < type(uint256).max) {
            _op.status = OperatorStatus.JAILED;
            _op.jailedUntil = block.timestamp + _result.jailDuration;
            emit OperatorJailed(_operator, _op.jailedUntil);
        }
        
        // Handle burns
        if (_result.burnAmount > 0) {
            IERC20(vamsToken).safeTransfer(BURN_ADDRESS, _result.burnAmount);
            emit TokensBurned(_result.burnAmount);
        }
    }
    
    // ============ View Functions ============
    
    function getOperatorStatus(address _operator) external view returns (
        uint256 stake,
        OperatorStatus status,
        uint256 jailedUntil,
        uint256 livenessOffenses,
        uint256 equivocationOffenses,
        uint256 slashedTotal
    ) {
        OperatorRecord storage op = operators[_operator];
        return (
            op.stake,
            op.status,
            op.jailedUntil,
            op.livenessOffenses,
            op.equivocationOffenses,
            op.totalSlashed
        );
    }
    
    function isOperatorActive(address _operator) external view returns (bool) {
        OperatorRecord storage op = operators[_operator];
        return op.status == OperatorStatus.ACTIVE && op.stake >= SlashingParameters.MIN_OPERATOR_STAKE;
    }
    
    // ============ Internal: Verification Functions ============
    
    /**
     * @notice Verify equivocation proof (double-signing)
     * @dev Proof format: [8 bytes blockInfo][32 bytes msgHash1][65 bytes sig1][32 bytes msgHash2][65 bytes sig2]
     * Both signatures must be from the same operator but on different data at same height
     */
    function _verifyEquivocationProof(
        address _operator,
        bytes calldata _proof
    ) internal view returns (bool) {
        // Minimum proof length: 8 + 2 x (32 bytes hash + 65 bytes signature) = 202 bytes
        if (_proof.length < 202) return false;
        
        // Extract height and messages
        uint64 blockHeight = uint64(bytes8(_proof[0:8]));
        if (blockHeight > block.number) return false;
        
        bytes32 msgHash1 = bytes32(_proof[8:40]);
        bytes memory sig1 = _proof[40:105];
        bytes32 msgHash2 = bytes32(_proof[105:137]);
        bytes memory sig2 = _proof[137:202];
        
        // Messages must be different (proof of double-sign)
        if (msgHash1 == msgHash2) return false;
        
        // Recover signers
        bytes32 ethHash1 = MessageHashUtils.toEthSignedMessageHash(msgHash1);
        bytes32 ethHash2 = MessageHashUtils.toEthSignedMessageHash(msgHash2);
        
        address signer1 = ECDSA.recover(ethHash1, sig1);
        address signer2 = ECDSA.recover(ethHash2, sig2);
        
        // Both signatures must be from the same operator
        if (signer1 != _operator || signer2 != _operator) return false;
        
        // If we reach here, operator signed two different messages
        // In a real implementation, we would also verify:
        // - Both messages are for the same block height/round
        // - Messages are valid protocol messages
        // This is simplified for the initial implementation
        
        return true;
    }
    
    /**
     * @notice Validate malicious behavior evidence
     * @dev Evidence format: [1 byte type][variable evidence data]
     * Types: 0x01 = Invalid computation, 0x02 = Censorship, 0x03 = Data manipulation
     */
    function _validateMaliciousEvidence(
        address _operator,
        address _victim,
        bytes calldata _evidence
    ) internal view returns (bool) {
        // Evidence must have at least a type byte
        if (_evidence.length < 1) return false;
        
        uint8 evidenceType = uint8(_evidence[0]);
        
        // Validate evidence type is known
        if (evidenceType == 0 || evidenceType > 3) return false;
        
        // Validate operator exists and is active/jailed (not tombstoned)
        OperatorRecord storage op = operators[_operator];
        if (op.stake == 0) return false;
        if (op.status == OperatorStatus.TOMBSTONED) return false;
        
        // For type 0x01 (Invalid computation): requires computation proof
        // For type 0x02 (Censorship): requires transaction inclusion proof
        // For type 0x03 (Data manipulation): requires before/after hash proof
        // Simplified validation - in production would have type-specific checks
        
        // Evidence must include victim signature if victim provided
        if (_victim != address(0) && _evidence.length >= 66) {
            // Last 65 bytes should be victim's signature on evidence
            bytes32 evidenceHash = keccak256(_evidence[0:_evidence.length - 65]);
            bytes memory victimSig = _evidence[_evidence.length - 65:];
            
            bytes32 ethHash = MessageHashUtils.toEthSignedMessageHash(evidenceHash);
            address recovered = ECDSA.recover(ethHash, victimSig);
            
            // Victim must have signed the evidence
            if (recovered != _victim) return false;
        } else {
            // M-02: Explicitly reject address(0) for victim when evidence requires validation
            // to prevent bypassing signature check.
            return false;
        }
        
        return true;
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
