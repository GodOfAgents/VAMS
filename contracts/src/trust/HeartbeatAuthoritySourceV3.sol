// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OperationAwareVAMSTimelockControllerV3} from "../governance/OperationAwareVAMSTimelockControllerV3.sol";
import {HeartbeatConsentPolicyV3} from "./HeartbeatConsentPolicyV3.sol";
import {
    HeartbeatAuthorityTypesV3 as Types,
    IHeartbeatCustodyAuthorityAdapterV1,
    IHeartbeatAuthoritySourceV3
} from "./HeartbeatAuthorityTypesV3.sol";

/// @notice Read-only V3 producer for directly observed Timelock, policy and custody state.
/// @dev Inactive prototype. A real reviewed custody adapter is mandatory for any activation.
contract HeartbeatAuthoritySourceV3 is IHeartbeatAuthoritySourceV3 {
    error InvalidConfiguration();
    error TimelockUnavailable();
    error PolicyUnavailable();
    error CustodyUnavailable();
    error ProfileUnavailable();
    error ChainIdentityMismatch();

    uint256 public constant RECOVERY_DELAY = 48 hours;
    /// @dev Fixed mechanism budget. A real adapter must independently qualify within it.
    uint256 public constant CUSTODY_READ_GAS = 50_000;

    address public override timelock;
    address public override policy;
    address public custodyAdapter;
    bytes32 public expectedCustodyAdapterRuntimeCodeHash;
    uint256 public expectedChainId;
    bytes32 public networkContextDigest;

    constructor(
        address timelock_,
        address policy_,
        address custodyAdapter_,
        bytes32 expectedCustodyAdapterRuntimeCodeHash_,
        uint256 expectedChainId_,
        bytes32 networkContextDigest_
    ) {
        if (expectedChainId_ == 0 || block.chainid != expectedChainId_) revert ChainIdentityMismatch();
        bytes32 expectedTimelockHash = keccak256(type(OperationAwareVAMSTimelockControllerV3).runtimeCode);
        bytes32 expectedPolicyHash = keccak256(type(HeartbeatConsentPolicyV3).runtimeCode);
        if (
            timelock_ == address(0) || policy_ == address(0) || custodyAdapter_ == address(0) ||
            timelock_.code.length == 0 || policy_.code.length == 0 || custodyAdapter_.code.length == 0 ||
            timelock_.codehash != expectedTimelockHash || policy_.codehash != expectedPolicyHash ||
            expectedCustodyAdapterRuntimeCodeHash_ == bytes32(0) ||
            custodyAdapter_.codehash != expectedCustodyAdapterRuntimeCodeHash_ ||
            networkContextDigest_ == bytes32(0) ||
            OperationAwareVAMSTimelockControllerV3(payable(timelock_)).getMinDelay() < RECOVERY_DELAY
        ) revert InvalidConfiguration();

        HeartbeatConsentPolicyV3 policyContract = HeartbeatConsentPolicyV3(policy_);
        if (
            policyContract.governance() != timelock_ ||
            policyContract.timelockRuntimeCodeHash() != expectedTimelockHash
        ) revert InvalidConfiguration();

        timelock = timelock_;
        policy = policy_;
        custodyAdapter = custodyAdapter_;
        expectedCustodyAdapterRuntimeCodeHash = expectedCustodyAdapterRuntimeCodeHash_;
        expectedChainId = expectedChainId_;
        networkContextDigest = networkContextDigest_;
    }

    /// @notice Compute the current digest without requiring the stored policy digest to match.
    /// @dev This is called during configure before the policy stores the returned digest.
    function computeAuthorityConfigDigest() external view returns (bytes32) {
        return _readState().authorityConfigDigest;
    }

    function currentState() external view returns (Types.ProducerState memory) {
        return _readState();
    }

    function _readState() private view returns (Types.ProducerState memory state) {
        if (block.chainid != expectedChainId || expectedChainId == 0) revert ChainIdentityMismatch();
        bytes32 expectedTimelockHash = keccak256(type(OperationAwareVAMSTimelockControllerV3).runtimeCode);
        bytes32 expectedPolicyHash = keccak256(type(HeartbeatConsentPolicyV3).runtimeCode);
        if (
            timelock.code.length == 0 || timelock.codehash != expectedTimelockHash ||
            OperationAwareVAMSTimelockControllerV3(payable(timelock)).getMinDelay() < RECOVERY_DELAY
        ) revert TimelockUnavailable();
        if (policy.code.length == 0 || policy.codehash != expectedPolicyHash) revert PolicyUnavailable();
        if (
            custodyAdapter.code.length == 0 ||
            custodyAdapter.codehash != expectedCustodyAdapterRuntimeCodeHash
        ) revert CustodyUnavailable();

        HeartbeatConsentPolicyV3 policyContract = HeartbeatConsentPolicyV3(policy);
        Types.Profile memory p = policyContract.consentProfile();
        bytes32 sourceRuntimeHash = address(this).codehash;
        if (
            !p.configured || p.schema != Types.PROFILE_SCHEMA ||
            p.authoritySource != address(this) || p.authoritySourceRuntimeCodeHash != sourceRuntimeHash ||
            policyContract.authoritySource() != address(this) ||
            policyContract.expectedAuthoritySourceRuntimeCodeHash() != sourceRuntimeHash ||
            p.networkContextDigest != networkContextDigest ||
            p.custodyAdapter != custodyAdapter ||
            p.custodyAdapterRuntimeCodeHash != expectedCustodyAdapterRuntimeCodeHash ||
            p.policyRoot != policyContract.policyRoot() || p.policyVersion != policyContract.policyVersion() ||
            p.authorityEpoch != policyContract.authorityEpoch() ||
            p.challengeProvider == address(0) || p.challengeProvider.code.length == 0 ||
            p.challengeProvider.codehash != p.challengeProviderRuntimeCodeHash
        ) revert ProfileUnavailable();

        Types.CustodyState memory custody = _readCustody();

        OperationAwareVAMSTimelockControllerV3 lock =
            OperationAwareVAMSTimelockControllerV3(payable(timelock));
        uint256 minDelay = lock.getMinDelay();
        uint64 authoritySequence = lock.authorityChangeSequence();
        bytes32 authorityCommitment = lock.authorityConfigCommitment();
        if (authorityCommitment == bytes32(0)) revert TimelockUnavailable();
        bytes32 profileDigest = Types.profileProjectionDigest(p);

        state = Types.ProducerState({
            sourceSchema: Types.SOURCE_SCHEMA,
            scheme: Types.EVM_SCHEME,
            chainId: block.chainid,
            networkContextDigest: networkContextDigest,
            source: address(this),
            sourceRuntimeCodeHash: sourceRuntimeHash,
            timelock: timelock,
            timelockRuntimeCodeHash: expectedTimelockHash,
            authorityChangeSequence: authoritySequence,
            authorityConfigCommitment: authorityCommitment,
            minDelay: minDelay,
            policy: policy,
            policyRuntimeCodeHash: expectedPolicyHash,
            policyRoot: p.policyRoot,
            policyVersion: p.policyVersion,
            authorityEpoch: p.authorityEpoch,
            policyProjectionDigest: profileDigest,
            custodyAdapter: custodyAdapter,
            custodyAdapterRuntimeCodeHash: expectedCustodyAdapterRuntimeCodeHash,
            custodyChangeSequence: custody.changeSequence,
            custodyConfigurationDigest: custody.configurationDigest,
            authorityConfigDigest: bytes32(0)
        });

        // SHA-256 over a fixed bytes32 ASCII domain and ABI-encoded static tuple.
        // The helper uses the exact R2 field order while reducing live stack values.
        state.authorityConfigDigest = Types.authorityConfigDigest(state);
        if (state.authorityConfigDigest == bytes32(0)) revert ProfileUnavailable();
    }

    /// @dev Copy only the three static ABI words, even on a revert or oversized response.
    ///      Validate narrow integer words before casting; ABI padding is part of the format.
    function _readCustody() private view returns (Types.CustodyState memory custody) {
        bytes memory input = abi.encodeCall(IHeartbeatCustodyAuthorityAdapterV1.currentCustodyState, ());
        bytes memory output = new bytes(96);
        address adapter = custodyAdapter;
        bool success;
        uint256 returnSize;
        assembly ("memory-safe") {
            success := staticcall(CUSTODY_READ_GAS, adapter, add(input, 32), mload(input), add(output, 32), 96)
            returnSize := returndatasize()
        }
        if (!success || returnSize != 96) revert CustodyUnavailable();

        uint256 schema;
        uint256 sequence;
        bytes32 configurationDigest;
        assembly ("memory-safe") {
            schema := mload(add(output, 32))
            sequence := mload(add(output, 64))
            configurationDigest := mload(add(output, 96))
        }
        if (
            schema != uint256(Types.CUSTODY_SCHEMA) || sequence == 0 ||
            sequence > type(uint64).max || configurationDigest == bytes32(0)
        ) revert CustodyUnavailable();
        return Types.CustodyState(uint16(schema), uint64(sequence), configurationDigest);
    }
}

