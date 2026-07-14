import json
import time
import logging
import os
import hashlib
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
try:
    from neuron.secp256k1 import PrivateKey, sign_message, verify_message
except ModuleNotFoundError:  # Support direct execution from neuron/.
    from secp256k1 import PrivateKey, sign_message, verify_message

logger = logging.getLogger("VAMS-Comms")

@dataclass
class SignedMessage:
    sender_id: str
    recipient_id: str
    timestamp: float
    payload: str  # JSON string
    signature: str 
    metadata: Dict[str, Any] = None 

class AuditLogger:
    """Immutable audit log for all agent interactions."""
    
    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
        # Ensure file exists
        if not os.path.exists(log_file):
            with open(log_file, "w") as f:
                f.write(f"VAMS AUDIT LOG PIVOT | Created: {time.time()}\n")

    def log_event(self, direction: str, message: SignedMessage, verified: bool):
        """Log a communication event."""
        entry = {
            "time": time.time(),
            "direction": direction,
            "verified": verified,
            "sender": message.sender_id,
            "recipient": message.recipient_id,
            "payload_hash": hashlib.sha256(message.payload.encode()).hexdigest()[:16], # Deterministic audit hash
            "signature": message.signature[:16] + "..."
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

class AgentCommunicator:
    """
    Handles secure, auditable communication between agents.
    "Trust but Verify"
    """
    
    def __init__(self, sk: PrivateKey, node_id: str):
        self.sk = sk
        self.node_id = node_id
        self.audit = AuditLogger()
        logger.info(f"AgentCommunicator initialized for {node_id}")

    def create_message(self, recipient_id: str, payload_dict: Dict[str, Any]) -> SignedMessage:
        """Create a cryptographically signed message."""
        payload_str = json.dumps(payload_dict, sort_keys=True)
        timestamp = time.time()
        
        # Data to sign: sender + recipient + timestamp + payload
        sign_data = f"{self.node_id}|{recipient_id}|{timestamp}|{payload_str}".encode()
        signature = sign_message(self.sk, sign_data).hex()
        
        msg = SignedMessage(
            sender_id=self.node_id,
            recipient_id=recipient_id,
            timestamp=timestamp,
            payload=payload_str,
            signature=signature,
            metadata={"version": "1.0"}
        )
        
        self.audit.log_event("OUTGOING", msg, verified=True)
        return msg

    def verify_message(self, msg: SignedMessage, sender_vk_hex: str) -> bool:
        """Verify the authenticity and integrity of a message."""
        try:
            # Reconstruct sign data
            sign_data = f"{msg.sender_id}|{msg.recipient_id}|{msg.timestamp}|{msg.payload}".encode()

            is_valid = verify_message(
                bytes.fromhex(sender_vk_hex),
                sign_data,
                bytes.fromhex(msg.signature),
            )
            
            self.audit.log_event("INCOMING", msg, verified=is_valid)
            return is_valid
            
        except Exception as e:
            logger.error(f"Verification Failed: {e}")
            self.audit.log_event("INCOMING_FAILED", msg, verified=False)
            return False

    def receive_message(self, msg_json: Dict[str, Any], sender_vk_hex: str) -> Optional[Dict[str, Any]]:
        """Process an incoming message JSON."""
        try:
            msg = SignedMessage(**msg_json)
            if self.verify_message(msg, sender_vk_hex):
                logger.info(f"✅ Verified message from {msg.sender_id}")
                return json.loads(msg.payload)
            else:
                logger.warning(f"❌ Signature Mismatch from {msg.sender_id}")
                return None
        except Exception as e:
            logger.error(f"Message parsing error: {e}")
            return None
