// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/economic/VAMSInsuranceFund.sol";
import "../../src/economic/IVAMSInsuranceFund.sol";
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

    function test_claimWithYieldDeployed_RejectsCapBreakingPayoutAndAllowsDelayedRetry() public {
        _deploy(3_000 ether);
        bytes32 claimId = _submitAndApproveClaim(agentOwner, 4_000 ether, 1);

        // Independent oracle: 10,000 - 4,000 = 6,000; floor(30% * 6,000) = 1,800.
        uint256 fundLiquidBefore = vamsToken.balanceOf(address(fund));
        uint256 claimantBefore = vamsToken.balanceOf(agentOwner);
        VAMSInsuranceFund.Claim memory claimBefore = fund.getClaim(claimId);
        vm.expectRevert();
        fund.executePayout(claimId);

        _assertClaimApproved(claimId, 4_000 ether);
        assertEq(fund.getClaim(claimId).submittedAt, claimBefore.submittedAt);
        assertEq(fund.getClaim(claimId).resolvedAt, claimBefore.resolvedAt);
        assertEq(fund.totalFundBalance(), 10_000 ether);
        assertEq(fund.totalDeployedBalance(), 3_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), fundLiquidBefore);
        assertEq(vamsToken.balanceOf(agentOwner), claimantBefore);

        // An approved claim remains retryable after its original review window.
        vm.warp(claimBefore.submittedAt + fund.CLAIM_WINDOW() + 1);
        _returnYield(1_200 ether);
        assertEq(fund.totalFundBalance(), 10_000 ether);
        assertEq(fund.totalDeployedBalance(), 1_800 ether);

        fund.executePayout(claimId);
        assertEq(uint8(fund.getClaim(claimId).status), uint8(IVAMSInsuranceFund.ClaimStatus.PAID));
        assertEq(fund.totalFundBalance(), 6_000 ether);
        assertEq(fund.totalDeployedBalance(), 1_800 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 4_200 ether);
        assertEq(vamsToken.balanceOf(agentOwner), 4_000 ether);
    }

    function test_executePayout_RejectsOneWeiAbovePostPayoutCap() public {
        _deploy(1_800 ether + 1);
        bytes32 claimId = _submitAndApproveClaim(agentOwner, 4_000 ether, 2);
        uint256 fundLiquidBefore = vamsToken.balanceOf(address(fund));

        // floor(3,000 * 6,000 ether / 10,000) = 1,800 ether exactly.
        vm.expectRevert();
        fund.executePayout(claimId);

        _assertClaimApproved(claimId, 4_000 ether);
        assertEq(fund.totalDeployedBalance(), 1_800 ether + 1);
        assertEq(fund.totalFundBalance(), 10_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), fundLiquidBefore);
        assertEq(vamsToken.balanceOf(agentOwner), 0);
    }

    function test_executePayout_AcceptsExactOneWeiCapBoundary() public {
        _deploy(1_800 ether);
        bytes32 claimId = _submitAndApproveClaim(agentOwner, 4_000 ether, 3);

        fund.executePayout(claimId);

        assertEq(uint8(fund.getClaim(claimId).status), uint8(IVAMSInsuranceFund.ClaimStatus.PAID));
        assertEq(fund.totalFundBalance(), 6_000 ether);
        assertEq(fund.totalDeployedBalance(), 1_800 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 4_200 ether);
        assertEq(vamsToken.balanceOf(agentOwner), 4_000 ether);
    }

    function test_executePayout_InsufficientCurrentLiquidLeavesLaterApprovedClaimRetryable() public {
        _deploy(1_000 ether);
        bytes32 firstClaim = _submitAndApproveClaim(agentOwner, 5_000 ether, 4);
        bytes32 laterClaim = _submitAndApproveClaim(address(8), 4_500 ether, 5);

        fund.executePayout(firstClaim);
        assertEq(fund.totalFundBalance(), 5_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 4_000 ether);
        assertEq(fund.totalDeployedBalance(), 1_000 ether);

        // Later claim was approved against the original 10,000 total. Current liquid is 4,000.
        uint256 laterOwnerBefore = vamsToken.balanceOf(address(8));
        vm.expectRevert(abi.encodeWithSelector(
            IVAMSInsuranceFund.InsufficientFunds.selector,
            4_500 ether,
            4_000 ether
        ));
        fund.executePayout(laterClaim);

        _assertClaimApproved(laterClaim, 4_500 ether);
        assertEq(fund.totalFundBalance(), 5_000 ether);
        assertEq(fund.totalDeployedBalance(), 1_000 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 4_000 ether);
        assertEq(vamsToken.balanceOf(address(8)), laterOwnerBefore);
    }

    function test_executePayout_ZeroDeployedCompliantPayoutSucceeds() public {
        bytes32 claimId = _submitAndApproveClaim(agentOwner, 4_000 ether, 6);

        fund.executePayout(claimId);

        assertEq(uint8(fund.getClaim(claimId).status), uint8(IVAMSInsuranceFund.ClaimStatus.PAID));
        assertEq(fund.totalFundBalance(), 6_000 ether);
        assertEq(fund.totalDeployedBalance(), 0);
        assertEq(vamsToken.balanceOf(address(fund)), 6_000 ether);
        assertEq(vamsToken.balanceOf(agentOwner), 4_000 ether);
    }

    function test_executePayout_ReevaluatesCapAfterEachSequentialPayout() public {
        _deploy(2_700 ether);
        bytes32 firstClaim = _submitAndApproveClaim(agentOwner, 1_000 ether, 7);
        bytes32 secondClaim = _submitAndApproveClaim(address(8), 1_000 ether, 8);

        // First payout leaves T=9,000 and D=2,700, exactly the 30% boundary.
        fund.executePayout(firstClaim);
        assertEq(fund.totalFundBalance(), 9_000 ether);
        assertEq(fund.totalDeployedBalance(), 2_700 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 6_300 ether);
        assertEq(vamsToken.balanceOf(agentOwner), 1_000 ether);

        // Second payout leaves T=8,000, whose independent cap is 2,400.
        uint256 secondOwnerBefore = vamsToken.balanceOf(address(8));
        vm.expectRevert();
        fund.executePayout(secondClaim);

        _assertClaimApproved(secondClaim, 1_000 ether);
        assertEq(fund.totalFundBalance(), 9_000 ether);
        assertEq(fund.totalDeployedBalance(), 2_700 ether);
        assertEq(vamsToken.balanceOf(address(fund)), 6_300 ether);
        assertEq(vamsToken.balanceOf(address(8)), secondOwnerBefore);
    }

    function test_executePayout_PausedTokenTransferRollsBackPaidState() public {
        bytes32 claimId = _submitAndApproveClaim(agentOwner, 1_000 ether, 9);
        uint256 fundBefore = vamsToken.balanceOf(address(fund));
        uint256 claimantBefore = vamsToken.balanceOf(agentOwner);

        vm.prank(admin);
        vamsToken.pause();
        vm.expectRevert(VAMSToken.TokenPaused.selector);
        fund.executePayout(claimId);

        _assertClaimApproved(claimId, 1_000 ether);
        assertEq(fund.totalFundBalance(), 10_000 ether);
        assertEq(fund.totalDeployedBalance(), 0);
        assertEq(vamsToken.balanceOf(address(fund)), fundBefore);
        assertEq(vamsToken.balanceOf(agentOwner), claimantBefore);

        vm.prank(admin);
        vamsToken.unpause();
        fund.executePayout(claimId);
        assertEq(uint8(fund.getClaim(claimId).status), uint8(IVAMSInsuranceFund.ClaimStatus.PAID));
        assertEq(vamsToken.balanceOf(agentOwner), 1_000 ether);
    }

    function _deploy(uint256 amount) internal {
        vm.prank(yieldManager);
        fund.deployToYield(vault, amount);
    }

    function _returnYield(uint256 amount) internal {
        // Mirrors the existing test accounting path; this is not a vault redemption test.
        vm.prank(vault);
        vamsToken.transfer(yieldManager, amount);
        vm.startPrank(yieldManager);
        vamsToken.approve(address(fund), amount);
        fund.withdrawFromYield(vault, amount);
        vm.stopPrank();
    }

    function _submitAndApproveClaim(address claimant, uint256 amount, uint256 claimNonce)
        internal
        returns (bytes32 claimId)
    {
        staking.setStake(claimant, 10_000 ether);
        vm.prank(claimant);
        claimId = fund.submitClaim(bytes32(claimNonce), amount, "Synthetic insurance claim");

        vm.startPrank(admin);
        fund.grantRole(GUARDIAN_ROLE, address(7));
        vm.stopPrank();
        vm.prank(guardian);
        fund.approveClaim(claimId);
        vm.prank(address(7));
        fund.approveClaim(claimId);
    }

    function _assertClaimApproved(bytes32 claimId, uint256 expectedAmount) internal view {
        VAMSInsuranceFund.Claim memory claim = fund.getClaim(claimId);
        assertEq(uint8(claim.status), uint8(IVAMSInsuranceFund.ClaimStatus.APPROVED));
        assertEq(claim.amount, expectedAmount);
        assertEq(claim.approvalCount, 2);
        assertTrue(fund.hasApproved(claimId, guardian));
        assertTrue(fund.hasApproved(claimId, address(7)));
    }
}
