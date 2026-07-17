// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/token/VAMSToken.sol";
import "../src/vesting/VAMSVesting.sol";
import "../src/staking/VAMSStaking.sol";
import "../src/vesting/IVAMSVesting.sol";
import "../src/governance/VAMSGovernor.sol";
import "../src/governance/VAMSTimelockController.sol";
import "../src/economic/VAMSFeeCollector.sol";
import "../src/economic/VAMSInsuranceFund.sol";
import "../src/economic/VAMSPaymentHandler.sol";
import "../src/routing/VAMSRouter.sol";
import "../src/registry/VAMSAgentRegistry.sol";
import "../src/slashing/VAMSSlasher.sol";
import "../src/sentinel/VAMSSentinel.sol";

contract DeployV2 is Script {
    /// @dev Legacy integration script. It intentionally fails closed unless a
    ///      maintainer explicitly acknowledges that it is not the approved
    ///      public-testnet deployment ceremony.
    string internal constant LEGACY_DEPLOY_ACK = "VAMS_ALLOW_UNSAFE_LEGACY_DEPLOYMENT";

    // State variables to avoid stack-too-deep
    VAMSTimelockController public timelock;
    VAMSToken public token;
    VAMSVesting public vesting;
    VAMSStaking public staking;
    VAMSGovernor public governor;
    VAMSInsuranceFund public insurance;
    VAMSSlasher public slasher;
    VAMSAgentRegistry public registry;
    VAMSFeeCollector public feeCollector;
    VAMSPaymentHandler public paymentHandler;
    VAMSRouter public router;

    function run() external {
        bool legacyDeployAcknowledged = vm.envOr(LEGACY_DEPLOY_ACK, false);
        require(legacyDeployAcknowledged, "DeployV2 blocked: use audited Safe/timelock testnet ceremony");

        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        // =========================================================================
        // 1. Governance Infrastructure (Timelock needs to be deployed early for Treasury)
        // =========================================================================

        // Timelock Controller (hard minimum 48 hours)
        address[] memory proposers = new address[](0);
        address[] memory executors = new address[](0);
        timelock = new VAMSTimelockController(
            2 days,
            proposers,
            executors,
            deployer // Admin (will renounce later if fully decentralized, keeping for now)
        );
        console.log("VAMSTimelockController deployed to:", address(timelock));

        // =========================================================================
        // 2. Token & Vesting
        // =========================================================================

        // VAMS Token
        // Constructor mints 1B tokens to deployer (acting as temporary holder before distribution)
        token = new VAMSToken(deployer, deployer);
        console.log("VAMSToken deployed to:", address(token));

        // VAMS Vesting
        vesting = new VAMSVesting(address(token), deployer);
        console.log("VAMSVesting deployed to:", address(vesting));

        // =========================================================================
        // 3. Core Staking (Inflationary)
        // =========================================================================

        // Initial Emission Rate: 25M / year
        // 25,000,000 * 1e18 / 31,536,000 seconds
        uint256 emissionsY1 = 25_000_000 * 1e18;
        uint256 ratePerSecond = emissionsY1 / 31_536_000;

        staking = new VAMSStaking(address(token), address(token), ratePerSecond, deployer);
        console.log("VAMSStaking deployed to:", address(staking));

        // Grant Staking Contract MINTER_ROLE
        bytes32 MINTER_ROLE = keccak256("MINTER_ROLE");
        token.grantRole(MINTER_ROLE, address(staking));
        console.log("Granted MINTER_ROLE to Staking Contract");

        // =========================================================================
        // 4. Governance (Governor)
        // =========================================================================

        // VAMS Governor
        governor = new VAMSGovernor(IVotes(address(token)), timelock);
        console.log("VAMSGovernor deployed to:", address(governor));

        // Connect Governor to Timelock
        bytes32 PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
        bytes32 EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
        bytes32 CANCELLER_ROLE = keccak256("CANCELLER_ROLE");

        timelock.grantRole(PROPOSER_ROLE, address(governor));
        timelock.grantRole(EXECUTOR_ROLE, address(0)); // Allow anyone to execute
        timelock.grantRole(CANCELLER_ROLE, address(governor));
        console.log("Governance Roles granted on Timelock");

        // =========================================================================
        // 5. Economic & Security Layer
        // =========================================================================

        // Guardians for Insurance/Router (using deployer for testnet)
        address[] memory guardians = new address[](1);
        guardians[0] = deployer;

        // VAMS Insurance Fund
        insurance = new VAMSInsuranceFund();
        insurance.initialize(deployer, address(token), address(staking), guardians);
        console.log("VAMSInsuranceFund deployed to:", address(insurance));

        // VAMS Slasher (Operators)
        slasher = new VAMSSlasher();
        slasher.initialize(deployer, address(insurance), address(token));
        console.log("VAMSSlasher deployed to:", address(slasher));

        // VAMS Agent Registry (Agents)
        registry = new VAMSAgentRegistry();
        registry.initialize(deployer, address(token), address(slasher));
        console.log("VAMSAgentRegistry deployed to:", address(registry));

        // VAMS Fee Collector
        // Treasury Address = Timelock
        feeCollector = new VAMSFeeCollector();
        feeCollector.initialize(
            deployer,
            address(token),
            address(timelock), // Treasury
            address(staking),
            address(insurance)
        );
        console.log("VAMSFeeCollector deployed to:", address(feeCollector));

        // VAMS Payment Handler
        paymentHandler = new VAMSPaymentHandler();
        paymentHandler.initialize(
            deployer,
            address(token),
            address(timelock) // Treasury
        );
        console.log("VAMSPaymentHandler deployed to:", address(paymentHandler));

        // VAMS Router
        router = new VAMSRouter();
        router.initialize(deployer, guardians);
        console.log("VAMSRouter deployed to:", address(router));

        // =========================================================================
        // 6. Token Distribution & Vesting Setup
        // =========================================================================

        // Total to vest: 900M (100M Liquid left in deployer for Airdrop/Liquidity)
        uint256 totalVestingAmount = 900_000_000 * 1e18;
        token.approve(address(vesting), totalVestingAmount);

        // A. Community Ecosystem (40% = 400M)
        // Beneficiary: DAO Timelock (The DAO controls the ecosystem fund)
        vesting.createVestingSchedule(address(timelock), 400_000_000 * 1e18, IVAMSVesting.ScheduleType.COMMUNITY, true);
        console.log("Created Community Schedule (400M) -> Timelock");

        // B. DAO Treasury (12% = 120M)
        // Beneficiary: DAO Timelock (The DAO controls its own treasury)
        // Using FOUNDATION type (48 months vesting)
        vesting.createVestingSchedule(address(timelock), 120_000_000 * 1e18, IVAMSVesting.ScheduleType.FOUNDATION, true);
        console.log("Created DAO Treasury Schedule (120M) -> Timelock");

        // C. Architect (12% = 120M)
        // Beneficiary: Deployer (simulating Architect wallet)
        vesting.createVestingSchedule(deployer, 120_000_000 * 1e18, IVAMSVesting.ScheduleType.ARCHITECT, true);
        console.log("Created Architect Schedule (120M) -> Deployer");

        // D. Team/Future Hires (13% = 130M)
        // Beneficiary: Deployer (Simulating Team Reserve Wallet)
        vesting.createVestingSchedule(deployer, 130_000_000 * 1e18, IVAMSVesting.ScheduleType.TEAM, true);
        console.log("Created Team Reserve Schedule (130M) -> Deployer");

        // E. Early Investors (5% = 50M)
        // Beneficiary: Deployer (Simulating Investor Custodian)
        vesting.createVestingSchedule(deployer, 50_000_000 * 1e18, IVAMSVesting.ScheduleType.EARLY_INVESTOR, true);
        console.log("Created Early Investor Schedule (50M) -> Deployer");

        // F. Regular Investors (8% = 80M)
        // Beneficiary: Deployer (Simulating Investor Custodian)
        vesting.createVestingSchedule(deployer, 80_000_000 * 1e18, IVAMSVesting.ScheduleType.REG_INVESTOR, true);
        console.log("Created Regular Investor Schedule (80M) -> Deployer");

        console.log("Deployment V2 Complete. 1B Supply distributed.");

        // =========================================================================
        // 7. INTG02: Integration Wiring — Missing Role Grants
        // =========================================================================

        // ── Deploy VAMSSentinel ──
        // Needed before wiring SENTINEL_ROLE grants.
        // Using deployer as DAO (testnet only) and no fallback multisig.
        VAMSSentinel sentinel = new VAMSSentinel(
            deployer, // admin
            address(token), // vamsToken for keeper bonds
            deployer, // dao (testnet placeholder)
            address(0) // no fallback multisig on testnet
        );
        console.log("VAMSSentinel deployed to:", address(sentinel));

        // ── (1-2) Slasher wiring to InsuranceFund ──
        // VAMSSlasher must be able to receive slashed funds into InsuranceFund.
        bytes32 SLASHER_ROLE = keccak256("SLASHER_ROLE");
        insurance.grantRole(SLASHER_ROLE, address(slasher));
        console.log("INTG02.1: Granted SLASHER_ROLE to Slasher on InsuranceFund");

        // ── (3) Slasher authorized on AgentRegistry ──
        // AgentRegistry.slasher field set at init, but SLASHER_ROLE also needed
        // for future direct slash calls routed through access control.
        registry.grantRole(SLASHER_ROLE, address(slasher));
        console.log("INTG02.3: Granted SLASHER_ROLE to Slasher on AgentRegistry");

        // ── (4-9) INTG01: SENTINEL_ROLE on all 6 pausable contracts ──
        bytes32 SENTINEL_ROLE = keccak256("SENTINEL_ROLE");

        // 4. VAMSFeeCollector
        feeCollector.grantRole(SENTINEL_ROLE, address(sentinel));
        sentinel.addPausableTarget(address(feeCollector));
        console.log("INTG02.4: SENTINEL_ROLE + addPausableTarget FeeCollector");

        // 5. VAMSPaymentHandler
        paymentHandler.grantRole(SENTINEL_ROLE, address(sentinel));
        sentinel.addPausableTarget(address(paymentHandler));
        console.log("INTG02.5: SENTINEL_ROLE + addPausableTarget PaymentHandler");

        // 6. VAMSAgentRegistry
        registry.grantRole(SENTINEL_ROLE, address(sentinel));
        sentinel.addPausableTarget(address(registry));
        console.log("INTG02.6: SENTINEL_ROLE + addPausableTarget AgentRegistry");

        // 7. VAMSInsuranceFund
        insurance.grantRole(SENTINEL_ROLE, address(sentinel));
        sentinel.addPausableTarget(address(insurance));
        console.log("INTG02.7: SENTINEL_ROLE + addPausableTarget InsuranceFund");

        // 8. VAMSRouter (no emergencyPause yet — future sprint; register for
        //    monitoring only when that function is added)
        console.log("INTG02.8: VAMSRouter emergencyPause pending Sprint-2");

        // ── (10) InsuranceFund address set on FeeCollector (was missing) ──
        // FeeCollector already received insurance address in initialize() above.
        // No separate call needed.

        // ── (11) Grant FeeCollector permissions on Router ──
        // Router must accept fee routing calls from the FeeCollector.
        bytes32 FEE_COLLECTOR_ROLE = keccak256("FEE_COLLECTOR_ROLE");
        router.grantRole(FEE_COLLECTOR_ROLE, address(feeCollector));
        console.log("INTG02.11: Granted FEE_COLLECTOR_ROLE to FeeCollector on Router");

        // ── (12) Slashing: Slasher needs SLASHER_ROLE on Staking ──
        staking.grantRole(SLASHER_ROLE, address(slasher));
        console.log("INTG02.12: Granted SLASHER_ROLE to Slasher on Staking");

        // ── (13-14) Keeper setup for Sentinel ──
        // The Sentinel needs at least one keeper to be useful on testnet.
        // The deployer self-bonds 10,000 VAMS as keeper (testnet only).
        uint256 keeperBond = 10_000e18;
        token.approve(address(sentinel), keeperBond);
        sentinel.registerKeeper(keeperBond);
        console.log("INTG02.13-14: Deployer self-bonded as Sentinel keeper (testnet)");

        console.log("INTG02: All missing role grants applied.");

        vm.stopBroadcast();
    }
}
