// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IVAMSVesting
 * @author VAMS Protocol
 * @notice Interface for multi-schedule token vesting
 * @dev Supports 7 schedule types matching TOKENOMICS.md specifications
 */
interface IVAMSVesting {
    // ============ Enums ============

    /// @notice Pre-defined vesting schedule types
    enum ScheduleType {
        FOUNDER,        // 12mo cliff, 48mo vest, 25% cliff unlock
        TEAM,           // 12mo cliff, 36mo vest, 25% cliff unlock
        ALLIANCE,       // 12mo cliff, 36mo vest, 25% cliff unlock (Pre-seed)
        SEED,           // 6mo cliff, 24mo vest, 20% cliff unlock
        STRATEGIC,      // 3mo cliff, 18mo vest, 15% cliff unlock
        COMMUNITY,      // 0 cliff, 60mo vest, 0% cliff unlock (linear)
        TREASURY        // 6mo cliff, 48mo vest, 2%/month unlock
    }

    // ============ Structs ============

    /// @notice Vesting schedule details
    struct VestingSchedule {
        address beneficiary;        // Recipient of vested tokens
        uint256 totalAmount;        // Total tokens to vest
        uint256 startTimestamp;     // Vesting start (TGE)
        uint256 cliffDuration;      // Seconds until cliff
        uint256 vestingDuration;    // Total seconds to full vest
        uint16 cliffUnlockBps;      // Basis points unlocked at cliff
        uint256 releasedAmount;     // Tokens already released
        bool revoked;               // If schedule was revoked
        bool revocable;             // If schedule can be revoked
    }

    // ============ Events ============

    /// @notice Emitted when a new vesting schedule is created
    event VestingScheduleCreated(
        bytes32 indexed scheduleId,
        address indexed beneficiary,
        uint256 amount,
        ScheduleType scheduleType,
        uint256 cliffDuration,
        uint256 vestingDuration
    );

    /// @notice Emitted when tokens are released to beneficiary
    event TokensReleased(
        bytes32 indexed scheduleId,
        address indexed beneficiary,
        uint256 amount
    );

    /// @notice Emitted when a vesting schedule is revoked
    event VestingScheduleRevoked(
        bytes32 indexed scheduleId,
        address indexed revoker,
        uint256 unvestedAmount
    );

    // ============ Errors ============

    /// @notice Thrown when beneficiary address is zero
    error ZeroAddress();

    /// @notice Thrown when amount is zero
    error ZeroAmount();

    /// @notice Thrown when schedule does not exist
    error ScheduleNotFound(bytes32 scheduleId);

    /// @notice Thrown when schedule is not revocable
    error NotRevocable(bytes32 scheduleId);

    /// @notice Thrown when schedule is already revoked
    error AlreadyRevoked(bytes32 scheduleId);

    /// @notice Thrown when no tokens are releasable
    error NothingToRelease(bytes32 scheduleId);

    /// @notice Thrown when caller is not the beneficiary
    error NotBeneficiary(address caller, address beneficiary);

    /// @notice Thrown when array lengths don't match
    error ArrayLengthMismatch();

    /// @notice Thrown when cliff duration exceeds vesting duration
    error InvalidCliffDuration(uint256 cliff, uint256 vesting);

    // ============ Schedule Management ============

    /// @notice Create vesting schedule using pre-defined type
    /// @param beneficiary Address to receive vested tokens
    /// @param amount Total amount to vest
    /// @param scheduleType Pre-defined schedule type
    /// @param revocable Whether schedule can be revoked by admin
    /// @return scheduleId Unique identifier for this schedule
    function createVestingSchedule(
        address beneficiary,
        uint256 amount,
        ScheduleType scheduleType,
        bool revocable
    ) external returns (bytes32 scheduleId);

    /// @notice Create custom vesting schedule
    /// @param beneficiary Address to receive vested tokens
    /// @param amount Total amount to vest
    /// @param cliffDuration Seconds until cliff
    /// @param vestingDuration Total seconds to full vest
    /// @param cliffUnlockBps Percentage unlocked at cliff (basis points)
    /// @param revocable Whether schedule can be revoked
    /// @return scheduleId Unique identifier for this schedule
    function createCustomSchedule(
        address beneficiary,
        uint256 amount,
        uint256 cliffDuration,
        uint256 vestingDuration,
        uint16 cliffUnlockBps,
        bool revocable
    ) external returns (bytes32 scheduleId);

    /// @notice Batch create schedules with same type
    /// @param beneficiaries Array of beneficiary addresses
    /// @param amounts Array of amounts
    /// @param scheduleType Schedule type for all
    /// @param revocable Whether schedules can be revoked
    /// @return scheduleIds Array of schedule IDs
    function batchCreateSchedules(
        address[] calldata beneficiaries,
        uint256[] calldata amounts,
        ScheduleType scheduleType,
        bool revocable
    ) external returns (bytes32[] memory scheduleIds);

    // ============ Token Release ============

    /// @notice Release vested tokens for a specific schedule
    /// @param scheduleId Schedule to release from
    /// @return released Amount of tokens released
    function release(bytes32 scheduleId) external returns (uint256 released);

    /// @notice Release tokens for multiple schedules
    /// @param scheduleIds Array of schedule IDs
    /// @return totalReleased Total amount released
    function batchRelease(bytes32[] calldata scheduleIds) external returns (uint256 totalReleased);

    /// @notice Release all vested tokens for caller
    /// @return totalReleased Total amount released
    function releaseAll() external returns (uint256 totalReleased);

    // ============ Revocation ============

    /// @notice Revoke a vesting schedule (admin only)
    /// @param scheduleId Schedule to revoke
    function revoke(bytes32 scheduleId) external;

    // ============ View Functions ============

    /// @notice Get vesting schedule details
    /// @param scheduleId Schedule ID
    /// @return schedule The vesting schedule
    function getSchedule(bytes32 scheduleId) external view returns (VestingSchedule memory schedule);

    /// @notice Get all schedule IDs for a beneficiary
    /// @param beneficiary Address to query
    /// @return scheduleIds Array of schedule IDs
    function getScheduleIds(address beneficiary) external view returns (bytes32[] memory scheduleIds);

    /// @notice Get total number of vesting schedules
    /// @return count Number of schedules
    function getScheduleCount() external view returns (uint256 count);

    /// @notice Calculate currently vested amount for a schedule
    /// @param scheduleId Schedule ID
    /// @return amount Amount currently vested
    function vestedAmount(bytes32 scheduleId) external view returns (uint256 amount);

    /// @notice Calculate currently releasable amount
    /// @param scheduleId Schedule ID
    /// @return amount Amount that can be released
    function releasableAmount(bytes32 scheduleId) external view returns (uint256 amount);

    /// @notice Get total vested across all schedules for beneficiary
    /// @param beneficiary Address to query
    /// @return total Total vested amount
    function totalVestedFor(address beneficiary) external view returns (uint256 total);

    /// @notice Get total releasable across all schedules for beneficiary
    /// @param beneficiary Address to query
    /// @return total Total releasable amount
    function totalReleasableFor(address beneficiary) external view returns (uint256 total);

    /// @notice Get total tokens locked in vesting contract
    /// @return total Total locked tokens
    function totalLocked() external view returns (uint256 total);
}
