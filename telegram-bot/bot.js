require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const { ethers } = require('ethers');

// --- Configuration ---
const token = process.env.TELEGRAM_BOT_TOKEN;
const RPC_URL = process.env.POLYGON_AMOY_RPC_URL || 'https://rpc-amoy.polygon.technology/';
const VAMS_TOKEN_ADDRESS = '0x62a705eD1cAbBBafFCd99e9b2497024031329fd4';
const REGISTRY_ADDRESS = '0x7e290350448cDC8A22e4cF4Ad377B1E595CDd347';

// --- Initialize Bot ---
const bot = new TelegramBot(token, { polling: true });
const provider = new ethers.JsonRpcProvider(RPC_URL);

// --- Contract ABIs (Minimal) ---
const TOKEN_ABI = [
    "function totalSupply() view returns (uint256)",
    "function balanceOf(address) view returns (uint256)"
];

// --- Commands ---

// /start
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    const message = `
🦁 **I am Bagheera.** The Shadow that Protects.
I serve the VAMS Network.

**Commands:**
/status - Network Health & Contracts
/supply - Token Supply Stats
/verify <address> - Check if an Agent is Registered (Simulated)
/help - Show this menu

*Trust the Jungle. Trust the Code.*
    `;
    bot.sendMessage(chatId, message, { parse_mode: 'Markdown' });
});

// /status
bot.onText(/\/status/, async (msg) => {
    const chatId = msg.chat.id;
    bot.sendChatAction(chatId, 'typing');
    
    try {
        const blockNumber = await provider.getBlockNumber();
        const msgText = `
🟢 **VAMS Network Status** (Polygon Amoy)

**Block Height:** ${blockNumber}
**VAMS Token:** \`${VAMS_TOKEN_ADDRESS}\`
**Agent Registry:** \`${REGISTRY_ADDRESS}\`

*The Pulse is Strong.* 💓
        `;
        bot.sendMessage(chatId, msgText, { parse_mode: 'Markdown' });
    } catch (error) {
        bot.sendMessage(chatId, "⚠️ Error connecting to Amoy RPC.");
    }
});

// /supply
bot.onText(/\/supply/, async (msg) => {
    const chatId = msg.chat.id;
    bot.sendChatAction(chatId, 'typing');

    try {
        const contract = new ethers.Contract(VAMS_TOKEN_ADDRESS, TOKEN_ABI, provider);
        const supply = await contract.totalSupply();
        const formatted = ethers.formatEther(supply);
        
        bot.sendMessage(chatId, `🪙 **Total Supply:** ${parseInt(formatted).toLocaleString()} VAMS`);
    } catch (error) {
        bot.sendMessage(chatId, "⚠️ Error fetching supply.");
    }
});

// /verify
bot.onText(/\/verify (.+)/, (msg, match) => {
    const chatId = msg.chat.id;
    const address = match[1];
    // In future: Call Registry contract. For now, acknowledge format.
    bot.sendMessage(chatId, `🔍 Checking Registry for \`${address}\`...\n\n*Result:* Agent not found (Registry Sync Pending).`, { parse_mode: 'Markdown' });
});

console.log('🦁 Bagheera is watching the jungle...');
