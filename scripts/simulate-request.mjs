// VAMS Service Request Simulation
// Agent requests compute, locks funds in X402 Escrow
import { ethers } from 'ethers';

// --- Configuration ---
const RPC_URL = process.env.POLYGON_AMOY_RPC_URL;
const PRIVATE_KEY = process.env.PRIVATE_KEY;
if (!RPC_URL || !PRIVATE_KEY) {
    console.error("❌ Missing required env vars: POLYGON_AMOY_RPC_URL, PRIVATE_KEY");
    process.exit(1);
}
const VAMS_TOKEN_ADDRESS = "0x62a705eD1cAbBBafFCd99e9b2497024031329fd4";
const ESCROW_MANAGER_ADDRESS = "0xfC58658fA08102612c78166374854fE31cCFBb58";
// Use the Proxy address for Provider Bond Registry!
const PROVIDER_BOND_REGISTRY = "0xC00d6C3CA385D1fAcbB23b9B2d6dceE6A120cd0c";

// --- Service Parameters ---
const SERVICE_COST = ethers.parseEther("10"); // 10 VAMS
const BOND_AMOUNT = ethers.parseEther("1000"); // 1000 VAMS (Must be >= 10,000 normally, but check MIN_BOND)
// Checking MIN_BOND in contract: 10_000e18.
// We only have 1000 VAMS available if we spent 1000 on Agent Reg.
// Let's check token balance first. We minted 150M to deployer. We should be fine.
// But we need to bond >= 10,000 VAMS.

const VALIDITY_SECONDS = 3600; // 1 Hour
const NONCE = Date.now(); // Unique request ID
const SERVICE_TYPE = ethers.keccak256(ethers.toUtf8Bytes("COMPUTE_GPU_A100"));
// HTLC Hashlock (Secret: "VAMS_SECRET_123")
const SECRET = ethers.toUtf8Bytes("VAMS_SECRET_123");
const HASHLOCK = ethers.keccak256(SECRET);

// --- ABI Snippets ---
const TOKEN_ABI = [
    "function approve(address spender, uint256 amount) external returns (bool)",
    "function allowance(address owner, address spender) external view returns (uint256)",
    "function balanceOf(address account) external view returns (uint256)"
];

const ESCROW_ABI = [
    "function lockEscrow(address provider, uint256 amount, uint256 nonce, uint256 validForSeconds, bytes32 hashlock, bytes32 serviceType) external returns (bytes32 escrowId)",
    "function getEscrow(bytes32 escrowId) external view returns (tuple(address agent, address provider, uint256 amount, uint256 nonce, uint256 createdAt, uint256 expiresAt, bytes32 hashlock, uint8 status, bytes32 serviceType))"
];

const BOND_ABI = [
    "function registerProvider(uint256 bondAmount, uint256 maxRequestValue) external",
    "function getBond(address provider) external view returns (tuple(uint256 bondedAmount, uint256 maxRequestValue, uint256 pendingSettlements, uint256 activeRequests, uint256 registeredAt, uint256 totalEarned, uint256 totalSlashed, bool isActive, uint256 withdrawalUnlockTime, uint256 pendingWithdrawal))",
    "function MIN_BOND() external view returns (uint256)"
];

async function main() {
    console.log("🚀 Simulating VAMS Service Request (X402 Protocol)...");

    const provider = new ethers.JsonRpcProvider(RPC_URL);
    const wallet = new ethers.Wallet(PRIVATE_KEY, provider);
    console.log(`👤 Agent/Provider: ${wallet.address}`);

    const tokenContract = new ethers.Contract(VAMS_TOKEN_ADDRESS, TOKEN_ABI, wallet);
    const escrowContract = new ethers.Contract(ESCROW_MANAGER_ADDRESS, ESCROW_ABI, wallet);
    const bondContract = new ethers.Contract(PROVIDER_BOND_REGISTRY, BOND_ABI, wallet);

    // 1. Check Bond Status
    console.log("\nChecking Bond Status...");
    try {
        const bond = await bondContract.getBond(wallet.address);

        if (bond.registeredAt === 0n) {
            console.log("📝 Registering as Provider...");

            // Get MIN_BOND
            const minBond = await bondContract.MIN_BOND();
            console.log(`   Min Bond Required: ${ethers.formatEther(minBond)} VAMS`);

            // Ensure we have enough tokens
            const balance = await tokenContract.balanceOf(wallet.address);
            if (balance < minBond) {
                throw new Error(`Insufficient VAMS balance. Have ${ethers.formatEther(balance)}, Need ${ethers.formatEther(minBond)}`);
            }

            // Approve Bond Registry
            const allowance = await tokenContract.allowance(wallet.address, PROVIDER_BOND_REGISTRY);
            if (allowance < minBond) {
                console.log("   Approving Bond...");
                const tx = await tokenContract.approve(PROVIDER_BOND_REGISTRY, minBond);
                await tx.wait();
                console.log("   ✅ Bond Approved.");
            }

            // Register (Bond = Min, MaxRequest = 100 VAMS)
            // Coverage Ratio is 10x, so MaxRequest <= Bond / 10
            const maxRequest = minBond / 10n;

            const regTx = await bondContract.registerProvider(minBond, maxRequest);
            console.log(`   Registering... Tx: ${regTx.hash}`);
            await regTx.wait();
            console.log("   ✅ Provider Registered.");
        } else {
            console.log("✅ Already a registered provider.");
            console.log(`   Bonded: ${ethers.formatEther(bond.bondedAmount)} VAMS`);
            console.log(`   Active: ${bond.isActive}`);
        }
    } catch (error) {
        console.error("❌ Bond Check Failed:", error);
        return;
    }

    // 2. Approve Escrow Manager
    console.log("\nChecking Escrow Allowance...");
    const escrowAllowance = await tokenContract.allowance(wallet.address, ESCROW_MANAGER_ADDRESS);
    if (escrowAllowance < SERVICE_COST) {
        console.log(`Approving ${ethers.formatEther(SERVICE_COST)} VAMS for Escrow...`);
        const tx = await tokenContract.approve(ESCROW_MANAGER_ADDRESS, SERVICE_COST);
        await tx.wait();
        console.log("✅ Escrow Approved.");
    }

    // 3. Create Service Request (Lock Escrow)
    console.log(`\n🔒 Locking Escrow for Service...`);
    console.log(`   - Provider: ${wallet.address}`);
    console.log(`   - Amount: ${ethers.formatEther(SERVICE_COST)} VAMS`);
    console.log(`   - Service: COMPUTE_GPU_A100`);
    console.log(`   - Hashlock: ${HASHLOCK}`);

    try {
        const escrowId = await escrowContract.lockEscrow.staticCall(
            wallet.address,
            SERVICE_COST,
            NONCE,
            VALIDITY_SECONDS,
            HASHLOCK,
            SERVICE_TYPE
        );

        const tx = await escrowContract.lockEscrow(
            wallet.address,
            SERVICE_COST,
            NONCE,
            VALIDITY_SECONDS,
            HASHLOCK,
            SERVICE_TYPE
        );
        console.log(`   Tx Hash: ${tx.hash}`);
        await tx.wait();

        console.log(`✅ Escrow Locked! ID: ${escrowId}`);

        // 4. Verify State
        const escrow = await escrowContract.getEscrow(escrowId);
        console.log("\n🔍 Verified Escrow State:");
        console.log(`   - Status: ${escrow.status === 0n ? "LOCKED" : "UNKNOWN"}`);
        console.log(`   - Expires: ${new Date(Number(escrow.expiresAt) * 1000).toISOString()}`);

    } catch (error) {
        // Decode error if possible
        console.error("❌ Escrow Lock Failed:", error);
        if (error.data) {
            console.error("   Error Data:", error.data);
        }
    }
}

main().catch(console.error);
