// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/token/VAMSToken.sol";

/**
 * @title VAMSTokenTest
 * @notice Comprehensive tests for VAMSToken contract
 */
contract VAMSTokenTest is BaseTest {
    VAMSToken public vamsToken;

    // Test constants
    uint256 constant INITIAL_SUPPLY = 1_000_000_000 ether; // Total Supply
    uint256 constant ANTI_WHALE_DURATION = 180 days;
    uint256 constant INITIAL_MAX_WALLET_BPS = 500; // 5%
    uint256 constant INITIAL_DAILY_LIMIT_BPS = 100; // 1%

    function setUp() public override {
        super.setUp();

        // Deploy real VAMS token
        vm.prank(admin);
        vamsToken = new VAMSToken(admin, treasury);
        vm.label(address(vamsToken), "VAMSToken");
    }

    // ============ Initialization Tests ============

    function test_Initialize_SetsCorrectSupply() public view {
        assertEq(vamsToken.totalSupply(), INITIAL_SUPPLY);
    }

    function test_Initialize_AssignsSupplyToTreasury() public view {
        assertEq(vamsToken.balanceOf(treasury), INITIAL_SUPPLY);
    }

    function test_Initialize_SetsCorrectName() public view {
        assertEq(vamsToken.name(), "VAMS");
        assertEq(vamsToken.symbol(), "VAMS");
    }

    function test_Initialize_SetsCorrectDecimals() public view {
        assertEq(vamsToken.decimals(), 18);
    }

    function test_Initialize_AdminHasRoles() public view {
        assertTrue(vamsToken.hasRole(vamsToken.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(vamsToken.hasRole(vamsToken.PAUSER_ROLE(), admin));
    }

    function test_Initialize_TreasuryExemptFromLimits() public view {
        assertTrue(vamsToken.isExemptFromLimits(treasury));
    }

    function test_Initialize_AntiWhaleEnabled() public view {
        assertTrue(vamsToken.antiWhaleEnabled());
    }

    function test_Initialize_SetsMaxWalletBps() public view {
        assertEq(vamsToken.maxWalletBps(), INITIAL_MAX_WALLET_BPS);
    }

    function test_Initialize_SetsDailyLimitBps() public view {
        assertEq(vamsToken.dailyTransferLimitBps(), INITIAL_DAILY_LIMIT_BPS);
    }

    function test_Initialize_RevertOnZeroAdmin() public {
        vm.expectRevert(IVAMSToken.ZeroAddress.selector);
        new VAMSToken(address(0), treasury);
    }

    function test_Initialize_RevertOnZeroTreasury() public {
        vm.expectRevert(IVAMSToken.ZeroAddress.selector);
        new VAMSToken(admin, address(0));
    }

    // ============ ERC20 Compliance Tests ============

    function test_Transfer_UpdatesBalances() public {
        uint256 amount = 1000 ether;

        // Transfer from treasury to user1 (treasury is exempt)
        vm.prank(treasury);
        bool success = // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount);
        assertTrue(success, "Transfer failed");

        assertEq(vamsToken.balanceOf(user1), amount);
        assertEq(vamsToken.balanceOf(treasury), INITIAL_SUPPLY - amount);
    }

    function test_Transfer_EmitsEvent() public {
        uint256 amount = 1000 ether;

        vm.expectEmit(true, true, false, true);
        emit IERC20.Transfer(treasury, user1, amount);

        vm.prank(treasury);
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(user1, amount);
    }

    function test_Transfer_RevertsOnInsufficientBalance() public {
        uint256 amount = 1000 ether;

        vm.prank(user1);
        vm.expectRevert();
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(user2, amount);
    }

    function test_Approve_SetsAllowance() public {
        uint256 amount = 1000 ether;

        vm.prank(user1);
        vamsToken.approve(user2, amount);

        assertEq(vamsToken.allowance(user1, user2), amount);
    }

    function test_Approve_EmitsEvent() public {
        uint256 amount = 1000 ether;

        vm.expectEmit(true, true, false, true);
        emit IERC20.Approval(user1, user2, amount);

        vm.prank(user1);
        vamsToken.approve(user2, amount);
    }

    function test_TransferFrom_UsesAllowance() public {
        uint256 amount = 1000 ether;

        // Treasury transfers to user1
        vm.prank(treasury);
        bool success = // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount);
        assertTrue(success, "Treasury transfer failed");

        // Exempt user1 from limits for testing
        vm.prank(admin);
        vamsToken.addExemptAddress(user1);

        // user1 approves user2
        vm.prank(user1);
        vamsToken.approve(user2, amount);

        // user2 transfers from user1
        vm.prank(user2);
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transferFrom(user1, user3, amount / 2);

        assertEq(vamsToken.balanceOf(user3), amount / 2);
        assertEq(vamsToken.allowance(user1, user2), amount / 2);
    }

    function test_TransferFrom_RevertsOnInsufficientAllowance() public {
        uint256 amount = 1000 ether;

        vm.prank(treasury);
        // We verify success here to silence warning, though main test is expectation below
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount)
        );

        // No approval
        vm.prank(user2);
        vm.expectRevert();
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transferFrom(user1, user3, amount);
    }

    // ============ Minting Tests ============

    function test_Mint_WithMinterRole() public {
        // Admin grants MINTER_ROLE to itself
        vm.startPrank(admin);
        vamsToken.grantRole(vamsToken.MINTER_ROLE(), admin);

        // Burn some tokens first to make room for minting
        vamsToken.addExemptAddress(user1);
        vamsToken.addExemptAddress(admin);
        vm.stopPrank();

        // Transfer some tokens to user1 and burn them
        vm.prank(treasury);
        bool success = // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, 1000 ether);
        assertTrue(success);

        vm.prank(user1);
        vamsToken.burn(1000 ether);

        // Now there's room to mint
        vm.prank(admin);
        vamsToken.mint(user1, 500 ether);

        assertEq(vamsToken.balanceOf(user1), 500 ether);
    }

    function test_Mint_RevertsWithoutRole() public {
        vm.prank(user1);
        vm.expectRevert();
        vamsToken.mint(user1, 1000 ether);
    }

    function test_Mint_RevertsAboveFixedSupplyCap() public {
        uint256 attemptedSupply = vamsToken.INITIAL_SUPPLY() + 1;
        uint256 maxSupply = vamsToken.MAX_SUPPLY();
        vm.expectRevert(abi.encodeWithSelector(IVAMSToken.MaxSupplyExceeded.selector, attemptedSupply, maxSupply));
        vm.prank(admin);
        vamsToken.mint(user1, 1);
    }

    // ============ Burning Tests ============

    function test_Burn_ReducesBalance() public {
        uint256 amount = 1000 ether;
        uint256 burnAmount = 100 ether;

        vm.prank(treasury);
        bool success = // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount);
        assertTrue(success);

        vm.prank(user1);
        vamsToken.burn(burnAmount);

        assertEq(vamsToken.balanceOf(user1), amount - burnAmount);
        assertEq(vamsToken.totalSupply(), INITIAL_SUPPLY - burnAmount);
    }

    function test_Burn_EmitsEvent() public {
        uint256 amount = 1000 ether;
        uint256 burnAmount = 100 ether;

        vm.prank(treasury);
        bool success = // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount);
        assertTrue(success);

        vm.expectEmit(true, true, false, true);
        emit IERC20.Transfer(user1, address(0), burnAmount);

        vm.prank(user1);
        vamsToken.burn(burnAmount);
    }

    function test_BurnFrom_UsesAllowance() public {
        uint256 amount = 1000 ether;
        uint256 burnAmount = 100 ether;

        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount)
        );

        vm.prank(user1);
        vamsToken.approve(user2, burnAmount);

        vm.prank(user2);
        vamsToken.burnFrom(user1, burnAmount);

        assertEq(vamsToken.balanceOf(user1), amount - burnAmount);
    }

    // ============ Pause Tests ============

    function test_Pause_BlocksTransfers() public {
        uint256 amount = 1000 ether;

        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount)
        );

        vm.prank(admin);
        vamsToken.pause();

        vm.prank(user1);
        vm.expectRevert();
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(user2, 100 ether);
    }

    function test_Pause_OnlyPauserRole() public {
        vm.prank(user1);
        vm.expectRevert();
        vamsToken.pause();
    }

    function test_Unpause_EnablesTransfers() public {
        uint256 amount = 1000 ether;

        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount)
        );

        // Exempt user1 for this test
        vm.prank(admin);
        vamsToken.addExemptAddress(user1);

        vm.prank(admin);
        vamsToken.pause();

        vm.prank(admin);
        vamsToken.unpause();

        vm.prank(user1);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user2, 100 ether)
        );

        assertEq(vamsToken.balanceOf(user2), 100 ether);
    }

    // ============ Anti-Whale Tests ============

    function test_AntiWhale_BlocksExcessiveWallet() public {
        // Max wallet is 5% of initial supply
        uint256 maxWallet = vamsToken.maxWalletAmount();

        // First transfer some tokens from treasury to user2 (user2 will be our tester)
        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user2, maxWallet + 10 ether)
        );

        // Now user2 (not exempt) tries to send to user1
        // This should fail because user1 would exceed max wallet
        vm.prank(user2);
        vm.expectRevert();
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(user1, maxWallet + 1 ether);
    }

    function test_AntiWhale_AllowsWithinLimit() public {
        uint256 dailyLimit = vamsToken.dailyTransferLimit(); // 1% = 1.5M tokens
        uint256 transferAmount = dailyLimit / 2; // Transfer half of daily limit

        // Transfer from treasury to user2 first
        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user2, transferAmount)
        );

        // User2 (non-exempt) transfers to user1 within both wallet and daily limits
        vm.prank(user2);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, transferAmount / 2)
        );

        assertEq(vamsToken.balanceOf(user1), transferAmount / 2);
    }

    function test_AntiWhale_ExemptAddressBypasses() public {
        uint256 overLimit = vamsToken.maxWalletAmount() + 1_000_000 ether;

        // Treasury is already exempt, so it can transfer any amount
        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, overLimit)
        );

        assertEq(vamsToken.balanceOf(user1), overLimit);
    }

    function test_AntiWhale_DailyLimitEnforced() public {
        // Transfer some tokens to user1 (within limits)
        uint256 amount = 20_000_000 ether; // 2% of supply, within max wallet
        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount)
        );

        // Daily limit is 1% = 10M tokens
        uint256 dailyLimit = vamsToken.dailyTransferLimit();

        // First transfer should work (if within daily limit)
        uint256 firstTransfer = dailyLimit / 2;
        vm.prank(user1);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user2, firstTransfer)
        );

        // Second transfer exceeding daily limit should fail
        vm.prank(user1);
        vm.expectRevert();
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        vamsToken.transfer(user2, dailyLimit); // Would exceed daily limit
    }

    function test_AntiWhale_DailyLimitResetsNextDay() public {
        uint256 amount = vamsToken.dailyTransferLimit();

        // Exempt user1 from max wallet for this test
        vm.prank(admin);
        vamsToken.addExemptAddress(user1);

        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, amount * 3)
        );

        // Remove exemption to test daily limits on transfers
        vm.prank(admin);
        vamsToken.removeExemptAddress(user1);

        // First day transfer
        vm.prank(user1);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user2, amount / 2)
        );

        // Advance to next day
        _advanceTime(1 days + 1);

        // Should be able to transfer again
        vm.prank(user1);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user3, amount / 2)
        );

        assertEq(vamsToken.balanceOf(user3), amount / 2);
    }

    function test_AntiWhale_DisabledAfterPeriod() public {
        // Advance past anti-whale period
        _advanceTime(ANTI_WHALE_DURATION + 1);

        // Should be able to receive unlimited tokens
        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, 100_000_000 ether)
        );

        assertEq(vamsToken.balanceOf(user1), 100_000_000 ether);
    }

    function test_AntiWhale_CanBeDisabledByAdmin() public {
        vm.prank(admin);
        vamsToken.setAntiWhaleEnabled(false);

        assertFalse(vamsToken.antiWhaleEnabled());

        // Should now bypass limits
        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, 100_000_000 ether)
        );

        assertEq(vamsToken.balanceOf(user1), 100_000_000 ether);
    }

    // ============ Admin Function Tests ============

    function test_SetMaxWalletBps_UpdatesLimit() public {
        uint256 newBps = 500; // 5%

        vm.prank(admin);
        vamsToken.setMaxWalletBps(newBps);

        assertEq(vamsToken.maxWalletBps(), newBps);
    }

    function test_SetMaxWalletBps_EmitsEvent() public {
        uint256 newBps = 500;

        vm.expectEmit(false, false, false, true);
        emit IVAMSToken.MaxWalletUpdated(newBps);

        vm.prank(admin);
        vamsToken.setMaxWalletBps(newBps);
    }

    function test_SetMaxWalletBps_RevertsOnExceedLimit() public {
        vm.prank(admin);
        vm.expectRevert();
        vamsToken.setMaxWalletBps(10001); // > 100%
    }

    function test_SetDailyTransferLimitBps_UpdatesLimit() public {
        uint256 newBps = 200; // 2%

        vm.prank(admin);
        vamsToken.setDailyTransferLimitBps(newBps);

        assertEq(vamsToken.dailyTransferLimitBps(), newBps);
    }

    function test_AddExemptAddress_Works() public {
        assertFalse(vamsToken.isExemptFromLimits(user1));

        vm.prank(admin);
        vamsToken.addExemptAddress(user1);

        assertTrue(vamsToken.isExemptFromLimits(user1));
    }

    function test_RemoveExemptAddress_Works() public {
        vm.prank(admin);
        vamsToken.addExemptAddress(user1);
        assertTrue(vamsToken.isExemptFromLimits(user1));

        vm.prank(admin);
        vamsToken.removeExemptAddress(user1);
        assertFalse(vamsToken.isExemptFromLimits(user1));
    }

    function test_AddExemptAddress_OnlyAdmin() public {
        vm.prank(user1);
        vm.expectRevert();
        vamsToken.addExemptAddress(user1);
    }

    // ============ View Function Tests ============

    function test_MaxWalletAmount_CalculatesCorrectly() public view {
        uint256 expected = (INITIAL_SUPPLY * INITIAL_MAX_WALLET_BPS) / 10000;
        assertEq(vamsToken.maxWalletAmount(), expected);
    }

    function test_DailyTransferLimit_CalculatesCorrectly() public view {
        uint256 expected = (INITIAL_SUPPLY * INITIAL_DAILY_LIMIT_BPS) / 10000;
        assertEq(vamsToken.dailyTransferLimit(), expected);
    }

    // ============ Fuzz Tests ============

    function testFuzz_Transfer(address to, uint256 amount) public {
        vm.assume(to != address(0) && to != treasury);
        amount = bound(amount, 1, vamsToken.maxWalletAmount());

        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(to, amount)
        );

        assertEq(vamsToken.balanceOf(to), amount);
    }

    function testFuzz_Approve(address spender, uint256 amount) public {
        vm.assume(spender != address(0));

        vm.prank(user1);
        vamsToken.approve(spender, amount);

        assertEq(vamsToken.allowance(user1, spender), amount);
    }

    function testFuzz_Burn(uint256 burnAmount) public {
        uint256 userBalance = 10_000 ether;
        burnAmount = bound(burnAmount, 1, userBalance);

        vm.prank(treasury);
        assertTrue( // forge-lint: disable-next-line(erc20-unchecked-transfer)
            vamsToken.transfer(user1, userBalance)
        );

        uint256 supplyBefore = vamsToken.totalSupply();

        vm.prank(user1);
        vamsToken.burn(burnAmount);

        assertEq(vamsToken.totalSupply(), supplyBefore - burnAmount);
        assertEq(vamsToken.balanceOf(user1), userBalance - burnAmount);
    }
}

