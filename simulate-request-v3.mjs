// VAMS Service Request Simulation
// Agent requests compute, locks funds in X402 Escrow
import { ethers } from 'ethers';

// --- Configuration ---
const RPC_URL = "https://polygon-amoy.infura.io/v3/726db297eb03483ea9ed9f3c76ca1087";
// VAMS Node Wallet Private Key
const PRIVATE_KEY = "ROTATED_KEY_PLACEHOLDER";
const VAMS_TOKEN_ADDRESS = "0x62a705eD1cAbBBafFCd99e9b2497024031329fd4";
const ESCROW_MANAGER_ADDRESS = "0xfC58658fA08102612c78166374854fE31cCFBb58";
// Use the Proxy address for Provider Bond Registry!
const PROVIDER_BOND_REGISTRY = "0xC00d6C3CA385D1fAcbB23b9B2d6dceE6A120cd0c";

// --- Service Parameters ---
const SERVICE_COST = ethers.parseEther("10"); // 10 VAMS
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

async function main() {
    console.log("🚀 Simulating VAMS Service Request (X402 Protocol)...");
    
    const provider = new ethers.JsonRpcProvider(RPC_URL);
    const wallet = new ethers.Wallet(PRIVATE_KEY, provider);
    console.log(`👤 Agent/Provider: ${wallet.address}`);
    
    const tokenContract = new ethers.Contract(VAMS_TOKEN_ADDRESS, TOKEN_ABI, wallet);
    const escrowContract = new ethers.Contract(ESCROW_MANAGER_ADDRESS, ESCROW_ABI, wallet);
    
    // 2. Approve Escrow Manager (Double Check & Force Approve)
    console.log("\nChecking Escrow Allowance...");
    const escrowAllowance = await tokenContract.allowance(wallet.address, ESCROW_MANAGER_ADDRESS);
    console.log(`   Allowance: ${ethers.formatEther(escrowAllowance)} VAMS`);
    
    // Always approve to be safe if less than cost
    if (escrowAllowance < SERVICE_COST) {
        console.log(`   Approving ${ethers.formatEther(SERVICE_COST)} VAMS for Escrow...`);
        const tx = await tokenContract.approve(ESCROW_MANAGER_ADDRESS, SERVICE_COST);
        console.log(`   Tx Hash: ${tx.hash}`);
        await tx.wait();
        console.log("   ✅ Escrow Approved.");
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
        console.log(`\n🔍 Verifying Escrow: ${escrowId}`);
        const escrow = await escrowContract.getEscrow(escrowId);
        
        const statusMap = ["LOCKED", "REFUNDED", "CLAIMED", "DISPUTED", "RESOLVED"];
        
        console.log(`   - Status: ${statusMap[Number(escrow.status)]}`);
        console.log(`   - Created: ${new Date(Number(escrow.createdAt) * 1000).toISOString()}`);
        console.log(`   - Expires: ${new Date(Number(escrow.expiresAt) * 1000).toISOString()}`);
        console.log(`   - Amount: ${ethers.formatEther(escrow.amount)} VAMS`);
        
    } catch (error) {
        console.error("❌ Escrow Lock Failed:", error);
    }
}

main().catch(console.error);
