// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {RewardDistributor} from "../../src/economic/RewardDistributor.sol";
import {IRewardDistributor} from "../../src/economic/IRewardDistributor.sol";
import {RegionalIncentives} from "../../src/economic/RegionalIncentives.sol";

// ═══════════════════ Mock Contracts ═══════════════════

contract MockToken {
    mapping(address => uint256) public balances;

    function mint(address to, uint256 amount) external { balances[to] += amount; }
    function balanceOf(address a) external view returns (uint256) { return balances[a]; }
    function transfer(address to, uint256 am) external returns (bool) {
        require(balances[msg.sender] >= am, "Insufficient");
        balances[msg.sender] -= am; balances[to] += am; return true;
    }
    function transferFrom(address f, address t, uint256 am) external returns (bool) {
        require(balances[f] >= am, "Insufficient");
        balances[f] -= am; balances[t] += am; return true;
    }
    function approve(address, uint256) external pure returns (bool) { return true; }
}

contract MockStaking {
    mapping(address => uint256) public stakes;

    function setStake(address provider, uint256 amount) external {
        stakes[provider] = amount;
    }

    function getStakedAmount(address provider) external view returns (uint256) {
        return stakes[provider];
    }
}

// ═══════════════════ Test Suite ═══════════════════

contract RewardDistributorTest is Test {
    RewardDistributor public distributor;
    RegionalIncentives public ri;
    MockToken public token;
    MockStaking public staking;

    address public admin = address(0xAD);
    address public keeper = address(0xEE);
    address public provider1 = address(0x11);
    address public provider2 = address(0x22);
    address public builder1 = address(0xBB);

    bytes32 public US_EAST = keccak256("us-east-1");
    bytes32 public AF_SOUTH = keccak256("af-south-1");

    function setUp() public {
        token = new MockToken();
        staking = new MockStaking();
        ri = new RegionalIncentives(admin);

        distributor = new RewardDistributor(
            admin,
            address(token),
            address(ri),
            address(staking)
        );

        vm.startPrank(admin);
        distributor.grantRole(distributor.KEEPER_ROLE(), keeper);
        distributor.grantRole(distributor.ACCUMULATOR_ROLE(), keeper);

        // Configure regions
        ri.setRegionConfig(US_EAST, "US East", 500, 10_000); // 1.0x
        ri.setRegionConfig(AF_SOUTH, "Africa South", 50, 30_000); // 3.0x
        ri.updateCapacity(US_EAST, 500); // At target → 1.0x
        ri.updateCapacity(AF_SOUTH, 10); // 20% → full 3.0x bootstrap
        vm.stopPrank();

        // Fund distributor
        token.mint(address(distributor), 10_000_000 ether);

        // Set up staking tiers
        staking.setStake(provider1, 100_000 ether); // SILVER tier (+5%)
        staking.setStake(provider2, 1_500_000 ether); // DIAMOND tier (+20%)
    }

    // ═══════════════════ Accumulation Tests ═══════════════════

    function test_accumulateReward_baseOnly() public {
        vm.prank(keeper);
        distributor.accumulateReward(provider1, 1000 ether, US_EAST);

        // US_EAST at target → multiplier = 1.0x → no regional bonus
        // Provider1 SILVER → +5% staking boost = 50 ether
        uint256 unclaimed = distributor.getUnclaimedRewards(provider1);
        uint256 expectedBase = 1000 ether;
        uint256 expectedBoost = (1000 ether * 500) / 10_000; // 50 ether
        assertEq(unclaimed, expectedBase + expectedBoost);
    }

    function test_accumulateReward_withRegionalBonus() public {
        vm.prank(keeper);
        distributor.accumulateReward(provider1, 1000 ether, AF_SOUTH);

        // AF_SOUTH at 20% → multiplier = 3.0x → bonus = (3.0 - 1.0) × 1000 = 2000
        // SILVER boost = 50 ether
        IRewardDistributor.ProviderReward memory breakdown =
            distributor.getRewardBreakdown(provider1);

        assertEq(breakdown.baseReward, 1000 ether);
        assertEq(breakdown.regionalBonus, 2000 ether);
        assertEq(breakdown.stakingBoost, 50 ether);
        assertEq(breakdown.totalReward, 3050 ether);
    }

    function test_accumulateReward_diamondTier() public {
        vm.prank(keeper);
        distributor.accumulateReward(provider2, 1000 ether, US_EAST);

        // DIAMOND → +20% = 200 ether staking boost
        // US_EAST at target → no regional bonus
        IRewardDistributor.ProviderReward memory breakdown =
            distributor.getRewardBreakdown(provider2);

        assertEq(breakdown.baseReward, 1000 ether);
        assertEq(breakdown.stakingBoost, 200 ether);
        assertEq(breakdown.totalReward, 1200 ether);
    }

    function test_accumulateReward_multipleAccumulations() public {
        vm.startPrank(keeper);
        distributor.accumulateReward(provider1, 500 ether, US_EAST);
        distributor.accumulateReward(provider1, 300 ether, AF_SOUTH);
        vm.stopPrank();

        IRewardDistributor.ProviderReward memory breakdown =
            distributor.getRewardBreakdown(provider1);

        // Two base rewards summed
        assertEq(breakdown.baseReward, 800 ether);
        // Regional bonus only from AF_SOUTH
        assertEq(breakdown.regionalBonus, 600 ether);
        assertTrue(breakdown.totalReward > 1400 ether);
    }

    // ═══════════════════ Builder Revenue Tests ═══════════════════

    function test_accumulateBuilderRevenue() public {
        vm.prank(keeper);
        distributor.accumulateBuilderRevenue(builder1, 500 ether);

        assertEq(distributor.getUnclaimedRewards(builder1), 500 ether);
        assertEq(distributor.builderRevenue(builder1), 500 ether);

        IRewardDistributor.ProviderReward memory breakdown =
            distributor.getRewardBreakdown(builder1);
        assertEq(breakdown.builderRevenue, 500 ether);
    }

    // ═══════════════════ Claim Tests ═══════════════════

    function test_claimRewards_success() public {
        vm.prank(keeper);
        distributor.accumulateReward(provider1, 1000 ether, US_EAST);

        uint256 expected = distributor.getUnclaimedRewards(provider1);
        uint256 balBefore = token.balanceOf(provider1);

        vm.prank(provider1);
        distributor.claimRewards();

        assertEq(token.balanceOf(provider1), balBefore + expected);
        assertEq(distributor.getUnclaimedRewards(provider1), 0);
    }

    function test_claimRewards_reverts_noRewards() public {
        vm.prank(provider1);
        vm.expectRevert(
            abi.encodeWithSelector(IRewardDistributor.NoRewardsToClaim.selector, provider1)
        );
        distributor.claimRewards();
    }

    function test_claimRewards_resetsBreakdown() public {
        vm.prank(keeper);
        distributor.accumulateReward(provider1, 1000 ether, AF_SOUTH);

        vm.prank(provider1);
        distributor.claimRewards();

        IRewardDistributor.ProviderReward memory breakdown =
            distributor.getRewardBreakdown(provider1);
        assertEq(breakdown.totalReward, 0);
    }

    // ═══════════════════ Epoch Tests ═══════════════════

    function test_finalizeEpoch() public {
        vm.prank(keeper);
        distributor.finalizeEpoch(0);
        assertEq(distributor.currentEpoch(), 1);
    }

    function test_finalizeEpoch_reverts_alreadyFinalized() public {
        vm.startPrank(keeper);
        distributor.finalizeEpoch(0);

        vm.expectRevert(
            abi.encodeWithSelector(IRewardDistributor.EpochAlreadyFinalized.selector, 0)
        );
        distributor.finalizeEpoch(0);
        vm.stopPrank();
    }

    // ═══════════════════ Tier Tests ═══════════════════

    function test_getProviderTier_iron() public view {
        string memory tier = distributor.getProviderTier(address(0x99));
        assertEq(tier, "IRON");
    }

    function test_getProviderTier_silver() public view {
        string memory tier = distributor.getProviderTier(provider1);
        assertEq(tier, "SILVER"); // 100k staked
    }

    function test_getProviderTier_diamond() public view {
        string memory tier = distributor.getProviderTier(provider2);
        assertEq(tier, "DIAMOND"); // 1.5M staked
    }

    // ═══════════════════ Access Control ═══════════════════

    function test_accumulateReward_reverts_nonAccumulator() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert();
        distributor.accumulateReward(provider1, 1000, US_EAST);
    }

    // ═══════════════════ Emergency ═══════════════════

    function test_emergencyWithdraw() public {
        vm.prank(admin);
        distributor.emergencyWithdraw(admin, 1000 ether);
        assertEq(token.balanceOf(admin), 1000 ether);
    }
}
