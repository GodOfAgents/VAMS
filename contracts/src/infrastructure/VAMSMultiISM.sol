// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title IInterchainSecurityModule
 * @notice Minimal Hyperlane ISM interface
 */
interface IInterchainSecurityModule {
    /**
     * @notice Defines a security model (e.g. routing, multisig, etc.)
     */
    function moduleType() external view returns (uint8);

    /**
     * @notice Verify a cross-chain message
     * @param _metadata ISM specific metadata
     * @param _message Formatted Hyperlane message
     * @return True if verified
     */
    function verify(bytes calldata _metadata, bytes calldata _message) external returns (bool);
}

/**
 * @title VAMSMultiISM
 * @author VAMS Protocol
 * @notice Aggregates multiple Hyperlane Interchain Security Modules (ISMs)
 * @dev Enforces a 2-of-3 threshold among Phala, Oracle, and Multisig ISMs
 */
contract VAMSMultiISM is AccessControl, IInterchainSecurityModule {
    bytes32 public constant CONFIGURER_ROLE = keccak256("CONFIGURER_ROLE");

    IInterchainSecurityModule public phalaISM;
    IInterchainSecurityModule public oracleISM;
    IInterchainSecurityModule public multisigISM;

    uint8 public constant THRESHOLD = 2; // 2 of 3 required

    event ISMConfigured(string ismType, address ismAddress);

    constructor(address _admin) {
        require(_admin != address(0), "Zero address not allowed");
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(CONFIGURER_ROLE, _admin);
    }

    /**
     * @notice Set the Phala TEE ISM
     */
    function setPhalaISM(address _ism) external onlyRole(CONFIGURER_ROLE) {
        require(_ism != address(0), "Zero address");
        phalaISM = IInterchainSecurityModule(_ism);
        emit ISMConfigured("PHALA", _ism);
    }

    /**
     * @notice Set the Oracle Network ISM
     */
    function setOracleISM(address _ism) external onlyRole(CONFIGURER_ROLE) {
        require(_ism != address(0), "Zero address");
        oracleISM = IInterchainSecurityModule(_ism);
        emit ISMConfigured("ORACLE", _ism);
    }

    /**
     * @notice Set the Governance Multisig ISM
     */
    function setMultisigISM(address _ism) external onlyRole(CONFIGURER_ROLE) {
        require(_ism != address(0), "Zero address");
        multisigISM = IInterchainSecurityModule(_ism);
        emit ISMConfigured("MULTISIG", _ism);
    }

    /**
     * @notice Module type identifier for Hyperlane
     * @return 1 (Routing / Aggregation type usually)
     */
    function moduleType() external pure override returns (uint8) {
        return 1;
    }

    /**
     * @notice Verifies cross-chain message using M-of-N threshold
     * @param _metadata Aggregated or unified metadata payload
     * @param _message Hyperlane formatted message
     */
    function verify(bytes calldata _metadata, bytes calldata _message) external override returns (bool) {
        require(
            address(phalaISM) != address(0) && address(oracleISM) != address(0) && address(multisigISM) != address(0),
            "ISMs not fully configured"
        );

        uint8 validations = 0;

        // Try Phala ISM
        try phalaISM.verify(_metadata, _message) returns (bool success) {
            if (success) validations++;
        } catch {} // Ignore reverts, continue to next

        // Try Oracle ISM
        try oracleISM.verify(_metadata, _message) returns (bool success) {
            if (success) validations++;
        } catch {}

        // Try Multisig ISM
        try multisigISM.verify(_metadata, _message) returns (bool success) {
            if (success) validations++;
        } catch {}

        return validations >= THRESHOLD;
    }
}
