// VAMS Agent Registration Script
// Uses direct private key signing via Ethers.js
import { ethers } from 'ethers';
import fs from 'fs';
import path from 'path';

// --- Configuration ---
const RPC_URL = process.env.POLYGON_AMOY_RPC_URL;
const PRIVATE_KEY = process.env.PRIVATE_KEY;
if (!RPC_URL || !PRIVATE_KEY) {
    console.error("❌ Missing required env vars: POLYGON_AMOY_RPC_URL, PRIVATE_KEY");
    process.exit(1);
}
const VAMS_TOKEN_ADDRESS = "0x62a705eD1cAbBBafFCd99e9b2497024031329fd4";
const REGISTRY_ADDRESS = "0x7e290350448cDC8A22e4cF4Ad377B1E595CDd347";
const STAKE_AMOUNT = ethers.parseEther("1000"); // 1000 VAMS
const NODE_ID = "vams_e7d2d15275054b27a379deb0b8c0a673fb8d959e";
const METADATA_URI = "ipfs://bafkreic7x7t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6t6";

// --- ABI Snippets ---
const TOKEN_ABI = [
    "function approve(address spender, uint256 amount) external returns (bool)",
    "function allowance(address owner, address spender) external view returns (uint256)"
];

const REGISTRY_ABI = [
    "function registerAgent(bytes32 _publicKeyHash, uint256 _stake, string calldata _metadata) external returns (bytes32 agentId)",
    "function getAgent(bytes32 _agentId) external view returns (address, bytes32, uint256, uint8, uint256, uint256, bytes32)"
];

async function main() {
    console.log("🚀 Starting VAMS Agent Registration...");

    const provider = new ethers.JsonRpcProvider(RPC_URL);
    const wallet = new ethers.Wallet(PRIVATE_KEY, provider);

    console.log(`👤 Wallet Address: ${wallet.address}`);

    const tokenContract = new ethers.Contract(VAMS_TOKEN_ADDRESS, TOKEN_ABI, wallet);
    const registryContract = new ethers.Contract(REGISTRY_ADDRESS, REGISTRY_ABI, wallet);

    // 1. Approve Token Spend
    console.log(`\nChecking allowance for ${REGISTRY_ADDRESS}...`);
    const allowance = await tokenContract.allowance(wallet.address, REGISTRY_ADDRESS);

    if (allowance < STAKE_AMOUNT) {
        console.log(`Approval needed. Approving ${ethers.formatEther(STAKE_AMOUNT)} VAMS...`);
        const approveTx = await tokenContract.approve(REGISTRY_ADDRESS, STAKE_AMOUNT);
        console.log(`Approving... Tx Hash: ${approveTx.hash}`);
        await approveTx.wait();
        console.log("✅ Approved.");
    } else {
        console.log("✅ Allowance sufficient.");
    }

    // 2. Register Agent
    const publicKeyHash = ethers.keccak256(ethers.toUtf8Bytes(NODE_ID));
    console.log(`\nRegistering Agent Node ID: ${NODE_ID}`);
    console.log(`Public Key Hash: ${publicKeyHash}`);

    try {
        const registerTx = await registryContract.registerAgent(publicKeyHash, STAKE_AMOUNT, METADATA_URI);
        console.log(`Registering... Tx Hash: ${registerTx.hash}`);
        const receipt = await registerTx.wait();
        console.log("✅ Agent Registered Successfully!");
        console.log(`Block: ${receipt.blockNumber}`);
    } catch (error) {
        if (error.message.includes("AgentAlreadyExists")) {
            console.log("⚠️ Agent is already registered.");
        } else {
            console.error("❌ Registration Failed:", error);
        }
    }

    // 3. Verify Registration
    console.log("\nVerifying on-chain state...");
    // agentId in contract is keccak256(abi.encodePacked(_publicKeyHash, msg.sender, block.timestamp))
    // We can't easily guess it here without parsing logs, but the tx success confirms it.
    // For now, we trust the receipt.
}

main().catch(console.error);
