"""
VAMS Neuron - Payment Channel Manager (x402)
============================================
Manages off-chain state channels for high-frequency agent payments.
Handles:
- Channel opening/closing
- Balance tracking
- Nonce management
- Signature generation (EIP-712 compatible)
"""

import time
import json
import os
import logging
from typing import Dict, Optional, Any, List
from threading import Lock
from dataclasses import dataclass, asdict

from payments.delivery_proof import ServiceDeliveryProof
from payments.batch_settlement import Payment

logger = logging.getLogger("VAMS-Channels")

@dataclass
class ChannelState:
    channel_id: str
    agent_address: str
    provider_address: str
    deposit_amount: int    # Total capacity
    spent_amount: int      # Current utilization
    nonce: int
    status: str            # OPEN, CLOSING, CLOSED
    opened_at: float
    expires_at: float
    signatures: List[str]  # History of payment signatures

class PaymentChannelManager:
    """
    Manages local state of multiple payment channels.
    Thread-safe. Persists to JSON.
    """
    
    def __init__(self, persistence_path: str = "channels.json"):
        self.persistence_path = persistence_path
        self.channels: Dict[str, ChannelState] = {}
        self.lock = Lock()
        self._load_state()

    def create_channel(self, agent: str, provider: str, deposit: int, duration_hours: int = 24) -> str:
        """Initialize a new channel state locally."""
        channel_id = f"ch_{provider[:6]}_{int(time.time())}"
        
        with self.lock:
            self.channels[channel_id] = ChannelState(
                channel_id=channel_id,
                agent_address=agent,
                provider_address=provider,
                deposit_amount=deposit,
                spent_amount=0,
                nonce=0,
                status="OPEN",
                opened_at=time.time(),
                expires_at=time.time() + (duration_hours * 3600),
                signatures=[]
            )
            self._save_state()
            
        logger.info(f"Created channel {channel_id} with {deposit} capacity")
        return channel_id

    def sign_payment(self, channel_id: str, amount: int, service_type: str) -> Optional[Dict[str, Any]]:
        """
        Generate a payment for a specific service.
        Updates local state (nonce/spent).
        """
        with self.lock:
            channel = self.channels.get(channel_id)
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                return None
            
            if channel.status != "OPEN":
                logger.error(f"Channel {channel_id} is {channel.status}")
                return None
                
            if channel.spent_amount + amount > channel.deposit_amount:
                logger.error(f"Insufficient channel capacity: {channel.spent_amount} + {amount} > {channel.deposit_amount}")
                return None
                
            # Update state
            channel.spent_amount += amount
            channel.nonce += 1
            
            # Create payment object
            payment = Payment(
                agent=channel.agent_address,
                provider=channel.provider_address,
                amount=amount,
                nonce=channel.nonce,
                service_type=service_type.encode().ljust(32, b'\0')
            )
            
            # Simulate signature (In real implementation: sign hash(payment) with private key)
            # For now, we return the payment struct which will be added to a batch
            receipt = {
                "channel_id": channel_id,
                "payment": payment.to_tuple(),  # (agent, provider, amount, nonce, service)
                "signature": f"sig_mock_{channel.nonce}", 
                "timestamp": time.time()
            }
            
            channel.signatures.append(receipt["signature"])
            self._save_state()
            
            return receipt

    def get_channel(self, channel_id: str) -> Optional[ChannelState]:
        return self.channels.get(channel_id)

    def _save_state(self):
        """Persist channels to disk."""
        try:
            data = {cid: asdict(c) for cid, c in self.channels.items()}
            # Convert binary service_type if needed, or handle serialization
            # Here we just dump as JSON
            with open(self.persistence_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save channel state: {e}")

    def _load_state(self):
        """Load channels from disk."""
        if not os.path.exists(self.persistence_path):
            return
            
        try:
            with open(self.persistence_path, "r") as f:
                data = json.load(f)
                for cid, c_data in data.items():
                    self.channels[cid] = ChannelState(**c_data)
        except Exception as e:
            logger.error(f"Failed to load channel state: {e}")
