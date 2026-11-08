// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {HeartbeatPrincipalV1 as P} from "../src/trust/HeartbeatPrincipalV1.sol";
import {GovernedHeartbeatPrincipalRegistryV1 as Registry} from "../src/trust/GovernedHeartbeatPrincipalRegistryV1.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {VAMSTimelockController} from "../src/governance/VAMSTimelockController.sol";

contract HeartbeatRegistrySafeSingletonFixture {}

/// @dev Local synthetic Safe-shaped fixture, not Safe implementation or custody evidence.
contract HeartbeatRegistrySafeFixture {
    address private immutable _singleton;
    address[3] private _owners;
    uint256 private immutable _threshold;

    constructor(address singleton_, address[3] memory owners_, uint256 threshold_) {
        _singleton = singleton_;
        for (uint256 i; i < 3; ++i) _owners[i] = owners_[i];
        _threshold = threshold_;
    }

    function masterCopy() external view returns (address) { return _singleton; }
    function getOwners() external view returns (address[] memory owners) {
        owners = new address[](3);
        for (uint256 i; i < 3; ++i) owners[i] = _owners[i];
    }
    function getThreshold() external view returns (uint256) { return _threshold; }
}

/// @dev Getter-compatible impostor; runtime identity must reject it before getters are trusted.
contract HeartbeatRegistryFakePolicyFixture {
    function governance() external pure returns (address) { return address(0x1234); }
    function hostDomain() external pure returns (bytes32) { return bytes32(uint256(5)); }
    function budgetUnit() external pure returns (bytes32) { return bytes32(uint256(6)); }
    function policyRoot() external pure returns (bytes32) { return bytes32(uint256(7)); }
    function policyVersion() external pure returns (uint256) { return 1; }
    function authorityEpoch() external pure returns (uint256) { return 1; }
}

contract HeartbeatRegistryShapeOnlySafeFixture {
    function masterCopy() external pure returns (address) { return address(0x8888); }
    function getOwners() external pure returns (address[] memory owners) {
        owners = new address[](3);
        owners[0] = address(0xA001);
        owners[1] = address(0xA002);
        owners[2] = address(0xA003);
    }
    function getThreshold() external pure returns (uint256) { return 2; }
}

contract GovernedHeartbeatPrincipalRegistryV1Tests is Test {
    bytes32 internal constant HOST = bytes32(uint256(5));
    bytes32 internal constant SERVICE = bytes32(uint256(6));
    bytes32 internal constant UNIT = bytes32(uint256(7));
    bytes32 internal constant ROOT1 = bytes32(uint256(0xAA));
    bytes32 internal constant ROOT2 = bytes32(uint256(0xBB));

    VAMSTimelockController internal timelock;
    RestrictedTestnetPolicyV1 internal policy;
    HeartbeatRegistrySafeSingletonFixture internal singleton;
    HeartbeatRegistrySafeFixture internal emergencySafe;
    Registry internal registry;
    uint256 internal operationSalt;

    function setUp() public {
        vm.warp(1_700_000_001);
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        timelock = new VAMSTimelockController(48 hours, proposers, executors, address(this));
        singleton = new HeartbeatRegistrySafeSingletonFixture();
        address[3] memory owners = [address(0xA001), address(0xA002), address(0xA003)];
        emergencySafe = new HeartbeatRegistrySafeFixture(address(singleton), owners, 2);
        policy = new RestrictedTestnetPolicyV1(address(timelock), HOST, UNIT);
        registry = _deployRegistry(address(policy), address(emergencySafe), _safeIdentity(emergencySafe));
    }

    function testStartsPausedAndEmergencySafeHasPauseOnlyAuthority() public {
        assertTrue(registry.paused());
        _configurePolicy(ROOT1, 1, 1);
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT1, uint64(1), uint64(1))));
        assertFalse(registry.paused());

        vm.prank(address(emergencySafe));
        registry.pause();
        assertTrue(registry.paused());
        vm.expectRevert(Registry.Unauthorized.selector);
        vm.prank(address(emergencySafe));
        registry.unpause(ROOT1, 1, 1);
        vm.warp(block.timestamp + 30 days);
        assertTrue(registry.paused());

        P.Record memory record = _record(1, ROOT1, 1, 1);
        bytes memory encoded = P.canonicalBytes(record);
        vm.expectRevert(Registry.Unauthorized.selector);
        vm.prank(address(emergencySafe));
        registry.registerPrincipal(encoded, bytes32(0), 0);
    }

    function testTimelockRegistrationCasAndReadback() public {
        _configurePolicy(ROOT1, 1, 1);
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT1, uint64(1), uint64(1))));
        P.Record memory record = _record(1, ROOT1, 1, 1);
        bytes memory encoded = P.canonicalBytes(record);
        _timelockCall(address(registry), abi.encodeCall(registry.registerPrincipal, (encoded, bytes32(0), uint64(0))));
        (bytes memory stored, bytes32 digest_, uint64 generation, bool tombstone, bool active) =
            registry.principalState(record.principalId);
        assertEq(stored, encoded);
        assertEq(digest_, P.digest(record));
        assertEq(generation, 1);
        assertFalse(tombstone);
        assertTrue(active);
    }

    function testPolicyAdvanceInvalidatesOldRecordAndCurrentCasReplacementRestoresIt() public {
        _configurePolicy(ROOT1, 1, 1);
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT1, uint64(1), uint64(1))));
        P.Record memory first = _record(1, ROOT1, 1, 1);
        bytes memory firstBytes = P.canonicalBytes(first);
        _timelockCall(address(registry), abi.encodeCall(registry.registerPrincipal, (firstBytes, bytes32(0), uint64(0))));

        _configurePolicy(ROOT2, 2, 2);
        (,,,, bool activeBefore) = registry.principalState(first.principalId);
        assertFalse(activeBefore);

        P.Record memory replacement = _record(2, ROOT2, 2, 2);
        bytes memory replacementBytes = P.canonicalBytes(replacement);
        _timelockCall(address(registry), abi.encodeCall(
            registry.replacePrincipal, (first.principalId, P.digest(first), uint64(1), replacementBytes)
        ));
        (bytes memory stored, bytes32 newDigest, uint64 generation, bool tombstone, bool active) =
            registry.principalState(first.principalId);
        assertEq(stored, replacementBytes);
        assertEq(newDigest, P.digest(replacement));
        assertEq(generation, 2);
        assertFalse(tombstone);
        assertTrue(active);
    }

    function testRevocationPersistsTombstoneAndBlocksReenrollment() public {
        _configurePolicy(ROOT1, 1, 1);
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT1, uint64(1), uint64(1))));
        P.Record memory record = _record(1, ROOT1, 1, 1);
        bytes memory encoded = P.canonicalBytes(record);
        bytes32 digest_ = P.digest(record);
        _timelockCall(address(registry), abi.encodeCall(registry.registerPrincipal, (encoded, bytes32(0), uint64(0))));
        _timelockCall(address(registry), abi.encodeCall(
            registry.revokePrincipal,
            (record.principalId, digest_, uint64(1), ROOT1, uint64(1), uint64(1))
        ));
        (bytes memory stored, bytes32 tombstoneDigest, uint64 generation, bool tombstone, bool active) =
            registry.principalState(record.principalId);
        assertEq(stored, encoded);
        assertTrue(tombstoneDigest != digest_);
        assertEq(generation, 2);
        assertTrue(tombstone);
        assertFalse(active);

        bytes memory staleEnroll = abi.encodeCall(registry.registerPrincipal, (encoded, bytes32(0), uint64(0)));
        bytes32 salt = bytes32(++operationSalt);
        _schedule(address(registry), staleEnroll, salt);
        vm.expectRevert(Registry.CompareAndSetFailed.selector);
        _executeScheduled(address(registry), staleEnroll, salt);
    }

    function testQueuedUnpauseWithOldPolicySnapshotFailsAtExecution() public {
        _configurePolicy(ROOT1, 1, 1);
        bytes memory staleUnpause = abi.encodeCall(registry.unpause, (ROOT1, uint64(1), uint64(1)));
        bytes32 salt = bytes32(++operationSalt);
        _schedule(address(registry), staleUnpause, salt);
        _configurePolicy(ROOT2, 2, 2);
        vm.expectRevert(Registry.StalePolicySnapshot.selector);
        _executeScheduled(address(registry), staleUnpause, salt);
        assertTrue(registry.paused());
    }

    function testGetterCompatiblePolicyImpostorRejectedBeforeGetters() public {
        HeartbeatRegistryFakePolicyFixture fake = new HeartbeatRegistryFakePolicyFixture();
        vm.expectRevert(Registry.PolicyRuntimeMismatch.selector);
        _deployRegistry(address(fake), address(emergencySafe), _safeIdentity(emergencySafe));
    }

    function testRealPolicyWithDifferentImmutableHostRejected() public {
        RestrictedTestnetPolicyV1 wrongHost = new RestrictedTestnetPolicyV1(address(timelock), bytes32(uint256(0x55)), UNIT);
        vm.expectRevert(Registry.PolicyRuntimeMismatch.selector);
        _deployRegistry(address(wrongHost), address(emergencySafe), _safeIdentity(emergencySafe));
    }

    function testSafeGetterShapeWithoutPinnedCodeIdentityRejected() public {
        HeartbeatRegistryShapeOnlySafeFixture fake = new HeartbeatRegistryShapeOnlySafeFixture();
        vm.expectRevert(Registry.InvalidEmergencySafe.selector);
        _deployRegistry(address(policy), address(fake), _safeIdentity(emergencySafe));
    }

    function testSafeWithWrongThresholdRejectedEvenWhenItsRuntimeIsConfigured() public {
        address[3] memory owners = [address(0xB001), address(0xB002), address(0xB003)];
        HeartbeatRegistrySafeFixture wrongThreshold =
            new HeartbeatRegistrySafeFixture(address(singleton), owners, 1);
        vm.expectRevert(Registry.InvalidEmergencySafe.selector);
        _deployRegistry(address(policy), address(wrongThreshold), _safeIdentity(wrongThreshold));
    }

    function _deployRegistry(address policyAddress, address safe, Registry.SafeIdentity memory safeIdentity)
        internal returns (Registry)
    {
        return new Registry(policyAddress, address(timelock), HOST, SERVICE, UNIT, safe, safeIdentity);
    }

    function _configurePolicy(bytes32 root, uint256 version, uint256 epoch) internal {
        _timelockCall(address(policy), abi.encodeCall(policy.configure, (root, version, epoch, 4, 1_000, 600)));
    }

    function _timelockCall(address target, bytes memory data) internal {
        bytes32 salt = bytes32(++operationSalt);
        _schedule(target, data, salt);
        _executeScheduled(target, data, salt);
    }

    function _schedule(address target, bytes memory data, bytes32 salt) internal {
        timelock.schedule(target, 0, data, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
    }

    function _executeScheduled(address target, bytes memory data, bytes32 salt) internal {
        timelock.execute(target, 0, data, bytes32(0), salt);
    }

    function _safeIdentity(HeartbeatRegistrySafeFixture safe)
        internal view returns (Registry.SafeIdentity memory)
    {
        return Registry.SafeIdentity({
            proxyRuntimeCodeHash: address(safe).codehash,
            singleton: address(singleton),
            singletonRuntimeCodeHash: address(singleton).codehash
        });
    }

    function _record(uint64 generation, bytes32 root, uint64 version, uint64 epoch)
        internal view returns (P.Record memory record)
    {
        bytes memory signerKey = new bytes(64);
        bytes memory did = bytes("did:key:");
        bytes memory hexAlphabet = bytes("0123456789abcdef");
        for (uint256 i; i < 64; ++i) {
            signerKey[i] = 0x11;
            did = bytes.concat(did, hexAlphabet[1], hexAlphabet[1]);
        }
        bytes memory bodyKey = new bytes(64);
        for (uint256 i; i < 64; ++i) bodyKey[i] = 0x04;
        bytes32 nodeCommitment = bytes32(0x79121d7d912632aaf935e2b08d31942fa6c2242e3d17dd751612188321f6d26d);
        record = P.Record({
            principalId: P.principalIdFor(HOST, SERVICE, nodeCommitment),
            nodeIdCommitment: nodeCommitment,
            m2SignerDid: string(did),
            m2SignerPublicKey: signerKey,
            certificateFingerprint: bytes32(uint256(3)),
            bodyPublicKey: bodyKey,
            hostDomain: HOST,
            serviceDomain: SERVICE,
            audience: "gateway.testnet",
            method: "POST",
            path: "/heartbeat",
            query: bytes(""),
            policyRoot: root,
            policyVersion: version,
            authorityEpoch: epoch,
            principalGeneration: generation,
            notBefore: uint64(block.timestamp - 1),
            expiresAt: uint64(block.timestamp + 365 days)
        });
        require(P.valid(record), "Invalid local record fixture");
    }
}

/// @dev Variable cardinality Safe-shaped fixture; tests only the registry's bounded shape checks.
contract HeartbeatRegistryVariableSafeFixture {
    address private immutable _singleton;
    address[] private _owners;
    uint256 private immutable _threshold;

    constructor(address singleton_, address[] memory owners_, uint256 threshold_) {
        _singleton = singleton_;
        _owners = owners_;
        _threshold = threshold_;
    }

    function masterCopy() external view returns (address) { return _singleton; }
    function getOwners() external view returns (address[] memory) { return _owners; }
    function getThreshold() external view returns (uint256) { return _threshold; }
}

/// @dev Local adversarial tests only; all timelocks, policies, and Safe-shaped contracts are fixtures.
contract GovernedHeartbeatPrincipalRegistryV1AdversarialTests is Test {
    bytes32 internal constant HOST = bytes32(uint256(5));
    bytes32 internal constant SERVICE = bytes32(uint256(6));
    bytes32 internal constant UNIT = bytes32(uint256(7));
    bytes32 internal constant ROOT = bytes32(uint256(0xAA));

    VAMSTimelockController internal timelock;
    RestrictedTestnetPolicyV1 internal policy;
    HeartbeatRegistrySafeSingletonFixture internal singleton;
    HeartbeatRegistrySafeFixture internal emergencySafe;
    Registry internal registry;
    uint256 internal operationSalt;

    function setUp() public {
        vm.warp(1_700_000_001);
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        timelock = new VAMSTimelockController(48 hours, proposers, executors, address(this));
        singleton = new HeartbeatRegistrySafeSingletonFixture();
        address[3] memory owners = [address(0xA001), address(0xA002), address(0xA003)];
        emergencySafe = new HeartbeatRegistrySafeFixture(address(singleton), owners, 2);
        policy = new RestrictedTestnetPolicyV1(address(timelock), HOST, UNIT);
        registry = _deploy(address(policy), address(timelock), address(emergencySafe), _safeIdentity(address(emergencySafe), address(singleton)));
    }

    function testRejectsWrongTimelockRuntimeAfterPolicyIdentityMatches() public {
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(this);
        executors[0] = address(this);
        VAMSTimelockController boundTarget = new VAMSTimelockController(48 hours, proposers, executors, address(this));
        RestrictedTestnetPolicyV1 boundPolicy = new RestrictedTestnetPolicyV1(address(boundTarget), HOST, UNIT);
        vm.etch(address(boundTarget), hex"00");

        vm.expectRevert(Registry.TimelockIdentityMismatch.selector);
        _deploy(address(boundPolicy), address(boundTarget), address(emergencySafe), _safeIdentity(address(emergencySafe), address(singleton)));
    }

    function testRejectsTimelockDelayBelowFloorWithPolicyIdentityMatching() public {
        vm.mockCall(
            address(timelock),
            abi.encodeWithSignature("getMinDelay()"),
            abi.encode(47 hours)
        );
        vm.expectRevert(Registry.TimelockIdentityMismatch.selector);
        _deploy(address(policy), address(timelock), address(emergencySafe), _safeIdentity(address(emergencySafe), address(singleton)));
        vm.clearMockedCalls();
    }

    function testRejectsSafeOwnerListsWithWrongCardinality() public {
        address[] memory two = new address[](2);
        two[0] = address(0xA001);
        two[1] = address(0xA002);
        HeartbeatRegistryVariableSafeFixture twoOwner =
            new HeartbeatRegistryVariableSafeFixture(address(singleton), two, 2);
        vm.expectRevert(Registry.InvalidEmergencySafe.selector);
        _deploy(address(policy), address(timelock), address(twoOwner), _safeIdentity(address(twoOwner), address(singleton)));

        address[] memory four = new address[](4);
        four[0] = address(0xA001);
        four[1] = address(0xA002);
        four[2] = address(0xA003);
        four[3] = address(0xA004);
        HeartbeatRegistryVariableSafeFixture fourOwner =
            new HeartbeatRegistryVariableSafeFixture(address(singleton), four, 2);
        vm.expectRevert(Registry.InvalidEmergencySafe.selector);
        _deploy(address(policy), address(timelock), address(fourOwner), _safeIdentity(address(fourOwner), address(singleton)));
    }

    function testRejectsDuplicateSafeOwners() public {
        address[3] memory owners = [address(0xA001), address(0xA001), address(0xA003)];
        HeartbeatRegistrySafeFixture duplicate =
            new HeartbeatRegistrySafeFixture(address(singleton), owners, 2);
        vm.expectRevert(Registry.InvalidEmergencySafe.selector);
        _deploy(address(policy), address(timelock), address(duplicate), _safeIdentity(address(duplicate), address(singleton)));
    }

    function testRejectsEmergencySafeWithMismatchedSingletonIdentity() public {
        HeartbeatRegistrySafeSingletonFixture otherSingleton = new HeartbeatRegistrySafeSingletonFixture();
        vm.expectRevert(Registry.InvalidEmergencySafe.selector);
        _deploy(address(policy), address(timelock), address(emergencySafe), _safeIdentity(address(emergencySafe), address(otherSingleton)));
    }

    function testStaleReplacementCasCannotReplayAfterGenerationAdvances() public {
        _configurePolicy();
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT, uint64(1), uint64(1))));
        P.Record memory first = _record(1);
        bytes memory firstBytes = P.canonicalBytes(first);
        _timelockCall(address(registry), abi.encodeCall(registry.registerPrincipal, (firstBytes, bytes32(0), uint64(0))));

        P.Record memory replacement = _record(2);
        bytes memory replacementBytes = P.canonicalBytes(replacement);
        _timelockCall(address(registry), abi.encodeCall(
            registry.replacePrincipal, (first.principalId, P.digest(first), uint64(1), replacementBytes)
        ));

        bytes memory staleCall = abi.encodeCall(
            registry.replacePrincipal, (first.principalId, P.digest(first), uint64(1), replacementBytes)
        );
        bytes32 salt = bytes32(++operationSalt);
        _schedule(address(registry), staleCall, salt);
        vm.expectRevert(Registry.CompareAndSetFailed.selector);
        _executeScheduled(address(registry), staleCall, salt);
    }

    function testNotBeforeAndExpiryUseExactHalfOpenBoundaries() public {
        _configurePolicy();
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT, uint64(1), uint64(1))));
        P.Record memory record = _record(1);
        record.notBefore = uint64(block.timestamp + 48 hours + 1);
        record.expiresAt = record.notBefore + 1;
        bytes memory encoded = P.canonicalBytes(record);
        bytes memory callData = abi.encodeCall(registry.registerPrincipal, (encoded, bytes32(0), uint64(0)));
        bytes32 salt = bytes32(++operationSalt);
        _schedule(address(registry), callData, salt);

        // The timelock is ready one second before notBefore; the reverted attempt remains queued.
        vm.expectRevert(Registry.RecordNotCurrentlyValid.selector);
        _executeScheduled(address(registry), callData, salt);
        vm.warp(block.timestamp + 1);
        _executeScheduled(address(registry), callData, salt);
        (,,,, bool activeAtNotBefore) = registry.principalState(record.principalId);
        assertTrue(activeAtNotBefore);
        vm.warp(block.timestamp + 1);
        (,,,, bool activeAtExpiry) = registry.principalState(record.principalId);
        assertFalse(activeAtExpiry);
    }

    function testMalformedAndOversizedRegistrationRecordsFailClosed() public {
        _configurePolicy();
        _timelockCall(address(registry), abi.encodeCall(registry.unpause, (ROOT, uint64(1), uint64(1))));
        bytes memory malformed = hex"01";
        bytes memory malformedCall = abi.encodeCall(registry.registerPrincipal, (malformed, bytes32(0), uint64(0)));
        bytes32 malformedSalt = bytes32(++operationSalt);
        _schedule(address(registry), malformedCall, malformedSalt);
        vm.expectRevert(Registry.InvalidRecord.selector);
        _executeScheduled(address(registry), malformedCall, malformedSalt);

        bytes memory oversized = new bytes(1025);
        bytes memory oversizedCall = abi.encodeCall(registry.registerPrincipal, (oversized, bytes32(0), uint64(0)));
        bytes32 oversizedSalt = bytes32(++operationSalt);
        _schedule(address(registry), oversizedCall, oversizedSalt);
        vm.expectRevert(Registry.InvalidRecord.selector);
        _executeScheduled(address(registry), oversizedCall, oversizedSalt);
    }

    function _deploy(address policyAddress, address timelockAddress, address safe, Registry.SafeIdentity memory identity)
        internal returns (Registry)
    {
        return new Registry(policyAddress, timelockAddress, HOST, SERVICE, UNIT, safe, identity);
    }

    function _safeIdentity(address safe, address singletonAddress)
        internal view returns (Registry.SafeIdentity memory)
    {
        return Registry.SafeIdentity({
            proxyRuntimeCodeHash: safe.codehash,
            singleton: singletonAddress,
            singletonRuntimeCodeHash: singletonAddress.codehash
        });
    }

    function _configurePolicy() internal {
        _timelockCall(address(policy), abi.encodeCall(policy.configure, (ROOT, uint256(1), uint256(1), uint256(4), uint256(1_000), uint256(600))));
    }

    function _timelockCall(address target, bytes memory data) internal {
        bytes32 salt = bytes32(++operationSalt);
        _schedule(target, data, salt);
        _executeScheduled(target, data, salt);
    }

    function _schedule(address target, bytes memory data, bytes32 salt) internal {
        timelock.schedule(target, 0, data, bytes32(0), salt, 48 hours);
        vm.warp(block.timestamp + 48 hours);
    }

    function _executeScheduled(address target, bytes memory data, bytes32 salt) internal {
        timelock.execute(target, 0, data, bytes32(0), salt);
    }

    function _record(uint64 generation) internal view returns (P.Record memory record) {
        bytes memory signerKey = new bytes(64);
        bytes memory did = bytes("did:key:");
        bytes memory hexAlphabet = bytes("0123456789abcdef");
        for (uint256 i; i < 64; ++i) {
            signerKey[i] = 0x11;
            did = bytes.concat(did, hexAlphabet[1], hexAlphabet[1]);
        }
        bytes memory bodyKey = new bytes(64);
        for (uint256 i; i < 64; ++i) bodyKey[i] = 0x04;
        bytes32 nodeCommitment = bytes32(0x79121d7d912632aaf935e2b08d31942fa6c2242e3d17dd751612188321f6d26d);
        record = P.Record({
            principalId: P.principalIdFor(HOST, SERVICE, nodeCommitment),
            nodeIdCommitment: nodeCommitment,
            m2SignerDid: string(did),
            m2SignerPublicKey: signerKey,
            certificateFingerprint: bytes32(uint256(3)),
            bodyPublicKey: bodyKey,
            hostDomain: HOST,
            serviceDomain: SERVICE,
            audience: "gateway.testnet",
            method: "POST",
            path: "/heartbeat",
            query: bytes(""),
            policyRoot: ROOT,
            policyVersion: 1,
            authorityEpoch: 1,
            principalGeneration: generation,
            notBefore: uint64(block.timestamp - 1),
            expiresAt: uint64(block.timestamp + 365 days)
        });
        require(P.valid(record), "Invalid local record fixture");
    }
}/// @dev Shape-only 5/3 fixture. Foundry impersonation below does not prove Safe signatures or custody.
contract HeartbeatRegistryGovernanceSafeFixture {
    address[5] private _owners;
    uint256 private constant _threshold = 3;

    constructor(address[5] memory owners_) {
        for (uint256 i; i < 5; ++i) _owners[i] = owners_[i];
    }

    function getOwners() external view returns (address[] memory owners) {
        owners = new address[](5);
        for (uint256 i; i < 5; ++i) owners[i] = _owners[i];
    }

    function getThreshold() external pure returns (uint256) { return _threshold; }
}

/// @dev Role wiring and delayed operations only; fixtures do not emulate multisig signatures.
contract GovernedHeartbeatPrincipalRegistryV1GovernanceRoleTests is Test {
    bytes32 internal constant HOST = bytes32(uint256(5));
    bytes32 internal constant SERVICE = bytes32(uint256(6));
    bytes32 internal constant UNIT = bytes32(uint256(7));
    bytes32 internal constant ROOT = bytes32(uint256(0xAA));

    uint256 internal operationSalt;
    HeartbeatRegistryGovernanceSafeFixture internal governanceFixture;
    VAMSTimelockController internal timelock;
    HeartbeatRegistrySafeSingletonFixture internal singleton;
    HeartbeatRegistrySafeFixture internal emergencySafe;
    RestrictedTestnetPolicyV1 internal policy;
    Registry internal registry;

    function setUp() public {
        vm.warp(1_700_000_001);
        address[5] memory governorOwners = [
            address(0xB001), address(0xB002), address(0xB003), address(0xB004), address(0xB005)
        ];
        governanceFixture = new HeartbeatRegistryGovernanceSafeFixture(governorOwners);
        address[] memory proposers = new address[](1);
        address[] memory executors = new address[](1);
        proposers[0] = address(governanceFixture);
        executors[0] = address(0); // Execution is open; scheduling remains restricted.
        timelock = new VAMSTimelockController(48 hours, proposers, executors, address(0));

        singleton = new HeartbeatRegistrySafeSingletonFixture();
        address[3] memory emergencyOwners = [address(0xA001), address(0xA002), address(0xA003)];
        emergencySafe = new HeartbeatRegistrySafeFixture(address(singleton), emergencyOwners, 2);
        policy = new RestrictedTestnetPolicyV1(address(timelock), HOST, UNIT);
        registry = new Registry(
            address(policy), address(timelock), HOST, SERVICE, UNIT, address(emergencySafe),
            Registry.SafeIdentity({
                proxyRuntimeCodeHash: address(emergencySafe).codehash,
                singleton: address(singleton),
                singletonRuntimeCodeHash: address(singleton).codehash
            })
        );
    }

    function testFiveOfThreeRoleWiringAndDirectAccessDenials() public {
        address[] memory owners = governanceFixture.getOwners();
        assertEq(owners.length, 5);
        assertEq(governanceFixture.getThreshold(), 3);
        address[] memory emergencyOwnerSet = emergencySafe.getOwners();
        assertEq(emergencyOwnerSet.length, 3);
        assertEq(emergencySafe.getThreshold(), 2);
        assertTrue(timelock.hasRole(timelock.PROPOSER_ROLE(), address(governanceFixture)));
        assertTrue(timelock.hasRole(timelock.CANCELLER_ROLE(), address(governanceFixture)));
        assertFalse(timelock.hasRole(timelock.PROPOSER_ROLE(), address(emergencySafe)));
        assertFalse(timelock.hasRole(timelock.CANCELLER_ROLE(), address(emergencySafe)));
        assertFalse(timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), address(this)));
        assertFalse(timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), address(governanceFixture)));
        assertFalse(timelock.hasRole(timelock.PROPOSER_ROLE(), address(this)));
        assertFalse(timelock.hasRole(timelock.CANCELLER_ROLE(), address(this)));
        assertTrue(registry.paused());

        bytes memory configureData = abi.encodeCall(
            policy.configure, (ROOT, uint256(1), uint256(1), uint256(4), uint256(1_000), uint256(600))
        );
        bytes32 ordinarySalt = bytes32(++operationSalt);
        vm.expectRevert();
        vm.prank(address(this));
        timelock.schedule(address(policy), 0, configureData, bytes32(0), ordinarySalt, 48 hours);

        P.Record memory record = _record();
        bytes memory recordBytes = P.canonicalBytes(record);
        vm.expectRevert(Registry.Unauthorized.selector);
        vm.prank(address(this));
        registry.registerPrincipal(recordBytes, bytes32(0), 0);
    }

    function testGovernanceConfigurationRequiresFortyEightHourDelay() public {
        bytes memory configureData = abi.encodeCall(
            policy.configure, (ROOT, uint256(1), uint256(1), uint256(4), uint256(1_000), uint256(600))
        );
        _scheduleAndAssertFortyEightHourDelay(address(policy), configureData);
        assertEq(policy.policyRoot(), ROOT);
        assertEq(policy.policyVersion(), 1);
        assertEq(policy.authorityEpoch(), 1);
    }

    function testEmergencySafeCanOnlyPauseNotScheduleCancelOrUnpause() public {
        _configureAndUnpause();
        vm.prank(address(emergencySafe));
        registry.pause();
        assertTrue(registry.paused());

        vm.expectRevert(Registry.Unauthorized.selector);
        vm.prank(address(emergencySafe));
        registry.unpause(ROOT, 1, 1);

        bytes memory pauseData = abi.encodeCall(registry.pause, ());
        bytes32 deniedSalt = bytes32(++operationSalt);
        vm.expectRevert();
        vm.prank(address(emergencySafe));
        timelock.schedule(address(registry), 0, pauseData, bytes32(0), deniedSalt, 48 hours);

        bytes32 queuedSalt = bytes32(++operationSalt);
        bytes32 queuedId = timelock.hashOperation(address(registry), 0, pauseData, bytes32(0), queuedSalt);
        _scheduleAs(address(governanceFixture), address(registry), pauseData, queuedSalt);
        vm.expectRevert();
        vm.prank(address(emergencySafe));
        timelock.cancel(queuedId);
        assertTrue(registry.paused());
    }

    function testTimelockUnpauseAndRegistrationEachWaitFortyEightHours() public {
        _configureAndUnpause();
        vm.prank(address(emergencySafe));
        registry.pause();
        assertTrue(registry.paused());

        bytes memory unpauseData = abi.encodeCall(registry.unpause, (ROOT, uint64(1), uint64(1)));
        _scheduleAndAssertFortyEightHourDelay(address(registry), unpauseData);
        assertFalse(registry.paused());

        P.Record memory record = _record();
        bytes memory recordBytes = P.canonicalBytes(record);
        bytes memory registerData = abi.encodeCall(registry.registerPrincipal, (recordBytes, bytes32(0), uint64(0)));
        _scheduleAndAssertFortyEightHourDelay(address(registry), registerData);
        (,,,, bool active) = registry.principalState(record.principalId);
        assertTrue(active);
    }

    function _configureAndUnpause() internal {
        bytes memory configureData = abi.encodeCall(
            policy.configure, (ROOT, uint256(1), uint256(1), uint256(4), uint256(1_000), uint256(600))
        );
        _scheduleAndExecute(address(policy), configureData);
        bytes memory unpauseData = abi.encodeCall(registry.unpause, (ROOT, uint64(1), uint64(1)));
        _scheduleAndExecute(address(registry), unpauseData);
        assertFalse(registry.paused());
    }

    function _scheduleAndAssertFortyEightHourDelay(address target, bytes memory data) internal {
        bytes32 salt = _scheduleAs(address(governanceFixture), target, data, _nextSalt());
        vm.expectRevert();
        timelock.execute(target, 0, data, bytes32(0), salt);
        vm.warp(block.timestamp + 48 hours);
        timelock.execute(target, 0, data, bytes32(0), salt);
    }

    function _scheduleAndExecute(address target, bytes memory data) internal {
        _scheduleAs(address(governanceFixture), target, data, _nextSalt());
        vm.warp(block.timestamp + 48 hours);
        timelock.execute(target, 0, data, bytes32(0), bytes32(operationSalt));
    }

    function _scheduleAs(address proposer, address target, bytes memory data, bytes32 salt)
        internal returns (bytes32)
    {
        vm.prank(proposer);
        timelock.schedule(target, 0, data, bytes32(0), salt, 48 hours);
        return salt;
    }

    function _nextSalt() internal returns (bytes32 salt) {
        salt = bytes32(++operationSalt);
    }

    function _record() internal view returns (P.Record memory record) {
        bytes memory signerKey = new bytes(64);
        bytes memory did = bytes("did:key:");
        bytes memory alphabet = bytes("0123456789abcdef");
        for (uint256 i; i < 64; ++i) {
            signerKey[i] = 0x11;
            did = bytes.concat(did, alphabet[1], alphabet[1]);
        }
        bytes memory bodyKey = new bytes(64);
        for (uint256 i; i < 64; ++i) bodyKey[i] = 0x04;
        bytes32 nodeCommitment = bytes32(0x79121d7d912632aaf935e2b08d31942fa6c2242e3d17dd751612188321f6d26d);
        record = P.Record({
            principalId: P.principalIdFor(HOST, SERVICE, nodeCommitment),
            nodeIdCommitment: nodeCommitment,
            m2SignerDid: string(did),
            m2SignerPublicKey: signerKey,
            certificateFingerprint: bytes32(uint256(3)),
            bodyPublicKey: bodyKey,
            hostDomain: HOST,
            serviceDomain: SERVICE,
            audience: "gateway.testnet",
            method: "POST",
            path: "/heartbeat",
            query: bytes(""),
            policyRoot: ROOT,
            policyVersion: 1,
            authorityEpoch: 1,
            principalGeneration: 1,
            notBefore: uint64(block.timestamp - 1),
            expiresAt: uint64(block.timestamp + 365 days)
        });
        require(P.valid(record), "Invalid local record fixture");
    }
}