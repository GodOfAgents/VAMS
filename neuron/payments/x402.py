import logging
import time
from typing import Dict, Any, Optional

# web3 import - handle case where we have a local web3 folder
try:
    import importlib
    web3_module = importlib.import_module("web3")
    Web3 = web3_module.Web3
except (ImportError, AttributeError):
    Web3 = None  # Fallback: run without on-chain features

logger = logging.getLogger("VAMSx402")

class X402Client:
    """
    Economic Layer (Layer 5) - x402 Payment Protocol Client.
    Handles HTTP 402 responses and generates payment channel signatures.
    """
    
    def __init__(self, private_key: Optional[str] = None, rpc_url: Optional[str] = None):
        self.private_key = private_key
        self.rpc_url = rpc_url or "https://polygon-rpc.com"
        
        # Initialize Web3 if available
        if Web3 is not None:
            try:
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url)) if rpc_url else Web3()
            except Exception:
                self.w3 = None
        else:
            self.w3 = None
            
        # Mock balance for PoC
        self.balance = 1000.0
        self.channels: Dict[str, Dict[str, Any]] = {}  # channel_id -> state
        logger.info(f"X402 Client initialized (RPC: {self.rpc_url[:30]}..., Web3: {'Yes' if self.w3 else 'No'})")

    def open_channel(self, counterparty: str, deposit: float, duration_hours: int = 24) -> Optional[str]:
        """
        Open a payment channel with a counterparty.
        Returns channel_id on success.
        """
        if deposit > self.balance:
            logger.error(f"Insufficient balance to open channel: {deposit} > {self.balance}")
            return None
            
        channel_id = f"ch_{counterparty[:8]}_{int(time.time())}"
        
        self.channels[channel_id] = {
            "counterparty": counterparty,
            "deposit": deposit,
            "spent": 0.0,
            "opened_at": time.time(),
            "expires_at": time.time() + (duration_hours * 3600),
            "state": "open",
            "nonce": 0
        }
        
        self.balance -= deposit
        logger.info(f"Opened channel {channel_id} with {counterparty} (Deposit: {deposit} VAMS)")
        
        # In production: Call on-chain contract to lock funds
        # self._call_contract("openChannel", counterparty, deposit)
        
        return channel_id

    def close_channel(self, channel_id: str, cooperative: bool = True) -> bool:
        """
        Close a payment channel and settle on-chain.
        cooperative=True means both parties agree on final balance.
        """
        if channel_id not in self.channels:
            logger.error(f"Channel {channel_id} not found")
            return False
            
        channel = self.channels[channel_id]
        
        if channel["state"] != "open":
            logger.warning(f"Channel {channel_id} already {channel['state']}")
            return False
        
        # Calculate refund
        refund = channel["deposit"] - channel["spent"]
        self.balance += refund
        
        channel["state"] = "closed"
        channel["closed_at"] = time.time()
        
        logger.info(f"Closed channel {channel_id} (Spent: {channel['spent']}, Refund: {refund})")
        
        # In production: Submit final state to on-chain contract
        # self._call_contract("closeChannel", channel_id, channel["spent"], signature)
        
        return True

    def get_channel_balance(self, channel_id: str) -> Optional[float]:
        """Get remaining balance in a channel."""
        if channel_id not in self.channels:
            return None
        channel = self.channels[channel_id]
        return channel["deposit"] - channel["spent"]

    def handle_402(self, response_headers: Dict[str, str], url: str) -> Optional[str]:
        """
        Parse 402 headers and generate payment token.
        Headers expected: "WWW-Authenticate: x402 chain=137 contract=0x... amount=100"
        """
        auth_header = response_headers.get("WWW-Authenticate") or response_headers.get("www-authenticate")
        if not auth_header or "x402" not in auth_header:
            return None
            
        # Parse params (simplified)
        try:
            params = {}
            parts = auth_header.replace("x402 ", "").split(" ")
            for p in parts:
                if "=" in p:
                    k, v = p.split("=")
                    params[k] = v.strip('"')
            
            amount = float(params.get("amount", 0))
            contract = params.get("contract")
            
            if amount > 0:
                return self._sign_payment(contract, amount)
                
        except Exception as e:
            logger.error(f"Failed to parse x402 header: {e}")
            
        return None

    def _sign_payment(self, contract: str, amount: float) -> str:
        """Generate payment signature (off-chain channel update)."""
        if self.balance < amount:
            logger.warning("Insufficient VAMS balance for payment")
            return None
            
        self.balance -= amount
        logger.info(f"Signing payment of {amount} VAMS for {contract}")
        
        # Real signing would use EIP-712 typed data
        # For PoC we return a mock signature
        timestamp = int(time.time())
        proof = f"x402-proof-{contract}-{amount}-{timestamp}"
        
        return proof

    def get_headers(self, auth_token: str) -> Dict[str, str]:
        """Return headers with Authorization: x402 <token>"""
        return {"Authorization": f"x402 {auth_token}"}
