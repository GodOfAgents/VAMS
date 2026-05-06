import logging
import time
import os
from typing import Dict, Any, Optional

# web3 import - handle case where we have a local web3 folder
try:
    import importlib
    web3_module = importlib.import_module("web3")
    Web3 = web3_module.Web3
except (ImportError, AttributeError):
    Web3 = None

from payments.payment_channel import PaymentChannelManager
from payments.delivery_proof import create_proof
from payments.batch_settlement import Payment

logger = logging.getLogger("VAMSx402")

class X402Client:
    """
    Economic Layer (Layer 5) - x402 Payment Protocol Client.
    Handles HTTP 402 responses, channel management, and atomic payments.
    """
    
    def __init__(self, private_key: Optional[str] = None, session_key: Optional[str] = None, smart_wallet_address: Optional[str] = None, rpc_url: Optional[str] = None, circuit_breaker: Optional[Any] = None):
        self.private_key = private_key
        self.session_key = session_key
        self.smart_wallet_address = smart_wallet_address
        self.rpc_url = rpc_url or "https://polygon-rpc.com"
        self.breaker = circuit_breaker
        
        # Initialize Managers
        self.channel_manager = PaymentChannelManager()
        
        # Initialize Web3
        if Web3 is not None and rpc_url:
            try:
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                try:
                    from sdk.signer import SignerFactory
                    if self.session_key and self.smart_wallet_address:
                        self.signer = SignerFactory.create({
                            "session_key": self.session_key,
                            "smart_wallet_address": self.smart_wallet_address
                        })
                    elif self.private_key:
                        self.signer = SignerFactory.create({"private_key": self.private_key})
                    else:
                        self.signer = None
                        
                    if self.signer:
                        self.address = self.signer.address
                    else:
                        self.address = "0x0000000000000000000000000000000000000000"
                except ImportError:
                    self.signer = None
                    if self.private_key:
                        self.account = self.w3.eth.account.from_key(self.private_key)
                        self.address = self.account.address
                    else:
                        self.address = "0x0000000000000000000000000000000000000000"
            except Exception as e:
                logger.error(f"Web3 init failed: {e}")
                self.w3 = None
        else:
            self.w3 = None
            self.address = "0xMockAgentAddress"

        logger.info(f"X402 Client initialized (Address: {self.address})")

    def open_channel(self, counterparty: str, deposit: float, duration_hours: int = 24) -> Optional[str]:
        """
        Open a payment channel with a counterparty.
        """
        # Circuit Breaker Check
        if self.breaker and not self.breaker.is_active():
            logger.error("❌ Circuit Breaker prohibits new channels")
            return None

        # 1. Create local state
        # Convert float VAMS to uint256 wei (assume 18 decimals)
        deposit_wei = int(deposit * 10**18)
        
        channel_id = self.channel_manager.create_channel(
            agent=self.address,
            provider=counterparty,
            deposit=deposit_wei,
            duration_hours=duration_hours
        )
        
        if self.breaker:
            self.breaker.update_exposure(deposit)
        
        logger.info(f"Opened channel {channel_id} with {counterparty} (Cap: {deposit} VAMS)")
        return channel_id

    def handle_402(self, response_headers: Dict[str, str], url: str) -> Optional[str]:
        """
        Parse 402 headers and generate payment token.
        Headers: "WWW-Authenticate: x402 chain=137 contract=0x... amount=100 service=inference-01"
        """
        if self.breaker and not self.breaker.is_active():
            logger.error("❌ Circuit Breaker prohibits payments")
            return None

        auth_header = response_headers.get("WWW-Authenticate") or response_headers.get("www-authenticate")
        if not auth_header or "x402" not in auth_header:
            return None
            
        try:
            params = self._parse_header(auth_header)
            
            amount_float = float(params.get("amount", 0))
            amount_wei = int(amount_float * 10**18)
            contract_addr = params.get("contract") # This is the provider address/contract
            service_type = params.get("service", "default")
            
            if amount_wei > 0 and contract_addr:
                # Find or open channel
                # For PoC, we just reuse any open channel or create a temp one
                # Real logic: lookup channel by provider address
                
                # ... lookup logic skipped ...
                # Assuming we have a channel_id from open_channel called previously
                # defaulting to creating a fresh one for this request if none exists (mock)
                
                channel_id = self._get_or_create_channel(contract_addr, amount_float * 10) # 10x buffer
                
                if not channel_id:
                     if self.breaker: self.breaker.record_failure("Channel creation failed")
                     return None

                # Generate payment
                receipt = self.channel_manager.sign_payment(channel_id, amount_wei, service_type)
                
                if receipt:
                    if self.breaker: self.breaker.record_success()
                    # Format: "x402 <token>"
                    # Token includes channel_id, payment proof, signature
                    token = self._encode_token(receipt)
                    return token
                else:
                    if self.breaker: self.breaker.record_failure("Payment signing failed")
                
        except Exception as e:
            logger.error(f"Failed to handle 402: {e}")
            if self.breaker: self.breaker.record_failure(str(e))
            
        return None

    def _parse_header(self, header: str) -> Dict[str, str]:
        params = {}
        parts = header.replace("x402 ", "").split(" ")
        for p in parts:
            if "=" in p:
                k, v = p.split("=")
                params[k] = v.strip('"')
        return params

    def _get_or_create_channel(self, provider: str, deposit: float) -> str:
        """Find an open channel for provider or create one."""
        # Simple search
        with self.channel_manager.lock:
            for cid, c in self.channel_manager.channels.items():
                if c.provider_address == provider and c.status == "OPEN":
                    return cid
        
        # Create new
        return self.open_channel(provider, deposit)

    def _encode_token(self, receipt: Dict[str, Any]) -> str:
        """Base64 encode payment receipt for header."""
        import base64
        import json
        return base64.b64encode(json.dumps(receipt, default=str).encode()).decode()

    def get_headers(self, auth_token: str) -> Dict[str, str]:
        """Return headers with Authorization: x402 <token>"""
        return {"Authorization": f"x402 {auth_token}"}

    def get_channel_balance(self, channel_id: str) -> int:
        """Return remaining balance in channel (wei)."""
        channel = self.channel_manager.get_channel(channel_id)
        if not channel:
            return 0
        return channel.deposit_amount - channel.spent_amount

