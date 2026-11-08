"""Strict runtime-mode policy shared by VAMS process boundaries.

``VAMS_ENV`` is the single authoritative runtime-mode selector. Runtime mode
is never inferred from credentials, provider availability, or mock flags.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional


RUNTIME_MODE_VARIABLE = "VAMS_ENV"
GATEWAY_MOCK_VARIABLE = "VAMS_MOCK_MODE"

# Complete M1 registry. Live preflight parses every flag here even when the
# corresponding client is not constructed, so a dormant mock request cannot be
# promoted as a valid live process configuration.
REGISTERED_MOCK_VARIABLES = (
    GATEWAY_MOCK_VARIABLE,
    "AKASH_MOCK_MODE",
    "ANCHOR_MOCK_MODE",
    "AVAIL_ADAPTER_MOCK_MODE",
    "AVAIL_MOCK_MODE",
    "BRIDGE_ISM_MOCK_MODE",
    "BRIDGE_MOCK_MODE",
    "CELESTIA_LIGHT_MOCK_MODE",
    "COGNITIVE_SYNC_MOCK_MODE",
    "COINME_MOCK_MODE",
    "DA_ROUTER_MOCK_MODE",
    "EIGENDA_ADAPTER_MOCK_MODE",
    "EIGENDA_MOCK_MODE",
    "ESCROW_STATE_MOCK_MODE",
    "IAGON_MOCK_MODE",
    "MEV_MOCK_MODE",
    "NEURON_MOCK_MODE",
    "OMS_MOCK_MODE",
    "PAYMENT_CHANNEL_MOCK_MODE",
    "PHALA_MOCK_MODE",
    "SENTINEL_MOCK_MODE",
    "TRAILS_MOCK_MODE",
    "VAMS_IVT_MOCK",
    "X402_MOCK_MODE",
    "X402_RECOVERY_MOCK_MODE",
)

REGISTERED_MOCK_COMPONENTS = {
    "VAMS_MOCK_MODE": "gateway DA audit",
    "AKASH_MOCK_MODE": "AkashOrchestratorSDK",
    "ANCHOR_MOCK_MODE": "L1StateAnchor",
    "AVAIL_ADAPTER_MOCK_MODE": "AvailDAAdapter",
    "AVAIL_MOCK_MODE": "AvailDASDK",
    "BRIDGE_ISM_MOCK_MODE": "MultiISMVerifier",
    "BRIDGE_MOCK_MODE": "BridgeExecutor",
    "CELESTIA_LIGHT_MOCK_MODE": "CelestiaLightClient",
    "COGNITIVE_SYNC_MOCK_MODE": "CognitiveDriftDetector",
    "COINME_MOCK_MODE": "CoinmeClient",
    "DA_ROUTER_MOCK_MODE": "DARouter",
    "EIGENDA_ADAPTER_MOCK_MODE": "EigenDAAdapter",
    "EIGENDA_MOCK_MODE": "EigenDASDK",
    "ESCROW_STATE_MOCK_MODE": "EscrowStateClient",
    "IAGON_MOCK_MODE": "IagonStorageSDK",
    "MEV_MOCK_MODE": "EncryptedMempool",
    "NEURON_MOCK_MODE": "VamsNeuron",
    "OMS_MOCK_MODE": "OMSIdentityVerifier",
    "PAYMENT_CHANNEL_MOCK_MODE": "PaymentChannelManager",
    "PHALA_MOCK_MODE": "PhalaTEE",
    "SENTINEL_MOCK_MODE": "VAMSSentinelNode",
    "TRAILS_MOCK_MODE": "TrailsClient",
    "VAMS_IVT_MOCK": "InterruptVectorTable",
    "X402_MOCK_MODE": "X402Client",
    "X402_RECOVERY_MOCK_MODE": "X402InterruptHandler",
}


class RuntimeMode(str, Enum):
    """Canonical, case-sensitive runtime modes accepted by VAMS."""

    TEST = "test"
    LOCAL = "local"
    DEMO = "demo"
    STAGING = "staging"
    TESTNET = "testnet"
    PRODUCTION = "production"


LIVE_MODES = frozenset(
    {RuntimeMode.STAGING, RuntimeMode.TESTNET, RuntimeMode.PRODUCTION}
)
LIVE_ENVIRONMENTS = frozenset(mode.value for mode in LIVE_MODES)


class LiveModeSafetyError(RuntimeError):
    """Raised when runtime configuration would weaken a safety boundary."""


class RuntimeConfigurationError(LiveModeSafetyError):
    """Raised when the central runtime-mode contract is invalid."""


class ImmutableRuntimeConfiguration:
    """Prevent effective runtime/component configuration from drifting in place."""

    _immutable_runtime_fields: frozenset[str] = frozenset()

    def _freeze_runtime_configuration(self) -> None:
        object.__setattr__(self, "_runtime_configuration_frozen", True)

    def __setattr__(self, name: str, value: object) -> None:
        frozen = getattr(self, "_runtime_configuration_frozen", False)
        if frozen and (
            name in {"_runtime_configuration_frozen", "_immutable_runtime_fields"}
            or name in self._immutable_runtime_fields
        ):
            raise RuntimeConfigurationError(
                f"{type(self).__name__} runtime configuration is immutable"
            )
        object.__setattr__(self, name, value)


def _display_value(value: object) -> str:
    """Return a bounded diagnostic representation of a non-secret mode value."""

    rendered = repr(value)
    return rendered if len(rendered) <= 80 else rendered[:77] + "..."


def _parse_mode(environ: Mapping[str, str]) -> RuntimeMode:
    raw = environ.get(RUNTIME_MODE_VARIABLE)
    accepted = ", ".join(mode.value for mode in RuntimeMode)
    if raw is None:
        raise RuntimeConfigurationError(
            f"{RUNTIME_MODE_VARIABLE} is required and must be one of: {accepted}"
        )
    if not isinstance(raw, str) or not raw or raw != raw.strip() or raw != raw.lower():
        raise RuntimeConfigurationError(
            f"Malformed {RUNTIME_MODE_VARIABLE} value {_display_value(raw)}; "
            f"use one exact lowercase value: {accepted}"
        )
    try:
        return RuntimeMode(raw)
    except ValueError as exc:
        raise RuntimeConfigurationError(
            f"Unknown {RUNTIME_MODE_VARIABLE} value {_display_value(raw)}; "
            f"use one of: {accepted}"
        ) from exc


def _parse_optional_boolean(
    environ: Mapping[str, str], name: str, *, component: str = "gateway DA audit"
) -> bool:
    raw = environ.get(name)
    if raw is None:
        return False
    if raw not in {"true", "false"}:
        raise RuntimeConfigurationError(
            f"Malformed {name} for {component}; use exactly 'true' or 'false'"
        )
    return raw == "true"


@dataclass(frozen=True)
class RuntimePolicy:
    """Immutable effective runtime policy for one process startup."""

    mode: RuntimeMode
    gateway_mock_enabled: bool
    enabled_mock_variables: tuple[str, ...] = ()

    @classmethod
    def from_environment(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> "RuntimePolicy":
        source = os.environ if environ is None else environ
        mode = _parse_mode(source)
        enabled_mock_variables = tuple(
            variable
            for variable in REGISTERED_MOCK_VARIABLES
            if _parse_optional_boolean(
                source,
                variable,
                component="registered runtime component",
            )
        )
        gateway_mock_enabled = GATEWAY_MOCK_VARIABLE in enabled_mock_variables
        if mode in LIVE_MODES and enabled_mock_variables:
            offending = enabled_mock_variables[0]
            component = REGISTERED_MOCK_COMPONENTS[offending]
            raise RuntimeConfigurationError(
                f"{component} registered mock mode ({offending}=true) is forbidden when "
                f"{RUNTIME_MODE_VARIABLE}={mode.value}"
            )
        return cls(
            mode=mode,
            gateway_mock_enabled=gateway_mock_enabled,
            enabled_mock_variables=enabled_mock_variables,
        )

    @property
    def is_live(self) -> bool:
        return self.mode in LIVE_MODES

    @property
    def is_demo(self) -> bool:
        return self.mode is RuntimeMode.DEMO

    @property
    def runtime_classification(self) -> str:
        return "live" if self.is_live else "non-live"

    @property
    def evidence_classification(self) -> str:
        # A live mode is necessary but never sufficient proof of a live result.
        return "runtime-mode-only" if self.is_live else "non-authoritative"

    def sanitized_summary(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "runtime_classification": self.runtime_classification,
            "evidence_classification": self.evidence_classification,
            "gateway_mock_enabled": self.gateway_mock_enabled,
        }

    def authorize_component_mock(self, component: str, requested: bool) -> bool:
        """Authorize an explicitly requested component mock in this policy."""

        if not isinstance(requested, bool):
            raise RuntimeConfigurationError(
                f"Malformed mock selection for {component}; use a boolean"
            )
        if requested and self.is_live:
            raise LiveModeSafetyError(
                f"{component} cannot run in mock mode when "
                f"{RUNTIME_MODE_VARIABLE}={self.mode.value}"
            )
        return requested


def load_runtime_policy(
    environ: Optional[Mapping[str, str]] = None,
) -> RuntimePolicy:
    """Parse and validate one immutable effective runtime policy."""

    return RuntimePolicy.from_environment(environ)


def resolve_component_mock_mode(
    component: str,
    variable: str,
    explicit: Optional[bool],
    *,
    policy: Optional[RuntimePolicy] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> bool:
    """Resolve one component mock flag once, rejecting ambiguity and live use."""

    source = os.environ if environ is None else environ
    observed = load_runtime_policy(source)
    if policy is not None and policy != observed:
        raise RuntimeConfigurationError(
            f"Conflicting runtime policy for {component}; supplied policy does not "
            f"match effective {RUNTIME_MODE_VARIABLE} or registered mock flags"
        )
    effective = policy or observed
    configured = _parse_optional_boolean(source, variable, component=component)
    if explicit is not None and not isinstance(explicit, bool):
        raise RuntimeConfigurationError(
            f"Malformed explicit mock selection for {component}; use a boolean"
        )
    if explicit is not None and variable in source and explicit != configured:
        raise RuntimeConfigurationError(
            f"Conflicting mock configuration for {component}: explicit selection "
            f"does not match {variable}"
        )
    requested = configured if explicit is None else explicit
    return effective.authorize_component_mock(component, requested)


def current_environment(policy: Optional[RuntimePolicy] = None) -> str:
    return (policy or load_runtime_policy()).mode.value


def is_live_environment(policy: Optional[RuntimePolicy] = None) -> bool:
    return (policy or load_runtime_policy()).is_live


def env_flag(name: str, default: bool = False) -> bool:
    """Legacy client flag reader retained until the scoped M1.2 migrations."""

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def require_not_live_mock(
    component: str,
    mock_mode: bool,
    *,
    policy: Optional[RuntimePolicy] = None,
) -> None:
    effective = policy or load_runtime_policy()
    if effective.is_live and mock_mode:
        raise LiveModeSafetyError(
            f"{component} cannot run in mock mode when "
            f"{RUNTIME_MODE_VARIABLE}={effective.mode.value}"
        )


def require_live_secret(
    component: str,
    value: str,
    *,
    insecure_values=None,
    policy: Optional[RuntimePolicy] = None,
) -> None:
    effective = policy or load_runtime_policy()
    insecure_values = set(insecure_values or ())
    if effective.is_live and (not value or value in insecure_values):
        raise LiveModeSafetyError(
            f"{component} requires a non-default secret when "
            f"{RUNTIME_MODE_VARIABLE}={effective.mode.value}"
        )
