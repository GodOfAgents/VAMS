// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {VDSOTypes} from "../../src/vdso/VDSOTypes.sol";
import {VAMSObjectStore} from "../../src/vdso/VAMSObjectStore.sol";
import {VAMSReservationManager} from "../../src/vdso/VAMSReservationManager.sol";
import {VAMSAdapterRegistry} from "../../src/vdso/VAMSAdapterRegistry.sol";
import {VAMSProgramRegistry} from "../../src/vdso/VAMSProgramRegistry.sol";
import {VAMSProofRouter} from "../../src/vdso/VAMSProofRouter.sol";
import {VAMSCapabilityRouter} from "../../src/vdso/VAMSCapabilityRouter.sol";
import {VAMSExecutionKernel} from "../../src/vdso/VAMSExecutionKernel.sol";
import {IVAMSExecutionAdapter} from "../../src/vdso/interfaces/IVAMSExecutionAdapter.sol";
import {IVAMSProofVerifier} from "../../src/vdso/interfaces/IVAMSProofVerifier.sol";
import {IVAMSRecoveryVerifier} from "../../src/vdso/interfaces/IVAMSRecoveryVerifier.sol";

contract MockVDSOExecutionAdapter is IVAMSExecutionAdapter {
    VDSOTypes.Host private immutable _host;
    uint256 private immutable _capabilityMask;
    bytes32 public evidenceMode = keccak256("VAMS:LIVE_EVIDENCE:v1");
    bool public settlementResult = true;
    bool public settlementShouldRevert;

    constructor(VDSOTypes.Host host_, uint256 capabilityMask_) {
        _host = host_;
        _capabilityMask = capabilityMask_;
    }

    function host() external view returns (VDSOTypes.Host) {
        return _host;
    }

    function capabilityMask() external view returns (uint256) {
        return _capabilityMask;
    }

    function setEvidenceMode(bytes32 evidenceMode_) external {
        evidenceMode = evidenceMode_;
    }

    function setSettlementResult(bool result) external {
        settlementResult = result;
    }

    function setSettlementShouldRevert(bool shouldRevert) external {
        settlementShouldRevert = shouldRevert;
    }

    function verifySettlement(
        bytes32 transitionHash,
        VDSOTypes.SettlementMetadata calldata settlement,
        bytes calldata settlementProof
    ) external view returns (bool) {
        if (settlementShouldRevert) {
            revert("settlement verifier unavailable");
        }
        if (!settlementResult || settlementProof.length != 32) return false;
        bytes32 expectedProof = keccak256(
            abi.encode(
                transitionHash,
                settlement.sourceChainId,
                settlement.sourceTransactionHash,
                settlement.bridgeProofHash,
                settlement.payloadHash
            )
        );
        return abi.decode(settlementProof, (bytes32)) == expectedProof;
    }
}

contract MockVDSORecoveryVerifier is IVAMSRecoveryVerifier {
    bool public result = true;
    bool public shouldRevert;

    function setResult(bool result_) external {
        result = result_;
    }

    function setShouldRevert(bool shouldRevert_) external {
        shouldRevert = shouldRevert_;
    }

    function verifyNonExecution(
        bytes32 reservationId,
        bytes32 objectId,
        bytes32 domainId,
        bytes32 intentId,
        uint64 authorityEpoch,
        uint64 fencingToken,
        bytes calldata proof
    ) external view returns (bool) {
        if (shouldRevert) revert("recovery verifier unavailable");
        return result && reservationId != bytes32(0) && objectId != bytes32(0) && domainId != bytes32(0)
            && intentId != bytes32(0) && authorityEpoch != 0 && fencingToken != 0
            && keccak256(proof) == keccak256("authenticated-non-execution");
    }
}

contract MockVDSOProofVerifier is IVAMSProofVerifier {
    bool public result;
    bool public shouldRevert;

    constructor(bool result_) {
        result = result_;
    }

    function setResult(bool result_) external {
        result = result_;
    }

    function setShouldRevert(bool shouldRevert_) external {
        shouldRevert = shouldRevert_;
    }

    function verify(bytes32 programId, bytes32 transitionHash, bytes calldata proof) external view returns (bool) {
        if (shouldRevert) revert("verifier unavailable");
        return result && programId != bytes32(0) && transitionHash != bytes32(0) && proof.length != 0;
    }
}

contract VAMSObjectStoreTest is Test {
    VAMSObjectStore private store;
    address private pauser = makeAddr("pauser");
    address private polygonWriter = makeAddr("polygonWriter");
    address private cardanoWriter = makeAddr("cardanoWriter");
    address private attacker = makeAddr("attacker");

    bytes32 private constant POLYGON_DOMAIN = keccak256("polygon-settlement");
    bytes32 private constant CARDANO_DOMAIN = keccak256("cardano-governance");

    function setUp() public {
        store = new VAMSObjectStore(address(this), pauser);
        store.grantRole(store.KERNEL_ROLE(), polygonWriter);
        store.grantRole(store.KERNEL_ROLE(), cardanoWriter);
    }

    function testAccessControlRejectsUnauthorizedAuthorityChanges() public {
        vm.prank(attacker);
        vm.expectRevert();
        store.assignDomainAuthority(POLYGON_DOMAIN, VDSOTypes.Host.POLYGON, attacker);
    }

    function testDualHostDomainsHaveIndependentSoleWriters() public {
        store.assignDomainAuthority(POLYGON_DOMAIN, VDSOTypes.Host.POLYGON, polygonWriter);
        store.assignDomainAuthority(CARDANO_DOMAIN, VDSOTypes.Host.CARDANO, cardanoWriter);

        vm.prank(polygonWriter);
        store.writeObject(
            keccak256("polygon-object"), POLYGON_DOMAIN, 0, keccak256("polygon-state"), keccak256("polygon-evidence")
        );
        vm.prank(cardanoWriter);
        store.writeObject(
            keccak256("cardano-object"), CARDANO_DOMAIN, 0, keccak256("cardano-state"), keccak256("cardano-evidence")
        );

        vm.prank(cardanoWriter);
        vm.expectRevert();
        store.writeObject(keccak256("unauthorized-object"), POLYGON_DOMAIN, 0, keccak256("state"), bytes32(0));

        VAMSObjectStore.DomainAuthority memory polygonAuthority = store.getDomainAuthority(POLYGON_DOMAIN);
        VAMSObjectStore.DomainAuthority memory cardanoAuthority = store.getDomainAuthority(CARDANO_DOMAIN);
        assertEq(uint8(polygonAuthority.host), uint8(VDSOTypes.Host.POLYGON));
        assertEq(uint8(cardanoAuthority.host), uint8(VDSOTypes.Host.CARDANO));
        assertEq(polygonAuthority.writer, polygonWriter);
        assertEq(cardanoAuthority.writer, cardanoWriter);
    }

    function testAuthorityReplacementImmediatelyFencesOldWriter() public {
        store.assignDomainAuthority(POLYGON_DOMAIN, VDSOTypes.Host.POLYGON, polygonWriter);
        store.assignDomainAuthority(POLYGON_DOMAIN, VDSOTypes.Host.POLYGON, cardanoWriter);

        vm.prank(polygonWriter);
        vm.expectRevert();
        store.writeObject(keccak256("object"), POLYGON_DOMAIN, 0, keccak256("state"), bytes32(0));
    }
}

contract VAMSReservationManagerTest is Test {
    VAMSReservationManager private manager;
    MockVDSORecoveryVerifier private recoveryVerifier;
    address private pauser = makeAddr("pauser");
    address private recovery = makeAddr("recovery");
    address private kernel = makeAddr("kernel");
    address private holder = makeAddr("holder");

    bytes32 private constant OBJECT_ID = keccak256("object");
    bytes32 private constant DOMAIN_ID = keccak256("domain");
    bytes32 private constant INTENT_ID = keccak256("intent");
    bytes32 private constant RESERVATION_ONE = keccak256("reservation-one");
    bytes32 private constant RESERVATION_TWO = keccak256("reservation-two");

    function setUp() public {
        recoveryVerifier = new MockVDSORecoveryVerifier();
        manager = new VAMSReservationManager(address(this), pauser, recovery, address(recoveryVerifier));
        manager.grantRole(manager.KERNEL_ROLE(), kernel);
    }

    function testExpiryOnlyEnablesRecoveryAndNeverUnlocks() public {
        uint64 expiresAt = uint64(block.timestamp + 1 days);
        uint64 firstToken = _reserve(RESERVATION_ONE, expiresAt);
        assertEq(firstToken, 1);

        vm.warp(expiresAt);
        manager.markRecoveryPending(RESERVATION_ONE);
        assertEq(manager.activeReservation(OBJECT_ID), RESERVATION_ONE);

        vm.prank(kernel);
        vm.expectRevert();
        manager.reserve(RESERVATION_TWO, OBJECT_ID, DOMAIN_ID, INTENT_ID, holder, 1, uint64(block.timestamp + 1 days));

        vm.prank(recovery);
        vm.expectRevert(VAMSReservationManager.MissingRecoveryProof.selector);
        manager.abortRecovery(RESERVATION_ONE, "");

        vm.prank(kernel);
        vm.expectRevert();
        manager.abortRecovery(RESERVATION_ONE, bytes("authenticated-non-execution"));
        assertEq(manager.activeReservation(OBJECT_ID), RESERVATION_ONE);

        vm.prank(recovery);
        vm.expectRevert(VAMSReservationManager.InvalidRecoveryProof.selector);
        manager.abortRecovery(RESERVATION_ONE, bytes("forged-non-execution"));
        assertEq(manager.activeReservation(OBJECT_ID), RESERVATION_ONE);

        vm.prank(recovery);
        manager.abortRecovery(RESERVATION_ONE, bytes("authenticated-non-execution"));
        assertEq(manager.activeReservation(OBJECT_ID), bytes32(0));

        uint64 secondToken = _reserve(RESERVATION_TWO, uint64(block.timestamp + 1 days));
        assertEq(secondToken, 2);
    }

    function testRecoveryAbortFailsClosedWithoutVerifier() public {
        VAMSReservationManager disabled = new VAMSReservationManager(address(this), pauser, recovery, address(0));
        disabled.grantRole(disabled.KERNEL_ROLE(), kernel);
        vm.prank(kernel);
        disabled.reserve(RESERVATION_ONE, OBJECT_ID, DOMAIN_ID, INTENT_ID, holder, 1, uint64(block.timestamp + 1));
        vm.warp(block.timestamp + 1);
        disabled.markRecoveryPending(RESERVATION_ONE);

        vm.prank(recovery);
        vm.expectRevert(VAMSReservationManager.RecoveryAbortDisabled.selector);
        disabled.abortRecovery(RESERVATION_ONE, bytes("authenticated-non-execution"));
        assertEq(disabled.activeReservation(OBJECT_ID), RESERVATION_ONE);
    }

    function testPauseBlocksNewReservationsButAllowsCommit() public {
        uint64 token = _reserve(RESERVATION_ONE, uint64(block.timestamp + 1 days));
        vm.prank(pauser);
        manager.pause();

        vm.prank(kernel);
        vm.expectRevert();
        manager.reserve(
            RESERVATION_TWO,
            keccak256("other-object"),
            DOMAIN_ID,
            INTENT_ID,
            holder,
            1,
            uint64(block.timestamp + 1 days)
        );

        vm.prank(kernel);
        manager.commit(RESERVATION_ONE, token, keccak256("transition"), _settlement());
        assertEq(manager.activeReservation(OBJECT_ID), bytes32(0));
    }

    function testReservationIdReplayAndStaleFencingFailClosed() public {
        uint64 token = _reserve(RESERVATION_ONE, uint64(block.timestamp + 1 days));
        vm.prank(kernel);
        vm.expectRevert();
        manager.commit(RESERVATION_ONE, token + 1, keccak256("transition"), _settlement());

        vm.prank(kernel);
        manager.commit(RESERVATION_ONE, token, keccak256("transition"), _settlement());

        vm.prank(kernel);
        vm.expectRevert();
        manager.reserve(RESERVATION_ONE, OBJECT_ID, DOMAIN_ID, INTENT_ID, holder, 1, uint64(block.timestamp + 1 days));
    }

    function _reserve(bytes32 reservationId, uint64 expiresAt) private returns (uint64) {
        vm.prank(kernel);
        return manager.reserve(reservationId, OBJECT_ID, DOMAIN_ID, INTENT_ID, holder, 1, expiresAt);
    }

    function _settlement() private pure returns (VDSOTypes.SettlementMetadata memory) {
        return VDSOTypes.SettlementMetadata({
            sourceChainId: 80002,
            sourceTransactionHash: keccak256("source-tx"),
            bridgeProofHash: keccak256("bridge-proof"),
            payloadHash: keccak256("payload")
        });
    }
}

contract VAMSAdapterRegistryTest is Test {
    VAMSAdapterRegistry private registry;
    VAMSCapabilityRouter private router;
    MockVDSOExecutionAdapter private polygonAdapter;
    address private pauser = makeAddr("pauser");
    address private guardian = makeAddr("guardian");

    bytes32 private constant ADAPTER_ID = keccak256("polygon-adapter");
    bytes32 private constant VERIFIER_ID = keccak256("sp1-risc0");
    uint256 private constant CAPABILITIES = 0x07;

    function setUp() public {
        registry = new VAMSAdapterRegistry(address(this), pauser, guardian);
        router = new VAMSCapabilityRouter(address(this), pauser, address(registry));
        polygonAdapter = new MockVDSOExecutionAdapter(VDSOTypes.Host.POLYGON, CAPABILITIES);
        registry.proposeAdapter(
            ADAPTER_ID,
            address(polygonAdapter),
            VDSOTypes.Host.POLYGON,
            CAPABILITIES,
            VERIFIER_ID,
            keccak256("profile"),
            keccak256("conformance"),
            1,
            uint64(block.timestamp + 30 days)
        );
    }

    function testActivationIsTimelockedAndCapabilityExact() public {
        vm.expectRevert();
        registry.activateAdapter(ADAPTER_ID);

        vm.warp(block.timestamp + registry.ACTIVATION_DELAY());
        registry.activateAdapter(ADAPTER_ID);

        bytes32[] memory candidates = new bytes32[](1);
        candidates[0] = ADAPTER_ID;
        assertEq(router.selectAdapter(candidates, 0x03, VDSOTypes.Host.POLYGON, VERIFIER_ID), ADAPTER_ID);

        vm.expectRevert(VAMSCapabilityRouter.NoCapableAdapter.selector);
        router.selectAdapter(candidates, 0x08, VDSOTypes.Host.POLYGON, VERIFIER_ID);
        vm.expectRevert(VAMSCapabilityRouter.NoCapableAdapter.selector);
        router.selectAdapter(candidates, 0x03, VDSOTypes.Host.CARDANO, VERIFIER_ID);
    }

    function testQuarantineFailsClosedAndReactivationIsDelayed() public {
        vm.warp(block.timestamp + registry.ACTIVATION_DELAY());
        registry.activateAdapter(ADAPTER_ID);

        vm.prank(guardian);
        registry.quarantineAdapter(ADAPTER_ID, keccak256("proof mismatch"));
        assertFalse(registry.isActiveAndCapable(ADAPTER_ID, 0x01, VDSOTypes.Host.POLYGON, VERIFIER_ID));

        registry.scheduleReactivation(ADAPTER_ID, uint64(block.timestamp + 30 days));
        vm.expectRevert();
        registry.activateAdapter(ADAPTER_ID);
    }

    function testOnlyGuardianMayQuarantine() public {
        vm.warp(block.timestamp + registry.ACTIVATION_DELAY());
        registry.activateAdapter(ADAPTER_ID);
        vm.prank(makeAddr("attacker"));
        vm.expectRevert();
        registry.quarantineAdapter(ADAPTER_ID, keccak256("fake"));
    }

    function testMockEvidenceModeIsRejectedAndDowngradeFailsClosed() public {
        MockVDSOExecutionAdapter mockAdapter = new MockVDSOExecutionAdapter(VDSOTypes.Host.POLYGON, CAPABILITIES);
        mockAdapter.setEvidenceMode(keccak256("VAMS:MOCK_EVIDENCE:v1"));
        vm.expectRevert(VAMSAdapterRegistry.AdapterSelfReportMismatch.selector);
        registry.proposeAdapter(
            keccak256("mock-adapter"),
            address(mockAdapter),
            VDSOTypes.Host.POLYGON,
            CAPABILITIES,
            VERIFIER_ID,
            keccak256("profile"),
            keccak256("conformance"),
            1,
            uint64(block.timestamp + 30 days)
        );

        vm.warp(block.timestamp + registry.ACTIVATION_DELAY());
        registry.activateAdapter(ADAPTER_ID);
        polygonAdapter.setEvidenceMode(keccak256("VAMS:MOCK_EVIDENCE:v1"));
        assertFalse(registry.isActiveAndCapable(ADAPTER_ID, 0x01, VDSOTypes.Host.POLYGON, VERIFIER_ID));
    }
}

contract VAMSProgramRegistryTest is Test {
    VAMSProgramRegistry private registry;
    address private guardian = makeAddr("guardian");

    bytes32 private constant VIR_V1_HOST_FUNCTION_SET_HASH =
        0x926aa059fa0db9477ba813b969d5c1dcf92fbcdbf7e00d6ceeec13ceef33e860;
    bytes32 private constant VIR_V1_GAS_SCHEDULE_HASH =
        0xea7983ef0e10911d248e354efebafd3b05a479e50ba5f0cfa46890f74034f773;
    bytes32 private constant VIR_V1_ARITHMETIC_POLICY_HASH =
        0xe6231804a0697191feee14abb9b5806f393a2725a10c0fc92f0159ee79c893a5;

    function setUp() public {
        registry = new VAMSProgramRegistry(address(this), guardian, guardian);
    }

    function testProgramIdUsesExactAsciiPrefixAndU16BigEndianVersion() public {
        uint16 virVersion = 0x0102;
        bytes32 bytecodeHash = keccak256("bytecode");
        bytes32 hostFunctionSetHash = keccak256("host-functions");
        bytes32 gasScheduleHash = keccak256("gas-schedule");
        bytes32 arithmeticPolicyHash = keccak256("arithmetic-policy");
        bytes32 expected = keccak256(
            abi.encodePacked(
                bytes("VAMS:PROGRAM:v1"),
                virVersion,
                bytecodeHash,
                hostFunctionSetHash,
                gasScheduleHash,
                arithmeticPolicyHash
            )
        );

        assertEq(
            registry.computeProgramId(
                virVersion, bytecodeHash, hostFunctionSetHash, gasScheduleHash, arithmeticPolicyHash
            ),
            expected
        );
    }

    function testRegisterProgramRequiresExactVirV1Policies() public {
        bytes32 bytecodeHash = keccak256("bytecode");
        bytes32 verifierId = keccak256("verifier");
        bytes32 programId = registry.registerProgram(
            1,
            bytecodeHash,
            VIR_V1_HOST_FUNCTION_SET_HASH,
            VIR_V1_GAS_SCHEDULE_HASH,
            VIR_V1_ARITHMETIC_POLICY_HASH,
            verifierId
        );

        assertEq(registry.VIR_V1_HOST_FUNCTION_SET_HASH(), VIR_V1_HOST_FUNCTION_SET_HASH);
        assertEq(registry.VIR_V1_GAS_SCHEDULE_HASH(), VIR_V1_GAS_SCHEDULE_HASH);
        assertEq(registry.VIR_V1_ARITHMETIC_POLICY_HASH(), VIR_V1_ARITHMETIC_POLICY_HASH);
        assertEq(registry.SUPPORTED_VIR_VERSION(), 1);
        assertEq(
            programId,
            registry.computeProgramId(
                1, bytecodeHash, VIR_V1_HOST_FUNCTION_SET_HASH, VIR_V1_GAS_SCHEDULE_HASH, VIR_V1_ARITHMETIC_POLICY_HASH
            )
        );
        VAMSProgramRegistry.ProgramConfig memory config = registry.getProgram(programId);
        assertEq(config.virVersion, 1);
        assertEq(config.verifierId, verifierId);
        assertTrue(config.active);
    }

    function testRegisterProgramRejectsUnsupportedVersion() public {
        vm.expectRevert(abi.encodeWithSelector(VAMSProgramRegistry.UnsupportedVIRVersion.selector, uint16(2)));
        registry.registerProgram(
            2,
            keccak256("bytecode"),
            VIR_V1_HOST_FUNCTION_SET_HASH,
            VIR_V1_GAS_SCHEDULE_HASH,
            VIR_V1_ARITHMETIC_POLICY_HASH,
            keccak256("verifier")
        );
    }

    function testRegisterProgramRejectsArbitraryPolicyCommitments() public {
        bytes32 wrongHost = keccak256("attacker-host-functions");
        vm.expectRevert(
            abi.encodeWithSelector(
                VAMSProgramRegistry.UnsupportedPolicyCommitment.selector,
                wrongHost,
                VIR_V1_GAS_SCHEDULE_HASH,
                VIR_V1_ARITHMETIC_POLICY_HASH
            )
        );
        registry.registerProgram(
            1,
            keccak256("bytecode"),
            wrongHost,
            VIR_V1_GAS_SCHEDULE_HASH,
            VIR_V1_ARITHMETIC_POLICY_HASH,
            keccak256("verifier")
        );

        bytes32 wrongGas = keccak256("attacker-gas-schedule");
        vm.expectRevert(
            abi.encodeWithSelector(
                VAMSProgramRegistry.UnsupportedPolicyCommitment.selector,
                VIR_V1_HOST_FUNCTION_SET_HASH,
                wrongGas,
                VIR_V1_ARITHMETIC_POLICY_HASH
            )
        );
        registry.registerProgram(
            1,
            keccak256("bytecode"),
            VIR_V1_HOST_FUNCTION_SET_HASH,
            wrongGas,
            VIR_V1_ARITHMETIC_POLICY_HASH,
            keccak256("verifier")
        );

        bytes32 wrongArithmetic = keccak256("attacker-arithmetic");
        vm.expectRevert(
            abi.encodeWithSelector(
                VAMSProgramRegistry.UnsupportedPolicyCommitment.selector,
                VIR_V1_HOST_FUNCTION_SET_HASH,
                VIR_V1_GAS_SCHEDULE_HASH,
                wrongArithmetic
            )
        );
        registry.registerProgram(
            1,
            keccak256("bytecode"),
            VIR_V1_HOST_FUNCTION_SET_HASH,
            VIR_V1_GAS_SCHEDULE_HASH,
            wrongArithmetic,
            keccak256("verifier")
        );
    }
}

contract VAMSProofRouterTest is Test {
    VAMSProofRouter private router;
    MockVDSOProofVerifier private accepting;
    MockVDSOProofVerifier private rejecting;
    address private pauser = makeAddr("pauser");

    bytes32 private constant DUAL_VERIFIER = keccak256("dual-verifier");
    bytes32 private constant SINGLE_VERIFIER = keccak256("single-verifier");
    bytes32 private constant PROGRAM_ID = keccak256("program");
    bytes32 private constant TRANSITION_HASH = keccak256("transition");

    function setUp() public {
        router = new VAMSProofRouter(address(this), pauser);
        accepting = new MockVDSOProofVerifier(true);
        rejecting = new MockVDSOProofVerifier(false);
        router.grantRole(router.KERNEL_ROLE(), address(this));
    }

    function testIndependentVerifierDisagreementFailsClosed() public {
        router.configureVerifier(DUAL_VERIFIER, address(accepting), address(rejecting), true);
        vm.expectRevert(abi.encodeWithSelector(VAMSProofRouter.ProofDisagreement.selector, DUAL_VERIFIER));
        router.verifyAndRecord(keccak256("receipt"), DUAL_VERIFIER, PROGRAM_ID, TRANSITION_HASH, hex"01", hex"02");
    }

    function testAgreementRequiresDistinctVerifierAddresses() public {
        vm.expectRevert(VAMSProofRouter.InvalidVerifier.selector);
        router.configureVerifier(DUAL_VERIFIER, address(accepting), address(accepting), true);
    }

    function testUnsupportedAndRevertingVerifiersFailClosed() public {
        vm.expectRevert();
        router.verifyAndRecord(
            keccak256("unsupported-receipt"), keccak256("unsupported"), PROGRAM_ID, TRANSITION_HASH, hex"01", ""
        );

        accepting.setShouldRevert(true);
        router.configureVerifier(SINGLE_VERIFIER, address(accepting), address(0), false);
        vm.expectRevert();
        router.verifyAndRecord(
            keccak256("reverting-receipt"), SINGLE_VERIFIER, PROGRAM_ID, TRANSITION_HASH, hex"01", ""
        );
    }

    function testProofReceiptReplayIsRejected() public {
        router.configureVerifier(SINGLE_VERIFIER, address(accepting), address(0), false);
        bytes32 receiptId = keccak256("receipt");
        router.verifyAndRecord(receiptId, SINGLE_VERIFIER, PROGRAM_ID, TRANSITION_HASH, hex"01", "");
        assertTrue(router.receiptUsed(receiptId));

        vm.expectRevert(abi.encodeWithSelector(VAMSProofRouter.ReceiptReplay.selector, receiptId));
        router.verifyAndRecord(receiptId, SINGLE_VERIFIER, PROGRAM_ID, TRANSITION_HASH, hex"01", "");
    }

    function testVerifierIdIsImmutableAndCodeHashPinned() public {
        router.configureVerifier(SINGLE_VERIFIER, address(accepting), address(0), false);
        vm.expectRevert(abi.encodeWithSelector(VAMSProofRouter.VerifierAlreadyConfigured.selector, SINGLE_VERIFIER));
        router.configureVerifier(SINGLE_VERIFIER, address(rejecting), address(0), false);

        vm.etch(address(accepting), hex"00");
        vm.expectPartialRevert(VAMSProofRouter.VerifierCodeChanged.selector);
        router.verifyAndRecord(
            keccak256("changed-code-receipt"), SINGLE_VERIFIER, PROGRAM_ID, TRANSITION_HASH, hex"01", ""
        );
    }
}

contract VAMSExecutionKernelTest is Test {
    VAMSObjectStore private objectStore;
    VAMSReservationManager private reservationManager;
    VAMSAdapterRegistry private adapterRegistry;
    VAMSProgramRegistry private programRegistry;
    VAMSProofRouter private proofRouter;
    VAMSCapabilityRouter private capabilityRouter;
    VAMSExecutionKernel private kernel;
    MockVDSOExecutionAdapter private adapter;
    MockVDSOProofVerifier private verifier;

    address private guardian = makeAddr("guardian");
    address private recovery = makeAddr("recovery");
    address private holder;

    bytes32 private constant DOMAIN_ID = keccak256("polygon-canary-domain");
    bytes32 private constant OBJECT_ID = keccak256("object");
    bytes32 private constant INTENT_ID = keccak256("intent");
    bytes32 private constant RESERVATION_ID = keccak256("reservation");
    bytes32 private constant EXECUTION_ID = keccak256("execution");
    bytes32 private constant ADAPTER_ID = keccak256("adapter");
    bytes32 private constant VERIFIER_ID = keccak256("verifier");

    function setUp() public {
        holder = address(this);
        objectStore = new VAMSObjectStore(address(this), guardian);
        reservationManager = new VAMSReservationManager(address(this), guardian, recovery, address(0));
        adapterRegistry = new VAMSAdapterRegistry(address(this), guardian, guardian);
        programRegistry = new VAMSProgramRegistry(address(this), guardian, guardian);
        proofRouter = new VAMSProofRouter(address(this), guardian);
        capabilityRouter = new VAMSCapabilityRouter(address(this), guardian, address(adapterRegistry));
        kernel = new VAMSExecutionKernel(
            address(this),
            guardian,
            address(objectStore),
            address(reservationManager),
            address(adapterRegistry),
            address(programRegistry),
            address(proofRouter),
            address(capabilityRouter)
        );

        reservationManager.grantRole(reservationManager.KERNEL_ROLE(), address(kernel));
        proofRouter.grantRole(proofRouter.KERNEL_ROLE(), address(kernel));
        objectStore.grantRole(objectStore.KERNEL_ROLE(), address(kernel));
        objectStore.assignDomainAuthority(DOMAIN_ID, VDSOTypes.Host.POLYGON, address(kernel));

        verifier = new MockVDSOProofVerifier(true);
        proofRouter.configureVerifier(VERIFIER_ID, address(verifier), address(0), false);
        adapter = new MockVDSOExecutionAdapter(VDSOTypes.Host.POLYGON, 0x03);
        adapterRegistry.proposeAdapter(
            ADAPTER_ID,
            address(adapter),
            VDSOTypes.Host.POLYGON,
            0x03,
            VERIFIER_ID,
            keccak256("profile"),
            keccak256("conformance"),
            1,
            uint64(block.timestamp + 30 days)
        );
        vm.warp(block.timestamp + adapterRegistry.ACTIVATION_DELAY());
        adapterRegistry.activateAdapter(ADAPTER_ID);
    }

    function testKernelCoordinatesReservedTransitionWhilePausedAndRejectsReplay() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        vm.prank(guardian);
        kernel.pause();

        vm.expectRevert();
        kernel.beginReservation(
            keccak256("blocked-reservation"),
            keccak256("blocked-object"),
            DOMAIN_ID,
            keccak256("blocked-intent"),
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );

        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);
        bytes32[] memory candidates = new bytes32[](1);
        candidates[0] = ADAPTER_ID;
        uint64 version = kernel.executeTransition(request, candidates, hex"01", "", _adapterSettlementProof(request));
        assertEq(version, 1);
        assertTrue(kernel.executionUsed(EXECUTION_ID));
        assertEq(kernel.executionAdapter(EXECUTION_ID), ADAPTER_ID);

        VAMSObjectStore.ObjectHeader memory objectHeader = objectStore.getObject(OBJECT_ID);
        assertEq(objectHeader.domainId, DOMAIN_ID);
        assertEq(objectHeader.stateRoot, request.newStateRoot);
        assertEq(objectHeader.version, 1);

        VAMSReservationManager.Reservation memory reservation = reservationManager.getReservation(RESERVATION_ID);
        assertEq(uint8(reservation.status), uint8(VDSOTypes.ReservationStatus.COMMITTED));
        assertEq(reservation.settlement.bridgeProofHash, request.settlement.bridgeProofHash);
        assertEq(reservation.settlement.payloadHash, request.settlement.payloadHash);

        vm.expectRevert(abi.encodeWithSelector(VAMSExecutionKernel.ExecutionReplay.selector, EXECUTION_ID));
        kernel.executeTransition(request, candidates, hex"01", "", _adapterSettlementProof(request));
    }

    function testKernelRejectsCardanoReserveAndPausedUnreservedTransition() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                VAMSExecutionKernel.UnsupportedCanaryHostAccessMode.selector,
                VDSOTypes.Host.CARDANO,
                VDSOTypes.AccessMode.RESERVE
            )
        );
        kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.CARDANO,
            1
        );

        bytes32 programId = _registerProgram();
        vm.prank(guardian);
        kernel.pause();
        VDSOTypes.TransitionRequest memory request = _request(programId, 0);
        request.accessMode = VDSOTypes.AccessMode.ACCUMULATE;
        request.reservationId = bytes32(0);
        request.reservationHolder = address(0);
        bytes32[] memory candidates = new bytes32[](1);
        candidates[0] = ADAPTER_ID;
        vm.expectRevert(VAMSExecutionKernel.PausedTransitionRequiresReservation.selector);
        kernel.executeTransition(request, candidates, hex"01", "", _adapterSettlementProof(request));
    }

    function testEvmKernelRejectsCardanoAccumulateWithMatchingAuthorityAndAdapter() public {
        bytes32 cardanoDomain = keccak256("cardano-native-domain");
        bytes32 cardanoAdapterId = keccak256("cardano-adapter");
        objectStore.assignDomainAuthority(cardanoDomain, VDSOTypes.Host.CARDANO, address(kernel));

        MockVDSOExecutionAdapter cardanoAdapter = new MockVDSOExecutionAdapter(VDSOTypes.Host.CARDANO, 0x03);
        adapterRegistry.proposeAdapter(
            cardanoAdapterId,
            address(cardanoAdapter),
            VDSOTypes.Host.CARDANO,
            0x03,
            VERIFIER_ID,
            keccak256("cardano-profile"),
            keccak256("cardano-conformance"),
            1,
            uint64(block.timestamp + 30 days)
        );
        vm.warp(block.timestamp + adapterRegistry.ACTIVATION_DELAY());
        adapterRegistry.activateAdapter(cardanoAdapterId);

        VDSOTypes.TransitionRequest memory request = _request(_registerProgram(), 0);
        request.executionId = keccak256("cardano-execution");
        request.objectId = keccak256("cardano-object");
        request.domainId = cardanoDomain;
        request.reservationId = bytes32(0);
        request.reservationHolder = address(0);
        request.fencingToken = 0;
        request.requiredHost = VDSOTypes.Host.CARDANO;
        request.accessMode = VDSOTypes.AccessMode.ACCUMULATE;
        request.settlement = VDSOTypes.SettlementMetadata({
            sourceChainId: 0, sourceTransactionHash: bytes32(0), bridgeProofHash: bytes32(0), payloadHash: bytes32(0)
        });
        request.transitionHash = kernel.computeSemanticTransitionHash(request, bytes32(0));
        bytes32[] memory candidates = new bytes32[](1);
        candidates[0] = cardanoAdapterId;

        vm.expectRevert(
            abi.encodeWithSelector(
                VAMSExecutionKernel.UnsupportedCanaryHostAccessMode.selector,
                VDSOTypes.Host.CARDANO,
                VDSOTypes.AccessMode.ACCUMULATE
            )
        );
        kernel.executeTransition(request, candidates, hex"01", "", _adapterSettlementProof(request));

        assertFalse(kernel.executionUsed(request.executionId));
        assertEq(objectStore.getObject(request.objectId).version, 0);
    }

    function testSemanticHashBindsConsensusWireHostAndAuthorityEpoch() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);
        bytes32 expectedWireHash = _manualSemanticHash(request, 0);
        bytes32 enumOrdinalHash = _manualSemanticHash(request, uint8(request.requiredHost));
        request.authorityEpoch = 2;
        bytes32 nextEpochHash = kernel.computeSemanticTransitionHash(request, bytes32(0));

        assertEq(request.transitionHash, expectedWireHash);
        assertNotEq(request.transitionHash, enumOrdinalHash);
        assertNotEq(request.transitionHash, nextEpochHash);
    }

    function testAuthorityReassignmentInvalidatesStaleReservationEpoch() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);
        objectStore.assignDomainAuthority(DOMAIN_ID, VDSOTypes.Host.POLYGON, address(kernel));

        vm.expectPartialRevert(VAMSExecutionKernel.DomainAuthorityMismatch.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        request.authorityEpoch = 2;
        request.transitionHash = kernel.computeSemanticTransitionHash(request, bytes32(0));
        vm.expectPartialRevert(VAMSExecutionKernel.ReservationMismatch.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        VAMSReservationManager.Reservation memory reservation = reservationManager.getReservation(RESERVATION_ID);
        assertEq(reservation.authorityEpoch, 1);
        assertEq(reservation.domainId, DOMAIN_ID);
        assertEq(reservationManager.activeReservation(OBJECT_ID), RESERVATION_ID);
    }

    function testSemanticProofCannotAuthorizeTamperedRootObjectOrVersion() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        bytes32[] memory candidates = _candidates();

        VDSOTypes.TransitionRequest memory rootTamper = _request(programId, fencingToken);
        rootTamper.newStateRoot = keccak256("attacker-root");
        vm.expectPartialRevert(VAMSExecutionKernel.TransitionHashMismatch.selector);
        kernel.executeTransition(rootTamper, candidates, hex"01", "", _adapterSettlementProof(rootTamper));

        VDSOTypes.TransitionRequest memory objectTamper = _request(programId, fencingToken);
        objectTamper.objectId = keccak256("attacker-object");
        vm.expectPartialRevert(VAMSExecutionKernel.TransitionHashMismatch.selector);
        kernel.executeTransition(objectTamper, candidates, hex"01", "", _adapterSettlementProof(objectTamper));

        VDSOTypes.TransitionRequest memory versionTamper = _request(programId, fencingToken);
        versionTamper.expectedObjectVersion = 1;
        vm.expectPartialRevert(VAMSExecutionKernel.TransitionHashMismatch.selector);
        kernel.executeTransition(versionTamper, candidates, hex"01", "", _adapterSettlementProof(versionTamper));

        assertFalse(kernel.executionUsed(EXECUTION_ID));
        assertEq(reservationManager.activeReservation(OBJECT_ID), RESERVATION_ID);
    }

    function testSettlementIsOutsideSemanticHashButAdapterProofBindsIt() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);
        bytes32 semanticHashBefore = request.transitionHash;
        bytes memory settlementProofBefore = _adapterSettlementProof(request);

        request.settlement.payloadHash = keccak256("different-payload");
        bytes32 semanticHashAfter = kernel.computeSemanticTransitionHash(request, bytes32(0));
        assertEq(semanticHashBefore, semanticHashAfter);

        vm.expectPartialRevert(VAMSExecutionKernel.AdapterSettlementRejected.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", settlementProofBefore);
        assertFalse(proofRouter.receiptUsed(EXECUTION_ID));
    }

    function testAdapterFalseAndRevertBothFailClosedBeforeProof() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);

        adapter.setSettlementResult(false);
        vm.expectPartialRevert(VAMSExecutionKernel.AdapterSettlementRejected.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        adapter.setSettlementResult(true);
        adapter.setSettlementShouldRevert(true);
        vm.expectPartialRevert(VAMSExecutionKernel.AdapterSettlementRejected.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        assertFalse(proofRouter.receiptUsed(EXECUTION_ID));
        assertEq(reservationManager.activeReservation(OBJECT_ID), RESERVATION_ID);
    }

    function testCrossHostSettlementRequiresSeparatedNonzeroCommitments() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);

        request.settlement.bridgeProofHash = request.settlement.payloadHash;
        vm.expectRevert(VAMSExecutionKernel.InvalidCrossHostSettlement.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        request.settlement.bridgeProofHash = bytes32(0);
        vm.expectRevert(VAMSExecutionKernel.InvalidCrossHostSettlement.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        request = _request(programId, fencingToken);
        request.settlement.sourceTransactionHash = bytes32(0);
        vm.expectRevert(VAMSExecutionKernel.InvalidCrossHostSettlement.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        request.settlement.sourceChainId = 0;
        request.settlement.payloadHash = bytes32(0);
        request.settlement.bridgeProofHash = bytes32(0);
        request.settlement.sourceTransactionHash = keccak256("malformed-local-tx");
        vm.expectRevert(VAMSExecutionKernel.InvalidCrossHostSettlement.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        request.settlement.sourceTransactionHash = bytes32(0);
        uint64 version = kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));
        assertEq(version, 1);

        assertTrue(kernel.executionUsed(EXECUTION_ID));
    }

    function testRecoveryPendingLateCommitRequiresAuditAndVerifiedSettlement() public {
        bytes32 programId = _registerProgram();
        uint64 expiresAt = uint64(block.timestamp + 1);
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID, OBJECT_ID, DOMAIN_ID, INTENT_ID, holder, expiresAt, VDSOTypes.Host.POLYGON, 1
        );
        vm.warp(expiresAt);
        reservationManager.markRecoveryPending(RESERVATION_ID);

        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);
        vm.expectRevert(VAMSExecutionKernel.MissingRecoveryExecutionProof.selector);
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        bytes memory primaryProof = hex"01";
        request.recoveryExecutionProofHash = keccak256("unbound-audit-hash");
        vm.expectPartialRevert(VAMSExecutionKernel.RecoveryExecutionProofHashMismatch.selector);
        kernel.executeTransition(request, _candidates(), primaryProof, "", _adapterSettlementProof(request));

        bytes32 recoveryAuditHash = kernel.computeRecoveryExecutionProofHash(request.transitionHash, primaryProof);
        request.recoveryExecutionProofHash = recoveryAuditHash;
        adapter.setSettlementResult(false);
        vm.expectPartialRevert(VAMSExecutionKernel.AdapterSettlementRejected.selector);
        kernel.executeTransition(request, _candidates(), primaryProof, "", _adapterSettlementProof(request));
        assertEq(reservationManager.activeReservation(OBJECT_ID), RESERVATION_ID);

        adapter.setSettlementResult(true);
        uint64 version =
            kernel.executeTransition(request, _candidates(), primaryProof, "", _adapterSettlementProof(request));
        assertEq(version, 1);

        VAMSReservationManager.Reservation memory reservation = reservationManager.getReservation(RESERVATION_ID);
        assertEq(uint8(reservation.status), uint8(VDSOTypes.ReservationStatus.COMMITTED));
        assertEq(reservation.recoveryProofHash, recoveryAuditHash);
        assertEq(reservationManager.activeReservation(OBJECT_ID), bytes32(0));
    }

    function testOnlyBoundReservationHolderMayExecute() public {
        bytes32 programId = _registerProgram();
        uint64 fencingToken = kernel.beginReservation(
            RESERVATION_ID,
            OBJECT_ID,
            DOMAIN_ID,
            INTENT_ID,
            holder,
            uint64(block.timestamp + 7 days),
            VDSOTypes.Host.POLYGON,
            1
        );
        VDSOTypes.TransitionRequest memory request = _request(programId, fencingToken);
        address otherExecutor = makeAddr("other-executor");
        kernel.grantRole(kernel.EXECUTOR_ROLE(), otherExecutor);

        vm.prank(otherExecutor);
        vm.expectRevert(
            abi.encodeWithSelector(VAMSExecutionKernel.UnauthorizedReservationHolder.selector, holder, otherExecutor)
        );
        kernel.executeTransition(request, _candidates(), hex"01", "", _adapterSettlementProof(request));

        assertFalse(proofRouter.receiptUsed(EXECUTION_ID));
        assertEq(reservationManager.activeReservation(OBJECT_ID), RESERVATION_ID);
    }

    function _registerProgram() private returns (bytes32) {
        return programRegistry.registerProgram(
            1,
            keccak256("bytecode"),
            0x926aa059fa0db9477ba813b969d5c1dcf92fbcdbf7e00d6ceeec13ceef33e860,
            0xea7983ef0e10911d248e354efebafd3b05a479e50ba5f0cfa46890f74034f773,
            0xe6231804a0697191feee14abb9b5806f393a2725a10c0fc92f0159ee79c893a5,
            VERIFIER_ID
        );
    }

    function _candidates() private pure returns (bytes32[] memory candidates) {
        candidates = new bytes32[](1);
        candidates[0] = ADAPTER_ID;
    }

    function _request(bytes32 programId, uint64 fencingToken)
        private
        view
        returns (VDSOTypes.TransitionRequest memory)
    {
        VDSOTypes.TransitionRequest memory request =
            VDSOTypes.TransitionRequest({
                executionId: EXECUTION_ID,
                intentId: INTENT_ID,
                programId: programId,
                objectId: OBJECT_ID,
                domainId: DOMAIN_ID,
                reservationId: RESERVATION_ID,
                transitionHash: bytes32(0),
                newStateRoot: keccak256("new-state"),
                evidenceRoot: keccak256("evidence"),
                verifierId: VERIFIER_ID,
                recoveryExecutionProofHash: bytes32(0),
                reservationHolder: holder,
                expectedObjectVersion: 0,
                authorityEpoch: 1,
                fencingToken: fencingToken,
                requiredCapabilities: 0x03,
                requiredHost: VDSOTypes.Host.POLYGON,
                accessMode: VDSOTypes.AccessMode.RESERVE,
                settlement: VDSOTypes.SettlementMetadata({
                    sourceChainId: 80002,
                    sourceTransactionHash: keccak256("source-tx"),
                    bridgeProofHash: keccak256("bridge-proof"),
                    payloadHash: keccak256("payload")
                })
            });
        request.transitionHash = kernel.computeSemanticTransitionHash(request, bytes32(0));
        return request;
    }

    function _adapterSettlementProof(VDSOTypes.TransitionRequest memory request) private pure returns (bytes memory) {
        return abi.encode(
            keccak256(
                abi.encode(
                    request.transitionHash,
                    request.settlement.sourceChainId,
                    request.settlement.sourceTransactionHash,
                    request.settlement.bridgeProofHash,
                    request.settlement.payloadHash
                )
            )
        );
    }

    function _manualSemanticHash(VDSOTypes.TransitionRequest memory request, uint8 wireHost)
        private
        view
        returns (bytes32)
    {
        bytes memory identity = abi.encode(
            kernel.SEMANTIC_TRANSITION_DOMAIN(),
            request.intentId,
            request.programId,
            request.objectId,
            request.domainId,
            request.authorityEpoch,
            request.reservationHolder
        );
        bytes memory effect = abi.encode(
            bytes32(0),
            request.newStateRoot,
            request.evidenceRoot,
            request.expectedObjectVersion,
            request.fencingToken,
            request.accessMode,
            wireHost,
            request.requiredCapabilities
        );
        return keccak256(bytes.concat(identity, effect));
    }
}
