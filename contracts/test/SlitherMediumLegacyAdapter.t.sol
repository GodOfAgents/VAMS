// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {VAMSERC8004Adapter} from "../src/infrastructure/VAMSERC8004Adapter.sol";
import {IERC8004Verifier} from "../src/infrastructure/interfaces/IERC8004Verifier.sol";

/// @dev Synthetic ABI fixtures only. A true flag is not authentic TEE evidence.
contract MediumAdapterRegistryFixture {
    address internal immutable root;
    bool internal immutable unavailable;
    constructor(address owner_, bool fail_) { root = owner_; unavailable = fail_; }
    function getAgent(bytes32) external view returns (address, bytes32, uint256, uint8, uint256, uint256, bytes32) {
        require(!unavailable, "registry unavailable");
        return (root, bytes32(0), 0, 0, 0, 0, bytes32(0));
    }
}

contract MediumAdapterVerifierFixture is IERC8004Verifier {
    bytes internal reportData;
    bool internal immutable unavailable;
    constructor(bytes memory data_, bool fail_) { reportData = data_; unavailable = fail_; }
    function verifyAttestation(bytes calldata) external view returns (bool, EnclaveReport memory) {
        require(!unavailable, "verifier unavailable");
        return (true, EnclaveReport(bytes32(uint256(77)), bytes32(uint256(88)), reportData, 1));
    }
}

contract SlitherMediumLegacyAdapterTest is Test {
    bytes32 internal constant AGENT = bytes32(uint256(1));
    bytes4 internal constant DISABLED = bytes4(keccak256("LegacyAttestationDisabled()"));

    function test_verifierApprovedQuoteForAnotherRootCannotAcquireAgentTrust() public {
        VAMSERC8004Adapter adapter = _adapter(abi.encode(address(0xBAD)), false, false);
        vm.expectRevert(DISABLED);
        adapter.verifyAndRegister(AGENT, hex"010203");
        assertEq(adapter.verifiedEnclaves(AGENT), bytes32(0));
    }

    function testFuzz_neitherEmptyNorCallerBoundUnqualifiedReportCanAcquireTrust(bool empty) public {
        VAMSERC8004Adapter adapter = _adapter(empty ? bytes("") : abi.encode(address(this)), false, false);
        vm.expectRevert(DISABLED);
        adapter.verifyAndRegister(AGENT, hex"01");
        assertEq(adapter.verifiedEnclaves(AGENT), bytes32(0));
    }

    function test_disabledRouteDoesNotCallRegistryOrVerifier() public {
        VAMSERC8004Adapter adapter = _adapter(abi.encode(address(this)), true, true);
        vm.expectRevert(DISABLED);
        adapter.verifyAndRegister(AGENT, hex"00");
        assertEq(adapter.verifiedEnclaves(AGENT), bytes32(0));
    }

    function test_adminVerifierReplacementCannotReactivateLegacyAcceptance() public {
        VAMSERC8004Adapter adapter = _adapter(abi.encode(address(this)), false, false);
        MediumAdapterVerifierFixture replacement = new MediumAdapterVerifierFixture(abi.encode(address(this)), false);
        adapter.setVerifier(address(replacement));
        assertEq(address(adapter.verifier()), address(replacement));
        vm.expectRevert(DISABLED);
        adapter.verifyAndRegister(AGENT, hex"01");
        assertEq(adapter.verifiedEnclaves(AGENT), bytes32(0));
    }

    function _adapter(bytes memory data_, bool registryFails, bool verifierFails)
        internal returns (VAMSERC8004Adapter)
    {
        return new VAMSERC8004Adapter(
            address(new MediumAdapterRegistryFixture(address(this), registryFails)),
            address(new MediumAdapterVerifierFixture(data_, verifierFails))
        );
    }
}
