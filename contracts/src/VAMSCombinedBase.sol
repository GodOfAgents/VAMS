// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./base/VAMSUpgradeableBase.sol";
import "./base/VAMSEmergencyPausable.sol";

/**
 * @title VAMSCombinedBase
 * @author VAMS Protocol
 * @notice Combined base contract for VAMS upgradeable + pausable contracts
 * @dev Inherit from this for contracts that need both upgrade governance and emergency pause
 * 
 * Usage:
 * ```solidity
 * contract MyContract is VAMSCombinedBase {
 *     function initialize(address admin, address[] memory guardians) public initializer {
 *         __VAMSCombinedBase_init(admin, guardians);
 *     }
 *     
 *     function criticalFunction() external whenNotPausedOrExpired {
 *         // Protected by pause
 *     }
 * }
 * ```
 */
abstract contract VAMSCombinedBase is VAMSUpgradeableBase, VAMSEmergencyPausable {
    
    /**
     * @notice Initialize combined base
     * @param _admin Initial admin (deployer)
     * @param _guardians Guardian committee addresses (3 recommended)
     */
    function __VAMSCombinedBase_init(
        address _admin,
        address[] memory _guardians
    ) internal onlyInitializing {
        __VAMSUpgradeableBase_init(_admin);
        __VAMSEmergencyPausable_init(_admin, _guardians);
    }
    
    /**
     * @notice Resolve AccessControl conflict
     * @dev Both bases inherit AccessControlUpgradeable
     */
    function supportsInterface(bytes4 interfaceId) 
        public 
        view 
        virtual 
        override(AccessControlUpgradeable) 
        returns (bool) 
    {
        return super.supportsInterface(interfaceId);
    }
}
