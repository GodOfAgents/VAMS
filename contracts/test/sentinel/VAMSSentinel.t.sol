// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../utils/BaseTest.sol";
import "../../src/sentinel/VAMSSentinel.sol";
import "../../src/sentinel/IVAMSSentinel.sol";

// ═══════════════════ Mock Contracts ═══════════════════

contract MockPausableTarget is IPausableTarget {
    bool public paused;
    string public lastReason;

    function emergencyPause(string calldata reason) external override {
        paused = true;
        lastReason = reason;
    }

    function unpause() external override {
        paused = false;
    }
}

contract MockTVLProvider is ITVLProvider {
    uint256 public tvl;

    function setTVL(uint256 _tvl) external {
        tvl = _tvl;
    }

    function getTotalValueLocked() external view override returns (uint256) {
        return tvl;
    }
}

contract MockPriceOracle is ISentinelPriceOracle {
    uint256 public price;

    function setPrice(uint256 _price) external {
        price = _price;
    }

    function getVAMSPrice() external view override returns (uint256) {
        return price;
    }
}

// ═══════════════════ Test Contract ═══════════════════

/**
 * @title VAMSSentinelTest
 * @notice Comprehensive tests for autonomous anomaly detection and emergency pause system
 */
contract VAMSSentinelTest is BaseTest {
    VAMSSentinel public sentinel;
    MockPausableTarget public target1;
    MockPausableTarget public target2;
    MockTVLProvider public tvlProvider;
    MockPriceOracle public priceOracle;

    address public dao;
    address public fallbackMultisig;
    address public keeper1;
    address public keeper2;
    address public keeper3;

    uint256 public constant KEEPER_BOND = 100_000e18;

    function setUp() public override {
        // Warp to a realistic timestamp so cooldown checks don't falsely trigger
        // (at timestamp=1, _isCooldownActive returns true because 1 < 0 + 14400)
        vm.warp(100_000);
        super.setUp();

        dao = makeAddr("dao");
        fallbackMultisig = makeAddr("fallback");
        keeper1 = makeAddr("keeper1");
        keeper2 = makeAddr("keeper2");
        keeper3 = makeAddr("keeper3");

        // Deploy sentinel
        vm.prank(admin);
        sentinel = new VAMSSentinel(admin, address(token), dao, fallbackMultisig);
        vm.label(address(sentinel), "Sentinel");

        // Deploy mocks
        target1 = new MockPausableTarget();
        target2 = new MockPausableTarget();
        tvlProvider = new MockTVLProvider();
        priceOracle = new MockPriceOracle();

        vm.label(address(target1), "PausableTarget1");
        vm.label(address(target2), "PausableTarget2");

        // Config: add pausable targets
        vm.startPrank(admin);
        sentinel.addPausableTarget(address(target1));
        sentinel.addPausableTarget(address(target2));
        sentinel.setTVLProvider(address(tvlProvider));
        sentinel.setPriceOracle(address(priceOracle));
        vm.stopPrank();

        // Fund and register keepers
        _fundAndApprove(keeper1, address(sentinel), KEEPER_BOND);
        _fundAndApprove(keeper2, address(sentinel), KEEPER_BOND);
        _fundAndApprove(keeper3, address(sentinel), KEEPER_BOND);

        vm.prank(keeper1);
        sentinel.registerKeeper(KEEPER_BOND);

        vm.prank(keeper2);
        sentinel.registerKeeper(KEEPER_BOND);

        vm.prank(keeper3);
        sentinel.registerKeeper(KEEPER_BOND);

        // Advance blocks past KEEPER_VOTING_DELAY to allow keepers to vote
        vm.roll(block.number + 100);
    }

    // ═══════════════════ Initialization ═══════════════════

    function test_Initialization() public view {
        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.NORMAL));
        assertTrue(sentinel.hasRole(sentinel.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(sentinel.hasRole(sentinel.DAO_ROLE(), dao));
        assertTrue(sentinel.hasRole(sentinel.FALLBACK_ROLE(), fallbackMultisig));
    }

    function test_DefaultThresholds() public view {
        IVAMSSentinel.Thresholds memory t = sentinel.getThresholds();
        assertEq(t.tvlDrainBps, 1500);
        assertEq(t.priceCrashBps, 5000);
        assertEq(t.keeperConsensusMin, 3);
        assertEq(t.cooldownPeriod, 4 hours);
    }

    // ═══════════════════ Keeper Registration ═══════════════════

    function test_KeeperRegistered() public view {
        assertTrue(sentinel.hasRole(sentinel.KEEPER_ROLE(), keeper1));
        assertTrue(sentinel.isKeeper(keeper1));
        assertEq(sentinel.keeperBonds(keeper1), KEEPER_BOND);
    }

    function test_RegisterKeeper_RevertInsufficientBond() public {
        address newKeeper = makeAddr("newKeeper");
        uint256 lowBond = 5_000e18; // Below MIN_KEEPER_BOND
        _fundAndApprove(newKeeper, address(sentinel), lowBond);

        vm.expectRevert(abi.encodeWithSelector(
            IVAMSSentinel.InsufficientKeeperBond.selector, lowBond, KEEPER_BOND
        ));
        vm.prank(newKeeper);
        sentinel.registerKeeper(lowBond);
    }

    function test_RegisterKeeper_RevertAlreadyRegistered() public {
        vm.expectRevert(abi.encodeWithSelector(
            IVAMSSentinel.KeeperAlreadyRegistered.selector, keeper1
        ));
        vm.prank(keeper1);
        sentinel.registerKeeper(KEEPER_BOND);
    }

    // ═══════════════════ L1: TVL Drain Detection ═══════════════════

    function test_L1_TVLDrain_TriggersPause() public {
        // Set initial TVL
        tvlProvider.setTVL(1_000_000e18);

        // First call: snapshot the TVL
        sentinel.checkInvariantsAndPause();
        _advanceBlocks(1);

        // Simulate 20% drain (exceeds 15% threshold)
        tvlProvider.setTVL(800_000e18);

        // Should trigger pause
        bool paused = sentinel.checkInvariantsAndPause();
        assertTrue(paused, "Should have triggered pause");

        // Verify protocol is paused
        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.PAUSED));

        // Verify targets are paused
        assertTrue(target1.paused(), "Target 1 should be paused");
        assertTrue(target2.paused(), "Target 2 should be paused");

        // Verify anomaly recorded
        assertEq(sentinel.getAnomalyCount(), 1);
    }

    function test_L1_NoDrain_NoPause() public {
        tvlProvider.setTVL(1_000_000e18);
        sentinel.checkInvariantsAndPause();
        _advanceBlocks(1);

        // 5% drop — below 15% threshold
        tvlProvider.setTVL(950_000e18);
        bool paused = sentinel.checkInvariantsAndPause();
        assertFalse(paused, "Should NOT trigger pause");
        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.NORMAL));
    }

    // ═══════════════════ L2: Keeper Consensus ═══════════════════

    function test_L2_KeeperConsensus_3of3_TriggersPause() public {
        // 3 keepers submit high-score reports in the same block
        vm.prank(keeper1);
        sentinel.submitKeeperReport(90, keccak256("evidence1"));

        vm.prank(keeper2);
        sentinel.submitKeeperReport(85, keccak256("evidence2"));

        vm.prank(keeper3);
        sentinel.submitKeeperReport(95, keccak256("evidence3"));

        // Should be paused after 3rd report
        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.PAUSED));
    }

    function test_L2_BelowThreshold_NoPause() public {
        // 2 keepers submit (below consensus min of 3)
        vm.prank(keeper1);
        sentinel.submitKeeperReport(90, keccak256("ev1"));

        vm.prank(keeper2);
        sentinel.submitKeeperReport(85, keccak256("ev2"));

        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.NORMAL));
    }

    function test_L2_LowScore_DoesNotCount() public {
        // Score below 80 doesn't count toward consensus
        vm.prank(keeper1);
        sentinel.submitKeeperReport(79, keccak256("ev1")); // Below threshold

        vm.prank(keeper2);
        sentinel.submitKeeperReport(90, keccak256("ev2")); // Counts

        vm.prank(keeper3);
        sentinel.submitKeeperReport(50, keccak256("ev3")); // Below threshold

        // Only 1 high-score report, should NOT pause
        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.NORMAL));
    }

    function test_L2_RevertAlreadyPaused() public {
        // Trigger pause via L2
        vm.prank(keeper1);
        sentinel.submitKeeperReport(90, keccak256("ev1"));
        vm.prank(keeper2);
        sentinel.submitKeeperReport(85, keccak256("ev2"));
        vm.prank(keeper3);
        sentinel.submitKeeperReport(95, keccak256("ev3"));

        // Try submitting when already paused
        _advanceBlocks(1);
        vm.expectRevert(IVAMSSentinel.ProtocolAlreadyPaused.selector);
        vm.prank(keeper1);
        sentinel.submitKeeperReport(90, keccak256("ev4"));
    }

    // ═══════════════════ L3: Price Circuit Breaker ═══════════════════

    function test_L3_PriceCrash_TriggersPause() public {
        // Set price anchor
        priceOracle.setPrice(1e18); // $1.00
        vm.prank(keeper1);
        sentinel.updatePriceAnchor();

        // Crash to $0.40 (60% drop > 50% threshold)
        priceOracle.setPrice(0.4e18);

        bool paused = sentinel.checkInvariantsAndPause();
        assertTrue(paused, "Price crash should trigger pause");
        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.PAUSED));
    }

    function test_L3_SmallDip_NoPause() public {
        priceOracle.setPrice(1e18);
        vm.prank(keeper1);
        sentinel.updatePriceAnchor();

        // 20% dip — below 50% threshold
        priceOracle.setPrice(0.8e18);

        bool paused = sentinel.checkInvariantsAndPause();
        assertFalse(paused, "Small dip should NOT trigger pause");
    }

    // ═══════════════════ DAO Functions ═══════════════════

    function test_DAO_ResumeProtocol() public {
        // Trigger pause
        _triggerL2Pause();
        assertTrue(target1.paused());

        // DAO resumes
        vm.prank(dao);
        sentinel.resumeProtocol(0);

        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.NORMAL));
        assertFalse(target1.paused(), "Target should be unpaused");
    }

    function test_DAO_ResumeProtocol_RevertIfNotPaused() public {
        vm.expectRevert(IVAMSSentinel.ProtocolNotPaused.selector);
        vm.prank(dao);
        sentinel.resumeProtocol(0);
    }

    function test_DAO_ResumeProtocol_RevertUnauthorized() public {
        _triggerL2Pause();

        vm.expectRevert();
        vm.prank(user1);
        sentinel.resumeProtocol(0);
    }

    function test_DAO_UpdateThresholds() public {
        IVAMSSentinel.Thresholds memory newT = IVAMSSentinel.Thresholds({
            tvlDrainBps: 2000,
            whaleExitBps: 1000,
            bridgeFloodSigma: 4,
            priceCrashBps: 4000,
            keeperConsensusMin: 5,
            cooldownPeriod: 6 hours
        });

        vm.prank(dao);
        sentinel.updateThresholds(newT);

        IVAMSSentinel.Thresholds memory stored = sentinel.getThresholds();
        assertEq(stored.tvlDrainBps, 2000);
        assertEq(stored.keeperConsensusMin, 5);
        assertEq(stored.cooldownPeriod, 6 hours);
    }

    // ═══════════════════ Keeper Slashing ═══════════════════

    function test_SlashKeeper() public {
        _triggerL2Pause();

        uint256 bondBefore = sentinel.keeperBonds(keeper1);
        uint256 slashAmount = (bondBefore * 500) / 10_000; // 5%

        vm.prank(dao);
        sentinel.slashKeeper(keeper1, "false alarm");

        assertEq(sentinel.keeperBonds(keeper1), bondBefore - slashAmount);
    }

    function test_SlashKeeper_RevokesRoleWhenBelowMin() public {
        // First slash the keeper enough to bring below minimum
        // We need to repeatedly slash. Let's start fresh with a keeper at exactly minimum bond.
        _triggerL2Pause();

        // Slash 20 times (each 5%): 10000 * 0.95^20 ≈ 3585 < 10000 MIN_KEEPER_BOND
        // But we can only slash once without resuming. Let's just check logic:
        // After 1 slash: 10000 * 0.95 = 9500 < 10000 → role revoked
        vm.prank(dao);
        sentinel.slashKeeper(keeper1, "false alarm");

        // 9500 < 10000 MIN_KEEPER_BOND → role should be revoked
        assertFalse(sentinel.hasRole(sentinel.KEEPER_ROLE(), keeper1));
    }

    function test_SlashKeeper_RevertNotRegistered() public {
        _triggerL2Pause();

        vm.expectRevert(abi.encodeWithSelector(
            IVAMSSentinel.KeeperNotRegistered.selector, user1
        ));
        vm.prank(dao);
        sentinel.slashKeeper(user1, "not a keeper");
    }

    // ═══════════════════ Cooldown ═══════════════════

    function test_Cooldown_PreventsTooFrequentPauses() public {
        // First pause via L1
        tvlProvider.setTVL(1_000_000e18);
        sentinel.checkInvariantsAndPause();
        _advanceBlocks(1);
        tvlProvider.setTVL(800_000e18);
        sentinel.checkInvariantsAndPause(); // triggers pause

        // Resume
        vm.prank(dao);
        sentinel.resumeProtocol(0);

        // Try immediately again — should be in cooldown
        _advanceBlocks(1);
        tvlProvider.setTVL(600_000e18);
        vm.expectRevert(); // CooldownActive
        sentinel.checkInvariantsAndPause();
    }

    function test_Cooldown_AllowsAfterPeriod() public {
        tvlProvider.setTVL(1_000_000e18);
        sentinel.checkInvariantsAndPause();
        _advanceBlocks(1);
        tvlProvider.setTVL(800_000e18);
        sentinel.checkInvariantsAndPause(); // pause

        // Resume
        vm.prank(dao);
        sentinel.resumeProtocol(0);

        // Wait past cooldown
        _advanceTime(5 hours); // > 4 hour cooldown
        _advanceBlocks(1);

        tvlProvider.setTVL(500_000e18);
        bool paused = sentinel.checkInvariantsAndPause();
        assertTrue(paused, "Should allow pause after cooldown");
    }

    // ═══════════════════ Fallback Multi-sig ═══════════════════

    function test_FallbackPause() public {
        vm.prank(fallbackMultisig);
        sentinel.fallbackPause("Sentinel compromised");

        assertEq(uint256(sentinel.getProtocolMode()), uint256(IVAMSSentinel.ProtocolMode.PAUSED));
        assertTrue(target1.paused());
    }

    function test_FallbackPause_RevertUnauthorized() public {
        vm.expectRevert();
        vm.prank(user1);
        sentinel.fallbackPause("unauthorized");
    }

    // ═══════════════════ Admin Functions ═══════════════════

    function test_AddPausableTarget() public {
        MockPausableTarget target3 = new MockPausableTarget();
        vm.prank(admin);
        sentinel.addPausableTarget(address(target3));

        assertEq(sentinel.getPausableTargetCount(), 3);
    }

    function test_RemovePausableTarget() public {
        vm.prank(admin);
        sentinel.removePausableTarget(0);

        assertEq(sentinel.getPausableTargetCount(), 1);
    }

    // ═══════════════════ View Functions ═══════════════════

    function test_GetAnomalyCount() public {
        assertEq(sentinel.getAnomalyCount(), 0);

        _triggerL2Pause();
        assertEq(sentinel.getAnomalyCount(), 1);
    }

    function test_GetAnomalyReport() public {
        _triggerL2Pause();

        IVAMSSentinel.AnomalyReport memory report = sentinel.getAnomalyReport(0);
        assertEq(uint256(report.anomalyType), uint256(IVAMSSentinel.AnomalyType.KEEPER_CONSENSUS));
        assertTrue(report.pauseTriggered);
        assertEq(report.severity, 7);
    }

    // ═══════════════════ Helpers ═══════════════════

    function _triggerL2Pause() internal {
        vm.prank(keeper1);
        sentinel.submitKeeperReport(90, keccak256("ev1"));
        vm.prank(keeper2);
        sentinel.submitKeeperReport(85, keccak256("ev2"));
        vm.prank(keeper3);
        sentinel.submitKeeperReport(95, keccak256("ev3"));
    }
}
