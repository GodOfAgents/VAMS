// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./IVAMSFeeCollector.sol";

/**
 * @title VAMSFeeCollector
 * @author VAMS Protocol
 * @notice Collects and distributes protocol fees according to tokenomics
 * @dev Supports multiple tokens and phase-based distribution:
 * 
 * Phase 1: 100% burn (deflationary launch)
 * Phase 2: 40% burn, 30% staking, 20% treasury, 10% insurance
 * Phase 3: 30% burn, 35% staking, 25% treasury, 10% insurance
 * 
 * Features:
 * - Multi-token fee collection
 * - Auto-distribution when threshold reached
 * - Phase-based distribution presets
 * - Custom distribution support
 */
contract VAMSFeeCollector is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    IVAMSFeeCollector 
{
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Role for collecting fees
    bytes32 public constant FEE_COLLECTOR_ROLE = keccak256("FEE_COLLECTOR_ROLE");

    /// @notice Role for distributing fees
    bytes32 public constant FEE_DISTRIBUTOR_ROLE = keccak256("FEE_DISTRIBUTOR_ROLE");

    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;

    /// @notice Burn address
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD;

    // ============ State Variables ============

    /// @notice VAMS token address
    IERC20 public vamsToken;

    /// @notice Treasury address
    address public treasury;

    /// @notice Staking contract address
    address public stakingContract;

    /// @notice Insurance fund address
    address public insuranceFund;

    /// @notice Current distribution phase
    DistributionPhase public currentPhase;

    /// @notice Current distribution settings
    Distribution public distribution;

    /// @notice Auto-distribute threshold (in VAMS)
    uint256 public autoDistributeThreshold;

    /// @notice Accumulated fees per token
    mapping(address => uint256) public tokenFees;

    /// @notice Supported tokens
    mapping(address => bool) public supportedTokens;

    /// @notice List of supported token addresses
    address[] public supportedTokenList;

    // ============ Initializer ============

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice Initialize the fee collector
     * @param _admin Admin address
     * @param _vamsToken VAMS token address
     * @param _treasury Treasury address
     * @param _stakingContract Staking contract address
     * @param _insuranceFund Insurance fund address
     */
    function initialize(
        address _admin,
        address _vamsToken,
        address _treasury,
        address _stakingContract,
        address _insuranceFund
    ) external initializer {
        if (_admin == address(0)) revert ZeroAddress();
        if (_vamsToken == address(0)) revert ZeroAddress();
        if (_treasury == address(0)) revert ZeroAddress();

        __AccessControl_init();
        __Pausable_init();
        __ReentrancyGuard_init();

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(FEE_COLLECTOR_ROLE, _admin);
        _grantRole(FEE_DISTRIBUTOR_ROLE, _admin);

        vamsToken = IERC20(_vamsToken);
        treasury = _treasury;
        stakingContract = _stakingContract;
        insuranceFund = _insuranceFund;

        // Start in Phase 1: 100% burn
        currentPhase = DistributionPhase.PHASE_1;
        distribution = Distribution({
            burnBps: 10_000,
            stakingBps: 0,
            treasuryBps: 0,
            insuranceBps: 0
        });

        // Support VAMS token by default
        supportedTokens[_vamsToken] = true;
        supportedTokenList.push(_vamsToken);

        // Default auto-distribute threshold: 10,000 VAMS
        autoDistributeThreshold = 10_000 ether;

        emit TokenSupportUpdated(_vamsToken, true);
    }

    // ============ Fee Collection ============

    /// @inheritdoc IVAMSFeeCollector
    function collectFees(uint256 amount) external override onlyRole(FEE_COLLECTOR_ROLE) {
        _collectTokenFees(address(vamsToken), amount);
    }

    /// @inheritdoc IVAMSFeeCollector
    function collectTokenFees(
        address token, 
        uint256 amount
    ) external override onlyRole(FEE_COLLECTOR_ROLE) {
        _collectTokenFees(token, amount);
    }

    /**
     * @notice Internal fee collection
     */
    function _collectTokenFees(address token, uint256 amount) internal {
        if (amount == 0) revert ZeroAmount();
        if (!supportedTokens[token]) revert TokenNotSupported(token);

        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
        tokenFees[token] += amount;

        emit FeesCollected(msg.sender, token, amount);

        // Auto-distribute if threshold reached (for VAMS only)
        if (token == address(vamsToken) && tokenFees[token] >= autoDistributeThreshold) {
            _distributeTokenFees(token);
        }
    }

    // ============ Fee Distribution ============

    /// @inheritdoc IVAMSFeeCollector
    function distributeFees() external override nonReentrant whenNotPaused onlyRole(FEE_DISTRIBUTOR_ROLE) {
        _distributeTokenFees(address(vamsToken));
    }

    /// @inheritdoc IVAMSFeeCollector
    function distributeTokenFees(
        address token
    ) external override nonReentrant whenNotPaused onlyRole(FEE_DISTRIBUTOR_ROLE) {
        _distributeTokenFees(token);
    }

    /// @inheritdoc IVAMSFeeCollector
    function distributeAllFees() external override nonReentrant whenNotPaused onlyRole(FEE_DISTRIBUTOR_ROLE) {
        for (uint256 i = 0; i < supportedTokenList.length; i++) {
            address token = supportedTokenList[i];
            if (tokenFees[token] > 0) {
                _distributeTokenFees(token);
            }
        }
    }

    /**
     * @notice Internal fee distribution
     */
    function _distributeTokenFees(address token) internal {
        uint256 total = tokenFees[token];
        if (total == 0) revert NoFeesToDistribute();

        tokenFees[token] = 0;

        uint256 toBurn = (total * distribution.burnBps) / BPS_DENOMINATOR;
        uint256 toStaking = (total * distribution.stakingBps) / BPS_DENOMINATOR;
        uint256 toTreasury = (total * distribution.treasuryBps) / BPS_DENOMINATOR;
        uint256 toInsurance = total - toBurn - toStaking - toTreasury;

        IERC20 tokenContract = IERC20(token);

        if (toBurn > 0) {
            tokenContract.safeTransfer(BURN_ADDRESS, toBurn);
        }
        if (toStaking > 0 && stakingContract != address(0)) {
            tokenContract.safeTransfer(stakingContract, toStaking);
        }
        if (toTreasury > 0 && treasury != address(0)) {
            tokenContract.safeTransfer(treasury, toTreasury);
        }
        if (toInsurance > 0 && insuranceFund != address(0)) {
            tokenContract.safeTransfer(insuranceFund, toInsurance);
        }

        emit FeesDistributed(token, toBurn, toStaking, toTreasury, toInsurance);
    }

    // ============ Configuration ============

    /// @inheritdoc IVAMSFeeCollector
    function updateDistribution(
        uint256 _burnBps,
        uint256 _stakingBps,
        uint256 _treasuryBps,
        uint256 _insuranceBps
    ) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 total = _burnBps + _stakingBps + _treasuryBps + _insuranceBps;
        if (total != BPS_DENOMINATOR) revert InvalidDistribution(total);

        distribution = Distribution({
            burnBps: _burnBps,
            stakingBps: _stakingBps,
            treasuryBps: _treasuryBps,
            insuranceBps: _insuranceBps
        });

        currentPhase = DistributionPhase.CUSTOM;

        emit DistributionUpdated(
            DistributionPhase.CUSTOM,
            _burnBps,
            _stakingBps,
            _treasuryBps,
            _insuranceBps
        );
    }

    /// @inheritdoc IVAMSFeeCollector
    function transitionToPhase(
        DistributionPhase phase
    ) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        currentPhase = phase;

        if (phase == DistributionPhase.PHASE_1) {
            distribution = Distribution({
                burnBps: 10_000,
                stakingBps: 0,
                treasuryBps: 0,
                insuranceBps: 0
            });
        } else if (phase == DistributionPhase.PHASE_2) {
            distribution = Distribution({
                burnBps: 4_000,
                stakingBps: 3_000,
                treasuryBps: 2_000,
                insuranceBps: 1_000
            });
        } else if (phase == DistributionPhase.PHASE_3) {
            distribution = Distribution({
                burnBps: 3_000,
                stakingBps: 3_500,
                treasuryBps: 2_500,
                insuranceBps: 1_000
            });
        }

        emit DistributionUpdated(
            phase,
            distribution.burnBps,
            distribution.stakingBps,
            distribution.treasuryBps,
            distribution.insuranceBps
        );
    }

    /// @inheritdoc IVAMSFeeCollector
    function setAutoDistributeThreshold(
        uint256 threshold
    ) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        uint256 oldThreshold = autoDistributeThreshold;
        autoDistributeThreshold = threshold;
        emit AutoDistributeThresholdUpdated(oldThreshold, threshold);
    }

    /// @inheritdoc IVAMSFeeCollector
    function setTokenSupport(
        address token, 
        bool supported
    ) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        if (token == address(0)) revert ZeroAddress();

        if (supported && !supportedTokens[token]) {
            supportedTokens[token] = true;
            supportedTokenList.push(token);
        } else if (!supported && supportedTokens[token]) {
            supportedTokens[token] = false;
            // Note: We don't remove from list to avoid gas-expensive array operations
            // The token will simply be skipped during distributeAllFees
        }

        emit TokenSupportUpdated(token, supported);
    }

    // ============ Admin Functions ============

    /**
     * @notice Update treasury address
     * @param _treasury New treasury address
     */
    function setTreasury(address _treasury) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = _treasury;
    }

    /**
     * @notice Update staking contract address
     * @param _stakingContract New staking contract address
     */
    function setStakingContract(address _stakingContract) external onlyRole(DEFAULT_ADMIN_ROLE) {
        stakingContract = _stakingContract;
    }

    /**
     * @notice Update insurance fund address
     * @param _insuranceFund New insurance fund address
     */
    function setInsuranceFund(address _insuranceFund) external onlyRole(DEFAULT_ADMIN_ROLE) {
        insuranceFund = _insuranceFund;
    }

    /**
     * @notice Pause fee distribution
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @notice Unpause fee distribution
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    /**
     * @notice Emergency withdraw stuck tokens
     * @param token Token address
     * @param to Recipient address
     * @param amount Amount to withdraw
     */
    function emergencyWithdraw(
        address token,
        address to,
        uint256 amount
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (to == address(0)) revert ZeroAddress();
        IERC20(token).safeTransfer(to, amount);
    }

    // ============ View Functions ============

    /// @inheritdoc IVAMSFeeCollector
    function accumulatedFees() external view override returns (uint256) {
        return tokenFees[address(vamsToken)];
    }

    /// @inheritdoc IVAMSFeeCollector
    function getAccumulatedFees(address token) external view override returns (uint256) {
        return tokenFees[token];
    }

    /// @inheritdoc IVAMSFeeCollector
    function getDistribution() external view override returns (Distribution memory) {
        return distribution;
    }

    /// @inheritdoc IVAMSFeeCollector
    function getCurrentPhase() external view override returns (DistributionPhase) {
        return currentPhase;
    }

    /// @inheritdoc IVAMSFeeCollector
    function isTokenSupported(address token) external view override returns (bool) {
        return supportedTokens[token];
    }

    /// @inheritdoc IVAMSFeeCollector
    function getAutoDistributeThreshold() external view override returns (uint256) {
        return autoDistributeThreshold;
    }

    /**
     * @notice Get list of supported tokens
     * @return tokens Array of supported token addresses
     */
    function getSupportedTokens() external view returns (address[] memory) {
        return supportedTokenList;
    }

    /**
     * @notice Get total fees across all tokens (in their native decimals)
     * @return total Total accumulated fees
     */
    function getTotalAccumulatedFees() external view returns (uint256 total) {
        for (uint256 i = 0; i < supportedTokenList.length; i++) {
            total += tokenFees[supportedTokenList[i]];
        }
    }
}
