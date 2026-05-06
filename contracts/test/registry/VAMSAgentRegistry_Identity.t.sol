// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../../src/registry/VAMSAgentRegistry.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockVAMS is ERC20 {
    constructor() ERC20("VAMS", "VAMS") {}
    
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract VAMSAgentRegistryIdentityTest is Test {
    VAMSAgentRegistry public registry;
    MockVAMS public vamsToken;
    
    address public admin = address(1);
    address public slasher = address(2);
    address public owner = address(3);
    address public authorizedWallet = address(4);
    address public unauthorizedWallet = address(5);
    
    bytes32 public agentId;
    bytes32 public constant PUBLIC_KEY_HASH = keccak256("pubkey");
    
    function setUp() public {
        vamsToken = new MockVAMS();
        registry = new VAMSAgentRegistry();
        
        registry.initialize(admin, address(vamsToken), slasher);
        
        vm.startPrank(admin);
        registry.grantRole(registry.VERIFIER_ROLE(), admin);
        vm.stopPrank();
        
        // Mint tokens to owner
        vamsToken.mint(owner, 10000 ether);
        
        vm.startPrank(owner);
        vamsToken.approve(address(registry), type(uint256).max);
        
        agentId = registry.registerAgent(
            PUBLIC_KEY_HASH,
            registry.MIN_REGISTRATION_STAKE(),
            "ipfs://metadata",
            address(0)
        );
        vm.stopPrank();
    }
    
    function test_setAuthorizedWallet() public {
        vm.prank(owner);
        registry.setAuthorizedWallet(agentId, authorizedWallet);
        
        assertTrue(registry.isAuthorizedCaller(agentId, owner));
        assertTrue(registry.isAuthorizedCaller(agentId, authorizedWallet));
        assertFalse(registry.isAuthorizedCaller(agentId, unauthorizedWallet));
    }
    
    function test_setAuthorizedWallet_revertIfNotOwner() public {
        vm.prank(authorizedWallet);
        vm.expectRevert(VAMSAgentRegistry.NotAuthorizedCaller.selector);
        registry.setAuthorizedWallet(agentId, authorizedWallet);
    }
    
    function test_submitMerkleRoot_withAuthorizedWallet() public {
        vm.prank(owner);
        registry.setAuthorizedWallet(agentId, authorizedWallet);
        
        bytes32 merkleRoot = keccak256("merkle_root");
        
        vm.prank(authorizedWallet);
        registry.submitMerkleRoot(agentId, merkleRoot);
        
        (,,,,,,bytes32 storedRoot) = registry.getAgent(agentId);
        assertEq(storedRoot, merkleRoot);
    }
    
    function test_submitMerkleRoot_revertIfUnauthorized() public {
        vm.prank(owner);
        registry.setAuthorizedWallet(agentId, authorizedWallet);
        
        bytes32 merkleRoot = keccak256("merkle_root");
        
        vm.prank(unauthorizedWallet);
        vm.expectRevert(VAMSAgentRegistry.NotAuthorizedCaller.selector);
        registry.submitMerkleRoot(agentId, merkleRoot);
    }
    
    function test_updateTEEAttestation_withAuthorizedWallet() public {
        vm.prank(owner);
        registry.setAuthorizedWallet(agentId, authorizedWallet);
        
        bytes32 attestation = keccak256("attestation");
        
        vm.prank(authorizedWallet);
        registry.updateTEEAttestation(agentId, attestation);
        
        // We don't have a direct getter for teeAttestation in getAgent, 
        // so we'll just ensure the transaction doesn't revert.
    }
    
    function test_deregisterAgent_revertWithAuthorizedWallet() public {
        vm.prank(owner);
        registry.setAuthorizedWallet(agentId, authorizedWallet);
        
        vm.prank(authorizedWallet);
        vm.expectRevert(VAMSAgentRegistry.NotAuthorizedCaller.selector);
        registry.deregisterAgent(agentId);
    }
}
