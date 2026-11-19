// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {IVAMSToken} from "../../src/token/IVAMSToken.sol";

/// @notice Production-token regressions; synthetic minter authority is local only.
contract MintWindowAuditRegressionTest is Test {
    VAMSToken internal token;
    address internal constant RECIPIENT = address(0x1234);

    function setUp() public {
        token = new VAMSToken(address(this), address(this));
        token.burn(100_000_000 ether);
    }

    function testFuzz_dormantYearsDoNotAccumulateSpendableMintCaps(uint8 yearsRaw) public {
        uint256 yearsElapsed = bound(uint256(yearsRaw), 2, 100);
        uint256 period = token.SECONDS_PER_YEAR();
        uint256 origin = token.currentMintYearStart();
        uint256 cap = token.ANNUAL_MINT_CAP();
        vm.warp(origin + yearsElapsed * period + 1);

        token.mint(RECIPIENT, cap);
        assertEq(token.currentMintYearStart(), origin + yearsElapsed * period);
        assertEq(token.mintedThisYear(), cap);
        vm.expectRevert(abi.encodeWithSelector(IVAMSToken.AnnualMintCapExceeded.selector, cap + 1, cap));
        token.mint(RECIPIENT, 1);
        assertEq(token.totalSupply(), 925_000_000 ether);
    }

    function test_burnCannotResetCurrentPeriodBudget() public {
        uint256 origin = token.currentMintYearStart();
        uint256 period = token.SECONDS_PER_YEAR();
        uint256 cap = token.ANNUAL_MINT_CAP();
        vm.warp(origin + 3 * period + 17);
        token.mint(address(this), cap);
        token.burn(cap);
        vm.expectRevert(abi.encodeWithSelector(IVAMSToken.AnnualMintCapExceeded.selector, cap + 1, cap));
        token.mint(address(this), 1);
        assertEq(token.totalSupply(), 900_000_000 ether);
    }

    function test_nextPeriodRestoresExactlyOneCapAtOriginalBoundary() public {
        uint256 origin = token.currentMintYearStart();
        uint256 period = token.SECONDS_PER_YEAR();
        uint256 cap = token.ANNUAL_MINT_CAP();
        vm.warp(origin + 3 * period - 1);
        token.mint(address(this), cap);
        assertEq(token.currentMintYearStart(), origin + 2 * period);
        vm.warp(origin + 3 * period);
        token.mint(address(this), cap);
        assertEq(token.currentMintYearStart(), origin + 3 * period);
        assertEq(token.mintedThisYear(), cap);
        vm.expectRevert(abi.encodeWithSelector(IVAMSToken.AnnualMintCapExceeded.selector, cap + 1, cap));
        token.mint(address(this), 1);
        assertLe(token.totalSupply(), token.MAX_SUPPLY());
    }
}
