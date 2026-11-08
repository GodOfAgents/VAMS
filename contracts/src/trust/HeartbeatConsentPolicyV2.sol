// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV2} from "../governance/OperationAwareVAMSTimelockControllerV2.sol";
import {HeartbeatConsentProfileV2} from "./HeartbeatConsentProfileV2.sol";

/// @notice Separate, non-upgradeable policy profile for the schema-2 consent consumer prototype.
/// @dev No owner profile means no mutation. Constructor values and a nonzero runtime hash do not
///      establish authentic deployment, governance, custody, or chain state.
contract HeartbeatConsentPolicyV2 {
    error Unauthorized();
    error TimelockIdentityMismatch();
    error InvalidPolicyUpdate();

    address public governance;
    bytes32 public timelockRuntimeCodeHash;
    bytes32 public policyRoot;
    uint64 public policyVersion;
    uint64 public authorityEpoch;
    HeartbeatConsentProfileV2.Profile private _profile;

    event ConsentPolicyAdvanced(bytes32 indexed root, uint64 version, uint64 epoch, bytes32 profileDigest);

    constructor(address timelock_) {
        if (timelock_ == address(0) || timelock_.code.length == 0 ||
            timelock_.codehash != keccak256(type(OperationAwareVAMSTimelockControllerV2).runtimeCode) ||
            OperationAwareVAMSTimelockControllerV2(payable(timelock_)).getMinDelay() < 48 hours) {
            revert TimelockIdentityMismatch();
        }
        governance = timelock_;
        timelockRuntimeCodeHash = timelock_.codehash;
    }

    function consentProfile() external view returns (HeartbeatConsentProfileV2.Profile memory) {
        return _profile;
    }

    /// @notice Advance the current policy and install explicit non-default consent decisions.
    /// @dev This call itself must be executed by the pinned Timelock; unknown fields reject.
    function configure(
        bytes32 root,
        uint64 version,
        uint64 epoch,
        HeartbeatConsentProfileV2.Profile calldata next
    ) external {
        if (msg.sender != governance) revert Unauthorized();
        if (root == bytes32(0) || version <= policyVersion || epoch <= authorityEpoch ||
            next.policyRoot != root || next.policyVersion != version || next.authorityEpoch != epoch ||
            !HeartbeatConsentProfileV2.validProfile(next)) revert InvalidPolicyUpdate();
        policyRoot = root;
        policyVersion = version;
        authorityEpoch = epoch;
        _profile = next;
        emit ConsentPolicyAdvanced(root, version, epoch, keccak256(abi.encode(next)));
    }
}

