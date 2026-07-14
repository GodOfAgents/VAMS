import os
import json
import logging
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Optional

from neuron.runtime_safety import is_live_environment

logger = logging.getLogger("VAMSGateway")

class GatewayClient:
    """
    Interface to VAMS Gateway (Web2/Web3 Bridge).
    Handles heartbeats, task assignment, and reputation updates.
    """
    
    def __init__(self, base_url: str):
        self.base_url = self._validated_base_url(base_url)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/1.0",
            "Content-Type": "application/json"
        })
        self.registered = False
        self.agent_id = None
        logger.info(f"Gateway Client initialized for {self.base_url}")

    @staticmethod
    def _validated_base_url(base_url: str) -> str:
        """Require TLS for live gateways and loopback-only plaintext locally."""

        candidate = base_url.strip().rstrip('/')
        parsed = urlparse(candidate)
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("VAMS gateway URL must contain a host and no userinfo")
        if parsed.scheme == "https":
            return candidate
        if (
            parsed.scheme == "http"
            and not is_live_environment()
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            return candidate
        if is_live_environment():
            raise ValueError("live VAMS gateway URL must use HTTPS")
        raise ValueError("plaintext VAMS gateway URL is restricted to loopback")

    def register_agent(self, node_id: str, public_key: str, stake_amount: float, capabilities: Dict[str, Any] = None) -> Optional[str]:
        """
        Register this agent with the VAMS Gateway.
        Returns agent_id on success.
        """
        try:
            url = f"{self.base_url}/agents/register"
            payload = {
                "node_id": node_id,
                "public_key": public_key,
                "stake_amount": stake_amount,
                "capabilities": capabilities or {"compute": True, "storage": True},
                "version": "1.0.0"
            }
            response = self.session.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.agent_id = data.get("agent_id", node_id)
                self.registered = True
                logger.info(f"Agent registered successfully: {self.agent_id}")
                return self.agent_id
            elif response.status_code == 409:
                # Already registered
                logger.info(f"Agent already registered: {node_id}")
                self.agent_id = node_id
                self.registered = True
                return node_id
            else:
                logger.error(f"Registration failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None

    def deregister_agent(self, signature: str) -> bool:
        """Deregister this agent from the gateway."""
        if not self.agent_id:
            logger.warning("Cannot deregister: No agent_id")
            return False
            
        try:
            url = f"{self.base_url}/agents/{self.agent_id}/deregister"
            response = self.session.post(url, json={"signature": signature}, timeout=10)
            if response.status_code == 200:
                self.registered = False
                logger.info(f"Agent {self.agent_id} deregistered")
                return True
            return False
        except Exception as e:
            logger.error(f"Deregistration failed: {e}")
            return False

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
