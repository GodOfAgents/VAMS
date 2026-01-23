// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./IVAMSVesting.sol";

/**
 * @title VAMSVesting
 * @author VAMS Protocol
 * @notice Multi-schedule token vesting with cliff and linear unlock
 * @dev Implements 7 schedule types from TOKENOMICS.md:
 *
 * | Type       | Cliff  | Vest   | Cliff Unlock |
 * |------------|--------|--------|--------------|
 * | FOUNDER    | 12 mo  | 48 mo  | 25%          |
 * | TEAM       | 12 mo  | 36 mo  | 25%          |
 * | ALLIANCE   | 12 mo  | 36 mo  | 25%          |
 * | SEED       | 6 mo   | 24 mo  | 20%          |
 * | STRATEGIC  | 3 mo   | 18 mo  | 15%          |
 * | COMMUNITY  | 0      | 60 mo  | 0%           |
 * | TREASURY   | 6 mo   | 48 mo  | 0% (2%/mo)   |
 */
contract VAMSVesting is IVAMSVesting, AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // ============ Constants ============

    /// @notice Role for creating vesting schedules
    bytes32 public constant VESTING_ADMIN_ROLE = keccak256("VESTING_ADMIN_ROLE");

    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;

    /// @notice One month in seconds
    uint256 public constant ONE_MONTH = 30 days;

    // ============ Schedule Type Parameters ============

    // Cliff durations in seconds
    uint256 private constant CLIFF_FOUNDER = 12 * ONE_MONTH;
    uint256 private constant CLIFF_TEAM = 12 * ONE_MONTH;
    uint256 private constant CLIFF_ALLIANCE = 12 * ONE_MONTH;
    uint256 private constant CLIFF_SEED = 6 * ONE_MONTH;
    uint256 private constant CLIFF_STRATEGIC = 3 * ONE_MONTH;
    uint256 private constant CLIFF_COMMUNITY = 0;
    uint256 private constant CLIFF_TREASURY = 6 * ONE_MONTH;

    // Vesting durations in seconds
    uint256 private constant VEST_FOUNDER = 48 * ONE_MONTH;
    uint256 private constant VEST_TEAM = 36 * ONE_MONTH;
    uint256 private constant VEST_ALLIANCE = 36 * ONE_MONTH;
    uint256 private constant VEST_SEED = 24 * ONE_MONTH;
    uint256 private constant VEST_STRATEGIC = 18 * ONE_MONTH;
    uint256 private constant VEST_COMMUNITY = 60 * ONE_MONTH;
    uint256 private constant VEST_TREASURY = 48 * ONE_MONTH;

    // Cliff unlock percentages in basis points
    uint16 private constant UNLOCK_FOUNDER = 2500; // 25%
    uint16 private constant UNLOCK_TEAM = 2500; // 25%
    uint16 private constant UNLOCK_ALLIANCE = 2500; // 25%
    uint16 private constant UNLOCK_SEED = 2000; // 20%
    uint16 private constant UNLOCK_STRATEGIC = 1500; // 15%
    uint16 private constant UNLOCK_COMMUNITY = 0; // 0%
    uint16 private constant UNLOCK_TREASURY = 0; // 0% (linear from cliff)

    // ============ State Variables ============

    /// @notice The VAMS token contract
    IERC20 public immutable token;

    /// @notice TGE timestamp (start of all vesting)
    uint256 public immutable tgeTimestamp;

    /// @notice All vesting schedules by ID
    mapping(bytes32 scheduleId => VestingSchedule schedule) private _schedules;

    /// @notice Schedule IDs for each beneficiary
    mapping(address beneficiary => bytes32[] scheduleIds) private _beneficiarySchedules;

    /// @notice Total number of schedules created
    uint256 private _scheduleCount;

    /// @notice Total tokens currently locked in vesting
    uint256 private _totalLocked;

    // ============ Constructor ============

    /**
     * @notice Deploy the vesting contract
     * @param _token VAMS token address
     * @param admin Admin address
     */
    constructor(address _token, address admin) {
        if (_token == address(0)) revert ZeroAddress();
        if (admin == address(0)) revert ZeroAddress();

        token = IERC20(_token);
        tgeTimestamp = block.timestamp;

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(VESTING_ADMIN_ROLE, admin);
    }

    // ============ Schedule Creation ============

    /// @inheritdoc IVAMSVesting
    function createVestingSchedule(
        address beneficiary,
        uint256 amount,
        ScheduleType scheduleType,
        bool revocable
    ) external override onlyRole(VESTING_ADMIN_ROLE) returns (bytes32 scheduleId) {
        (uint256 cliff, uint256 vest, uint16 unlock) = _getScheduleParams(scheduleType);
        return _createSchedule(beneficiary, amount, cliff, vest, unlock, revocable, scheduleType);
    }

    /// @inheritdoc IVAMSVesting
    function createCustomSchedule(
        address beneficiary,
        uint256 amount,
        uint256 cliffDuration,
        uint256 vestingDuration,
        uint16 cliffUnlockBps,
        bool revocable
    ) external override onlyRole(VESTING_ADMIN_ROLE) returns (bytes32 scheduleId) {
        if (cliffDuration > vestingDuration) {
            revert InvalidCliffDuration(cliffDuration, vestingDuration);
        }
        if (cliffUnlockBps > BPS_DENOMINATOR) {
            revert InvalidCliffDuration(cliffUnlockBps, BPS_DENOMINATOR);
        }
        return _createSchedule(
            beneficiary, 
            amount, 
            cliffDuration, 
            vestingDuration, 
            cliffUnlockBps, 
            revocable,
            ScheduleType.FOUNDER // Custom uses FOUNDER as placeholder
        );
    }

    /// @inheritdoc IVAMSVesting
    function batchCreateSchedules(
        address[] calldata beneficiaries,
        uint256[] calldata amounts,
        ScheduleType scheduleType,
        bool revocable
    ) external override onlyRole(VESTING_ADMIN_ROLE) returns (bytes32[] memory scheduleIds) {
        if (beneficiaries.length != amounts.length) revert ArrayLengthMismatch();

        scheduleIds = new bytes32[](beneficiaries.length);
        (uint256 cliff, uint256 vest, uint16 unlock) = _getScheduleParams(scheduleType);

        for (uint256 i = 0; i < beneficiaries.length; i++) {
            scheduleIds[i] = _createSchedule(
                beneficiaries[i],
                amounts[i],
                cliff,
                vest,
                unlock,
                revocable,
                scheduleType
            );
        }
    }

    // ============ Token Release ============

    /// @inheritdoc IVAMSVesting
    function release(bytes32 scheduleId) external override nonReentrant returns (uint256 released) {
        VestingSchedule storage schedule = _schedules[scheduleId];
        
        if (schedule.beneficiary == address(0)) revert ScheduleNotFound(scheduleId);
        if (schedule.revoked) revert AlreadyRevoked(scheduleId);

        released = _releasableAmount(schedule);
        if (released == 0) revert NothingToRelease(scheduleId);

        schedule.releasedAmount += released;
        _totalLocked -= released;

        token.safeTransfer(schedule.beneficiary, released);

        emit TokensReleased(scheduleId, schedule.beneficiary, released);
    }

    /// @inheritdoc IVAMSVesting
    function batchRelease(bytes32[] calldata scheduleIds) 
        external 
        override 
        nonReentrant 
        returns (uint256 totalReleased) 
    {
        for (uint256 i = 0; i < scheduleIds.length; i++) {
            VestingSchedule storage schedule = _schedules[scheduleIds[i]];
            
            if (schedule.beneficiary == address(0)) continue;
            if (schedule.revoked) continue;

            uint256 released = _releasableAmount(schedule);
            if (released == 0) continue;

            schedule.releasedAmount += released;
            _totalLocked -= released;
            totalReleased += released;

            token.safeTransfer(schedule.beneficiary, released);

            emit TokensReleased(scheduleIds[i], schedule.beneficiary, released);
        }
    }

    /// @inheritdoc IVAMSVesting
    function releaseAll() external override nonReentrant returns (uint256 totalReleased) {
        bytes32[] memory scheduleIds = _beneficiarySchedules[msg.sender];

        for (uint256 i = 0; i < scheduleIds.length; i++) {
            VestingSchedule storage schedule = _schedules[scheduleIds[i]];
            
            if (schedule.revoked) continue;

            uint256 released = _releasableAmount(schedule);
            if (released == 0) continue;

            schedule.releasedAmount += released;
            _totalLocked -= released;
            totalReleased += released;

            emit TokensReleased(scheduleIds[i], msg.sender, released);
        }

        if (totalReleased > 0) {
            token.safeTransfer(msg.sender, totalReleased);
        }
    }

    // ============ Revocation ============

    /// @inheritdoc IVAMSVesting
    function revoke(bytes32 scheduleId) external override onlyRole(VESTING_ADMIN_ROLE) {
        VestingSchedule storage schedule = _schedules[scheduleId];

        if (schedule.beneficiary == address(0)) revert ScheduleNotFound(scheduleId);
        if (!schedule.revocable) revert NotRevocable(scheduleId);
        if (schedule.revoked) revert AlreadyRevoked(scheduleId);

        // Calculate unvested amount
        uint256 vested = _vestedAmount(schedule);
        uint256 unvested = schedule.totalAmount - vested;

        // Release any vested but unreleased tokens to beneficiary
        uint256 unreleased = vested - schedule.releasedAmount;
        if (unreleased > 0) {
            schedule.releasedAmount = vested;
            token.safeTransfer(schedule.beneficiary, unreleased);
            emit TokensReleased(scheduleId, schedule.beneficiary, unreleased);
        }

        // Mark as revoked
        schedule.revoked = true;
        _totalLocked -= unvested;

        // Return unvested tokens to admin
        if (unvested > 0) {
            token.safeTransfer(msg.sender, unvested);
        }

        emit VestingScheduleRevoked(scheduleId, msg.sender, unvested);
    }

    // ============ View Functions ============

    /// @inheritdoc IVAMSVesting
    function getSchedule(bytes32 scheduleId) 
        external 
        view 
        override 
        returns (VestingSchedule memory) 
    {
        return _schedules[scheduleId];
    }

    /// @inheritdoc IVAMSVesting
    function getScheduleIds(address beneficiary) 
        external 
        view 
        override 
        returns (bytes32[] memory) 
    {
        return _beneficiarySchedules[beneficiary];
    }

    /// @inheritdoc IVAMSVesting
    function getScheduleCount() external view override returns (uint256) {
        return _scheduleCount;
    }

    /// @inheritdoc IVAMSVesting
    function vestedAmount(bytes32 scheduleId) external view override returns (uint256) {
        VestingSchedule storage schedule = _schedules[scheduleId];
        if (schedule.beneficiary == address(0)) revert ScheduleNotFound(scheduleId);
        return _vestedAmount(schedule);
    }

    /// @inheritdoc IVAMSVesting
    function releasableAmount(bytes32 scheduleId) external view override returns (uint256) {
        VestingSchedule storage schedule = _schedules[scheduleId];
        if (schedule.beneficiary == address(0)) revert ScheduleNotFound(scheduleId);
        return _releasableAmount(schedule);
    }

    /// @inheritdoc IVAMSVesting
    function totalVestedFor(address beneficiary) external view override returns (uint256 total) {
        bytes32[] memory scheduleIds = _beneficiarySchedules[beneficiary];
        for (uint256 i = 0; i < scheduleIds.length; i++) {
            VestingSchedule storage schedule = _schedules[scheduleIds[i]];
            if (!schedule.revoked) {
                total += _vestedAmount(schedule);
            }
        }
    }

    /// @inheritdoc IVAMSVesting
    function totalReleasableFor(address beneficiary) external view override returns (uint256 total) {
        bytes32[] memory scheduleIds = _beneficiarySchedules[beneficiary];
        for (uint256 i = 0; i < scheduleIds.length; i++) {
            VestingSchedule storage schedule = _schedules[scheduleIds[i]];
            if (!schedule.revoked) {
                total += _releasableAmount(schedule);
            }
        }
    }

    /// @inheritdoc IVAMSVesting
    function totalLocked() external view override returns (uint256) {
        return _totalLocked;
    }

    // ============ Internal Functions ============

    /**
     * @notice Create a new vesting schedule
     */
    function _createSchedule(
        address beneficiary,
        uint256 amount,
        uint256 cliffDuration,
        uint256 vestingDuration,
        uint16 cliffUnlockBps,
        bool revocable,
        ScheduleType scheduleType
    ) internal returns (bytes32 scheduleId) {
        if (beneficiary == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        // Generate unique schedule ID
        scheduleId = keccak256(
            abi.encodePacked(beneficiary, amount, _scheduleCount, block.timestamp)
        );

        // Create schedule
        _schedules[scheduleId] = VestingSchedule({
            beneficiary: beneficiary,
            totalAmount: amount,
            startTimestamp: tgeTimestamp,
            cliffDuration: cliffDuration,
            vestingDuration: vestingDuration,
            cliffUnlockBps: cliffUnlockBps,
            releasedAmount: 0,
            revoked: false,
            revocable: revocable
        });

        // Track beneficiary schedules
        _beneficiarySchedules[beneficiary].push(scheduleId);
        _scheduleCount++;
        _totalLocked += amount;

        // Transfer tokens from admin to this contract
        token.safeTransferFrom(msg.sender, address(this), amount);

        emit VestingScheduleCreated(
            scheduleId,
            beneficiary,
            amount,
            scheduleType,
            cliffDuration,
            vestingDuration
        );
    }

    /**
     * @notice Get schedule parameters for a schedule type
     */
    function _getScheduleParams(ScheduleType scheduleType) 
        internal 
        pure 
        returns (uint256 cliff, uint256 vest, uint16 unlock) 
    {
        if (scheduleType == ScheduleType.FOUNDER) {
            return (CLIFF_FOUNDER, VEST_FOUNDER, UNLOCK_FOUNDER);
        } else if (scheduleType == ScheduleType.TEAM) {
            return (CLIFF_TEAM, VEST_TEAM, UNLOCK_TEAM);
        } else if (scheduleType == ScheduleType.ALLIANCE) {
            return (CLIFF_ALLIANCE, VEST_ALLIANCE, UNLOCK_ALLIANCE);
        } else if (scheduleType == ScheduleType.SEED) {
            return (CLIFF_SEED, VEST_SEED, UNLOCK_SEED);
        } else if (scheduleType == ScheduleType.STRATEGIC) {
            return (CLIFF_STRATEGIC, VEST_STRATEGIC, UNLOCK_STRATEGIC);
        } else if (scheduleType == ScheduleType.COMMUNITY) {
            return (CLIFF_COMMUNITY, VEST_COMMUNITY, UNLOCK_COMMUNITY);
        } else {
            return (CLIFF_TREASURY, VEST_TREASURY, UNLOCK_TREASURY);
        }
    }

    /**
     * @notice Calculate vested amount for a schedule
     */
    function _vestedAmount(VestingSchedule storage schedule) internal view returns (uint256) {
        if (schedule.revoked) {
            return schedule.releasedAmount;
        }

        uint256 elapsed = block.timestamp - schedule.startTimestamp;

        // Before cliff: nothing vested
        if (elapsed < schedule.cliffDuration) {
            return 0;
        }

        // After full vesting: everything vested
        if (elapsed >= schedule.vestingDuration) {
            return schedule.totalAmount;
        }

        // At/after cliff: calculate cliff unlock + linear vesting
        uint256 cliffAmount = (schedule.totalAmount * schedule.cliffUnlockBps) / BPS_DENOMINATOR;
        uint256 linearPortion = schedule.totalAmount - cliffAmount;

        // Time elapsed after cliff
        uint256 elapsedAfterCliff = elapsed - schedule.cliffDuration;
        uint256 vestingAfterCliff = schedule.vestingDuration - schedule.cliffDuration;

        // Linear vesting calculation
        uint256 linearVested = (linearPortion * elapsedAfterCliff) / vestingAfterCliff;

        return cliffAmount + linearVested;
    }

    /**
     * @notice Calculate releasable amount for a schedule
     */
    function _releasableAmount(VestingSchedule storage schedule) internal view returns (uint256) {
        return _vestedAmount(schedule) - schedule.releasedAmount;
    }
}
