// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

/**
 * @title VAMSUpgradeableBase
 * @author VAMS Protocol
 * @notice Base contract for all VAMS upgradeable contracts
 * @dev Implements UUPS upgrade pattern with progressive ownership transfer
 * 
 * Ownership Timeline:
 * - Phase 1: Deployer EOA (testnet)
 * - Phase 2: Team Multisig 3/5 (guarded mainnet)
 * - Phase 3: DAO Timelock Controller (decentralized)
 * - Phase 4: Renounce upgradeability (optional, permanent)
 */
abstract contract VAMSUpgradeableBase is 
    Initializable, 
    UUPSUpgradeable, 
    AccessControlUpgradeable 
{
    /// @notice Role required to upgrade the contract
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    
    /// @notice Current governance phase (1-4)
    uint8 public governancePhase;
    
    /// @notice Address of the timelock controller (set in Phase 3)
    address public timelockController;
    
    // ============ Events ============
    
    event GovernancePhaseAdvanced(uint8 indexed oldPhase, uint8 indexed newPhase);
    event OwnershipTransferredToMultisig(address indexed multisig);
    event OwnershipTransferredToDAO(address indexed daoTimelock);
    event UpgradeabilityRenounced(uint256 indexed timestamp);
    
    // ============ Errors ============
    
    error InvalidAddress();
    error InvalidPhaseTransition(uint8 currentPhase, uint8 targetPhase);
    error UpgradeabilityAlreadyRenounced();
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the base contract
     * @param _admin Initial admin address (deployer)
     */
    function __VAMSUpgradeableBase_init(address _admin) internal onlyInitializing {

        __AccessControl_init();
        
        if (_admin == address(0)) revert InvalidAddress();
        
        // AC02: Set DEFAULT_ADMIN_ROLE as the admin of UPGRADER_ROLE
        _setRoleAdmin(UPGRADER_ROLE, DEFAULT_ADMIN_ROLE);
        
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(UPGRADER_ROLE, _admin);
        governancePhase = 1;
    }
    
    // ============ Ownership Transfer ============
    
    /**
     * @notice Transfer upgrade authority to multisig (Phase 1 → 2)
     * @param _multisig Address of the team multisig
     */
    function transferToMultisig(address _multisig) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_multisig == address(0)) revert InvalidAddress();
        if (governancePhase != 1) revert InvalidPhaseTransition(governancePhase, 2);
        
        // Revoke from current admin
        _revokeRole(UPGRADER_ROLE, msg.sender);
        _revokeRole(DEFAULT_ADMIN_ROLE, msg.sender);
        
        // Grant to multisig
        _grantRole(UPGRADER_ROLE, _multisig);
        _grantRole(DEFAULT_ADMIN_ROLE, _multisig);
        
        governancePhase = 2;
        
        emit GovernancePhaseAdvanced(1, 2);
        emit OwnershipTransferredToMultisig(_multisig);
    }
    
    /**
     * @notice Transfer upgrade authority to DAO (Phase 2 → 3)
     * @param _daoTimelock Address of the DAO timelock controller
     */
    function transferToDAO(address _daoTimelock) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_daoTimelock == address(0)) revert InvalidAddress();
        if (governancePhase != 2) revert InvalidPhaseTransition(governancePhase, 3);
        
        // Revoke from current admin (multisig)
        _revokeRole(UPGRADER_ROLE, msg.sender);
        _revokeRole(DEFAULT_ADMIN_ROLE, msg.sender);
        
        // Grant to DAO timelock
        _grantRole(UPGRADER_ROLE, _daoTimelock);
        _grantRole(DEFAULT_ADMIN_ROLE, _daoTimelock);
        
        timelockController = _daoTimelock;
        governancePhase = 3;
        
        emit GovernancePhaseAdvanced(2, 3);
        emit OwnershipTransferredToDAO(_daoTimelock);
    }
    
    /**
     * @notice Permanently disable upgrades (Phase 3 → 4)
     * @dev This action is IRREVERSIBLE. Contract becomes immutable.
     */
    function renounceUpgradeability() external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (governancePhase == 4) revert UpgradeabilityAlreadyRenounced();
        if (governancePhase != 3) revert InvalidPhaseTransition(governancePhase, 4);
        
        // Revoke upgrader role from everyone
        _revokeRole(UPGRADER_ROLE, msg.sender);
        
        governancePhase = 4;
        
        emit GovernancePhaseAdvanced(3, 4);
        emit UpgradeabilityRenounced(block.timestamp);
    }
    
    // ============ UUPS Authorization ============
    
    /**
     * @notice Authorization check for UUPS upgrades
     * @dev Only accounts with UPGRADER_ROLE can upgrade
     */
    function _authorizeUpgrade(address newImplementation) internal override onlyRole(UPGRADER_ROLE) {
        // In Phase 4, no one has UPGRADER_ROLE, so this will always revert
        // Additional checks can be added here (e.g., implementation verification)
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Check if contract can still be upgraded
     * @return bool True if upgrades are possible
     */
    function isUpgradeable() external view returns (bool) {
        return governancePhase < 4;
    }
    
    /**
     * @notice Get current governance phase description
     * @return string Description of current phase
     */
    function getGovernancePhaseDescription() external view returns (string memory) {
        if (governancePhase == 1) return "Phase 1: Deployer EOA";
        if (governancePhase == 2) return "Phase 2: Team Multisig";
        if (governancePhase == 3) return "Phase 3: DAO Governance";
        if (governancePhase == 4) return "Phase 4: Immutable";
        return "Unknown";
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
