// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";
import {ActionContextV1} from "../src/trust/ActionContextV1.sol";
import {AutomataSgxActionVerifierV1, DcapHeaderV1} from "../src/trust/AutomataSgxActionVerifierV1.sol";
import {EzklActionVerifierV1} from "../src/trust/EzklActionVerifierV1.sol";

// These are ABI/control-flow fixtures. They verify NO hardware certificate or SNARK.
// Passing this suite cannot qualify any actual DCAP verifier, circuit or model.
contract CollateralBoundaryFixture {}
contract DcapBoundaryFixture {
    address public immutable pccsRouter;
    uint16 public constant quoteVersion = 3;
    bool public accepting;
    bytes private report;
    constructor(address router) { pccsRouter = router; }
    function setResult(bool accepted, bytes memory output) external { accepting = accepted; report = output; }
    function verifyQuote(DcapHeaderV1 calldata, bytes calldata, uint32) external view returns (bool, bytes memory) {
        return (accepting, report);
    }
}
contract EzklBoundaryFixture {
    bool public accepting;
    function setResult(bool value) external { accepting = value; }
    function verifyProof(bytes calldata proof, uint256[] calldata instances) external view returns (bool) {
        if (!accepting || proof.length != 2 || instances.length != 22) return false;
        for (uint256 i; i < 8; ++i) if (instances[i] != instances[12+i]) return false;
        return true;
    }
}

contract ActionEvidenceAdaptersTest is Test {
    uint256 private key;
    ActionContextV1.Context private c;
    bytes32 private outputHash;
    bytes32 private constant ENCLAVE = keccak256("LOCAL-ABI-FIXTURE-ENCLAVE");
    bytes32 private constant SIGNER = keccak256("LOCAL-ABI-FIXTURE-SIGNER");
    bytes32 private constant CIRCUIT = keccak256("LOCAL-ABI-FIXTURE-NOT-A-REAL-CIRCUIT");
    DcapBoundaryFixture private dcap;
    EzklBoundaryFixture private zk;
    AutomataSgxActionVerifierV1 private sgx;
    EzklActionVerifierV1 private ezkl;

    function setUp() public {
        vm.warp(1000);
        key = uint256(keccak256("VAMS-LOCAL-ONLY-ADAPTER-TEST-20261027"));
        c.actorRoot = bytes32(uint256(uint160(vm.addr(key))));
        c.providerId = c.actorRoot; c.runtimeId = keccak256("runtime"); c.modelId = keccak256("model");
        c.hostDomain = keccak256("host"); c.workflowId = keccak256("workflow"); c.intentId = keccak256("intent");
        c.actionHash = keccak256("action"); c.inputHash = keccak256("input"); c.policyRoot = keccak256("policy");
        c.target = bytes32(uint256(uint160(address(this)))); c.nonce = keccak256("nonce"); c.budgetUnit = keccak256("unit");
        c.rootScheme = 1; c.authorityEpoch = 1; c.policyVersion = 1; c.capabilities = 4;
        c.budget = 100; c.issuedAt = 1000; c.expiresAt = 1100; c.chainId = block.chainid;
        outputHash = keccak256("output");
        CollateralBoundaryFixture collateral = new CollateralBoundaryFixture();
        dcap = new DcapBoundaryFixture(address(collateral));
        sgx = new AutomataSgxActionVerifierV1(address(dcap), address(dcap).codehash,
            address(collateral), address(collateral).codehash, ENCLAVE, SIGNER, c.runtimeId, 1, 7);
        zk = new EzklBoundaryFixture();
        ezkl = new EzklActionVerifierV1(address(zk), address(zk).codehash, c.modelId, CIRCUIT);
    }

    function sign(bytes32 digest, uint256 signingKey) private pure returns (bytes memory) {
        (, bytes32 r, bytes32 s) = vm.sign(signingKey, digest);
        return abi.encode(r,s);
    }

    function put(bytes memory data, uint256 offset, bytes memory value) private pure {
        for (uint256 i; i < value.length; ++i) data[offset+i] = value[i];
    }

    function sgxFixture(uint8 tcb, uint256 signingKey) private returns (bytes memory) {
        return sgxFixtureWithDebug(tcb, signingKey, false);
    }

    function sgxFixtureWithDebug(uint8 tcb, uint256 signingKey, bool debug) private returns (bytes memory) {
        bytes memory quote = new bytes(1020);
        quote[0] = 0x03; quote[2] = 0x02;
        if (debug) quote[96] = 0x02;
        put(quote,12,hex"939a7233f79c4ca9940a0db3957f0607");
        put(quote,112,abi.encode(ENCLAVE)); put(quote,176,abi.encode(SIGNER));
        quote[306] = 0x01;
        quote[432] = 0x48; quote[433] = 0x02; // exact 584-byte auth fixture
        bytes32 digest = ActionContextV1.digest(c);
        bytes32 binding = sha256(abi.encodePacked("VAMS:SGX-ACTION:v1",hex"00",abi.encode(digest,c.actorRoot,outputHash)));
        put(quote,368,abi.encode(binding));
        bytes memory body = new bytes(384);
        for (uint256 i; i < 384; ++i) body[i] = quote[48+i];
        dcap.setResult(true,abi.encodePacked(uint16(3),uint16(1),tcb,bytes6(0),body));
        bytes32 control = sha256(abi.encodePacked("VAMS:SGX-ROOT-CONTROL:v1",hex"00",abi.encode(digest,outputHash,sha256(quote))));
        return abi.encode(quote,sign(control,signingKey));
    }

    function test_sgxAbiBoundaryAndRootControlWithNonAuthenticFixture() public {
        bytes memory evidence = sgxFixture(0,key);
        assertTrue(sgx.verifyAction(c,outputHash,evidence));
        assertFalse(sgx.verifyAction(c,keccak256("wrong-output"),evidence));
        c.nonce = keccak256("another-challenge");
        assertFalse(sgx.verifyAction(c,outputHash,evidence));
    }

    function test_sgxRejectsAdvisoryTcbAndDifferentRootSigner() public {
        assertFalse(sgx.verifyAction(c,outputHash,sgxFixture(1,key)));
        assertFalse(sgx.verifyAction(c,outputHash,sgxFixture(0,key+1)));
    }

    function test_debugEnclaveAndNoncanonicalEnvelopeReject() public {
        assertFalse(sgx.verifyAction(c,outputHash,sgxFixtureWithDebug(0,key,true)));
        bytes memory valid = sgxFixture(0,key);
        assertFalse(sgx.verifyAction(c,outputHash,bytes.concat(valid,hex"00")));
        bytes memory zkEvidence = zkFixture(key); zk.setResult(true);
        assertFalse(ezkl.verifyAction(c,outputHash,bytes.concat(zkEvidence,hex"00")));
    }

    function test_sgxRejectsUnverifiedBackendAndLegacyConcatenation() public {
        bytes memory evidence = sgxFixture(0,key);
        dcap.setResult(false,bytes("rejected"));
        assertFalse(sgx.verifyAction(c,outputHash,evidence));
        assertFalse(sgx.verifyAction(c,outputHash,abi.encode(abi.encodePacked(c.actionHash,outputHash),new bytes(64))));
    }

    function zkFixture(uint256 signingKey) private returns (bytes memory) {
        uint256[4] memory inputs = [uint256(1),2,3,4];
        uint256[2] memory outputs = [uint256(17),23];
        c.inputHash = sha256(abi.encode(inputs)); outputHash = sha256(abi.encode(outputs));
        bytes memory proof = hex"0102"; // ABI fixture only, not a SNARK.
        bytes32 digest = ActionContextV1.digest(c);
        bytes32 control = sha256(abi.encodePacked("VAMS:EZKL-ROOT-CONTROL:v1",hex"00",
            abi.encode(digest,outputHash,sha256(proof),CIRCUIT)));
        return abi.encode(proof,inputs,outputs,sign(control,signingKey));
    }

    function test_ezklAbiBoundaryWithNonCryptographicFixture() public {
        bytes memory evidence = zkFixture(key);
        zk.setResult(true);
        assertTrue(ezkl.verifyAction(c,outputHash,evidence));
        assertFalse(ezkl.verifyAction(c,keccak256("wrong-output"),evidence));
        c.inputHash = keccak256("wrong-input");
        assertFalse(ezkl.verifyAction(c,outputHash,evidence));
    }

    function test_ezklRejectsFalseBackendAndWrongRoot() public {
        bytes memory evidence = zkFixture(key);
        assertFalse(ezkl.verifyAction(c,outputHash,evidence));
        zk.setResult(true);
        assertFalse(ezkl.verifyAction(c,outputHash,zkFixture(key+1)));
    }

    function test_adaptersRejectExpiredContextAndWrongCodeIdentity() public {
        bytes memory evidence = zkFixture(key); zk.setResult(true);
        vm.warp(c.expiresAt);
        assertFalse(ezkl.verifyAction(c,outputHash,evidence));
        vm.expectRevert("Verifier identity mismatch");
        new EzklActionVerifierV1(address(zk),bytes32(uint256(1)),c.modelId,CIRCUIT);
    }
}
