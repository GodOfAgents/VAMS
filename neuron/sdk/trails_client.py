from dataclasses import dataclass
import time
import hashlib
import logging

logger = logging.getLogger("VAMS-Trails")

@dataclass
class TrailsReceipt:
    intent_id: str
    status: str
    estimated_settlement_time: int

@dataclass
class TrailsStatus:
    intent_id: str
    status: str
    tx_hash: str

class TrailsClient:
    """OMS Trails API Client wrapper."""
    
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def submit_intent(self, source: str, dest: str, payload: bytes, value: int = 0) -> TrailsReceipt:
        intent_id = hashlib.sha256(f"{source}:{dest}:{time.time()}".encode()).hexdigest()
        if self.mock_mode:
            logger.info(f"Mock Trails intent submitted: {intent_id}")
            # Mock settlement time of 5 seconds
            return TrailsReceipt(intent_id, "submitted", int(time.time()) + 5)
        raise NotImplementedError("Live Trails API not yet integrated")

    def get_status(self, intent_id: str) -> TrailsStatus:
        if self.mock_mode:
            tx_hash = hashlib.sha256(intent_id.encode()).hexdigest()
            return TrailsStatus(intent_id, "settled", f"0x{tx_hash}")
        raise NotImplementedError("Live Trails API not yet integrated")
