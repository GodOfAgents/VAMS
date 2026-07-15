// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title IOracleRegistry
 * @author VAMS Protocol
 */
interface IOracleRegistry {
    enum Category {
        PRICE,
        SERVICE,
        QUALITY,
        BINARY,
        EMERGENCY
    }

    struct CategoryConfig {
        uint256 requiredStake;
        uint256 slashingPercentage; // in basis points (10000 = 100%)
        uint256 consensusThreshold; // e.g., 2/3 required
        uint256 minParticipants;
    }

    function getCategoryConfig(Category category) external view returns (CategoryConfig memory);
    function isAuthorizedOracle(address oracle, Category category) external view returns (bool);
}

/**
 * @title OracleRegistry
 * @author VAMS Protocol
 * @notice Registry and configuration for different oracle categories
 */
contract OracleRegistry is AccessControl, IOracleRegistry {
    bytes32 public constant CONFIGURER_ROLE = keccak256("CONFIGURER_ROLE");

    mapping(Category => CategoryConfig) public categoryConfigs;
    mapping(address => mapping(Category => bool)) public authorizedOracles;

    event CategoryConfigUpdated(
        Category indexed category,
        uint256 requiredStake,
        uint256 slashingPercentage,
        uint256 consensusThreshold,
        uint256 minParticipants
    );
    event OracleAuthorizationUpdated(address indexed oracle, Category indexed category, bool isAuthorized);

    constructor(address _admin) {
        require(_admin != address(0), "Zero admin address");
        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(CONFIGURER_ROLE, _admin);

        // Set up defaults
        _setCategoryConfig(Category.PRICE, 50_000e18, 5000, 6666, 3); // 50% slash, 66.66% consensus, min 3
        _setCategoryConfig(Category.SERVICE, 10_000e18, 2000, 5100, 3); // 20% slash, 51% consensus, min 3
        _setCategoryConfig(Category.QUALITY, 25_000e18, 3000, 6666, 5);
        _setCategoryConfig(Category.BINARY, 10_000e18, 10000, 5100, 3); // 100% slash for lying on binary verifiable facts
        _setCategoryConfig(Category.EMERGENCY, 100_000e18, 10000, 7500, 5); // 75% consensus
    }

    function setCategoryConfig(
        Category category,
        uint256 requiredStake,
        uint256 slashingPercentage,
        uint256 consensusThreshold,
        uint256 minParticipants
    ) external onlyRole(CONFIGURER_ROLE) {
        require(slashingPercentage <= 10000, "Slashing > 100%");
        require(consensusThreshold <= 10000, "Threshold > 100%");
        _setCategoryConfig(category, requiredStake, slashingPercentage, consensusThreshold, minParticipants);
    }

    function _setCategoryConfig(
        Category category,
        uint256 requiredStake,
        uint256 slashingPercentage,
        uint256 consensusThreshold,
        uint256 minParticipants
    ) internal {
        categoryConfigs[category] = CategoryConfig({
            requiredStake: requiredStake,
            slashingPercentage: slashingPercentage,
            consensusThreshold: consensusThreshold,
            minParticipants: minParticipants
        });

        emit CategoryConfigUpdated(category, requiredStake, slashingPercentage, consensusThreshold, minParticipants);
    }

    function setOracleAuthorization(address oracle, Category category, bool authorized)
        external
        onlyRole(CONFIGURER_ROLE)
    {
        require(oracle != address(0), "Zero address");
        authorizedOracles[oracle][category] = authorized;
        emit OracleAuthorizationUpdated(oracle, category, authorized);
    }

    function getCategoryConfig(Category category) external view override returns (CategoryConfig memory) {
        return categoryConfigs[category];
    }

    function isAuthorizedOracle(address oracle, Category category) external view override returns (bool) {
        return authorizedOracles[oracle][category];
    }
}
