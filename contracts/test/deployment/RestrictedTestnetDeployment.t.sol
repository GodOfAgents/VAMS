// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {DeployRestrictedTestnet} from "../../script/DeployRestrictedTestnet.s.sol";
import {DeployTestnet} from "../../script/DeployTestnet.s.sol";
import {AuthorityIdentityValidator} from "../../script/utils/AuthorityIdentityValidator.sol";
import {FreshProviderBondRegistry} from "../../script/utils/FreshProviderBondRegistry.sol";
import {KnownSafeProxyFixture, KnownSafeSingletonFixture} from "../helpers/AuthorityIdentityFixtures.sol";
import {VAMSToken} from "../../src/token/VAMSToken.sol";
import {VAMSRestrictedStaking} from "../../src/staking/VAMSRestrictedStaking.sol";
import {VAMSTimelockController} from "../../src/governance/VAMSTimelockController.sol";
import {ServiceBlockRegistry} from "../../src/registry/ServiceBlockRegistry.sol";
import {ProviderBondRegistry} from "../../src/economic/ProviderBondRegistry.sol";
import {ComposedSettlement} from "../../src/economic/ComposedSettlement.sol";
import {RestrictedTestnetPolicyV1} from "../../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../../src/trust/ActionDeliveryVerifierV1.sol";
import {AutomataSgxActionVerifierV1} from "../../src/trust/AutomataSgxActionVerifierV1.sol";
import {EzklActionVerifierV1} from "../../src/trust/EzklActionVerifierV1.sol";

contract RestrictedInsuranceFixture {}
contract RestrictedCollateralFixture {}

/// @dev Constructor-interface fixture only: it NEVER accepts an attestation.
contract RestrictedDcapFixture {
    address public router;
    uint16 public version = 3;
    constructor(address router_) { router = router_; }
    function quoteVersion() external view returns (uint16) { return version; }
    function pccsRouter() external view returns (address) { return router; }
    function setVersion(uint16 value) external { version = value; }
    function setRouter(address value) external { router = value; }
}

/// @dev No genuine model/circuit: this backend rejects every proof.
contract RestrictedEzklFixture {
    function verifyProof(bytes calldata, uint256[] calldata) external pure returns (bool) { return false; }
}

contract RestrictedTestnetDeploymentTest is Test {
    DeployRestrictedTestnet private producer;
    KnownSafeSingletonFixture private singleton;
    KnownSafeProxyFixture private governance;
    KnownSafeProxyFixture private treasury;
    KnownSafeProxyFixture private emergency;
    RestrictedInsuranceFixture private insurance;
    RestrictedCollateralFixture private collateral;
    RestrictedDcapFixture private dcap;
    RestrictedEzklFixture private ezkl;

    function setUp() public {
        vm.chainId(80_002);
        producer = new DeployRestrictedTestnet();
        singleton = new KnownSafeSingletonFixture();
        governance = new KnownSafeProxyFixture(address(singleton), 5, 3, 0x1000);
        treasury = new KnownSafeProxyFixture(address(singleton), 5, 3, 0x2000);
        emergency = new KnownSafeProxyFixture(address(singleton), 3, 2, 0x3000);
        insurance = new RestrictedInsuranceFixture();
        collateral = new RestrictedCollateralFixture();
        dcap = new RestrictedDcapFixture(address(collateral));
        ezkl = new RestrictedEzklFixture();
    }

    function testCreatesElevenDistinctProtocolArtifacts() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        address[11] memory targets = [d.token, d.staking, d.timelock, d.sentinel, d.serviceRegistry,
            d.bondRegistry, d.policy, d.sgx, d.ezkl, d.deliveryVerifier, d.settlement];
        for (uint256 i; i < targets.length; ++i) {
            assertGt(targets[i].code.length, 0);
            for (uint256 j = i + 1; j < targets.length; ++j) assertNotEq(targets[i], targets[j]);
        }
        assertEq(producer.restrictedDeployment().settlement, d.settlement);
    }

    function testActualSettlementAndRegistryDependenciesMatch() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        ComposedSettlement settlement = ComposedSettlement(d.settlement);
        assertEq(address(settlement.vamsToken()), d.token);
        assertEq(address(settlement.bondRegistry()), d.bondRegistry);
        assertEq(address(settlement.serviceBlockRegistry()), d.serviceRegistry);
        assertEq(address(settlement.deliveryVerifier()), d.deliveryVerifier);
        // Owner decision 10: disputes are bound to this settlement and resolved by the timelock.
        assertEq(settlement.disputes().settlement(), d.settlement);
        assertEq(settlement.disputes().resolver(), d.timelock);
        assertEq(address(settlement.disputes().bondToken()), d.token);
        assertEq(settlement.treasury(), address(treasury));
        assertEq(address(ServiceBlockRegistry(d.serviceRegistry).vamsToken()), d.token);
        assertEq(address(ProviderBondRegistry(d.bondRegistry).vamsToken()), d.token);
        assertEq(ProviderBondRegistry(d.bondRegistry).insuranceFund(), address(insurance));
    }

    function testRegistryRolesBelongToTimelockAndExactSettlement() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        ProviderBondRegistry bonds = ProviderBondRegistry(d.bondRegistry);
        assertTrue(bonds.hasRole(bonds.DEFAULT_ADMIN_ROLE(), d.timelock));
        assertTrue(bonds.hasRole(bonds.ADMIN_ROLE(), d.timelock));
        assertTrue(bonds.hasRole(bonds.PAUSER_ROLE(), d.timelock));
        assertTrue(bonds.hasRole(bonds.ESCROW_ROLE(), d.settlement));
        assertFalse(bonds.hasRole(bonds.ESCROW_ROLE(), address(producer)));
        assertFalse(bonds.hasRole(bonds.DEFAULT_ADMIN_ROLE(), address(producer)));
        assertFalse(bonds.hasRole(bonds.ADMIN_ROLE(), address(producer)));
        assertFalse(bonds.hasRole(bonds.PAUSER_ROLE(), address(producer)));
        assertFalse(bonds.hasRole(bonds.SLASHER_ROLE(), d.timelock));
        assertFalse(bonds.hasRole(bonds.SLASHER_ROLE(), address(producer)));
        assertFalse(bonds.hasRole(bonds.HARDWARE_COMMITMENT_ROLE(), d.timelock));
        assertFalse(bonds.hasRole(bonds.SENTINEL_ROLE(), d.sentinel));
    }

    function testServiceAndSettlementDeployerRolesAreRemoved() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        ServiceBlockRegistry services = ServiceBlockRegistry(d.serviceRegistry);
        ComposedSettlement settlement = ComposedSettlement(d.settlement);
        assertTrue(services.hasRole(services.DEFAULT_ADMIN_ROLE(), d.timelock));
        assertTrue(services.hasRole(services.VERIFIER_ROLE(), d.timelock));
        assertFalse(services.hasRole(services.DEFAULT_ADMIN_ROLE(), address(producer)));
        assertFalse(services.hasRole(services.VERIFIER_ROLE(), address(producer)));
        assertTrue(settlement.hasRole(settlement.ADMIN_ROLE(), d.timelock));
        assertFalse(settlement.hasRole(settlement.ADMIN_ROLE(), address(producer)));
        assertFalse(settlement.hasRole(settlement.PAUSER_ROLE(), address(producer)));
        assertFalse(settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), address(producer)));
    }

    function testProofRouterPinsActualAdapterAndPolicyInstances() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        ActionDeliveryVerifierV1 delivery = ActionDeliveryVerifierV1(d.deliveryVerifier);
        assertEq(address(delivery.policy()), d.policy);
        assertEq(delivery.policyCodeHash(), d.policy.codehash);
        assertEq(address(delivery.sgx()), d.sgx);
        assertEq(delivery.sgxCodeHash(), d.sgx.codehash);
        assertEq(address(delivery.ezkl()), d.ezkl);
        assertEq(delivery.ezklCodeHash(), d.ezkl.codehash);
        assertEq(address(AutomataSgxActionVerifierV1(d.sgx).verifier()), address(dcap));
        assertEq(AutomataSgxActionVerifierV1(d.sgx).collateralRouter(), address(collateral));
        assertEq(address(EzklActionVerifierV1(d.ezkl).verifier()), address(ezkl));
        assertEq(EzklActionVerifierV1(d.ezkl).modelHash(), bytes32(uint256(5)));
    }

    function testPolicyStartsWithNoProtectedEffectAuthority() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        RestrictedTestnetPolicyV1 policy = RestrictedTestnetPolicyV1(d.policy);
        assertEq(policy.governance(), d.timelock);
        assertEq(policy.policyRoot(), bytes32(0));
        assertEq(policy.policyVersion(), 0);
        assertEq(policy.authorityEpoch(), 0);
        assertEq(policy.capabilityMask(), 0);
        address[] memory providers = new address[](1); providers[0] = address(0x1234);
        bytes32[] memory workloads = new bytes32[](1); workloads[0] = bytes32(uint256(123));
        assertFalse(ActionDeliveryVerifierV1(d.deliveryVerifier).authorizeEscrow(address(this), providers, workloads, 1, 60));
        vm.expectRevert("Governance only");
        policy.configure(bytes32(uint256(1)), 1, 1, 4, 1, 60);
    }

    function testRestrictedRewardsAndSupplyRemainUnchanged() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        VAMSToken token = VAMSToken(d.token);
        VAMSRestrictedStaking staking = VAMSRestrictedStaking(d.staking);
        assertEq(token.totalSupply(), 1_000_000_000e18);
        assertEq(token.balanceOf(address(treasury)), token.MAX_SUPPLY());
        assertEq(address(staking.stakingToken()), d.token);
        assertEq(address(staking.rewardToken()), d.token);
        assertEq(staking.rewardPerSecond(), 0);
        assertEq(staking.annualEmissionBudget(), 0);
        assertFalse(staking.rewardsEnabled());
        assertFalse(token.hasRole(token.MINTER_ROLE(), d.staking));
        assertFalse(token.hasRole(token.MINTER_ROLE(), address(producer)));
        vm.prank(d.timelock);
        vm.expectRevert();
        staking.updateEmissionRate(1);
    }

    function testTimelockHasOnlyGovernanceProposerAndFortyEightHourDelay() public {
        DeployRestrictedTestnet.Deployment memory d = _rehearse();
        VAMSTimelockController timelock = VAMSTimelockController(payable(d.timelock));
        assertEq(timelock.getMinDelay(), 48 hours);
        assertTrue(timelock.hasRole(timelock.PROPOSER_ROLE(), address(governance)));
        assertTrue(timelock.hasRole(timelock.CANCELLER_ROLE(), address(governance)));
        assertTrue(timelock.hasRole(timelock.EXECUTOR_ROLE(), address(0)));
        assertFalse(timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), address(producer)));
        assertFalse(timelock.hasRole(timelock.PROPOSER_ROLE(), d.staking));
        assertFalse(timelock.hasRole(timelock.PROPOSER_ROLE(), d.settlement));
        assertFalse(timelock.hasRole(timelock.PROPOSER_ROLE(), address(producer)));
    }

    function testFreshRegistryIsAlreadyInitializedAndBootstrapHasNoRole() public {
        VAMSToken token = new VAMSToken(address(this), address(treasury));
        FreshProviderBondRegistry bootstrap = new FreshProviderBondRegistry(address(this), address(token), address(insurance));
        ProviderBondRegistry bonds = bootstrap.registry();
        assertTrue(bonds.hasRole(bonds.DEFAULT_ADMIN_ROLE(), address(this)));
        assertFalse(bonds.hasRole(bonds.DEFAULT_ADMIN_ROLE(), address(bootstrap)));
        vm.prank(address(0xBAD));
        vm.expectRevert();
        bonds.initialize(address(0xBAD), address(token), address(insurance));
        assertFalse(bonds.hasRole(bonds.DEFAULT_ADMIN_ROLE(), address(0xBAD)));
    }

    function testTypedConfigurationRequiredBeforeDefaultEntryPoints() public {
        vm.expectRevert(DeployRestrictedTestnet.ExplicitRestrictedConfigurationRequired.selector);
        producer.run();
        vm.expectRevert(DeployRestrictedTestnet.ExplicitRestrictedConfigurationRequired.selector);
        producer.rehearse(address(governance), address(treasury), address(emergency), _identity());
    }

    function testWrongChainRejectsBeforeCreation() public {
        vm.chainId(137);
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert(abi.encodeWithSelector(DeployTestnet.InvalidChain.selector, uint256(137), uint256(80_002)));
        producer.rehearseRestricted(address(governance), address(treasury), address(emergency), _identity(), _configuration());
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function testBadInsuranceCodeHashRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.insuranceRecipientCodeHash = bytes32(uint256(1));
        _assertConfigurationRejects(c);
    }

    function testCodelessInsuranceRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.insuranceRecipient = address(0x1234);
        _assertConfigurationRejects(c);
    }

    function testWrongDcapRuntimeRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        vm.etch(address(dcap), hex"00");
        _assertConfigurationRejects(c);
    }

    function testWrongCollateralRuntimeRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.sgx.collateralRouterCodeHash = bytes32(uint256(1));
        _assertConfigurationRejects(c);
    }

    function testWrongEzklRuntimeRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.ezkl.backendCodeHash = bytes32(uint256(1));
        _assertConfigurationRejects(c);
    }

    function testMissingModelRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.ezkl.modelHash = 0;
        _assertConfigurationRejects(c);
    }

    function testMissingDomainRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.hostDomain = 0;
        _assertConfigurationRejects(c);
    }

    function testMissingTcbEvaluationRejectsBeforeCreation() public {
        DeployRestrictedTestnet.ServiceConfiguration memory c = _configuration();
        c.sgx.tcbEvaluation = 0;
        _assertConfigurationRejects(c);
    }

    function testUnsupportedDcapVersionRejectsRehearsalAtomically() public {
        dcap.setVersion(4);
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert("Unsupported DCAP backend");
        producer.rehearseRestricted(address(governance), address(treasury), address(emergency), _identity(), _configuration());
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function testPreflightRejectsUnsupportedDcapVersionBeforeAnyCreation() public {
        dcap.setVersion(4);
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert("Unsupported DCAP backend");
        producer.validateServiceConfiguration(_configuration());
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function testPreflightRejectsWrongDcapRouterBeforeAnyCreation() public {
        dcap.setRouter(address(insurance));
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert("Unsupported DCAP backend");
        producer.validateServiceConfiguration(_configuration());
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function testWrongDcapRouterRejectsRehearsalAtomically() public {
        dcap.setRouter(address(insurance));
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert("Unsupported DCAP backend");
        producer.rehearseRestricted(address(governance), address(treasury), address(emergency), _identity(), _configuration());
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function testInvalidAuthorityRejectsBeforeCreation() public {
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert();
        producer.rehearseRestricted(address(governance), address(treasury), address(governance), _identity(), _configuration());
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function _assertConfigurationRejects(DeployRestrictedTestnet.ServiceConfiguration memory c) private {
        uint256 beforeNonce = vm.getNonce(address(producer));
        vm.expectRevert();
        producer.rehearseRestricted(address(governance), address(treasury), address(emergency), _identity(), c);
        assertEq(vm.getNonce(address(producer)), beforeNonce);
    }

    function _rehearse() private returns (DeployRestrictedTestnet.Deployment memory) {
        return producer.rehearseRestricted(address(governance), address(treasury), address(emergency), _identity(), _configuration());
    }

    function _identity() private view returns (AuthorityIdentityValidator.SafeIdentity memory) {
        return AuthorityIdentityValidator.SafeIdentity({proxyRuntimeCodeHash: address(governance).codehash,
            singleton: address(singleton), singletonRuntimeCodeHash: address(singleton).codehash});
    }

    function _configuration() private view returns (DeployRestrictedTestnet.ServiceConfiguration memory) {
        return DeployRestrictedTestnet.ServiceConfiguration({hostDomain: bytes32(uint256(1)), budgetUnit: bytes32(uint256(2)),
            insuranceRecipient: address(insurance), insuranceRecipientCodeHash: address(insurance).codehash,
            sgx: DeployRestrictedTestnet.SgxConfiguration({backend: address(dcap), backendCodeHash: address(dcap).codehash,
                collateralRouter: address(collateral), collateralRouterCodeHash: address(collateral).codehash,
                enclaveMeasurement: bytes32(uint256(3)), signerMeasurement: bytes32(uint256(4)),
                runtimeId: bytes32(uint256(7)), minimumSvn: 1, tcbEvaluation: 1}),
            ezkl: DeployRestrictedTestnet.EzklConfiguration({backend: address(ezkl), backendCodeHash: address(ezkl).codehash,
                modelHash: bytes32(uint256(5)), circuitManifestHash: bytes32(uint256(6))})});
    }
}
