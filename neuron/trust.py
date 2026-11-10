"""
VAMS Neuron legacy trust-provider diagnostics.

This module reports endpoint observations and local fixtures only. It does not
verify TEE evidence or authorize provider effects.
"""

import json
import math
import os
import re
import time
import requests
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Tuple

try:
    from .runtime_safety import (
        ImmutableRuntimeConfiguration,
        LiveModeSafetyError,
        RuntimeConfigurationError,
        RuntimePolicy,
        load_runtime_policy,
        resolve_component_mock_mode,
    )
except ImportError:
    from runtime_safety import (
        ImmutableRuntimeConfiguration,
        LiveModeSafetyError,
        RuntimeConfigurationError,
        RuntimePolicy,
        load_runtime_policy,
        resolve_component_mock_mode,
    )


NEURON_MOCK_VARIABLE = "NEURON_MOCK_MODE"
TRUST_RUNTIME_COMPONENT = "VamsNeuron"
_RUNTIME_DRIFT_MESSAGE = "Trust provider runtime configuration changed during operation"
_PROVIDER_ERROR = "provider_error"
_DIAGNOSTIC_RESPONSE_LIMIT = 65_536
_DIAGNOSTIC_READ_REQUEST_LIMIT = 8_192


class _TrustRuntimeDriftError(RuntimeConfigurationError):
    """Fixed rejection for a changed process runtime or mock selection."""


class TrustStatus(Enum):
    """Health status for a diagnostic endpoint observation."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


def _bound_runtime(mock_mode: Optional[bool]) -> Tuple[RuntimePolicy, bool, Optional[str]]:
    """Bind to actual process configuration and the existing Neuron mock flag."""

    if mock_mode is not None and type(mock_mode) is not bool:
        raise RuntimeConfigurationError(
            "Malformed mock selection for TrustManager; use a boolean"
        )
    policy = load_runtime_policy(os.environ)
    effective_mock = resolve_component_mock_mode(
        TRUST_RUNTIME_COMPONENT,
        NEURON_MOCK_VARIABLE,
        mock_mode,
        policy=policy,
        environ=os.environ,
    )
    # Raw value kept only to detect later drift; the mode itself came from the resolver.
    return policy, effective_mock, os.environ.get(NEURON_MOCK_VARIABLE)  # nosemgrep: vams-direct-mock-flag-read


def _check_bound_runtime(policy: RuntimePolicy, mock_mode: bool, mock_flag: Optional[str]) -> None:
    """Reject process mode or registered mock-flag changes without details."""

    try:
        current = load_runtime_policy(os.environ)
        # Drift check against the raw value captured at startup; never selects a mode.
        if current != policy or os.environ.get(NEURON_MOCK_VARIABLE) != mock_flag:  # nosemgrep: vams-direct-mock-flag-read
            raise _TrustRuntimeDriftError(_RUNTIME_DRIFT_MESSAGE)
        current_mock = resolve_component_mock_mode(
            TRUST_RUNTIME_COMPONENT,
            NEURON_MOCK_VARIABLE,
            mock_mode,
            policy=current,
            environ=os.environ,
        )
        if current_mock != mock_mode:
            raise _TrustRuntimeDriftError(_RUNTIME_DRIFT_MESSAGE)
    except _TrustRuntimeDriftError:
        raise
    except RuntimeConfigurationError:
        raise _TrustRuntimeDriftError(_RUNTIME_DRIFT_MESSAGE) from None


@dataclass
class TrustInfo:
    """Status plus explicit provenance; never an attestation or eligibility token."""

    provider: str
    status: TrustStatus
    technology: str
    capacity: Optional[Dict[str, Any]] = None
    latency_ms: float = 0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    simulated: bool = False
    verification_scope: str = "unknown"
    evidence_classification: str = "non-authoritative"
    observations: Optional[Dict[str, Any]] = None

    @property
    def usable_as_live_evidence(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Project provenance with a constant false live-evidence flag."""

        scope = self.verification_scope
        if scope not in {"unknown", "fixture", "http_reachability", "provider_observation"}:
            scope = "unknown"
        return {
            "provider": self.provider,
            "status": self.status.value if isinstance(self.status, TrustStatus) else "unknown",
            "technology": self.technology,
            "capacity": self.capacity,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp,
            "simulated": self.simulated if type(self.simulated) is bool else True,
            "verification_scope": scope,
            "evidence_classification": "non-authoritative",
            "observations": dict(self.observations) if isinstance(self.observations, dict) else None,
            "usable_as_live_evidence": False,
        }


class TrustProvider(ImmutableRuntimeConfiguration, ABC):
    """A read-only status source bound to the current process policy."""

    name: str = "base"
    technology: str = "unknown"
    description: str = "Base trust provider"
    _immutable_runtime_fields = frozenset(
        {"runtime_policy", "mock_mode", "_mock_flag_snapshot"}
    )

    def __init__(
        self,
        endpoint: str,
        timeout: int = 15,
        *,
        mock_mode: Optional[bool] = None,
    ):
        policy, effective_mock, mock_flag = _bound_runtime(mock_mode)
        self.runtime_policy = policy
        self.mock_mode = effective_mock
        self._mock_flag_snapshot = mock_flag
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "VAMS-Neuron/0.5",
                "Accept": "text/html,application/json",
            }
        )
        self._freeze_runtime_configuration()

    def _assert_current_runtime(self) -> None:
        _check_bound_runtime(
            self.runtime_policy,
            self.mock_mode,
            self._mock_flag_snapshot,
        )

    @abstractmethod
    def get_status(self) -> TrustInfo:
        """Get non-authoritative provider status."""
        raise NotImplementedError

    def _read_chain_id_response(self, response) -> int:
        """Read a bounded identity-encoded JSON-RPC diagnostic body."""

        try:
            headers = response.headers
            if not isinstance(headers, Mapping):
                raise ValueError("invalid response headers")
            header_items = list(headers.items())
            if any(
                not isinstance(name, str) or not isinstance(value, str)
                for name, value in header_items
            ):
                raise ValueError("invalid response headers")
            encodings = [
                value
                for name, value in header_items
                if name.lower() == "content-encoding"
            ]
        except _TrustRuntimeDriftError:
            raise
        except Exception:
            raise ValueError("invalid response headers") from None
        if len(encodings) > 1 or (
            encodings
            and (
                not isinstance(encodings[0], str)
                or encodings[0].strip().lower() != "identity"
            )
        ):
            raise ValueError("unsupported response encoding")

        try:
            reader = response.raw.read
        except _TrustRuntimeDriftError:
            raise
        except Exception:
            raise ValueError("invalid response reader") from None
        if not callable(reader):
            raise ValueError("invalid response reader")

        body = bytearray()
        while True:
            self._assert_current_runtime()
            remaining = _DIAGNOSTIC_RESPONSE_LIMIT - len(body)
            amount = min(_DIAGNOSTIC_READ_REQUEST_LIMIT, remaining + 1)
            chunk = reader(amount, decode_content=False)
            # Do not inspect or retain bytes returned after a policy change.
            self._assert_current_runtime()
            if not isinstance(chunk, bytes) or len(chunk) > amount:
                raise ValueError("invalid response chunk")
            if not chunk:
                break
            if len(chunk) > remaining:
                raise ValueError("response body exceeds diagnostic limit")
            body.extend(chunk)

        data = json.loads(bytes(body).decode("utf-8", errors="strict"))
        if (
            type(data) is not dict
            or data.get("jsonrpc") != "2.0"
            or type(data.get("id")) is not int
            or data.get("id") != 1
        ):
            raise ValueError("invalid JSON-RPC response")
        result = data.get("result")
        if (
            type(result) is not str
            or re.fullmatch(r"0[xX][0-9a-fA-F]+", result) is None
        ):
            raise ValueError("invalid JSON-RPC result")
        return int(result[2:], 16)

    def _observe_status(
        self,
        request: Callable[[], Any],
        *,
        parse_chain_id: bool = False,
    ) -> TrustInfo:
        """Read one status response, close it once, and never format provider errors."""

        self._assert_current_runtime()
        response = None
        primary_error = None
        close_error = None
        final_error = None
        status_code = None
        chain_id = None
        latency_ms = 0.0
        status = TrustStatus.OFFLINE
        error = _PROVIDER_ERROR

        try:
            started = time.monotonic()
            response = request()
            self._assert_current_runtime()
            status_code = response.status_code
            self._assert_current_runtime()
            if type(status_code) is not int or not 100 <= status_code <= 599:
                raise ValueError("invalid HTTP status")
            if status_code == 200 and parse_chain_id:
                chain_id = self._read_chain_id_response(response)
            latency_ms = (time.monotonic() - started) * 1000
            status = TrustStatus.HEALTHY if status_code == 200 else TrustStatus.DEGRADED
            error = None if status == TrustStatus.HEALTHY else f"Status {status_code}"
        except BaseException as exc:
            primary_error = exc
        finally:
            if response is not None:
                try:
                    response.close()
                except BaseException as exc:
                    close_error = exc
            try:
                self._assert_current_runtime()
            except BaseException as exc:
                final_error = exc

        runtime_drift = next(
            (
                exc
                for exc in (primary_error, close_error, final_error)
                if isinstance(exc, _TrustRuntimeDriftError)
            ),
            None,
        )
        if runtime_drift is not None:
            raise runtime_drift
        for exc in (primary_error, close_error, final_error):
            if exc is not None and not isinstance(exc, Exception):
                raise exc
        if primary_error is not None or close_error is not None or final_error is not None:
            status = TrustStatus.OFFLINE
            error = _PROVIDER_ERROR
            chain_id = None
        observations = {"chain_id": chain_id} if chain_id is not None else None
        return TrustInfo(
            provider=self.name,
            status=status,
            technology=self.technology,
            capacity=None,
            latency_ms=latency_ms,
            error=error,
            simulated=False,
            verification_scope="http_reachability",
            evidence_classification="non-authoritative",
            observations=observations,
        )

    def generate_proof(self) -> Dict[str, Any]:
        """Reject legacy proof generation until an authenticated verifier exists."""

        raise LiveModeSafetyError("authentic_verifier_unavailable")


class PhalaProvider(TrustProvider):
    """Phala endpoint status; HTTP success is not SGX evidence."""

    name = "phala"
    technology = "Intel SGX"
    description = "Phat Contracts - Private Compute"

    def __init__(
        self,
        endpoint: str = "https://phala.network",
        timeout: int = 15,
        *,
        mock_mode: Optional[bool] = None,
    ):
        super().__init__(endpoint, timeout, mock_mode=mock_mode)

    def get_status(self) -> TrustInfo:
        """Return a non-authoritative HTTP reachability observation."""

        return self._observe_status(
            lambda: self.session.get(
                self.endpoint,
                timeout=self.timeout,
                stream=True,
                allow_redirects=False,
            )
        )


class MarlinProvider(TrustProvider):
    """Marlin website status; HTTP success is not Nitro evidence."""

    name = "marlin"
    technology = "AWS Nitro"
    description = "Oyster - TEE Coprocessors"

    def __init__(
        self,
        endpoint: str = "https://www.marlin.org",
        timeout: int = 15,
        *,
        mock_mode: Optional[bool] = None,
    ):
        super().__init__(endpoint, timeout, mock_mode=mock_mode)

    def get_status(self) -> TrustInfo:
        """Return a non-authoritative HTTP reachability observation."""

        return self._observe_status(
            lambda: self.session.get(
                self.endpoint,
                timeout=self.timeout,
                stream=True,
                allow_redirects=False,
            )
        )


class AutomataProvider(TrustProvider):
    """Automata JSON-RPC status; chain ID is an unverified observation only."""

    name = "automata"
    technology = "Multi-Prover"
    description = "1RPC - Privacy Relay"

    def __init__(
        self,
        endpoint: str = "https://1rpc.io/ata",
        timeout: int = 15,
        *,
        mock_mode: Optional[bool] = None,
    ):
        super().__init__(endpoint, timeout, mock_mode=mock_mode)

    def get_status(self) -> TrustInfo:
        """Return a non-authoritative JSON-RPC observation with a closed response."""

        return self._observe_status(
            lambda: self.session.post(
                self.endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_chainId",
                    "params": [],
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity",
                },
                timeout=self.timeout,
                stream=True,
                allow_redirects=False,
            ),
            parse_chain_id=True,
        )


class TrustManager(ImmutableRuntimeConfiguration):
    """Manage read-only TEE endpoint observations and local status fixtures."""

    _immutable_runtime_fields = frozenset(
        {"runtime_policy", "mock_mode", "_mock_flag_snapshot"}
    )

    def __init__(
        self,
        providers: Optional[List[TrustProvider]] = None,
        mock_mode: bool = False,
    ):
        if type(mock_mode) is not bool:
            raise RuntimeConfigurationError(
                "Malformed mock selection for TrustManager; use a boolean"
            )
        policy, effective_mock, mock_flag = _bound_runtime(mock_mode)
        self.runtime_policy = policy
        self.mock_mode = effective_mock
        self._mock_flag_snapshot = mock_flag
        if providers is None:
            providers = [
                PhalaProvider(mock_mode=effective_mock),
                MarlinProvider(mock_mode=effective_mock),
                AutomataProvider(mock_mode=effective_mock),
            ]
        self.providers: Dict[str, TrustProvider] = {p.name: p for p in providers}
        self.status_cache: Dict[str, TrustInfo] = {}
        self._freeze_runtime_configuration()

    def _assert_current_runtime(self) -> None:
        try:
            _check_bound_runtime(
                self.runtime_policy,
                self.mock_mode,
                self._mock_flag_snapshot,
            )
        except RuntimeConfigurationError:
            self.status_cache = {}
            raise

    @staticmethod
    def _offline_info(name: str, technology: str, scope: str) -> TrustInfo:
        return TrustInfo(
            provider=name,
            status=TrustStatus.OFFLINE,
            technology=technology,
            error=_PROVIDER_ERROR,
            simulated=False,
            verification_scope=scope,
            evidence_classification="non-authoritative",
        )

    def _normalize_status(self, name: str, provider, info: TrustInfo) -> TrustInfo:
        """Copy provider status while overwriting all claimed provenance/capacity."""

        if not isinstance(info, TrustInfo):
            return self._offline_info(name, "unknown", "provider_observation")
        provider_type = type(provider)
        trusted_builtin = provider_type in (PhalaProvider, MarlinProvider, AutomataProvider)
        scope = "http_reachability" if trusted_builtin else "provider_observation"
        technology = getattr(provider_type, "technology", "unknown")
        if type(technology) is not str:
            technology = "unknown"
        status = info.status if isinstance(info.status, TrustStatus) else TrustStatus.UNKNOWN
        error = None
        if status == TrustStatus.OFFLINE:
            error = _PROVIDER_ERROR
        elif status == TrustStatus.DEGRADED:
            error = "provider_degraded"
        latency = info.latency_ms
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
            latency = 0.0
        timestamp = info.timestamp
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
            timestamp = time.time()
        observations = None
        if provider_type is AutomataProvider and isinstance(info.observations, dict):
            chain_id = info.observations.get("chain_id")
            if type(chain_id) is int and chain_id >= 0:
                observations = {"chain_id": chain_id}
        return TrustInfo(
            provider=name,
            status=status,
            technology=technology,
            capacity=None,
            latency_ms=float(latency),
            error=error,
            timestamp=float(timestamp),
            simulated=False,
            verification_scope=scope,
            evidence_classification="non-authoritative",
            observations=observations,
        )

    def get_provider(self, name: str) -> Optional[TrustProvider]:
        self._assert_current_runtime()
        return self.providers.get(name)

    def check_all_status(self) -> Dict[str, TrustInfo]:
        """Build a complete snapshot, then replace the cache only after checks pass."""

        self._assert_current_runtime()
        temporary: Dict[str, TrustInfo] = {}
        try:
            if self.mock_mode:
                temporary = self._get_mock_status()
            else:
                for name, provider in self.providers.items():
                    self._assert_current_runtime()
                    try:
                        info = provider.get_status()
                    except _TrustRuntimeDriftError:
                        raise
                    except BaseException as exc:
                        if not isinstance(exc, Exception):
                            raise
                        raise RuntimeError(_PROVIDER_ERROR) from None
                    self._assert_current_runtime()
                    temporary[name] = self._normalize_status(name, provider, info)
            self._assert_current_runtime()
        except BaseException:
            self.status_cache = {}
            raise
        self.status_cache = temporary
        return dict(temporary)

    def _get_mock_status(self) -> Dict[str, TrustInfo]:
        """Build local-only fixtures; this helper cannot authorize mock status."""

        self._assert_current_runtime()
        if not self.mock_mode:
            raise LiveModeSafetyError("TrustManager mock status is not authorized")
        return {
            "phala": TrustInfo(
                provider="phala",
                status=TrustStatus.HEALTHY,
                technology="Intel SGX",
                capacity={"network": "mock", "mock": True},
                latency_ms=50.0,
                simulated=True,
                verification_scope="fixture",
                evidence_classification="non-authoritative",
            ),
            "marlin": TrustInfo(
                provider="marlin",
                status=TrustStatus.HEALTHY,
                technology="AWS Nitro",
                capacity={"service": "mock", "mock": True},
                latency_ms=45.0,
                simulated=True,
                verification_scope="fixture",
                evidence_classification="non-authoritative",
            ),
            "automata": TrustInfo(
                provider="automata",
                status=TrustStatus.HEALTHY,
                technology="Multi-Prover",
                capacity={"chain_id": 1, "mock": True},
                latency_ms=40.0,
                simulated=True,
                verification_scope="fixture",
                evidence_classification="non-authoritative",
            ),
        }

    def get_healthy_providers(self) -> List[str]:
        """No unverified endpoint observation qualifies a TEE provider."""

        self._assert_current_runtime()
        return []

    def list_providers(self) -> List[Dict[str, Any]]:
        """List provider descriptors with status provenance, never proof eligibility."""

        self._assert_current_runtime()
        result = []
        for name, provider in self.providers.items():
            info = self.status_cache.get(name)
            status = info if isinstance(info, TrustInfo) else None
            provider_type = type(provider)
            builtin = provider_type in (PhalaProvider, MarlinProvider, AutomataProvider)
            technology = getattr(type(provider), "technology", "unknown")
            description = getattr(type(provider), "description", "unknown provider")
            endpoint = getattr(provider, "endpoint", "")
            if type(technology) is not str:
                technology = "unknown"
            if type(description) is not str:
                description = "unknown provider"
            if type(endpoint) is not str:
                endpoint = ""
            if self.mock_mode:
                simulated = True
                scope = "fixture"
                capacity = {"mock": True} if status else None
            else:
                simulated = False
                scope = (
                    "http_reachability"
                    if status is not None and builtin
                    else ("provider_observation" if status is not None else "unknown")
                )
                capacity = None
            observations = None
            if status is not None and provider_type is AutomataProvider and isinstance(status.observations, dict):
                chain_id = status.observations.get("chain_id")
                if type(chain_id) is int and chain_id >= 0:
                    observations = {"chain_id": chain_id}
            latency = status.latency_ms if status else None
            if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
                latency = None
            result.append(
                {
                    "name": name,
                    "technology": technology,
                    "description": description,
                    "endpoint": endpoint,
                    "status": status.status.value if status and isinstance(status.status, TrustStatus) else "unknown",
                    "latency_ms": latency,
                    "capacity": capacity,
                    "observations": observations,
                    "simulated": simulated,
                    "verification_scope": scope,
                    "evidence_classification": "non-authoritative",
                    "usable_as_live_evidence": False,
                }
            )
        self._assert_current_runtime()
        return result


def create_trust_manager(mock_mode: bool = False) -> TrustManager:
    """Create the centrally bound trust diagnostics manager."""

    return TrustManager(mock_mode=mock_mode)
