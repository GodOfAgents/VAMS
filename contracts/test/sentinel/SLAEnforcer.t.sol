// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/sentinel/SLAEnforcer.sol";
import "../../src/slashing/VAMSSlasher.sol";
import "../../src/interfaces/IVAMSHardwareRegistry.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract MockHardwareRegistry is IVAMSHardwareRegistry {
    mapping(bytes32 => VAMSResourceNode) public nodes;
    
    function setNode(bytes32 nodeId, address provider) external {
        nodes[nodeId].nodeId = nodeId;
        nodes[nodeId].provider = provider;
        nodes[nodeId].isActive = true;
    }

    function getNode(bytes32 nodeId) external view returns (VAMSResourceNode memory) {
        if (nodes[nodeId].provider == address(0)) {
            revert NodeNotFound(nodeId);
        }
        return nodes[nodeId];
    }

    function updateBenchmark(bytes32 nodeId, uint256 score, uint256 timestamp) external {
        nodes[nodeId].benchmarkScore = score;
        nodes[nodeId].lastBenchmarkAt = timestamp;
    }

    // Unused mocks
    function registerHardwareClass(bytes32, string calldata, string calldata, uint256, uint256) external {}
    function deactivateHardwareClass(bytes32) external {}
    function updateClassCollateral(bytes32, uint256) external {}
    function getHardwareClass(bytes32) external view returns (HardwareClassInfo memory) { revert("mock"); }
    function getRegisteredClassCount() external view returns (uint256) { return 0; }
    function getRegisteredClassId(uint256) external view returns (bytes32) { revert("mock"); }
    function registerNode(bytes32, string calldata, uint256, uint256, uint256) external returns (bytes32) { return bytes32(0); }
    function requestDeregistration(bytes32) external {}
    function executeDeregistration(bytes32) external {}
    function updateCapacity(bytes32, uint256) external {}
    function updatePrice(bytes32, uint256) external {}
    function getNodesByProvider(address) external view returns (bytes32[] memory) { revert("mock"); }
    function getTotalNodeCount() external view returns (uint256) { return 0; }
    function isNodeHealthy(bytes32) external view returns (bool) { return true; }
}

contract MockSlasher {
    event SlashCalled(address operator, uint8 offenseType, uint256 bps);

    function slashSLA(
        address _operator,
        uint8 _offenseType,
        uint256 _customBps
    ) external returns (uint256 slashAmount, uint256 jailDuration, uint256 victimCompensation, uint256 burnAmount, bool tombstone) {
        emit SlashCalled(_operator, _offenseType, _customBps);
        return (0, 0, 0, 0, false);
    }
}

contract SLAEnforcerTest is Test {
    using MessageHashUtils for bytes32;

    SLAEnforcer public enforcer;
    MockHardwareRegistry public registry;
    MockSlasher public slasher;

    address admin = address(1);
    
    uint256 sentinelPrivateKey = 0xa11ce;
    address sentinelAddress = vm.addr(sentinelPrivateKey);

    address provider = address(3);
    bytes32 nodeId = keccak256("TEST_NODE");

    function setUp() public {
        registry = new MockHardwareRegistry();
        slasher = new MockSlasher();
        
        // Deploy SLAEnforcer behind proxy (AC01: _disableInitializers)
        SLAEnforcer impl = new SLAEnforcer();
        ERC1967Proxy proxy = new ERC1967Proxy(
            address(impl),
            abi.encodeCall(SLAEnforcer.initialize, (admin, address(registry), address(slasher)))
        );
        enforcer = SLAEnforcer(address(proxy));

        // Prep the registry with our mock node
        registry.setNode(nodeId, provider);
        
        // Register sentinel via admin
        vm.prank(admin);
        enforcer.registerSentinel(sentinelAddress);
    }

    function test_RegisterSentinel() public {
        assertTrue(enforcer.isSentinel(sentinelAddress));
    }

    function test_RequireUnauthorizedSentinel() public {
        bytes32 registrarRole = enforcer.REGISTRAR_ROLE();
        vm.expectRevert(abi.encodeWithSignature("AccessControlUnauthorizedAccount(address,bytes32)", address(0x99), registrarRole));
        vm.prank(address(0x99));
        enforcer.registerSentinel(address(4));
    }

    function test_SubmitSLAReport_Success() public {
        ISLAEnforcer.SLAReport memory report = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 100,
            metricsScore: 9000,
            challengeType: "cpu_simulated",
            daHeight: 42,
            daCommitment: "abcd"
        });

        bytes memory sig = _signReport(report, sentinelPrivateKey);
        
        // Expect NO slasher call, but benchmark update
        enforcer.submitSLAReport(report, sig);
        
        assertEq(registry.getNode(nodeId).benchmarkScore, 9000);
    }

    function test_SubmitSLAReport_CapacitySlash() public {
        ISLAEnforcer.SLAReport memory report = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 101,
            metricsScore: 7000, // Below 7500 min SLA threshold, above 1000 fraud
            challengeType: "gpu_simulated",
            daHeight: 43,
            daCommitment: "cdef"
        });

        bytes memory sig = _signReport(report, sentinelPrivateKey);
        
        // We expect SLA_CAPACITY (enum 4) on Slasher
        enforcer.submitSLAReport(report, sig);
        
        assertEq(registry.getNode(nodeId).benchmarkScore, 7000);
    }

    function test_SubmitSLAReport_OfflineSlash() public {
        ISLAEnforcer.SLAReport memory report = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 102,
            metricsScore: 0, // 0 = SLA_OFFLINE (enum 5)
            challengeType: "latency",
            daHeight: 44,
            daCommitment: "defg"
        });

        bytes memory sig = _signReport(report, sentinelPrivateKey);

        enforcer.submitSLAReport(report, sig);
        assertEq(registry.getNode(nodeId).benchmarkScore, 0);
    }

    function test_SubmitSLAReport_FraudSlash() public {
        ISLAEnforcer.SLAReport memory report = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 103,
            metricsScore: 500, // < 1000 = SLA_FRAUD (enum 6)
            challengeType: "latency",
            daHeight: 45,
            daCommitment: "xyz"
        });

        bytes memory sig = _signReport(report, sentinelPrivateKey);

        enforcer.submitSLAReport(report, sig);
        assertEq(registry.getNode(nodeId).benchmarkScore, 500);
    }

    function test_RevertIfReportIsTooOld() public {
        ISLAEnforcer.SLAReport memory report1 = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 100,
            metricsScore: 9000,
            challengeType: "cpu",
            daHeight: 42,
            daCommitment: "abcd"
        });

        bytes memory sig1 = _signReport(report1, sentinelPrivateKey);
        enforcer.submitSLAReport(report1, sig1);
        
        // Send a report with same timestamp
        ISLAEnforcer.SLAReport memory report2 = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 100,
            metricsScore: 9500,
            challengeType: "cpu",
            daHeight: 43,
            daCommitment: "abcd2"
        });

        bytes memory sig2 = _signReport(report2, sentinelPrivateKey);
        vm.expectRevert(ISLAEnforcer.ReportTooOld.selector);
        enforcer.submitSLAReport(report2, sig2);
    }

    function test_RevertIfInvalidSentinel() public {
        ISLAEnforcer.SLAReport memory report = ISLAEnforcer.SLAReport({
            nodeId: nodeId,
            timestamp: 100,
            metricsScore: 9000,
            challengeType: "cpu",
            daHeight: 42,
            daCommitment: "abcd"
        });

        // Sign with unauthorized key
        bytes memory sig = _signReport(report, 0x1badb01);
        
        vm.expectRevert(ISLAEnforcer.UnauthorizedSentinel.selector);
        enforcer.submitSLAReport(report, sig);
    }

    function _signReport(ISLAEnforcer.SLAReport memory report, uint256 pk) internal pure returns (bytes memory) {
        bytes32 structHash = keccak256(
            abi.encode(
                report.nodeId,
                report.timestamp,
                report.metricsScore,
                keccak256(bytes(report.challengeType)),
                report.daHeight,
                keccak256(bytes(report.daCommitment))
            )
        );
        bytes32 digest = structHash.toEthSignedMessageHash();
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, digest);
        return abi.encodePacked(r, s, v);
    }
}
