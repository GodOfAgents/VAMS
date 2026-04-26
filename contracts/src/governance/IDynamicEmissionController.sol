// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IDynamicEmissionController
 * @author VAMS Protocol
 * @notice Interface for the Dynamic Emission Controller (RL Model Governance)
 */
interface IDynamicEmissionController {
    // ============ Events ============

    event AdjustmentApplied(uint256 newEmissionRate, uint256 newFeeMultiplier, uint256 timestamp);
    event RollbackTriggered(string reason, uint256 previousEmission, uint256 previousFee);
    event BaselineModeActivated(uint256 epoch);
    event NormalModeRestored(uint256 epoch);
    event SignerUpdated(address indexed signer, bool active);
    event DaoSignerUpdated(address indexed signer, bool active);

    // ============ Functions ============

    /**
     * @notice Apply RL-recommended adjustment with safety checks
     * @param _newEmissionRate Recommended emission rate in bps
     * @param _newFeeMultiplier Recommended fee multiplier in bps
     * @param _modelSignature Centralized operator or consensus signature
     */
    function applyAdjustment(
        uint256 _newEmissionRate,
        uint256 _newFeeMultiplier,
        bytes calldata _modelSignature
    ) external;

    /**
     * @notice Restore normal RL execution mode after a fallback
     * @param _daoSignatures Signatures from DAO multisig for recovery
     */
    function restoreNormalMode(bytes[] calldata _daoSignatures) external;

    /**
     * @notice Get the current emission rate in BPS
     * @return The current emission rate (e.g. 200 = 2%)
     */
    function currentEmissionRate() external view returns (uint256);
}
