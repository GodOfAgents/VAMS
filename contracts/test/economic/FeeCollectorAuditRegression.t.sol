// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {VAMSFeeCollector} from "../../src/economic/VAMSFeeCollector.sol";

contract FeeCallbackToken is ERC20 {
    VAMSFeeCollector internal target;
    bool internal callback;

    constructor() ERC20("Audit fixture", "AUDIT") {
        _mint(msg.sender, 100_000 ether);
        _mint(address(this), 100 ether);
    }

    function arm(VAMSFeeCollector collector) external {
        target = collector;
        _approve(address(this), address(collector), type(uint256).max);
        callback = true;
    }

    function transferFrom(address from, address to, uint256 amount) public override returns (bool) {
        if (callback) {
            callback = false;
            target.collectTokenFees(address(this), 1 ether);
        }
        return super.transferFrom(from, to, amount);
    }
}

contract FeeCollectorAuditRegressionTest is Test {
    FeeCallbackToken internal token;
    VAMSFeeCollector internal collector;

    function setUp() public {
        token = new FeeCallbackToken();
        VAMSFeeCollector impl = new VAMSFeeCollector();
        collector = VAMSFeeCollector(address(new ERC1967Proxy(address(impl), abi.encodeCall(
            VAMSFeeCollector.initialize,
            (address(this), address(token), address(0x1234), address(0x2345), address(0x3456))
        ))));
        token.approve(address(collector), type(uint256).max);
    }

    function testFuzz_pausedCollectionCannotBypassPauseThroughAutoDistribution(bool generic, bool aboveThreshold) public {
        uint256 amount = aboveThreshold ? 10_000 ether : 1 ether;
        collector.pause();
        vm.expectRevert(bytes4(keccak256("EnforcedPause()")));
        if (generic) collector.collectTokenFees(address(token), amount);
        else collector.collectFees(amount);
        assertEq(collector.tokenFees(address(token)), 0);
        assertEq(token.balanceOf(address(collector)), 0);
        assertEq(token.balanceOf(collector.BURN_ADDRESS()), 0);
    }

    function testFuzz_tokenCallbackCannotReenterEitherCollectionPath(bool generic) public {
        collector.grantRole(collector.FEE_COLLECTOR_ROLE(), address(token));
        token.arm(collector);
        vm.expectRevert(bytes4(keccak256("ReentrancyGuardReentrantCall()")));
        if (generic) collector.collectTokenFees(address(token), 10_000 ether);
        else collector.collectFees(10_000 ether);
        assertEq(collector.tokenFees(address(token)), 0);
        assertEq(token.balanceOf(address(collector)), 0);
        assertEq(token.balanceOf(collector.BURN_ADDRESS()), 0);
    }

    function test_unpauseRestoresCollectionWithoutActivatingAnyNewRoute() public {
        collector.pause();
        collector.unpause();
        collector.collectFees(1 ether);
        assertEq(collector.tokenFees(address(token)), 1 ether);
        assertEq(token.balanceOf(address(collector)), 1 ether);
    }
}
