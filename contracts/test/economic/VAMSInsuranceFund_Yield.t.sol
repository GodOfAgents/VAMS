// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/economic/VAMSInsuranceFund.sol";
import "../../src/token/VAMSToken.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract MockStakingContract {
    mapping(address => uint256) public stakes;

    function setStake(address account, uint256 amount) external {
        stakes[account] = amount;
    }

    function getStakeInfo(address account) external view returns (uint256) {
        return stakes[account];
    }
}

contract VAMSInsuranceFund_YieldTest is Test {
    VAMSInsuranceFund public fund;
    VAMSToken public vamsToken;
    MockStakingContract public staking;

    address public admin = address(1);
    address public guardian = address(2);
    address public yieldManager = address(3);
    address public slasher = address(4);
    address public vault = address(5);
    address public agentOwner = address(6);

    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    bytes32 public constant YIELD_MANAGER_ROLE = keccak256("YIELD_MANAGER_ROLE");
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");

    function setUp() public {
        vm.startPrank(admin);
        vamsToken = new VAMSToken(admin, admin);
        staking = new MockStakingContract();
        VAMSInsuranceFund fundImpl = new VAMSInsuranceFund();
        address[] memory guardians = new address[](1);
        guardians[0] = guardian;

        ERC1967Proxy proxy = new ERC1967Proxy(
            address(fundImpl),
            abi.encodeCall(VAMSInsuranceFund.initialize, (admin, address(vamsToken), address(staking), guardians))
        );
        fund = VAMSInsuranceFund(address(proxy));

        fund.grantRole(YIELD_MANAGER_ROLE, yieldManager);
        fund.grantRole(SLASHER_ROLE, slasher);

        // Fund the slasher so it can deposit
        vamsToken.transfer(slasher, 100_000 ether);

        vm.stopPrank();

        // Deposit initial funds to Insurance Fund
        vm.startPrank(slasher);
        vamsToken.approve(address(fund), 10_000 ether);
        fund.receiveSlashedFunds(10_000 ether);
        vm.stopPrank();
    }

    function test_deployToYield_Success() public {
        assertEq(fund.totalFundBalance(), 10_000 ether);
        assertEq(fund.totalDeployedBalance(), 0);

        uint256 amountToDeploy = 3_000 ether; // 30% of 10,000

        vm.startPrank(yieldManager);
        fund.deployToYield(vault, amountToDeploy);
        vm.stopPrank();

        assertEq(fund.totalFundBalance(), 10_000 ether); // Total should remain the same
        assertEq(fund.totalDeployedBalance(), 3_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 7_000 ether);
        assertEq(vamsToken.balanceOf(vault), 3_000 ether);
    }

    function test_deployToYield_RevertsIfExceedsMax() public {
        uint256 amountToDeploy = 3_001 ether; // > 30% of 10,000

        vm.startPrank(yieldManager);
        vm.expectRevert("VAMSInsuranceFund: Max yield allocation exceeded");
        fund.deployToYield(vault, amountToDeploy);
        vm.stopPrank();
    }

    function test_withdrawFromYield_Success() public {
        uint256 amountToDeploy = 3_000 ether;

        vm.startPrank(yieldManager);
        fund.deployToYield(vault, amountToDeploy);
        vm.stopPrank();

        // Now withdraw
        uint256 amountToWithdraw = 1_000 ether;

        // Vault or someone needs to approve fund to take back the tokens
        vm.startPrank(vault);
        vamsToken.transfer(yieldManager, amountToWithdraw); // Simulating yield manager taking it back to send
        vm.stopPrank();

        vm.startPrank(yieldManager);
        vamsToken.approve(address(fund), amountToWithdraw);
        fund.withdrawFromYield(vault, amountToWithdraw);
        vm.stopPrank();

        assertEq(fund.totalFundBalance(), 10_000 ether);
        assertEq(fund.totalDeployedBalance(), 2_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 8_000 ether);
    }

    function test_withdrawFromYield_RevertsIfInsufficient() public {
        uint256 amountToDeploy = 1_000 ether;

        vm.startPrank(yieldManager);
        fund.deployToYield(vault, amountToDeploy);
        vm.expectRevert("VAMSInsuranceFund: Insufficient deployed balance");
        fund.withdrawFromYield(vault, 1_001 ether);
        vm.stopPrank();
    }

    function test_claimWithYieldDeployed() public {
        // Deploy 30% to yield
        vm.startPrank(yieldManager);
        fund.deployToYield(vault, 3_000 ether);
        vm.stopPrank();

        // Give agentOwner a stake to make them an AGENT
        staking.setStake(agentOwner, 10_000 ether);

        // Submit claim
        vm.startPrank(agentOwner);
        bytes32 claimId = fund.submitClaim(bytes32(uint256(1)), 4_000 ether, "Test claim");
        vm.stopPrank();

        // Approve claim
        vm.startPrank(admin);
        fund.grantRole(GUARDIAN_ROLE, address(7)); // Add a second guardian for threshold
        vm.stopPrank();

        vm.startPrank(guardian);
        fund.approveClaim(claimId);
        vm.stopPrank();

        vm.startPrank(address(7));
        fund.approveClaim(claimId);
        vm.stopPrank();

        // Execute payout
        fund.executePayout(claimId);

        // Balances: 10k total - 4k claim = 6k total.
        // Deployed is 3k. Balance of fund is 3k.
        assertEq(fund.totalFundBalance(), 6_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 3_000 ether);
        assertEq(vamsToken.balanceOf(agentOwner), 4_000 ether);
    }
}
