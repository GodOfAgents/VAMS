// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "../../src/slashing/StateCheckpointRegistryV2.sol";

/// @notice Public lifecycle regressions for the inactive checkpoint-bond prototype.
/// @dev All token balances and callback behavior are local test fixtures only.
contract StateCheckpointRegistryV2Test is Test {
    uint256 private constant BOND = 50_000e18;
    bytes4 private constant REENTRANCY_ERROR = bytes4(keccak256("ReentrancyGuardReentrantCall()"));
    bytes32 private constant ROOT_A = keccak256("root-a");
    bytes32 private constant ROOT_B = keccak256("root-b");
    bytes32 private constant ROOT_C = keccak256("root-c");

    address private constant OPERATOR_A = address(0xA001);
    address private constant OPERATOR_B = address(0xA002);
    address private constant OPERATOR_C = address(0xA003);
    address private constant CHALLENGER = address(0xB001);
    address private constant ARBITRATOR = address(0xC001);
    address private constant UNAUTHORIZED = address(0xD001);

    CheckpointAdversarialERC20 private token;
    StateCheckpointRegistryV2 private registry;

    function setUp() public {
        vm.warp(1_000);
        token = new CheckpointAdversarialERC20();
        registry = new StateCheckpointRegistryV2(address(this), address(token));
        registry.grantRole(registry.ARBITRATOR_ROLE(), ARBITRATOR);

        token.mint(OPERATOR_A, 5 * BOND);
        token.mint(OPERATOR_B, 5 * BOND);
        token.mint(OPERATOR_C, 5 * BOND);
        token.mint(CHALLENGER, 5 * BOND);
        token.mint(address(token), 5 * BOND);
        token.approveSelf(address(registry), type(uint256).max);
    }

    function test_submitAndDuplicateRejectWithoutTakingSecondBond() public {
        _submit(OPERATOR_A, ROOT_A);

        vm.expectRevert("Checkpoint already exists");
        vm.prank(OPERATOR_A);
        registry.submitCheckpoint(ROOT_A);

        StateCheckpointRegistryV2.Checkpoint memory cp = _checkpoint(ROOT_A);
        assertEq(cp.operator, OPERATOR_A);
        assertEq(cp.submittedAt, block.timestamp);
        assertFalse(cp.finalized);
        assertFalse(cp.challenged);
        assertEq(token.balanceOf(address(registry)), BOND);
    }

    function test_challengeIsAcceptedAtInclusiveDeadlineAndBlocksFinalization() public {
        _submit(OPERATOR_A, ROOT_A);
        _approve(CHALLENGER);
        uint256 deadline = block.timestamp + registry.CHALLENGE_PERIOD();

        vm.warp(deadline);
        _challenge(CHALLENGER, ROOT_A);
        StateCheckpointRegistryV2.Checkpoint memory cp = _checkpoint(ROOT_A);
        assertTrue(cp.challenged);
        assertEq(cp.challenger, CHALLENGER);
        assertFalse(cp.finalized, "challenge must not make the root final");
        assertEq(token.balanceOf(address(registry)), 2 * BOND);

        vm.expectRevert("Cannot finalize challenged checkpoint");
        registry.finalizeCheckpoint(ROOT_A);
    }

    function test_finalizeRequiresStrictlyAfterDeadlineAndReturnsBondOnce() public {
        _submit(OPERATOR_A, ROOT_A);
        uint256 deadline = block.timestamp + registry.CHALLENGE_PERIOD();

        vm.warp(deadline);
        vm.expectRevert("Challenge period active");
        registry.finalizeCheckpoint(ROOT_A);

        vm.warp(deadline + 1);
        vm.expectRevert("Challenge period over");
        vm.prank(CHALLENGER);
        registry.challengeCheckpoint(ROOT_A);

        uint256 operatorBalanceBefore = token.balanceOf(OPERATOR_A);
        registry.finalizeCheckpoint(ROOT_A);
        StateCheckpointRegistryV2.Checkpoint memory cp = _checkpoint(ROOT_A);
        assertTrue(cp.finalized);
        assertFalse(cp.challenged);
        assertEq(token.balanceOf(OPERATOR_A), operatorBalanceBefore + BOND);
        assertEq(token.balanceOf(address(registry)), 0);

        vm.expectRevert("Already finalized");
        registry.finalizeCheckpoint(ROOT_A);
        assertEq(token.balanceOf(OPERATOR_A), operatorBalanceBefore + BOND);
    }

    function test_missingAndUnchallengedRootsCannotMoveAnotherRootBond() public {
        _submit(OPERATOR_A, ROOT_A);
        uint256 heldBefore = token.balanceOf(address(registry));

        vm.expectRevert("Checkpoint missing");
        vm.prank(CHALLENGER);
        registry.challengeCheckpoint(ROOT_B);
        vm.expectRevert("Checkpoint missing");
        registry.finalizeCheckpoint(ROOT_B);
        vm.expectRevert("Checkpoint missing");
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_B, true);
        vm.expectRevert("Checkpoint not challenged");
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, true);

        assertEq(token.balanceOf(address(registry)), heldBefore);
        assertEq(_checkpoint(ROOT_A).operator, OPERATOR_A);
        assertEq(_checkpoint(ROOT_B).submittedAt, 0);
    }

    function test_onlyArbitratorCanResolveDispute() public {
        _submit(OPERATOR_A, ROOT_A);
        _approve(CHALLENGER);
        _challenge(CHALLENGER, ROOT_A);

        vm.expectRevert();
        vm.prank(UNAUTHORIZED);
        registry.resolveDispute(ROOT_A, true);

        assertTrue(_checkpoint(ROOT_A).challenged);
        assertFalse(_checkpoint(ROOT_A).finalized);
        assertEq(token.balanceOf(address(registry)), 2 * BOND);
    }

    function test_operatorWinReturnsBothBondsAndConsumesResolutionOnce() public {
        _submit(OPERATOR_A, ROOT_A);
        _approve(CHALLENGER);
        _challenge(CHALLENGER, ROOT_A);
        uint256 operatorBefore = token.balanceOf(OPERATOR_A);
        uint256 challengerBefore = token.balanceOf(CHALLENGER);

        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, true);

        StateCheckpointRegistryV2.Checkpoint memory cp = _checkpoint(ROOT_A);
        assertTrue(cp.finalized, "operator-win checkpoint is valid and finalized");
        assertTrue(cp.challenged);
        assertEq(token.balanceOf(OPERATOR_A), operatorBefore + 2 * BOND);
        assertEq(token.balanceOf(CHALLENGER), challengerBefore);
        assertEq(token.balanceOf(address(registry)), 0);

        vm.expectRevert("Already finalized");
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, true);
        assertEq(token.balanceOf(OPERATOR_A), operatorBefore + 2 * BOND);
    }

    function test_operatorWinTransferFailureRollsBackAndCanRetry() public {
        _assertArbitrationTransferFailureAndRetry(true);
    }

    function test_challengerWinTransferFailureRollsBackAndCanRetry() public {
        _assertArbitrationTransferFailureAndRetry(false);
    }

    function testFuzz_arbitrationPayoutCallbackCannotReplayResolution(bool operatorWins) public {
        _submit(OPERATOR_A, ROOT_A);
        _submit(OPERATOR_B, ROOT_B);
        _submit(OPERATOR_C, ROOT_C);
        _challenge(CHALLENGER, ROOT_A);
        registry.grantRole(registry.ARBITRATOR_ROLE(), address(token));

        uint256 operatorBefore = token.balanceOf(OPERATOR_A);
        uint256 challengerBefore = token.balanceOf(CHALLENGER);
        address winner = operatorWins ? OPERATOR_A : CHALLENGER;
        uint256 winnerBefore = token.balanceOf(winner);
        token.configureTransferHook(
            address(registry), abi.encodeWithSelector(registry.resolveDispute.selector, ROOT_A, operatorWins)
        );

        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, operatorWins);

        assertTrue(token.transferHookAttempted(), "payout token callback was not attempted");
        assertFalse(token.transferHookSucceeded(), "nested arbitration resolution unexpectedly succeeded");
        assertEq(
            token.transferHookReturnSelector(),
            REENTRANCY_ERROR,
            "nested arbitration did not fail at the shared reentrancy guard"
        );
        assertEq(token.balanceOf(winner), winnerBefore + 2 * BOND, "winner must receive the pool once");
        assertEq(token.balanceOf(address(registry)), 2 * BOND, "callback consumed unrelated root bonds");
        assertEq(token.balanceOf(OPERATOR_A), operatorBefore + (operatorWins ? 2 * BOND : 0));
        assertEq(token.balanceOf(CHALLENGER), challengerBefore + (operatorWins ? 0 : 2 * BOND));

        StateCheckpointRegistryV2.Checkpoint memory disputed = _checkpoint(ROOT_A);
        assertTrue(disputed.challenged);
        assertEq(disputed.finalized, operatorWins, "challenger win must retain invalid/unfinalized status");

        uint256 deadlineB = _checkpoint(ROOT_B).submittedAt + registry.CHALLENGE_PERIOD();
        vm.warp(deadlineB + 1);
        registry.finalizeCheckpoint(ROOT_B);
        registry.finalizeCheckpoint(ROOT_C);
        assertEq(token.balanceOf(OPERATOR_B), 5 * BOND);
        assertEq(token.balanceOf(OPERATOR_C), 5 * BOND);
        assertEq(token.balanceOf(address(registry)), 0);
    }

    function test_challengerWinKeepsInvalidStatusAndCannotReplayDrainOtherRoots() public {
        _submit(OPERATOR_A, ROOT_A);
        _submit(OPERATOR_B, ROOT_B);
        _submit(OPERATOR_C, ROOT_C);
        _approve(CHALLENGER);
        _challenge(CHALLENGER, ROOT_A);
        uint256 challengerBefore = token.balanceOf(CHALLENGER);
        assertEq(token.balanceOf(address(registry)), 4 * BOND);

        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, false);
        assertFalse(_checkpoint(ROOT_A).finalized, "invalid root must remain unfinalized");
        assertTrue(_checkpoint(ROOT_A).challenged);
        assertEq(token.balanceOf(CHALLENGER), challengerBefore + 2 * BOND);
        assertEq(token.balanceOf(address(registry)), 2 * BOND, "unrelated operator bonds remain held");

        vm.expectRevert();
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, false);
        assertEq(token.balanceOf(address(registry)), 2 * BOND, "resolved dispute replay drained other roots");

        uint256 deadlineB = _checkpoint(ROOT_B).submittedAt + registry.CHALLENGE_PERIOD();
        vm.warp(deadlineB + 1);
        registry.finalizeCheckpoint(ROOT_B);
        registry.finalizeCheckpoint(ROOT_C);
        assertEq(token.balanceOf(OPERATOR_B), 5 * BOND);
        assertEq(token.balanceOf(OPERATOR_C), 5 * BOND);
        assertEq(token.balanceOf(address(registry)), 0);
    }

    function test_failedTokenTransfersRollbackCheckpointLifecycle() public {
        _approve(OPERATOR_A);
        token.setFailures(true, false);
        vm.expectRevert();
        vm.prank(OPERATOR_A);
        registry.submitCheckpoint(ROOT_A);
        assertEq(_checkpoint(ROOT_A).submittedAt, 0);
        assertEq(token.balanceOf(address(registry)), 0);
        assertEq(token.balanceOf(OPERATOR_A), 5 * BOND);

        token.setFailures(false, false);
        _submit(OPERATOR_A, ROOT_A);
        _approve(CHALLENGER);
        token.setFailures(true, false);
        vm.expectRevert();
        vm.prank(CHALLENGER);
        registry.challengeCheckpoint(ROOT_A);
        assertFalse(_checkpoint(ROOT_A).challenged);
        assertEq(_checkpoint(ROOT_A).challenger, address(0));
        assertEq(token.balanceOf(address(registry)), BOND);

        token.setFailures(false, true);
        vm.warp(_checkpoint(ROOT_A).submittedAt + registry.CHALLENGE_PERIOD() + 1);
        vm.expectRevert();
        registry.finalizeCheckpoint(ROOT_A);
        assertFalse(_checkpoint(ROOT_A).finalized);
        assertEq(token.balanceOf(address(registry)), BOND);
    }

    function test_submitCallbackCannotCreateTwoBondsForOneRoot() public {
        _approve(OPERATOR_A);
        token.configureHook(
            address(registry), abi.encodeWithSelector(registry.submitCheckpoint.selector, ROOT_A)
        );

        vm.prank(OPERATOR_A);
        registry.submitCheckpoint(ROOT_A);

        assertTrue(token.hookAttempted(), "token callback did not reach the public submit path");
        assertFalse(token.hookSucceeded(), "reentrant submit unexpectedly succeeded");
        assertEq(token.hookReturnSelector(), REENTRANCY_ERROR, "reentrant submit was not guard-rejected");
        assertEq(_checkpoint(ROOT_A).operator, OPERATOR_A, "outer submit should remain the recorded operator");
        assertEq(
            token.balanceOf(address(registry)),
            BOND,
            "reentrant same-root submission stranded a second operator bond"
        );
    }

    function test_challengeCallbackCannotTakeTwoBondsForOneChallenge() public {
        _submit(OPERATOR_A, ROOT_A);
        _approve(CHALLENGER);
        token.configureHook(
            address(registry), abi.encodeWithSelector(registry.challengeCheckpoint.selector, ROOT_A)
        );

        vm.prank(CHALLENGER);
        registry.challengeCheckpoint(ROOT_A);

        StateCheckpointRegistryV2.Checkpoint memory cp = _checkpoint(ROOT_A);
        assertTrue(token.hookAttempted(), "token callback did not reach the public challenge path");
        assertFalse(token.hookSucceeded(), "reentrant challenge unexpectedly succeeded");
        assertEq(token.hookReturnSelector(), REENTRANCY_ERROR, "reentrant challenge was not guard-rejected");
        assertTrue(cp.challenged);
        assertEq(cp.challenger, CHALLENGER, "outer challenge should remain the recorded challenger");
        assertEq(
            token.balanceOf(address(registry)),
            2 * BOND,
            "reentrant challenge stranded a second challenger bond"
        );
    }

    function _approve(address account) private {
        vm.prank(account);
        token.approve(address(registry), type(uint256).max);
    }

    function _submit(address operator, bytes32 root) private {
        _approve(operator);
        vm.prank(operator);
        registry.submitCheckpoint(root);
    }

    function _challenge(address challenger, bytes32 root) private {
        _approve(challenger);
        vm.prank(challenger);
        registry.challengeCheckpoint(root);
    }

    function _assertArbitrationTransferFailureAndRetry(bool operatorWins) private {
        _submit(OPERATOR_A, ROOT_A);
        _submit(OPERATOR_B, ROOT_B);
        _submit(OPERATOR_C, ROOT_C);
        _challenge(CHALLENGER, ROOT_A);
        uint256 operatorBefore = token.balanceOf(OPERATOR_A);
        uint256 challengerBefore = token.balanceOf(CHALLENGER);

        token.setFailures(false, true);
        vm.expectRevert();
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, operatorWins);

        StateCheckpointRegistryV2.Checkpoint memory afterFailure = _checkpoint(ROOT_A);
        assertTrue(afterFailure.challenged);
        assertFalse(afterFailure.finalized, "failed payout consumed or finalized the dispute");
        assertEq(token.balanceOf(address(registry)), 4 * BOND);
        assertEq(token.balanceOf(OPERATOR_A), operatorBefore);
        assertEq(token.balanceOf(CHALLENGER), challengerBefore);

        token.setFailures(false, false);
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, operatorWins);

        StateCheckpointRegistryV2.Checkpoint memory afterRetry = _checkpoint(ROOT_A);
        assertTrue(afterRetry.challenged);
        assertEq(token.balanceOf(address(registry)), 2 * BOND);
        if (operatorWins) {
            assertTrue(afterRetry.finalized, "valid operator checkpoint must finalize");
            assertEq(token.balanceOf(OPERATOR_A), operatorBefore + 2 * BOND);
            assertEq(token.balanceOf(CHALLENGER), challengerBefore);
            vm.expectRevert("Already finalized");
        } else {
            assertFalse(afterRetry.finalized, "challenger win keeps the invalid root unfinalized");
            assertEq(token.balanceOf(OPERATOR_A), operatorBefore);
            assertEq(token.balanceOf(CHALLENGER), challengerBefore + 2 * BOND);
            vm.expectRevert();
        }
        vm.prank(ARBITRATOR);
        registry.resolveDispute(ROOT_A, operatorWins);

        assertEq(token.balanceOf(address(registry)), 2 * BOND, "replay consumed unrelated checkpoint bonds");
        uint256 deadlineB = _checkpoint(ROOT_B).submittedAt + registry.CHALLENGE_PERIOD();
        vm.warp(deadlineB + 1);
        registry.finalizeCheckpoint(ROOT_B);
        registry.finalizeCheckpoint(ROOT_C);
        assertEq(token.balanceOf(OPERATOR_B), 5 * BOND);
        assertEq(token.balanceOf(OPERATOR_C), 5 * BOND);
        assertEq(token.balanceOf(address(registry)), 0);
    }

    function _checkpoint(bytes32 root)
        private
        view
        returns (StateCheckpointRegistryV2.Checkpoint memory cp)
    {
        (cp.stateRoot, cp.operator, cp.submittedAt, cp.finalized, cp.challenged, cp.challenger) =
            registry.checkpoints(root);
    }
}

/// @dev Functional ERC20 ledger with test-only callback and false-return toggles.
contract CheckpointAdversarialERC20 is ERC20 {
    address private hookTarget;
    bytes private hookData;
    bool private hookArmed;
    bool public hookAttempted;
    bool public hookSucceeded;
    bytes4 public hookReturnSelector;
    bool private failTransferFrom;
    bool private failTransfer;
    address private _transferHookTarget;
    bytes private _transferHookData;
    bool private _transferHookArmed;
    bool private _transferHookAttempted;
    bool private _transferHookSucceeded;
    bytes4 private _transferHookReturnSelector;

    constructor() ERC20("Checkpoint Test Token", "CTT") {}

    function mint(address account, uint256 amount) external {
        _mint(account, amount);
    }

    function approveSelf(address spender, uint256 amount) external {
        _approve(address(this), spender, amount);
    }

    function configureHook(address target, bytes calldata data) external {
        hookTarget = target;
        hookData = data;
        hookArmed = true;
        hookAttempted = false;
        hookSucceeded = false;
        hookReturnSelector = bytes4(0);
    }

    function configureTransferHook(address target, bytes calldata data) external {
        _transferHookTarget = target;
        _transferHookData = data;
        _transferHookArmed = true;
        _transferHookAttempted = false;
        _transferHookSucceeded = false;
        _transferHookReturnSelector = bytes4(0);
    }

    function transferHookAttempted() external view returns (bool) {
        return _transferHookAttempted;
    }

    function transferHookSucceeded() external view returns (bool) {
        return _transferHookSucceeded;
    }

    function transferHookReturnSelector() external view returns (bytes4) {
        return _transferHookReturnSelector;
    }

    function setFailures(bool transferFromFails, bool transferFails) external {
        failTransferFrom = transferFromFails;
        failTransfer = transferFails;
    }

    function transfer(address to, uint256 value) public override returns (bool) {
        if (failTransfer) return false;
        bool moved = super.transfer(to, value);
        if (_transferHookArmed) {
            _transferHookArmed = false;
            _transferHookAttempted = true;
            bytes memory returnData;
            (_transferHookSucceeded, returnData) = _transferHookTarget.call(_transferHookData);
            if (returnData.length >= 4) {
                bytes4 selector;
                assembly {
                    selector := mload(add(returnData, 32))
                }
                _transferHookReturnSelector = selector;
            }
        }
        return moved;
    }

    function transferFrom(address from, address to, uint256 value) public override returns (bool) {
        if (failTransferFrom) return false;
        bool moved = super.transferFrom(from, to, value);
        if (hookArmed) {
            hookArmed = false;
            hookAttempted = true;
            bytes memory returnData;
            (hookSucceeded, returnData) = hookTarget.call(hookData);
            if (returnData.length >= 4) {
                bytes4 selector;
                assembly {
                    selector := mload(add(returnData, 32))
                }
                hookReturnSelector = selector;
            }
        }
        return moved;
    }
}
