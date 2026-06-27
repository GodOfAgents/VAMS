from dataclasses import dataclass
from typing import Optional
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

import os
import requests

from neuron.runtime_safety import require_live_secret, require_not_live_mock

class TrailsClient:
    """OMS Trails API Client wrapper."""
    
    def __init__(self, mock_mode: Optional[bool] = None, api_url: Optional[str] = None, api_key: Optional[str] = None):
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = os.getenv("TRAILS_MOCK_MODE", "true").lower() == "true"
            
        self.api_url = api_url or os.getenv("TRAILS_API_URL", "https://api.trails.polygon.technology/v1")
        self.api_key = api_key or os.getenv("TRAILS_API_KEY", "demo-key")
        require_not_live_mock("TrailsClient", self.mock_mode)
        require_live_secret("TrailsClient", self.api_key, insecure_values={"demo-key"})
        logger.info(f"Initialized TrailsClient (mock_mode={self.mock_mode}, url={self.api_url})")

    def submit_intent(self, source: str, dest: str, payload: bytes, value: int = 0) -> TrailsReceipt:
        intent_id = hashlib.sha256(f"{source}:{dest}:{time.time()}".encode()).hexdigest()
        
        if self.mock_mode:
            logger.info(f"Mock Trails intent submitted: {intent_id}")
            # Mock settlement time of 5 seconds
            return TrailsReceipt(intent_id, "submitted", int(time.time()) + 5)
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            body = {
                "source": source,
                "destination": dest,
                "payload": payload.hex(),
                "value": value
            }
            resp = requests.post(f"{self.api_url}/intents", json=body, headers=headers, timeout=10)
            if resp.status_code in (200, 201):
                data = resp.json()
                return TrailsReceipt(
                    intent_id=data.get("intent_id"),
                    status=data.get("status", "submitted"),
                    estimated_settlement_time=int(data.get("estimated_settlement_time", time.time() + 5))
                )
            else:
                logger.error(f"Trails submit_intent API failed: Status {resp.status_code}, Response: {resp.text}")
                raise requests.HTTPError(f"Trails API returned status {resp.status_code}", response=resp)
        except Exception as e:
            logger.error(f"Error submitting Trails intent: {e}")
            raise

    def get_status(self, intent_id: str) -> TrailsStatus:
        if self.mock_mode:
            tx_hash = hashlib.sha256(intent_id.encode()).hexdigest()
            return TrailsStatus(intent_id, "settled", f"0x{tx_hash}")
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(f"{self.api_url}/intents/{intent_id}", headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return TrailsStatus(
                    intent_id=data.get("intent_id"),
                    status=data.get("status", "settled"),
                    tx_hash=data.get("tx_hash", "")
                )
            else:
                logger.error(f"Trails get_status API failed: Status {resp.status_code}")
                raise requests.HTTPError(f"Trails API returned status {resp.status_code}", response=resp)
        except Exception as e:
            logger.error(f"Error fetching Trails status: {e}")
            raise
