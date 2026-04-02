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

contract DeployV2 is Script {
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
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        // =========================================================================
        // 1. Governance Infrastructure (Timelock needs to be deployed early for Treasury)
        // =========================================================================
        
        // Timelock Controller (Min delay 1 day)
        address[] memory proposers = new address[](0);
        address[] memory executors = new address[](0);
        timelock = new VAMSTimelockController(
            1 days,
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
        
        staking = new VAMSStaking(
            address(token), 
            address(token), 
            ratePerSecond, 
            deployer
        );
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
        insurance.initialize(
            deployer,
            address(token),
            address(staking),
            guardians
        );
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
        vesting.createVestingSchedule(
            address(timelock), 
            400_000_000 * 1e18, 
            IVAMSVesting.ScheduleType.COMMUNITY, 
            true
        );
        console.log("Created Community Schedule (400M) -> Timelock");
        
        // B. DAO Treasury (12% = 120M)
        // Beneficiary: DAO Timelock (The DAO controls its own treasury)
        // Using FOUNDATION type (48 months vesting)
        vesting.createVestingSchedule(
            address(timelock), 
            120_000_000 * 1e18, 
            IVAMSVesting.ScheduleType.FOUNDATION, 
            true
        );
        console.log("Created DAO Treasury Schedule (120M) -> Timelock");
        
        // C. Founder (12% = 120M)
        // Beneficiary: Deployer (Simulating Founder Wallet)
        vesting.createVestingSchedule(
            deployer, 
            120_000_000 * 1e18, 
            IVAMSVesting.ScheduleType.FOUNDER, 
            true
        );
        console.log("Created Founder Schedule (120M) -> Deployer");
        
        // D. Team/Future Hires (13% = 130M)
        // Beneficiary: Deployer (Simulating Team Reserve Wallet)
        vesting.createVestingSchedule(
            deployer, 
            130_000_000 * 1e18, 
            IVAMSVesting.ScheduleType.TEAM, 
            true
        );
        console.log("Created Team Reserve Schedule (130M) -> Deployer");
        
        // E. Early Investors (5% = 50M)
        // Beneficiary: Deployer (Simulating Investor Custodian)
        vesting.createVestingSchedule(
            deployer, 
            50_000_000 * 1e18, 
            IVAMSVesting.ScheduleType.EARLY_INVESTOR, 
            true
        );
        console.log("Created Early Investor Schedule (50M) -> Deployer");

        // F. Regular Investors (8% = 80M)
        // Beneficiary: Deployer (Simulating Investor Custodian)
        vesting.createVestingSchedule(
            deployer, 
            80_000_000 * 1e18, 
            IVAMSVesting.ScheduleType.REG_INVESTOR, 
            true
        );
        console.log("Created Regular Investor Schedule (80M) -> Deployer");

        console.log("Deployment V2 Complete. 1B Supply distributed.");
        
        vm.stopBroadcast();
    }
}
