import os
import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("VAMSGateway")

class GatewayClient:
    """
    Interface to VAMS Gateway (Web2/Web3 Bridge).
    Handles heartbeats, task assignment, and reputation updates.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/1.0",
            "Content-Type": "application/json"
        })
        logger.info(f"Gateway Client initialized for {self.base_url}")

    def send_heartbeat(self, payload: str, signature: str) -> bool:
        """Send authenticated heartbeat."""
        try:
            url = f"{self.base_url}/heartbeat"
            response = self.session.post(
                url, 
                json={"payload": payload, "signature": signature}, 
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")
            return False

    def poll_tasks(self, node_id: str) -> list:
        """Poll for assigned tasks."""
        try:
            url = f"{self.base_url}/tasks/pending?node_id={node_id}"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("tasks", [])
            return []
        except Exception:
            return []

    def submit_result(self, task_id: str, result: Dict[str, Any], signature: str) -> bool:
        """Submit task result to gateway."""
        try:
            url = f"{self.base_url}/tasks/{task_id}/result"
            response = self.session.post(
                url,
                json={"result": result, "signature": signature},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Result submission failed: {e}")
            return False
