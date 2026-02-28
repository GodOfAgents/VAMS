// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSToken
 * @author VAMS Protocol
 * @notice Interface for the VAMS ERC-20 token with governance capabilities
 * @dev Extends ERC-20 with burning, permit (EIP-2612), voting, and anti-whale provisions
 */
interface IVAMSToken {
    // ============ Events ============

    /// @notice Emitted when anti-whale protection is toggled
    event AntiWhaleToggled(bool enabled);

    /// @notice Emitted when an address exemption status changes
    event AddressExempted(address indexed account, bool exempt);

    /// @notice Emitted when daily transfer limit is updated
    event DailyLimitUpdated(uint256 newLimitBps);

    /// @notice Emitted when max wallet limit is updated
    event MaxWalletUpdated(uint256 newMaxBps);

    // ============ Errors ============

    /// @notice Thrown when transfer exceeds max wallet limit
    error ExceedsMaxWallet(address account, uint256 balance, uint256 max);

    /// @notice Thrown when transfer exceeds daily limit
    error ExceedsDailyLimit(address account, uint256 amount, uint256 limit);

    /// @notice Thrown when caller is not authorized
    error Unauthorized();

    /// @notice Thrown when anti-whale period has not expired
    error AntiWhalePeriodActive();

    /// @notice Thrown when amount is zero
    error ZeroAmount();

    /// @notice Thrown when address is zero
    error ZeroAddress();

    /// @notice Thrown when annual mint cap would be exceeded
    error AnnualMintCapExceeded(uint256 attempted, uint256 cap);

    // ============ View Functions ============

    /// @notice Check if anti-whale protection is enabled
    /// @return True if anti-whale is active
    function antiWhaleEnabled() external view returns (bool);

    /// @notice Get the maximum wallet balance in basis points
    /// @return Max wallet percentage (500 = 5%)
    function maxWalletBps() external view returns (uint256);

    /// @notice Get the daily transfer limit in basis points
    /// @return Daily limit percentage (100 = 1%)
    function dailyTransferLimitBps() external view returns (uint256);

    /// @notice Get the timestamp when anti-whale restrictions end
    /// @return Unix timestamp
    function antiWhaleEndTimestamp() external view returns (uint256);

    /// @notice Check if an address is exempt from anti-whale limits
    /// @param account Address to check
    /// @return True if exempt
    function isExemptFromLimits(address account) external view returns (bool);

    /// @notice Get the daily transfer amount for an account
    /// @param account Address to check
    /// @return Amount transferred today
    function getDailyTransferAmount(address account) external view returns (uint256);

    /// @notice Get the last transfer timestamp for an account
    /// @param account Address to check
    /// @return Unix timestamp of last transfer
    function getLastTransferTimestamp(address account) external view returns (uint256);

    /// @notice Calculate the maximum wallet amount based on total supply
    /// @return Maximum tokens an address can hold
    function maxWalletAmount() external view returns (uint256);

    /// @notice Calculate the daily transfer limit based on total supply
    /// @return Maximum tokens that can be transferred per day
    function dailyTransferLimit() external view returns (uint256);

    // ============ Minting ============

    /// @notice Mint new tokens (restricted to MINTER_ROLE)
    /// @param to Recipient address
    /// @param amount Amount to mint
    function mint(address to, uint256 amount) external;

    // ============ Anti-Whale Management ============

    /// @notice Enable or disable anti-whale protection
    /// @param enabled True to enable, false to disable
    function setAntiWhaleEnabled(bool enabled) external;

    /// @notice Add an address to the exemption list
    /// @param account Address to exempt
    function addExemptAddress(address account) external;

    /// @notice Remove an address from the exemption list
    /// @param account Address to remove
    function removeExemptAddress(address account) external;

    /// @notice Update the maximum wallet percentage
    /// @param newMaxBps New max in basis points (max 1000 = 10%)
    function setMaxWalletBps(uint256 newMaxBps) external;

    /// @notice Update the daily transfer limit percentage
    /// @param newLimitBps New limit in basis points (max 500 = 5%)
    function setDailyTransferLimitBps(uint256 newLimitBps) external;
}
