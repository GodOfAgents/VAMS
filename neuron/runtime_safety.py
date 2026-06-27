"""
Runtime safety gates for VAMS live environments.

Live environments must not silently accept mock evidence for identity,
data availability, bridge execution, payments, or TEE trust.
"""

import os


LIVE_ENVIRONMENTS = {"staging", "testnet", "production"}


class LiveModeSafetyError(RuntimeError):
    """Raised when a live environment would use an unsafe mock path."""


def current_environment() -> str:
    return os.getenv("VAMS_ENV", "local").strip().lower()


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
