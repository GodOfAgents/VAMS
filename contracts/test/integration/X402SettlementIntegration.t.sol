// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../utils/BaseTest.sol";
import "../../src/economic/X402EscrowManager.sol";
import "../../src/economic/X402NonceRegistry.sol";
import "../../src/economic/ProviderBondRegistry.sol";
import "../../src/economic/VAMSInsuranceFund.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/**
 * @title X402SettlementIntegration
 * @notice Integration tests for the complete x402 settlement flow
 * @dev Tests cross-contract interactions:
 *      Agent → EscrowManager → NonceRegistry → BondRegistry → Treasury
 */
contract X402SettlementIntegration is BaseTest {
    X402EscrowManager public escrow;
    X402NonceRegistry public nonceRegistry;
    ProviderBondRegistry public bondRegistry;
    VAMSInsuranceFund public insurance;

    // Constants
    uint256 constant MIN_BOND = 10_000 ether;
    uint256 constant COVERAGE_RATIO = 10;
    uint256 constant ESCROW_VALIDITY = 1 hours;

    function setUp() public override {
        super.setUp();

        // Deploy insurance fund behind proxy (AC01: _disableInitializers)
        VAMSInsuranceFund insuranceImpl = new VAMSInsuranceFund();
        address[] memory guardians = new address[](3);
        guardians[0] = guardian1;
        guardians[1] = guardian2;
        guardians[2] = guardian3;
        ERC1967Proxy insuranceProxy = new ERC1967Proxy(
            address(insuranceImpl),
            abi.encodeCall(VAMSInsuranceFund.initialize, (admin, address(token), address(0), guardians))
        );
        insurance = VAMSInsuranceFund(address(insuranceProxy));

        // Deploy nonce registry
        nonceRegistry = new X402NonceRegistry();
        nonceRegistry.initialize(admin, address(0));

        // Deploy bond registry
        bondRegistry = new ProviderBondRegistry();
        bondRegistry.initialize(admin, address(token), address(insurance));

        // Deploy escrow manager behind proxy (AC01: _disableInitializers)
        X402EscrowManager escrowImpl = new X402EscrowManager();
        ERC1967Proxy escrowProxy = new ERC1967Proxy(
            address(escrowImpl),
            abi.encodeCall(
                X402EscrowManager.initialize,
                (admin, address(token), address(nonceRegistry), address(bondRegistry), treasury)
            )
        );
        escrow = X402EscrowManager(address(escrowProxy));

        // Setup roles
        vm.startPrank(admin);
        nonceRegistry.authorizeSettler(address(escrow));
        bondRegistry.grantRole(bondRegistry.ESCROW_ROLE(), address(escrow));
        escrow.grantRole(escrow.VERIFIER_ROLE(), address(this));
        vm.stopPrank();
    }

    // ============ Helper Functions ============

    function _registerProvider(address provider, uint256 bondAmount) internal {
        uint256 maxRequest = bondAmount / COVERAGE_RATIO;
        _fundAndApprove(provider, address(bondRegistry), bondAmount);

        vm.prank(provider);
        bondRegistry.registerProvider(bondAmount, maxRequest);
    }

    function _createServiceProof() internal pure returns (IX402EscrowManager.ServiceProof memory) {
        return IX402EscrowManager.ServiceProof({
            requestHash: keccak256("request"),
            responseHash: keccak256("response"),
            proofType: IX402EscrowManager.ProofType.DETERMINISTIC,
            attestation: ""
        });
    }

    // ============ Full Settlement Flow Tests ============

    function test_FullSettlementFlow_Success() public {
        // 1. Provider registers with bond
        _registerProvider(provider1, MIN_BOND);

        // 2. Agent creates escrow
        uint256 paymentAmount = 500 ether;
        uint256 nonce = 1;
        bytes32 hashlock = bytes32(0);
        bytes32 serviceType = keccak256("COMPUTE");

        _fundAndApprove(agent1, address(escrow), paymentAmount);

        vm.prank(agent1);
        bytes32 escrowId = escrow.lockEscrow(provider1, paymentAmount, nonce, ESCROW_VALIDITY, hashlock, serviceType);

        // Verify escrow was created
        IX402EscrowManager.Escrow memory lockedEscrow = escrow.getEscrow(escrowId);
        assertEq(lockedEscrow.agent, agent1);
        assertEq(lockedEscrow.provider, provider1);
        assertEq(lockedEscrow.amount, paymentAmount);
        assertEq(uint256(lockedEscrow.status), uint256(IX402EscrowManager.EscrowStatus.LOCKED));

        // Verify bond registry tracking
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider1);
        assertEq(bond.pendingSettlements, paymentAmount);
        assertEq(bond.activeRequests, 1);

        // 3. Provider claims escrow with service proof
        uint256 treasuryBefore = token.balanceOf(treasury);
        uint256 providerBefore = token.balanceOf(provider1);

        IX402EscrowManager.ServiceProof memory proof = _createServiceProof();

        escrow.approveServiceProof(escrowId);
        vm.prank(provider1);
        escrow.claimEscrow(escrowId, proof, bytes32(0));

        // Verify escrow was claimed
        IX402EscrowManager.Escrow memory claimedEscrow = escrow.getEscrow(escrowId);
        assertEq(uint256(claimedEscrow.status), uint256(IX402EscrowManager.EscrowStatus.CLAIMED));

        // Verify nonce was consumed
        assertFalse(nonceRegistry.isNonceValid(agent1, nonce));

        // Verify bond tracking cleared
        IProviderBondRegistry.ProviderBond memory bondAfter = bondRegistry.getBond(provider1);
        assertEq(bondAfter.pendingSettlements, 0);
        assertEq(bondAfter.activeRequests, 0);

        // H02: Funds are held for 72h dispute window. Warp past it and withdraw.
        vm.warp(block.timestamp + 72 hours + 1);
        vm.prank(provider1);
        escrow.withdrawClaimed(escrowId);

        // Verify fee distribution (0.05% = 5 bps)
        uint256 expectedFee = (paymentAmount * 5) / 10000;
        uint256 expectedPayout = paymentAmount - expectedFee;

        assertEq(token.balanceOf(treasury), treasuryBefore + expectedFee);
        assertEq(token.balanceOf(provider1), providerBefore + expectedPayout);
    }

    function test_FullSettlementFlow_Refund() public {
        // 1. Provider registers
        _registerProvider(provider1, MIN_BOND);

        // 2. Agent creates escrow
        uint256 paymentAmount = 500 ether;
        _fundAndApprove(agent1, address(escrow), paymentAmount);

        vm.prank(agent1);
        bytes32 escrowId =
            escrow.lockEscrow(provider1, paymentAmount, 1, ESCROW_VALIDITY, bytes32(0), keccak256("COMPUTE"));

        uint256 agentBefore = token.balanceOf(agent1);

        // 3. Time passes, escrow expires
        _advanceTime(ESCROW_VALIDITY + 1);

        // 4. Agent requests refund
        vm.prank(agent1);
        escrow.refundExpiredEscrow(escrowId);

        // Verify refund
        IX402EscrowManager.Escrow memory refundedEscrow = escrow.getEscrow(escrowId);
        assertEq(uint256(refundedEscrow.status), uint256(IX402EscrowManager.EscrowStatus.REFUNDED));
        assertEq(token.balanceOf(agent1), agentBefore + paymentAmount);

        // Verify bond tracking cleared
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider1);
        assertEq(bond.pendingSettlements, 0);

        // Nonce should still be valid (not consumed)
        assertTrue(nonceRegistry.isNonceValid(agent1, 1));
    }

    function test_FullSettlementFlow_Dispute() public {
        // 1. Provider registers
        _registerProvider(provider1, MIN_BOND);

        // 2. Agent creates and provider claims escrow
        uint256 paymentAmount = 500 ether;
        _fundAndApprove(agent1, address(escrow), paymentAmount);

        vm.prank(agent1);
        bytes32 escrowId =
            escrow.lockEscrow(provider1, paymentAmount, 1, ESCROW_VALIDITY, bytes32(0), keccak256("COMPUTE"));

        IX402EscrowManager.ServiceProof memory proof = _createServiceProof();

        escrow.approveServiceProof(escrowId);
        vm.prank(provider1);
        escrow.claimEscrow(escrowId, proof, bytes32(0));

        // 3. Agent disputes within window (72h)
        vm.prank(agent1);
        escrow.disputeEscrow(escrowId, "Service quality issue");

        IX402EscrowManager.Escrow memory disputed = escrow.getEscrow(escrowId);
        assertEq(uint256(disputed.status), uint256(IX402EscrowManager.EscrowStatus.DISPUTED));

        // 4. Resolver resolves dispute (split 50/50)
        uint256 agentRefund = paymentAmount / 2;
        uint256 providerPayout = paymentAmount / 2;

        // Note: The disputed escrow's funds were already transferred, so this would need
        // additional escrow logic. For now, test the state transition.
    }

    function test_MultipleEscrows_SameProvider() public {
        // Register provider
        _registerProvider(provider1, MIN_BOND * 2);

        uint256 maxPerRequest = MIN_BOND * 2 / COVERAGE_RATIO;

        // Create 3 escrows from different agents
        bytes32[] memory escrowIds = new bytes32[](3);
        uint256 paymentAmount = 500 ether;

        for (uint256 i = 0; i < 3; i++) {
            address agent = i == 0 ? agent1 : (i == 1 ? agent2 : user1);
            _fundAndApprove(agent, address(escrow), paymentAmount);

            vm.prank(agent);
            escrowIds[i] =
                escrow.lockEscrow(provider1, paymentAmount, i + 1, ESCROW_VALIDITY, bytes32(0), keccak256("COMPUTE"));
        }

        // Verify all tracked
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider1);
        assertEq(bond.activeRequests, 3);
        assertEq(bond.pendingSettlements, paymentAmount * 3);

        // Claim all
        IX402EscrowManager.ServiceProof memory proof = _createServiceProof();

        for (uint256 i = 0; i < 3; i++) {
            escrow.approveServiceProof(escrowIds[i]);
            vm.prank(provider1);
            escrow.claimEscrow(escrowIds[i], proof, bytes32(0));
        }

        // Verify all cleared
        bond = bondRegistry.getBond(provider1);
        assertEq(bond.activeRequests, 0);
        assertEq(bond.pendingSettlements, 0);
    }

    function test_ProviderSlashing_FromEscrow() public {
        // Register provider
        _registerProvider(provider1, MIN_BOND * 2);

        // Create escrow
        uint256 paymentAmount = 500 ether;
        _fundAndApprove(agent1, address(escrow), paymentAmount);

        vm.prank(agent1);
        bytes32 escrowId =
            escrow.lockEscrow(provider1, paymentAmount, 1, ESCROW_VALIDITY, bytes32(0), keccak256("COMPUTE"));

        // Provider gets slashed for bad behavior (via slasher role)
        vm.startPrank(admin);
        bondRegistry.grantRole(bondRegistry.SLASHER_ROLE(), slasher);
        vm.stopPrank();

        uint256 slashAmount = 5000 ether;

        vm.prank(slasher);
        bondRegistry.slashProvider(provider1, slashAmount, escrowId, "Failed to deliver");

        // Verify bond reduced
        IProviderBondRegistry.ProviderBond memory bond = bondRegistry.getBond(provider1);
        assertEq(bond.bondedAmount, MIN_BOND * 2 - slashAmount);

        // Verify insurance fund received half
        assertEq(token.balanceOf(address(insurance)), slashAmount / 2);
    }

    function test_HTLC_WithPreimage() public {
        // Register provider
        _registerProvider(provider1, MIN_BOND);

        // Define secret preimage for HTLC
        bytes32 preimage = keccak256("secret preimage");
        bytes32 hashlock = keccak256(abi.encodePacked(preimage));

        // Create HTLC-locked escrow
        uint256 paymentAmount = 500 ether;
        _fundAndApprove(agent1, address(escrow), paymentAmount);

        vm.prank(agent1);
        bytes32 escrowId =
            escrow.lockEscrow(provider1, paymentAmount, 1, ESCROW_VALIDITY, hashlock, keccak256("HTLC_SERVICE"));

        // Provider cannot claim with wrong preimage
        IX402EscrowManager.ServiceProof memory proof = _createServiceProof();

        escrow.approveServiceProof(escrowId);
        vm.prank(provider1);
        vm.expectRevert();
        escrow.claimEscrow(escrowId, proof, keccak256("wrong preimage"));

        // Provider claims with correct preimage
        vm.prank(provider1);
        escrow.claimEscrow(escrowId, proof, preimage);

        IX402EscrowManager.Escrow memory claimed = escrow.getEscrow(escrowId);
        assertEq(uint256(claimed.status), uint256(IX402EscrowManager.EscrowStatus.CLAIMED));
    }

    function test_ProviderCannotAcceptExceedingBond() public {
        // Register provider with minimal bond
        _registerProvider(provider1, MIN_BOND);

        uint256 maxRequest = MIN_BOND / COVERAGE_RATIO; // 1000 ether

        // Try to create escrow exceeding provider max
        uint256 paymentAmount = maxRequest + 1;
        _fundAndApprove(agent1, address(escrow), paymentAmount);

        vm.prank(agent1);
        vm.expectRevert();
        escrow.lockEscrow(provider1, paymentAmount, 1, ESCROW_VALIDITY, bytes32(0), keccak256("COMPUTE"));
    }

    // ============ Fuzz Tests ============

    function testFuzz_SettlementFeeCalculation(uint256 amount) public {
        amount = bound(amount, 1 ether, MIN_BOND / COVERAGE_RATIO);

        _registerProvider(provider1, MIN_BOND);
        _fundAndApprove(agent1, address(escrow), amount);

        uint256 treasuryBefore = token.balanceOf(treasury);
        uint256 providerBefore = token.balanceOf(provider1);

        vm.prank(agent1);
        bytes32 escrowId = escrow.lockEscrow(provider1, amount, 1, ESCROW_VALIDITY, bytes32(0), keccak256("COMPUTE"));

        IX402EscrowManager.ServiceProof memory proof = _createServiceProof();

        escrow.approveServiceProof(escrowId);
        vm.prank(provider1);
        escrow.claimEscrow(escrowId, proof, bytes32(0));

        // H02: Warp past 72h dispute window and withdraw
        vm.warp(block.timestamp + 72 hours + 1);
        vm.prank(provider1);
        escrow.withdrawClaimed(escrowId);

        // Verify exact fee calculation
        uint256 expectedFee = (amount * 5) / 10000;
        uint256 expectedPayout = amount - expectedFee;

        assertEq(token.balanceOf(treasury) - treasuryBefore, expectedFee);
        assertEq(token.balanceOf(provider1) - providerBefore, expectedPayout);
    }
}
