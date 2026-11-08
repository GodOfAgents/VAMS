// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {console} from "forge-std/Script.sol";
import {DeployTestnet} from "./DeployTestnet.s.sol";
import {FreshProviderBondRegistry} from "./utils/FreshProviderBondRegistry.sol";
import {ServiceBlockRegistry} from "../src/registry/ServiceBlockRegistry.sol";
import {ProviderBondRegistry} from "../src/economic/ProviderBondRegistry.sol";
import {ComposedSettlement} from "../src/economic/ComposedSettlement.sol";
import {RestrictedTestnetPolicyV1} from "../src/trust/RestrictedTestnetPolicyV1.sol";
import {ActionDeliveryVerifierV1} from "../src/trust/ActionDeliveryVerifierV1.sol";
import {AutomataSgxActionVerifierV1, IAutomataQuoteVerifierV1} from "../src/trust/AutomataSgxActionVerifierV1.sol";
import {EzklActionVerifierV1} from "../src/trust/EzklActionVerifierV1.sol";

/// @notice Explicit-input restricted Amoy producer; policy starts without authority.
/// @dev Code pins are identity checks, never backend/model/custody qualification.
///      Rehearsal is local VM behavior. Broadcasting needs a separate reviewed ceremony.
contract DeployRestrictedTestnet is DeployTestnet {
    struct SgxConfiguration {
        address backend;
        bytes32 backendCodeHash;
        address collateralRouter;
        bytes32 collateralRouterCodeHash;
        bytes32 enclaveMeasurement;
        bytes32 signerMeasurement;
        bytes32 runtimeId;
        uint16 minimumSvn;
        uint32 tcbEvaluation;
    }

    struct EzklConfiguration {
        address backend;
        bytes32 backendCodeHash;
        bytes32 modelHash;
        bytes32 circuitManifestHash;
    }

    struct ServiceConfiguration {
        bytes32 hostDomain;
        bytes32 budgetUnit;
        address insuranceRecipient;
        bytes32 insuranceRecipientCodeHash;
        SgxConfiguration sgx;
        EzklConfiguration ezkl;
    }

    struct Deployment {
        address token;
        address staking;
        address timelock;
        address sentinel;
        address serviceRegistry;
        address bondRegistry;
        address policy;
        address sgx;
        address ezkl;
        address deliveryVerifier;
        address settlement;
    }

    error ExplicitRestrictedConfigurationRequired();
    error DependencyIdentityMismatch(address dependency, bytes32 expected, bytes32 actual);
    error MissingServiceIdentity();

    ServiceBlockRegistry private serviceRegistry;
    ProviderBondRegistry private bondRegistry;
    RestrictedTestnetPolicyV1 private policy;
    AutomataSgxActionVerifierV1 private sgx;
    EzklActionVerifierV1 private ezkl;
    ActionDeliveryVerifierV1 private delivery;
    ComposedSettlement private settlement;
    FreshProviderBondRegistry private bootstrap;
    Deployment private lastDeployment;

    /// @dev Do not silently run a core-only deployment from this script target.
    function run() external pure override {
        revert ExplicitRestrictedConfigurationRequired();
    }

    /// @dev The inherited core-only rehearsal is also ineligible at this target.
    function rehearse(address, address, address, SafeIdentity calldata) external pure override {
        revert ExplicitRestrictedConfigurationRequired();
    }

    function validateServiceConfiguration(ServiceConfiguration calldata configuration) external view {
        _requireAmoy();
        _validateServiceConfiguration(configuration);
    }

    function runRestricted(ServiceConfiguration calldata configuration) external returns (Deployment memory) {
        _requireAmoy();
        _validateServiceConfiguration(configuration);
        governanceSafe = vm.envAddress("VAMS_GOVERNANCE_SAFE");
        treasurySafe = vm.envAddress("VAMS_TREASURY_SAFE");
        emergencyCouncil = vm.envAddress("VAMS_EMERGENCY_COUNCIL");
        SafeIdentity memory identity = SafeIdentity({
            proxyRuntimeCodeHash: vm.envBytes32("VAMS_SAFE_PROXY_RUNTIME_CODE_HASH"),
            singleton: vm.envAddress("VAMS_SAFE_SINGLETON"),
            singletonRuntimeCodeHash: vm.envBytes32("VAMS_SAFE_SINGLETON_RUNTIME_CODE_HASH")
        });
        _validateAuthorityIdentities(governanceSafe, treasurySafe, emergencyCouncil, identity);
        // Read signing material only after public configuration/authority preflight.
        deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        deployer = vm.addr(deployerPrivateKey);
        vm.startBroadcast(deployerPrivateKey);
        _deployRestricted(configuration);
        vm.stopBroadcast();
        deployerPrivateKey = 0;
        _verifyRestricted(identity, configuration);
        _logDeployment(identity);
        _logServices();
        return lastDeployment;
    }

    /// @notice Same creation/handoff/postconditions in the local VM, without key access.
    function rehearseRestricted(address governanceAuthority, address treasuryAuthority,
        address emergencyAuthority, SafeIdentity calldata identity, ServiceConfiguration calldata configuration)
        external returns (Deployment memory) {
        _requireAmoy();
        _validateServiceConfiguration(configuration);
        _validateAuthorityIdentities(governanceAuthority, treasuryAuthority, emergencyAuthority, identity);
        deployer = address(this);
        governanceSafe = governanceAuthority;
        treasurySafe = treasuryAuthority;
        emergencyCouncil = emergencyAuthority;
        _deployRestricted(configuration);
        _verifyRestricted(identity, configuration);
        return lastDeployment;
    }

    function restrictedDeployment() external view returns (Deployment memory) {
        return lastDeployment;
    }

    function _deployRestricted(ServiceConfiguration memory configuration) private {
        _deployContracts();
        serviceRegistry = new ServiceBlockRegistry(address(timelock), address(token));
        bootstrap = new FreshProviderBondRegistry(deployer, address(token), configuration.insuranceRecipient);
        bondRegistry = bootstrap.registry();
        policy = new RestrictedTestnetPolicyV1(address(timelock), configuration.hostDomain, configuration.budgetUnit);
        _deployVerifiers(configuration);
        settlement = new ComposedSettlement(address(timelock), address(token), address(bondRegistry),
            treasurySafe, address(serviceRegistry), address(delivery));
        _handoffRegistry();
        _configureRoles();
        Deployment memory result;
        result.token = address(token); result.staking = address(staking);
        result.timelock = address(timelock); result.sentinel = address(sentinel);
        result.serviceRegistry = address(serviceRegistry); result.bondRegistry = address(bondRegistry);
        result.policy = address(policy); result.sgx = address(sgx); result.ezkl = address(ezkl);
        result.deliveryVerifier = address(delivery); result.settlement = address(settlement);
        lastDeployment = result;
    }

    function _verifyRestricted(SafeIdentity memory identity, ServiceConfiguration memory configuration) private view {
        _verifyPostconditions(identity);
        _verifyServices(configuration);
    }

    function _deployVerifiers(ServiceConfiguration memory configuration) private {
        SgxConfiguration memory s = configuration.sgx;
        sgx = new AutomataSgxActionVerifierV1(s.backend, s.backendCodeHash, s.collateralRouter,
            s.collateralRouterCodeHash, s.enclaveMeasurement, s.signerMeasurement, s.runtimeId,
            s.minimumSvn, s.tcbEvaluation);
        EzklConfiguration memory z = configuration.ezkl;
        ezkl = new EzklActionVerifierV1(z.backend, z.backendCodeHash, z.modelHash, z.circuitManifestHash);
        delivery = new ActionDeliveryVerifierV1(address(policy), address(policy).codehash,
            address(sgx), address(sgx).codehash, address(ezkl), address(ezkl).codehash);
    }

    function _handoffRegistry() private {
        bondRegistry.grantRole(bondRegistry.ESCROW_ROLE(), address(settlement));
        bondRegistry.grantRole(bondRegistry.DEFAULT_ADMIN_ROLE(), address(timelock));
        bondRegistry.grantRole(bondRegistry.ADMIN_ROLE(), address(timelock));
        bondRegistry.grantRole(bondRegistry.PAUSER_ROLE(), address(timelock));
        bondRegistry.revokeRole(bondRegistry.ADMIN_ROLE(), deployer);
        bondRegistry.revokeRole(bondRegistry.PAUSER_ROLE(), deployer);
        bondRegistry.renounceRole(bondRegistry.DEFAULT_ADMIN_ROLE(), deployer);
    }

    function _validateServiceConfiguration(ServiceConfiguration memory configuration) private view {
        if (configuration.hostDomain == 0 || configuration.budgetUnit == 0 ||
            configuration.sgx.enclaveMeasurement == 0 || configuration.sgx.signerMeasurement == 0 ||
            configuration.sgx.runtimeId == 0 || configuration.sgx.tcbEvaluation == 0 ||
            configuration.ezkl.modelHash == 0 || configuration.ezkl.circuitManifestHash == 0) {
            revert MissingServiceIdentity();
        }
        _requireDependency(configuration.insuranceRecipient, configuration.insuranceRecipientCodeHash);
        _requireDependency(configuration.sgx.backend, configuration.sgx.backendCodeHash);
        _requireDependency(configuration.sgx.collateralRouter, configuration.sgx.collateralRouterCodeHash);
        _requireDependency(configuration.ezkl.backend, configuration.ezkl.backendCodeHash);
        // Reject known-incompatible ABI/version/router before broadcast can create
        // even the core contracts. These read-only checks do not qualify a quote.
        IAutomataQuoteVerifierV1 backend = IAutomataQuoteVerifierV1(configuration.sgx.backend);
        require(backend.quoteVersion() == 3 && backend.pccsRouter() == configuration.sgx.collateralRouter,
            "Unsupported DCAP backend");
    }

    function _requireDependency(address dependency, bytes32 expected) private view {
        if (dependency == address(0) || dependency.code.length == 0 || expected == 0 || dependency.codehash != expected) {
            revert DependencyIdentityMismatch(dependency, expected, dependency.codehash);
        }
    }

    function _verifyServices(ServiceConfiguration memory configuration) private view {
        _validateServiceConfiguration(configuration);
        require(address(serviceRegistry.vamsToken()) == address(token), "Service token mismatch");
        require(serviceRegistry.hasRole(serviceRegistry.DEFAULT_ADMIN_ROLE(), address(timelock)), "Service admin missing");
        require(serviceRegistry.hasRole(serviceRegistry.VERIFIER_ROLE(), address(timelock)), "Service verifier missing");
        require(!serviceRegistry.hasRole(serviceRegistry.DEFAULT_ADMIN_ROLE(), deployer) &&
            !serviceRegistry.hasRole(serviceRegistry.VERIFIER_ROLE(), deployer), "Deployer service role");
        require(address(bondRegistry.vamsToken()) == address(token) &&
            bondRegistry.insuranceFund() == configuration.insuranceRecipient, "Bond dependency mismatch");
        require(bondRegistry.hasRole(bondRegistry.DEFAULT_ADMIN_ROLE(), address(timelock)) &&
            bondRegistry.hasRole(bondRegistry.ADMIN_ROLE(), address(timelock)) &&
            bondRegistry.hasRole(bondRegistry.PAUSER_ROLE(), address(timelock)), "Bond governance missing");
        require(bondRegistry.hasRole(bondRegistry.ESCROW_ROLE(), address(settlement)), "Settlement escrow role missing");
        require(!bondRegistry.hasRole(bondRegistry.DEFAULT_ADMIN_ROLE(), deployer) &&
            !bondRegistry.hasRole(bondRegistry.ADMIN_ROLE(), deployer) &&
            !bondRegistry.hasRole(bondRegistry.PAUSER_ROLE(), deployer) &&
            !bondRegistry.hasRole(bondRegistry.DEFAULT_ADMIN_ROLE(), address(bootstrap)), "Bootstrap role retained");
        require(!bondRegistry.hasRole(bondRegistry.SLASHER_ROLE(), deployer) &&
            !bondRegistry.hasRole(bondRegistry.SLASHER_ROLE(), address(timelock)), "Slash activation forbidden");
        require(policy.governance() == address(timelock) && policy.hostDomain() == configuration.hostDomain &&
            policy.budgetUnit() == configuration.budgetUnit, "Policy dependency mismatch");
        require(policy.policyRoot() == 0 && policy.policyVersion() == 0 && policy.authorityEpoch() == 0 &&
            policy.capabilityMask() == 0 && policy.maxActionBudget() == 0 && policy.maxLifetime() == 0,
            "Policy must start inactive");
        require(address(settlement.vamsToken()) == address(token) &&
            address(settlement.bondRegistry()) == address(bondRegistry) && settlement.treasury() == treasurySafe &&
            address(settlement.serviceBlockRegistry()) == address(serviceRegistry) &&
            address(settlement.deliveryVerifier()) == address(delivery), "Settlement dependency mismatch");
        require(settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), address(timelock)) &&
            settlement.hasRole(settlement.ADMIN_ROLE(), address(timelock)) &&
            settlement.hasRole(settlement.PAUSER_ROLE(), address(timelock)), "Settlement governance missing");
        require(!settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), deployer) &&
            !settlement.hasRole(settlement.ADMIN_ROLE(), deployer) &&
            !settlement.hasRole(settlement.PAUSER_ROLE(), deployer), "Deployer settlement role");
    }

    function _logServices() private view {
        console.log("Service registry:", address(serviceRegistry));
        console.log("Bond registry:", address(bondRegistry));
        console.log("Restricted policy:", address(policy));
        console.log("SGX adapter:", address(sgx));
        console.log("EZKL adapter:", address(ezkl));
        console.log("Delivery verifier:", address(delivery));
        console.log("Composed settlement:", address(settlement));
        console.log("Policy inactive; backend/custody qualification and governed activation required");
    }
}
