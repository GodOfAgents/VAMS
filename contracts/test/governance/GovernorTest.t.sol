// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "forge-std/console.sol";
import "../../src/token/VAMSToken.sol";
import "../../src/governance/VAMSGovernor.sol";
import "../../src/governance/VAMSTimelockController.sol";

contract GovernorTest is Test {
    VAMSToken token;
    VAMSGovernor governor;
    VAMSTimelockController timelock;
    address deployer = address(0x1);
    address voter1 = address(0x2);
    address voter2 = address(0x3);

    function setUp() public {
        vm.startPrank(deployer);

        // 1. Deploy Token
        token = new VAMSToken(deployer, deployer);

        // 2. Deploy Timelock
        address[] memory proposers = new address[](0);
        address[] memory executors = new address[](0);
        timelock = new VAMSTimelockController(1 days, proposers, executors, deployer);

        // 3. Deploy Governor
        governor = new VAMSGovernor(IVotes(address(token)), timelock);

        // 4. Setup Roles
        bytes32 PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
        bytes32 EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
        bytes32 CANCELLER_ROLE = keccak256("CANCELLER_ROLE");
        
        timelock.grantRole(PROPOSER_ROLE, address(governor));
        timelock.grantRole(EXECUTOR_ROLE, address(0)); 
        timelock.grantRole(CANCELLER_ROLE, address(governor));

        // Grant Timelock Admin Role on Token so it can execute the proposal
        token.grantRole(token.DEFAULT_ADMIN_ROLE(), address(timelock));

        // 5. Distribute Tokens for Voting
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        token.transfer(voter1, 100_000_000 * 1e18); // 10%
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        token.transfer(voter2, 100_000_000 * 1e18); // 10%

        vm.stopPrank();

        // 6. Delegate Votes (Required for Governor)
        vm.prank(voter1);
        token.delegate(voter1);
        vm.prank(voter2);
        token.delegate(voter2);
        
        vm.roll(block.number + 10); // Advance blocks to checkpoint votes
    }

    function test_ProposalLifecycle() public {
        // 1. Create Proposal
        address[] memory targets = new address[](1);
        targets[0] = address(token);
        uint256[] memory values = new uint256[](1);
        values[0] = 0;
        bytes[] memory calldatas = new bytes[](1);
        // Proposal: Grant a role (dummy action)
        calldatas[0] = abi.encodeWithSignature("grantRole(bytes32,address)", keccak256("MINTER_ROLE"), address(0x4));
        string memory description = "Proposal #1: Grant Minter";

        vm.prank(voter1);
        uint256 proposalId = governor.propose(targets, values, calldatas, description);

        // 2. Advance to Voting Period
        vm.roll(block.number + governor.votingDelay() + 1);

        // 3. Vote
        vm.prank(voter1);
        governor.castVote(proposalId, 1); // For
        vm.prank(voter2);
        governor.castVote(proposalId, 1); // For

        // 4. Advance to End of Voting
        vm.roll(block.number + governor.votingPeriod() + 1);

        // 5. Queue
        bytes32 descriptionHash = keccak256(bytes(description));
        governor.queue(targets, values, calldatas, descriptionHash);

        // 6. Advance Timelock Delay
        vm.warp(block.timestamp + timelock.getMinDelay() + 1);

        // 7. Execute
        governor.execute(targets, values, calldatas, descriptionHash);
        
        // Asset Minter Role granted
        assertTrue(token.hasRole(keccak256("MINTER_ROLE"), address(0x4)));
    }
}

