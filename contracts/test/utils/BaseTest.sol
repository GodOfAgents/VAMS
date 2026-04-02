// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../mocks/MockVAMSToken.sol";
import "./Constants.sol";

/**
 * @title BaseTest
 * @notice Base test contract with shared setup and utilities
 * @dev All test contracts should inherit from this
 */
abstract contract BaseTest is Test {
    // ============ Common Contracts ============
    MockVAMSToken public token;
    
    // ============ Common Addresses ============
    address public admin;
    address public treasury;
    address public user1;
    address public user2;
    address public user3;
    address public provider1;
    address public provider2;
    address public agent1;
    address public agent2;
    address public guardian1;
    address public guardian2;
    address public guardian3;
    address public slasher;
    
    // ============ Setup ============
    
    function setUp() public virtual {
        // Create labeled addresses
        admin = makeAddr("admin");
        treasury = makeAddr("treasury");
        user1 = makeAddr("user1");
        user2 = makeAddr("user2");
        user3 = makeAddr("user3");
        provider1 = makeAddr("provider1");
        provider2 = makeAddr("provider2");
        agent1 = makeAddr("agent1");
        agent2 = makeAddr("agent2");
        guardian1 = makeAddr("guardian1");
        guardian2 = makeAddr("guardian2");
        guardian3 = makeAddr("guardian3");
        slasher = makeAddr("slasher");
        
        // Deploy mock token
        vm.prank(admin);
        token = new MockVAMSToken();
        vm.label(address(token), "VAMSToken");
        
        // Fund common test accounts
        _fundAccount(user1, TestConstants.INITIAL_BALANCE);
        _fundAccount(user2, TestConstants.INITIAL_BALANCE);
        _fundAccount(provider1, TestConstants.INITIAL_BALANCE);
        _fundAccount(provider2, TestConstants.INITIAL_BALANCE);
        _fundAccount(agent1, TestConstants.INITIAL_BALANCE);
        _fundAccount(agent2, TestConstants.INITIAL_BALANCE);
    }
    
    // ============ Token Helpers ============
    
    /**
     * @notice Fund an account with tokens
     * @param account Account to fund
     * @param amount Amount to transfer
     */
    function _fundAccount(address account, uint256 amount) internal {
        vm.prank(admin);
        // forge-lint: disable-next-line(erc20-unchecked-transfer)
        token.transfer(account, amount);
    }
    
    /**
     * @notice Mint tokens to an account
     * @param account Account to mint to
     * @param amount Amount to mint
     */
    function _mintTo(address account, uint256 amount) internal {
        token.mint(account, amount);
    }
    
    /**
     * @notice Approve tokens for spending
     * @param owner Token owner
     * @param spender Approved spender
     * @param amount Amount to approve
     */
    function _approve(address owner, address spender, uint256 amount) internal {
        vm.prank(owner);
        token.approve(spender, amount);
    }
    
    /**
     * @notice Fund and approve in one call
     * @param account Account to setup
     * @param spender Address to approve
     * @param amount Amount to fund and approve
     */
    function _fundAndApprove(address account, address spender, uint256 amount) internal {
        _mintTo(account, amount);
        _approve(account, spender, amount);
    }
    
    // ============ Time Helpers ============
    
    /**
     * @notice Advance block timestamp
     * @param seconds_ Seconds to advance
     */
    function _advanceTime(uint256 seconds_) internal {
        vm.warp(block.timestamp + seconds_);
    }
    
    /**
     * @notice Advance to specific timestamp
     * @param timestamp Target timestamp
     */
    function _warpTo(uint256 timestamp) internal {
        vm.warp(timestamp);
    }
    
    /**
     * @notice Advance blocks
     * @param blocks Number of blocks to advance
     */
    function _advanceBlocks(uint256 blocks) internal {
        vm.roll(block.number + blocks);
    }
    
    // ============ Signature Helpers ============
    
    /**
     * @notice Create a test private key
     * @param seed Seed for key generation
     * @return Private key
     */
    function _makePrivateKey(string memory seed) internal pure returns (uint256) {
        return uint256(keccak256(abi.encodePacked(seed)));
    }
    
    /**
     * @notice Sign a message hash
     * @param privateKey Signer's private key
     * @param messageHash Hash to sign
     * @return Signature bytes
     */
    function _sign(uint256 privateKey, bytes32 messageHash) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, messageHash);
        return abi.encodePacked(r, s, v);
    }
    
    // ============ Hash Helpers ============
    
    /**
     * @notice Compute Ethereum signed message hash
     * @param messageHash Original hash
     * @return Prefixed hash
     */
    function _toEthSignedMessageHash(bytes32 messageHash) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", messageHash));
    }
    
    // ============ Array Helpers ============
    
    /**
     * @notice Create single-element address array
     * @param addr Address to wrap
     * @return Array with single element
     */
    function _toArray(address addr) internal pure returns (address[] memory) {
        address[] memory arr = new address[](1);
        arr[0] = addr;
        return arr;
    }
    
    /**
     * @notice Create two-element address array
     */
    function _toArray(address addr1, address addr2) internal pure returns (address[] memory) {
        address[] memory arr = new address[](2);
        arr[0] = addr1;
        arr[1] = addr2;
        return arr;
    }
    
    /**
     * @notice Create three-element address array
     */
    function _toArray(address addr1, address addr2, address addr3) internal pure returns (address[] memory) {
        address[] memory arr = new address[](3);
        arr[0] = addr1;
        arr[1] = addr2;
        arr[2] = addr3;
        return arr;
    }
    
    // ============ Merkle Helpers ============
    
    /**
     * @notice Compute leaf hash for Merkle tree
     * @param data Data to hash
     * @return Leaf hash
     */
    function _computeLeaf(bytes memory data) internal pure returns (bytes32) {
        return keccak256(data);
    }
    
    /**
     * @notice Compute parent hash in Merkle tree
     * @param left Left child hash
     * @param right Right child hash
     * @return Parent hash
     */
    function _hashPair(bytes32 left, bytes32 right) internal pure returns (bytes32) {
        if (left < right) {
            return keccak256(abi.encodePacked(left, right));
        } else {
            return keccak256(abi.encodePacked(right, left));
        }
    }
    
    // ============ Assertion Helpers ============
    
    /**
     * @notice Assert balance changed by exact amount
     * @param account Account to check
     * @param expectedChange Expected balance change (can be negative)
     * @param action Action to execute
     */
    function _assertBalanceChange(
        address account,
        int256 expectedChange,
        function() internal action
    ) internal {
        uint256 balanceBefore = token.balanceOf(account);
        action();
        uint256 balanceAfter = token.balanceOf(account);
        
        if (expectedChange >= 0) {
            // forge-lint: disable-next-line(unsafe-typecast)
            assertEq(balanceAfter, balanceBefore + uint256(expectedChange), "Balance did not increase as expected");
        } else {
            // forge-lint: disable-next-line(unsafe-typecast)
            assertEq(balanceAfter, balanceBefore - uint256(-expectedChange), "Balance did not decrease as expected");
        }
    }
    
    // ============ Bound Helpers ============
    
    /**
     * @notice Bound amount to valid range for token operations
     * @param amount Raw fuzz input
     * @return Bounded amount (1 wei to 100M tokens)
     */
    function _boundAmount(uint256 amount) internal pure returns (uint256) {
        return bound(amount, 1, 100_000_000 ether);
    }
    
    /**
     * @notice Bound time to valid range
     * @param time Raw fuzz input
     * @return Bounded time (1 second to 10 years)
     */
    function _boundTime(uint256 time) internal pure returns (uint256) {
        return bound(time, 1, 3650 days);
    }
    
    /**
     * @notice Bound basis points to valid range
     * @param bps Raw fuzz input
     * @return Bounded bps (0 to 10000)
     */
    function _boundBps(uint256 bps) internal pure returns (uint256) {
        return bound(bps, 0, 10000);
    }
}

