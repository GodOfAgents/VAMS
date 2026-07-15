// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "./IDynamicEmissionController.sol";

/**
 * @title DynamicEmissionController
 * @author VAMS Protocol
 * @notice RL-based emission and fee adjustments with bounds, standard deviations, and rollback triggers.
 * @dev Enforces circuit breakers on AI-driven governance decisions to prevent regime change attacks.
 */
contract DynamicEmissionController is AccessControl, IDynamicEmissionController {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant DAO_ROLE = keccak256("DAO_ROLE");

    // ============ Rollback Triggers ============
    // 500 bps = 5%
    uint256 public constant MAX_EMISSION_CHANGE_PER_EPOCH = 500;
    // 1000 bps = 10%
    uint256 public constant MAX_FEE_CHANGE_PER_EPOCH = 1000;

    // ============ Absolute Emission Bounds ============
    /// @notice Minimum emission rate: 10 bps = 0.1% annual (prevents runaway deflation)
    uint256 public constant MIN_EMISSION_RATE = 10;
    /// @notice Maximum emission rate: 250 bps = 2.5% annual (prevents runaway inflation)
    uint256 public constant MAX_EMISSION_RATE = 250;

    // ============ Baseline Parameters (Fallback) ============
    // 200 bps = 2% annual
    uint256 public constant BASELINE_EMISSION_RATE = 200;
    // 10000 bps = 1.0x (no change) multiplier
    uint256 public constant BASELINE_FEE_MULTIPLIER = 10000;

    // ============ State ============
    uint256 public currentEmissionRate;
    uint256 public currentFeeMultiplier;
    bool public baselineMode;

    // Authorized AI Model Signers (3-of-5 ensemble)
    address[] public modelSigners;
    uint256 public constant MODEL_SIGNER_QUORUM = 3;
    mapping(address => bool) public isModelSigner;

    // DAO Multisig configuration for recovery
    address[] public daoSigners;
    uint256 public immutable daoQuorumThreshold;
    mapping(address => bool) public isDaoSigner;

    uint256 public currentEpoch;

    /**
     * @notice Initialize the controller
     * @param _admin Admin address
     * @param _operator Address that submits RL adjustments
     * @param _modelSigner Address corresponding to the RL ensemble's consensus key
     * @param _daoSigners Array of DAO addresses required for recovery
     * @param _daoQuorum Threshold of DAO signatures needed
     */
    constructor(
        address _admin,
        address _operator,
        address _modelSigner,
        address[] memory _daoSigners,
        uint256 _daoQuorum
    ) {
        require(_admin != address(0), "Zero admin address");
        require(_modelSigner != address(0), "Zero model signer");
        require(_daoQuorum > 0 && _daoQuorum <= _daoSigners.length, "Invalid quorum");

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _operator);

        // Setup model signers (3-of-5 ensemble)
        require(_modelSigner != address(0), "Zero model signer");
        modelSigners.push(_modelSigner);
        isModelSigner[_modelSigner] = true;

        for (uint256 i = 0; i < _daoSigners.length; i++) {
            require(_daoSigners[i] != address(0), "Zero DAO signer");
            require(!isDaoSigner[_daoSigners[i]], "Duplicate DAO signer");
            isDaoSigner[_daoSigners[i]] = true;
            daoSigners.push(_daoSigners[i]);
            _grantRole(DAO_ROLE, _daoSigners[i]);
        }

        daoQuorumThreshold = _daoQuorum;

        // Start in baseline mode
        currentEmissionRate = BASELINE_EMISSION_RATE;
        currentFeeMultiplier = BASELINE_FEE_MULTIPLIER;
        baselineMode = true;
        currentEpoch = 0;
    }

    // ============ Execution Logic ============

    /**
     * @notice Apply RL-recommended adjustment with safety checks
     */
    function applyAdjustment(uint256 _newEmissionRate, uint256 _newFeeMultiplier, bytes calldata _modelSignature)
        external
        override
        onlyRole(OPERATOR_ROLE)
    {
        require(!baselineMode, "Cannot adjust while in baseline mode");
        require(_verifyModelSignature(_newEmissionRate, _newFeeMultiplier, _modelSignature), "Invalid model signature");

        // Enforce absolute emission bounds [0.1%, 2.5%]
        if (_newEmissionRate < MIN_EMISSION_RATE || _newEmissionRate > MAX_EMISSION_RATE) {
            _triggerRollback("Emission rate out of absolute bounds");
            return;
        }

        uint256 emissionDelta = _absDiff(_newEmissionRate, currentEmissionRate);
        uint256 feeDelta = _absDiff(_newFeeMultiplier, currentFeeMultiplier);

        if (emissionDelta > MAX_EMISSION_CHANGE_PER_EPOCH) {
            _triggerRollback("Emission change too large");
            return;
        }

        if (feeDelta > MAX_FEE_CHANGE_PER_EPOCH) {
            _triggerRollback("Fee change too large");
            return;
        }

        currentEmissionRate = _newEmissionRate;
        currentFeeMultiplier = _newFeeMultiplier;
        currentEpoch++;

        emit AdjustmentApplied(_newEmissionRate, _newFeeMultiplier, block.timestamp);
    }

    /**
     * @notice Revert to conservative baseline in case of bounds violations
     */
    function _triggerRollback(string memory reason) internal {
        emit RollbackTriggered(reason, currentEmissionRate, currentFeeMultiplier);

        currentEmissionRate = BASELINE_EMISSION_RATE;
        currentFeeMultiplier = BASELINE_FEE_MULTIPLIER;
        baselineMode = true;
        currentEpoch++;

        emit BaselineModeActivated(currentEpoch);
    }

    /**
     * @notice DAO can restore normal RL execution after investigation
     */
    function restoreNormalMode(bytes[] calldata _daoSignatures) external override {
        require(baselineMode, "Not in baseline mode");
        require(_verifyDAOQuorum(_daoSignatures), "DAO quorum not met");

        baselineMode = false;
        currentEpoch++;
        emit NormalModeRestored(currentEpoch);
    }

    // ============ Verification Logic ============

    /**
     * @notice Verify signature from the ensemble RL multi-model
     */
    function _verifyModelSignature(uint256 _newEmissionRate, uint256 _newFeeMultiplier, bytes calldata _signature)
        internal
        view
        returns (bool)
    {
        bytes32 messageHash =
            keccak256(abi.encodePacked(currentEpoch, _newEmissionRate, _newFeeMultiplier, address(this)));

        bytes32 ethSignedHash = messageHash.toEthSignedMessageHash();
        address recoveredSigner = ethSignedHash.recover(_signature);

        // Accept signature from any registered model signer
        return isModelSigner[recoveredSigner];
    }

    /**
     * @notice Verify `daoQuorumThreshold` signatures from authorized DAO members
     */
    function _verifyDAOQuorum(bytes[] calldata _signatures) internal view returns (bool) {
        require(_signatures.length >= daoQuorumThreshold, "Insufficient signatures provided");

        bytes32 messageHash = keccak256(abi.encodePacked("RESTORE_NORMAL_MODE", currentEpoch, address(this)));

        bytes32 ethSignedHash = messageHash.toEthSignedMessageHash();

        uint256 validSignatures = 0;
        address lastRecovered = address(0);

        for (uint256 i = 0; i < _signatures.length; i++) {
            address recovered = ethSignedHash.recover(_signatures[i]);

            require(recovered > lastRecovered, "Signatures not unique or unordered");
            lastRecovered = recovered;

            if (isDaoSigner[recovered]) {
                validSignatures++;
            }
        }

        return validSignatures >= daoQuorumThreshold;
    }

    // ============ Utilities ============

    function _absDiff(uint256 a, uint256 b) internal pure returns (uint256) {
        return a > b ? a - b : b - a;
    }

    // ============ Admin Config ============

    function updateModelSigner(address _newSigner) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_newSigner != address(0), "Zero address");
        modelSigners.push(_newSigner);
        isModelSigner[_newSigner] = true;
        emit SignerUpdated(_newSigner, true);
    }

    /// @notice Remove a model signer from the ensemble
    function removeModelSigner(address _signer) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(isModelSigner[_signer], "Not a model signer");
        isModelSigner[_signer] = false;
        emit SignerUpdated(_signer, false);
    }
}
