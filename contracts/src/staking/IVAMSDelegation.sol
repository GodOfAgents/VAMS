// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSDelegation
 * @author VAMS Protocol
 * @notice Interface for Delegated Proof of Stake (DPoS) agent delegation.
 *
 * Allows $VAMS holders to delegate their staking weight to agents 
 * (validators, keepers, compute providers) without transferring tokens.
 *
 * Phase 1: Stub interface for future implementation.
 * Phase 2: Full DPoS with delegation rewards, re-delegation, and slashing propagation.
 */
interface IVAMSDelegation {
    // ============ Structs ============

    /// @notice Delegation record
    struct Delegation {
        /// @notice Delegator address  
        address delegator;
        /// @notice Agent (delegatee) address
        address agent;
        /// @notice Amount of $VAMS delegated
        uint256 amount;
        /// @notice Timestamp of delegation
        uint256 delegatedAt;
        /// @notice Whether the delegation is active
        bool active;
    }

    // ============ Events ============

    /// @notice Emitted when a user delegates to an agent
    event Delegated(address indexed delegator, address indexed agent, uint256 amount);

    /// @notice Emitted when a user undelegates from an agent
    event Undelegated(address indexed delegator, address indexed agent, uint256 amount);

    /// @notice Emitted when a user re-delegates to a new agent
    event Redelegated(
        address indexed delegator, 
        address indexed fromAgent, 
        address indexed toAgent, 
        uint256 amount
    );

    /// @notice Emitted when delegation rewards are claimed
    event DelegationRewardsClaimed(address indexed delegator, uint256 amount);

    // ============ Errors ============

    error ZeroAmount();
    error ZeroAddress();
    error InsufficientDelegation(uint256 requested, uint256 available);
    error AgentNotRegistered(address agent);
    error AlreadyDelegated(address delegator, address agent);
    error NoDelegation(address delegator, address agent);
    error RedelegationCooldown(uint256 availableAt);

    // ============ Delegation Functions ============

    /**
     * @notice Delegate $VAMS to an agent
     * @param agent Agent address to delegate to
     * @param amount Amount of $VAMS to delegate
     */
    function delegate(address agent, uint256 amount) external;

    /**
     * @notice Undelegate $VAMS from an agent
     * @param agent Agent address to undelegate from
     * @param amount Amount to undelegate
     */
    function undelegate(address agent, uint256 amount) external;

    /**
     * @notice Re-delegate from one agent to another
     * @param fromAgent Current agent
     * @param toAgent New agent
     * @param amount Amount to re-delegate
     */
    function redelegate(address fromAgent, address toAgent, uint256 amount) external;

    /**
     * @notice Claim accumulated delegation rewards
     * @return amount Amount of rewards claimed
     */
    function claimDelegationRewards() external returns (uint256 amount);

    // ============ View Functions ============

    /**
     * @notice Get delegation info for a delegator-agent pair
     * @param delegator Delegator address
     * @param agent Agent address
     * @return delegation Delegation record
     */
    function getDelegation(
        address delegator, 
        address agent
    ) external view returns (Delegation memory delegation);

    /**
     * @notice Get total delegated to an agent
     * @param agent Agent address
     * @return total Total $VAMS delegated
     */
    function totalDelegatedTo(address agent) external view returns (uint256 total);

    /**
     * @notice Get total delegated by a delegator
     * @param delegator Delegator address
     * @return total Total $VAMS delegated out
     */
    function totalDelegatedBy(address delegator) external view returns (uint256 total);

    /**
     * @notice Get pending delegation rewards for a delegator
     * @param delegator Delegator address
     * @return rewards Pending rewards
     */
    function pendingDelegationRewards(address delegator) external view returns (uint256 rewards);
}
