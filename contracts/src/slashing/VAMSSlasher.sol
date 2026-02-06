// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
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
    ReentrancyGuardUpgradeable 
{
    using SlashingParameters for *;
    
    // ============ Roles ============
    
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");
    bytes32 public constant JAIL_MANAGER_ROLE = keccak256("JAIL_MANAGER_ROLE");
    
    // ============ Enums ============
    
    enum OffenseType {
        LIVENESS_MINOR,
        LIVENESS_MEDIUM,
        EQUIVOCATION,
        MALICIOUS_INPUT
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
    
    function initialize(
        address _admin,
        address _insuranceFund
    ) public initializer {
        __AccessControl_init();
        __ReentrancyGuard_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(SLASHER_ROLE, _admin);
        _grantRole(JAIL_MANAGER_ROLE, _admin);
        
        insuranceFund = _insuranceFund;
    }
    
    // ============ Operator Management ============
    
    /**
     * @notice Register an operator with stake
     */
    function registerOperator(address _operator, uint256 _stake) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_stake < SlashingParameters.MIN_OPERATOR_STAKE) {
            revert InsufficientStake(SlashingParameters.MIN_OPERATOR_STAKE, _stake);
        }
        
        operators[_operator] = OperatorRecord({
            stake: _stake,
            status: OperatorStatus.ACTIVE,
            jailedUntil: 0,
            livenessOffenses: 0,
            equivocationOffenses: 0,
            totalSlashed: 0
        });
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
            emit VictimCompensated(_victim, result.victimCompensation);
        }
        
        // Always tombstone for malicious
        op.status = OperatorStatus.TOMBSTONED;
        emit OperatorTombstoned(_operator, "Malicious input");
        emit OperatorSlashed(_operator, OffenseType.MALICIOUS_INPUT, result.slashAmount, 0);
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
        
        // Escalation: 1.5^n capped at 5x
        uint256 multiplier = SlashingParameters.BPS_DENOMINATOR;
        for (uint256 i = 0; i < _priorOffenses; i++) {
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
        
        // Handle burns (in real impl, transfer tokens)
        if (_result.burnAmount > 0) {
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
     * @dev Proof format: [32 bytes msgHash1][65 bytes sig1][32 bytes msgHash2][65 bytes sig2]
     * Both signatures must be from the same operator but on different data at same height
     */
    function _verifyEquivocationProof(
        address _operator,
        bytes calldata _proof
    ) internal pure returns (bool) {
        // Minimum proof length: 2 x (32 bytes hash + 65 bytes signature) = 194 bytes
        if (_proof.length < 194) return false;
        
        // Extract messages and signatures
        bytes32 msgHash1 = bytes32(_proof[0:32]);
        bytes memory sig1 = _proof[32:97];
        bytes32 msgHash2 = bytes32(_proof[97:129]);
        bytes memory sig2 = _proof[129:194];
        
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
        }
        
        return true;
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
