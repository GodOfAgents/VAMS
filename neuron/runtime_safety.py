"""
Runtime safety gates for VAMS live environments.

Live environments must not silently accept mock evidence for identity,
data availability, bridge execution, payments, or TEE trust.
"""

import os


ALLOWED_ENVIRONMENTS = frozenset({"local", "staging", "testnet", "production"})
LIVE_ENVIRONMENTS = frozenset({"staging", "testnet", "production"})
ALLOWED_NETWORKS = frozenset({"polygon-amoy", "cardano-preprod"})


class LiveModeSafetyError(RuntimeError):
    """Raised when a live environment would use an unsafe mock path."""


class RuntimeConfigurationError(RuntimeError):
    """Raised when a runtime selector is missing or outside its allowlist."""


def current_environment() -> str:
    raw_environment = os.getenv("VAMS_ENV")
    if raw_environment is None:
        raise RuntimeConfigurationError(
            "VAMS_ENV is required and must be explicitly set to local, staging, "
            "testnet, or production"
        )
    environment = raw_environment.strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        allowed = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
        raise RuntimeConfigurationError(
            f"VAMS_ENV must be one of {allowed}; received {environment!r}"
        )
    return environment


def current_network(*, required: bool = False) -> str | None:
    raw_network = os.getenv("VAMS_NETWORK")
    if raw_network is None:
        if required:
            raise RuntimeConfigurationError(
                "VAMS_NETWORK is required and must be polygon-amoy or cardano-preprod"
            )
        return None
    network = raw_network.strip().lower()
    if network not in ALLOWED_NETWORKS:
        allowed = ", ".join(sorted(ALLOWED_NETWORKS))
        raise RuntimeConfigurationError(
            f"VAMS_NETWORK must be one of {allowed}; received {network!r}"
        )
    return network


def is_live_environment() -> bool:
    return current_environment() in LIVE_ENVIRONMENTS


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def require_not_live_mock(component: str, mock_mode: bool) -> None:
    if is_live_environment() and mock_mode:
        raise LiveModeSafetyError(
            f"{component} cannot run in mock mode when VAMS_ENV={current_environment()}"
        )


def require_live_secret(component: str, value: str, *, insecure_values=None) -> None:
    insecure_values = set(insecure_values or ())
    if is_live_environment() and (not value or value in insecure_values):
        raise LiveModeSafetyError(
            f"{component} requires a non-default secret when VAMS_ENV={current_environment()}"
        )
