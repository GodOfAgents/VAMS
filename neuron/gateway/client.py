import os
import json
import logging
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Mapping, Optional

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
)

logger = logging.getLogger("VAMSGateway")


class _GatewayRuntimeDriftError(RuntimeConfigurationError):
    """Private fixed-message denial from this client’s current-policy guard."""

    def __init__(self):
        super().__init__("GatewayClient runtime policy changed; operation denied")


def _read_ambient_policy() -> RuntimePolicy:
    try:
        policy = load_runtime_policy(os.environ)
    except Exception:
        raise RuntimeConfigurationError("GatewayClient runtime policy is invalid") from None
    if type(policy) is not RuntimePolicy:
        raise RuntimeConfigurationError("GatewayClient runtime policy is invalid")
    return policy

class GatewayClient(ImmutableRuntimeConfiguration):
    """
    Interface to VAMS Gateway (Web2/Web3 Bridge).
    Handles heartbeats, task assignment, and reputation updates.
    """
    
    _immutable_runtime_fields = frozenset({"runtime_policy", "base_url"})

    def __init__(
        self,
        base_url: str,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
    ):
        observed = _read_ambient_policy()
        if runtime_policy is not None:
            if type(runtime_policy) is not RuntimePolicy:
                raise RuntimeConfigurationError("Malformed supplied runtime policy for GatewayClient")
            if runtime_policy != observed:
                raise RuntimeConfigurationError("Conflicting runtime policy for GatewayClient")
        if environ is not None:
            if not isinstance(environ, Mapping):
                raise RuntimeConfigurationError("Malformed supplied environment for GatewayClient")
            try:
                supplied = load_runtime_policy(environ)
            except Exception:
                raise RuntimeConfigurationError("Supplied GatewayClient environment is invalid") from None
            if type(supplied) is not RuntimePolicy or supplied != observed:
                raise RuntimeConfigurationError("Conflicting environment policy for GatewayClient")
        if observed.is_live:
            raise LiveModeSafetyError(
                "Legacy GatewayClient is unavailable in live modes until M2 client authentication is implemented"
            )

        self.runtime_policy = runtime_policy if runtime_policy is not None else observed
        self.base_url = self._validated_base_url(base_url)
        self._require_current_runtime()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VAMS-Neuron/1.0",
            "Content-Type": "application/json"
        })
        self.registered = False
        self.agent_id = None
        logger.info("Gateway Client initialized")
        self._freeze_runtime_configuration()

    def _require_current_runtime(self) -> None:
        """Require the actual process policy to remain this non-live policy."""

        try:
            if type(self.runtime_policy) is not RuntimePolicy or self.runtime_policy.is_live:
                raise _GatewayRuntimeDriftError()
            current = _read_ambient_policy()
            if current.is_live or current != self.runtime_policy:
                raise _GatewayRuntimeDriftError()
        except _GatewayRuntimeDriftError:
            raise
        except Exception:
            raise _GatewayRuntimeDriftError() from None

    def _validated_base_url(self, base_url: str) -> str:
        """Require TLS for live gateways and loopback-only plaintext locally."""

        candidate = base_url.strip().rstrip('/')
        parsed = urlparse(candidate)
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("VAMS gateway URL must contain a host and no userinfo")
        if parsed.scheme == "https":
            return candidate
        if (
            parsed.scheme == "http"
            and not self.runtime_policy.is_live
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            return candidate
        if self.runtime_policy.is_live:
            raise ValueError("live VAMS gateway URL must use HTTPS")
        raise ValueError("plaintext VAMS gateway URL is restricted to loopback")

    def register_agent(self, node_id: str, public_key: str, stake_amount: float, capabilities: Dict[str, Any] = None) -> Optional[str]:
        """
        Register this agent with the VAMS Gateway.
        Returns agent_id on success.
        """
        self._require_current_runtime()
        try:
            url = f"{self.base_url}/agents/register"
            payload = {
                "node_id": node_id,
                "public_key": public_key,
                "stake_amount": stake_amount,
                "capabilities": capabilities or {"compute": True, "storage": True},
                "version": "1.0.0"
            }
            self._require_current_runtime()
            response = self.session.post(url, json=payload, timeout=10, allow_redirects=False)
            self._require_current_runtime()
            status = response.status_code
            self._require_current_runtime()

            if status == 200:
                self._require_current_runtime()
                data = response.json()
                self._require_current_runtime()
                agent_id = data.get("agent_id", node_id)
                self._require_current_runtime()
                self.agent_id = agent_id
                self.registered = True
                logger.info(f"Agent registered successfully: {self.agent_id}")
                return self.agent_id
            elif status == 409:
                # Already registered
                self._require_current_runtime()
                logger.info(f"Agent already registered: {node_id}")
                self.agent_id = node_id
                self.registered = True
                return node_id
            else:
                logger.error("Registration failed")
                return None
                
        except _GatewayRuntimeDriftError:
            raise
        except Exception:
            self._require_current_runtime()
            logger.error("Registration error")
            return None

    def deregister_agent(self, signature: str) -> bool:
        """Deregister this agent from the gateway."""
        self._require_current_runtime()
        if not self.agent_id:
            logger.warning("Cannot deregister: No agent_id")
            return False
            
        try:
            url = f"{self.base_url}/agents/{self.agent_id}/deregister"
            self._require_current_runtime()
            response = self.session.post(url, json={"signature": signature}, timeout=10, allow_redirects=False)
            self._require_current_runtime()
            status = response.status_code
            self._require_current_runtime()
            if status == 200:
                self._require_current_runtime()
                self.registered = False
                logger.info(f"Agent {self.agent_id} deregistered")
                return True
            return False
        except _GatewayRuntimeDriftError:
            raise
        except Exception:
            self._require_current_runtime()
            logger.error("Deregistration failed")
            return False

    def send_heartbeat(self, payload: str, signature: str) -> bool:
        """Send authenticated heartbeat."""
        self._require_current_runtime()
        try:
            url = f"{self.base_url}/heartbeat"
            body = {"payload": payload, "signature": signature}
            self._require_current_runtime()
            response = self.session.post(
                url,
                json=body,
                timeout=5,
                allow_redirects=False
            )
            self._require_current_runtime()
            status = response.status_code
            self._require_current_runtime()
            return status == 200
        except _GatewayRuntimeDriftError:
            raise
        except Exception:
            self._require_current_runtime()
            logger.debug("Heartbeat failed")
            return False

    def poll_tasks(self, node_id: str) -> list:
        """Poll for assigned tasks."""
        self._require_current_runtime()
        try:
            url = f"{self.base_url}/tasks/pending?node_id={node_id}"
            self._require_current_runtime()
            response = self.session.get(url, timeout=5, allow_redirects=False)
            self._require_current_runtime()
            status = response.status_code
            self._require_current_runtime()
            if status == 200:
                self._require_current_runtime()
                data = response.json()
                self._require_current_runtime()
                tasks = data.get("tasks", [])
                self._require_current_runtime()
                return tasks
            return []
        except _GatewayRuntimeDriftError:
            raise
        except Exception:
            self._require_current_runtime()
            return []

    def submit_result(self, task_id: str, result: Dict[str, Any], signature: str) -> bool:
        """Submit task result to gateway."""
        self._require_current_runtime()
        try:
            url = f"{self.base_url}/tasks/{task_id}/result"
            body = {"result": result, "signature": signature}
            self._require_current_runtime()
            response = self.session.post(
                url,
                json=body,
                timeout=10,
                allow_redirects=False
            )
            self._require_current_runtime()
            status = response.status_code
            self._require_current_runtime()
            return status == 200
        except _GatewayRuntimeDriftError:
            raise
        except Exception:
            self._require_current_runtime()
            logger.error("Result submission failed")
            return False
