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
    
    // 4. Verify State (Fixed display logic)
    const escrowId = "0x9ab8eeccdf56c97a82c0d38af73d5cabae37c3dc90230c8cadabf1a8da49004d"; // Hardcoded from previous success
    console.log(`\n🔍 Verifying Escrow: ${escrowId}`);
    
    const escrow = await escrowContract.getEscrow(escrowId);
    console.log("   Escrow Data:", escrow);
    
    // Check status enum: LOCKED=0, REFUNDED=1, CLAIMED=2, DISPUTED=3, RESOLVED=4
    const statusMap = ["LOCKED", "REFUNDED", "CLAIMED", "DISPUTED", "RESOLVED"];
    
    console.log(`   - Status: ${statusMap[Number(escrow.status)]}`);
    console.log(`   - Created: ${new Date(Number(escrow.createdAt) * 1000).toISOString()}`);
    console.log(`   - Expires: ${new Date(Number(escrow.expiresAt) * 1000).toISOString()}`);
    console.log(`   - Amount: ${ethers.formatEther(escrow.amount)} VAMS`);
}

main().catch(console.error);
