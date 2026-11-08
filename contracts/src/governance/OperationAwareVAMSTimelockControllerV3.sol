// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV2} from "./OperationAwareVAMSTimelockControllerV2.sol";

/// @notice V2 operation epochs plus a global history commitment for effective authority changes.
/// @dev Inactive source prototype. V1/V2 identities and consent domains are unchanged. This
///      contract does not configure or activate the heartbeat authority consumer.
contract OperationAwareVAMSTimelockControllerV3 is OperationAwareVAMSTimelockControllerV2 {
    error AuthorityChangeSequenceOverflow();
    error ZeroAuthorityConfigurationCommitment();

    bytes32 public constant AUTHORITY_CONFIG_V3_DOMAIN =
        keccak256("VAMS_OPERATION_AWARE_TIMELOCK_AUTHORITY_CONFIG_V3");
    bytes32 public constant INITIAL_ROLE_CONFIG_V3_DOMAIN =
        keccak256("VAMS_OPERATION_AWARE_TIMELOCK_INITIAL_ROLE_CONFIG_V3");
    bytes32 public constant AUTHORITY_MUTATION_V3_DOMAIN =
        keccak256("VAMS_OPERATION_AWARE_TIMELOCK_AUTHORITY_MUTATION_V3");

    bytes32 private constant _ROLE_GRANTED = keccak256("ROLE_GRANTED");
    bytes32 private constant _ROLE_REVOKED = keccak256("ROLE_REVOKED");
    bytes32 private constant _ROLE_ADMIN_CHANGED = keccak256("ROLE_ADMIN_CHANGED");
    bytes32 private constant _MIN_DELAY_CHANGED = keccak256("MIN_DELAY_CHANGED");

    /// @notice Monotonic generation for effective role/admin/min-delay mutations.
    uint64 public authorityChangeSequence;

    /// @notice Chained history commitment; A→B→A does not restore an earlier commitment.
    bytes32 public authorityConfigCommitment;

    /// @notice Canonical digest of constructor role configuration, including this controller's self-admin membership.
    /// @dev Immutable-by-convention storage: this contract exposes no setter for this value.
    bytes32 public initialRoleConfigurationDigest;

    bool private _authorityTrackingEnabled;

    constructor(uint256 minDelay, address[] memory proposers, address[] memory executors, address admin)
        OperationAwareVAMSTimelockControllerV2(minDelay, proposers, executors, admin)
    {
        address[] memory adminMembers = new address[](
            admin != address(0) && admin != address(this) ? 2 : 1
        );
        adminMembers[0] = address(this);
        if (adminMembers.length == 2) adminMembers[1] = admin;

        address[] memory canonicalAdmins = _sortAndUnique(adminMembers);
        address[] memory canonicalProposers = _sortAndUnique(proposers);
        address[] memory canonicalExecutors = _sortAndUnique(executors);

        bytes32 adminSetDigest = keccak256(
            abi.encode(DEFAULT_ADMIN_ROLE, getRoleAdmin(DEFAULT_ADMIN_ROLE), canonicalAdmins)
        );
        bytes32 proposerSetDigest = keccak256(
            abi.encode(PROPOSER_ROLE, getRoleAdmin(PROPOSER_ROLE), canonicalProposers)
        );
        bytes32 cancellerSetDigest = keccak256(
            abi.encode(CANCELLER_ROLE, getRoleAdmin(CANCELLER_ROLE), canonicalProposers)
        );
        bytes32 executorSetDigest = keccak256(
            abi.encode(EXECUTOR_ROLE, getRoleAdmin(EXECUTOR_ROLE), canonicalExecutors)
        );
        initialRoleConfigurationDigest = keccak256(
            abi.encode(
                INITIAL_ROLE_CONFIG_V3_DOMAIN,
                getMinDelay(),
                adminSetDigest,
                proposerSetDigest,
                cancellerSetDigest,
                executorSetDigest
            )
        );

        authorityConfigCommitment = keccak256(
            abi.encode(
                AUTHORITY_CONFIG_V3_DOMAIN,
                block.chainid,
                address(this),
                initialRoleConfigurationDigest
            )
        );
        if (authorityConfigCommitment == bytes32(0)) revert ZeroAuthorityConfigurationCommitment();

        // Base constructors grant the initial Timelock roles before this point. Those grants
        // are represented by the canonical initial digest, not counted as later mutations.
        _authorityTrackingEnabled = true;
    }

    /// @dev The frozen VAMS updateDelay method is non-virtual. Its inherited implementation
    ///      still enforces the 48-hour floor and timelock self-call. Every executable target
    ///      (including each batch item) passes through this OpenZeppelin virtual hook. Observe
    ///      the effective delay transition after that call returns, before the next target.
    ///      V1 rejects nested execute/executeBatch; updateDelay makes no external callback.
    function _execute(address target, uint256 value, bytes calldata data) internal override {
        uint256 previousDelay = getMinDelay();
        super._execute(target, value, data);
        uint256 currentDelay = getMinDelay();
        if (_authorityTrackingEnabled && currentDelay != previousDelay) {
            _recordAuthorityChange(_MIN_DELAY_CHANGED, bytes32(0), address(0), previousDelay, currentDelay);
        }
    }

    function _grantRole(bytes32 role, address account) internal override returns (bool changed) {
        changed = super._grantRole(role, account);
        if (changed && _authorityTrackingEnabled) {
            _recordAuthorityChange(_ROLE_GRANTED, role, account, 0, 1);
        }
    }

    function _revokeRole(bytes32 role, address account) internal override returns (bool changed) {
        changed = super._revokeRole(role, account);
        if (changed && _authorityTrackingEnabled) {
            _recordAuthorityChange(_ROLE_REVOKED, role, account, 1, 0);
        }
    }

    function _setRoleAdmin(bytes32 role, bytes32 adminRole) internal override {
        bytes32 previousAdminRole = getRoleAdmin(role);
        super._setRoleAdmin(role, adminRole);
        if (_authorityTrackingEnabled && previousAdminRole != adminRole) {
            _recordAuthorityChange(
                _ROLE_ADMIN_CHANGED,
                role,
                address(0),
                uint256(previousAdminRole),
                uint256(adminRole)
            );
        }
    }

    function _recordAuthorityChange(
        bytes32 mutationKind,
        bytes32 role,
        address account,
        uint256 oldValue,
        uint256 newValue
    ) private {
        uint64 previousSequence = authorityChangeSequence;
        if (previousSequence == type(uint64).max) revert AuthorityChangeSequenceOverflow();
        uint64 nextSequence = previousSequence + 1;
        bytes32 nextCommitment = keccak256(
            abi.encode(
                AUTHORITY_MUTATION_V3_DOMAIN,
                authorityConfigCommitment,
                nextSequence,
                mutationKind,
                role,
                account,
                oldValue,
                newValue
            )
        );
        if (nextCommitment == bytes32(0)) revert ZeroAuthorityConfigurationCommitment();
        authorityChangeSequence = nextSequence;
        authorityConfigCommitment = nextCommitment;
    }

    /// @dev Sorts and deduplicates constructor role arrays so input order and duplicates do
    ///      not alter the digest of the effective initial membership set.
    function _sortAndUnique(address[] memory values) private pure returns (address[] memory uniqueValues) {
        for (uint256 i = 1; i < values.length; ++i) {
            address value = values[i];
            uint256 j = i;
            while (j > 0 && uint160(values[j - 1]) > uint160(value)) {
                values[j] = values[j - 1];
                unchecked { --j; }
            }
            values[j] = value;
        }

        uint256 uniqueCount;
        for (uint256 i; i < values.length; ++i) {
            if (i == 0 || values[i] != values[i - 1]) ++uniqueCount;
        }

        uniqueValues = new address[](uniqueCount);
        uint256 outputIndex;
        for (uint256 i; i < values.length; ++i) {
            if (i == 0 || values[i] != values[i - 1]) {
                uniqueValues[outputIndex] = values[i];
                ++outputIndex;
            }
        }
    }
}
