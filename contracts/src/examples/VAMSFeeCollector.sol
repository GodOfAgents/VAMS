// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../VAMSCombinedBase.sol";

/**
 * @title VAMSFeeCollector
 * @author VAMS Protocol
 * @notice Example upgradeable contract using VAMS base
 * @dev Demonstrates how to inherit from VAMSCombinedBase
 * 
 * Features:
 * - UUPS upgradeable with progressive ownership
 * - Emergency pausable with 48h auto-expiry
 * - Fee collection and distribution logic
 */
contract VAMSFeeCollector is VAMSCombinedBase {
    /// @notice Role for fee distribution
    bytes32 public constant FEE_MANAGER_ROLE = keccak256("FEE_MANAGER_ROLE");
    
    /// @notice Accumulated fees ready for distribution
    uint256 public accumulatedFees;
    
    /// @notice Buyback and burn percentage (basis points, e.g., 4000 = 40%)
    uint256 public burnBps;
    
    /// @notice Staking rewards percentage (basis points)
    uint256 public stakingBps;
    
    /// @notice Treasury percentage (basis points)
    uint256 public treasuryBps;
    
    /// @notice Insurance fund percentage (basis points)
    uint256 public insuranceBps;
    
    /// @notice Treasury address
    address public treasury;
    
    /// @notice Staking contract address
    address public stakingContract;
    
    /// @notice Insurance fund address
    address public insuranceFund;
    
    /// @notice Burn address
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;
    
    // ============ Events ============
    
    event FeesCollected(address indexed from, uint256 amount);
    event FeesDistributed(
        uint256 burned,
        uint256 toStaking,
        uint256 toTreasury,
        uint256 toInsurance
    );
    event DistributionUpdated(
        uint256 burnBps,
        uint256 stakingBps,
        uint256 treasuryBps,
        uint256 insuranceBps
    );
    
    // ============ Errors ============
    
    error InvalidDistribution(uint256 total);
    error NoFeesToDistribute();
    
    /**
     * @notice Initialize the fee collector
     * @param _admin Initial admin
     * @param _guardians Guardian committee addresses
     * @param _treasury Treasury address
     * @param _stakingContract Staking contract address
     * @param _insuranceFund Insurance fund address
     */
    function initialize(
        address _admin,
        address[] memory _guardians,
        address _treasury,
        address _stakingContract,
        address _insuranceFund
    ) public initializer {
        __VAMSCombinedBase_init(_admin, _guardians);
        
        _grantRole(FEE_MANAGER_ROLE, _admin);
        
        treasury = _treasury;
        stakingContract = _stakingContract;
        insuranceFund = _insuranceFund;
        
        // Phase 1 defaults: 100% burn
        burnBps = 10000; // 100%
        stakingBps = 0;
        treasuryBps = 0;
        insuranceBps = 0;
    }
    
    /**
     * @notice Collect fees (receive ETH)
     */
    receive() external payable {
        accumulatedFees += msg.value;
        emit FeesCollected(msg.sender, msg.value);
    }
    
    /**
     * @notice Distribute accumulated fees
     * @dev Protected by pause
     */
    function distributeFees() external whenNotPausedOrExpired onlyRole(FEE_MANAGER_ROLE) {
        if (accumulatedFees == 0) revert NoFeesToDistribute();
        
        uint256 total = accumulatedFees;
        accumulatedFees = 0;
        
        uint256 toBurn = (total * burnBps) / 10000;
        uint256 toStaking = (total * stakingBps) / 10000;
        uint256 toTreasury = (total * treasuryBps) / 10000;
        uint256 toInsurance = total - toBurn - toStaking - toTreasury;
        
        if (toBurn > 0) {
            payable(BURN_ADDRESS).transfer(toBurn);
        }
        if (toStaking > 0 && stakingContract != address(0)) {
            payable(stakingContract).transfer(toStaking);
        }
        if (toTreasury > 0 && treasury != address(0)) {
            payable(treasury).transfer(toTreasury);
        }
        if (toInsurance > 0 && insuranceFund != address(0)) {
            payable(insuranceFund).transfer(toInsurance);
        }
        
        emit FeesDistributed(toBurn, toStaking, toTreasury, toInsurance);
    }
    
    /**
     * @notice Update distribution percentages
     * @dev Only callable through timelock (admin role)
     */
    function updateDistribution(
        uint256 _burnBps,
        uint256 _stakingBps,
        uint256 _treasuryBps,
        uint256 _insuranceBps
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 total = _burnBps + _stakingBps + _treasuryBps + _insuranceBps;
        if (total != 10000) revert InvalidDistribution(total);
        
        burnBps = _burnBps;
        stakingBps = _stakingBps;
        treasuryBps = _treasuryBps;
        insuranceBps = _insuranceBps;
        
        emit DistributionUpdated(_burnBps, _stakingBps, _treasuryBps, _insuranceBps);
    }
    
    /**
     * @notice Transition to Phase 2 distribution
     * @dev 40% burn, 30% staking, 20% treasury, 10% insurance
     */
    function transitionToPhase2() external onlyRole(DEFAULT_ADMIN_ROLE) {
        burnBps = 4000;      // 40%
        stakingBps = 3000;   // 30%
        treasuryBps = 2000;  // 20%
        insuranceBps = 1000; // 10%
        
        emit DistributionUpdated(burnBps, stakingBps, treasuryBps, insuranceBps);
    }
}
