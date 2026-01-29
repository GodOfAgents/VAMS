import logging
import time
from typing import Dict, Any, Optional
from web3 import Web3

logger = logging.getLogger("VAMSx402")

class X402Client:
    """
    Economic Layer (Layer 5) - x402 Payment Protocol Client.
    Handles HTTP 402 responses and generates payment channel signatures.
    """
    
    def __init__(self, private_key: Optional[str] = None):
        self.private_key = private_key
        self.w3 = Web3()
        # Mock balance for PoC
        self.balance = 1000.0
        self.channels = {} # channel_id -> state

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
