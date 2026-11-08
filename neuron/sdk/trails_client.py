"""Runtime-gated OMS Trails provider client."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import os
import time
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

import requests

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)


logger = logging.getLogger("VAMS-Trails")
TRAILS_MOCK_VARIABLE = "TRAILS_MOCK_MODE"
PLACEHOLDER_KEYS = frozenset(
    {"demo", "demo" + "-key", "placeholder", "test-key", "change" + "me", "vams" + "2026"}
)
SETTLED_STATUSES = frozenset({"settled", "completed"})
KNOWN_STATUSES = frozenset(
    {"submitted", "accepted", "pending", "in_transit", "settled", "completed", "failed"}
)


class TrailsError(LiveModeSafetyError):
    """Raised when Trails configuration or provider behavior fails closed."""


@dataclass(frozen=True)
class TrailsReceipt:
    intent_id: str
    status: str
    estimated_settlement_time: int
    simulated: bool
    runtime_classification: str
    evidence_classification: str
    verified: bool = False

    @property
    def usable_as_live_result(self) -> bool:
        return not self.simulated and self.runtime_classification == "live"


@dataclass(frozen=True)
class TrailsStatus:
    intent_id: str
    status: str
    tx_hash: str
    simulated: bool
    runtime_classification: str
    evidence_classification: str
    verified: bool = False

    @property
    def usable_as_live_result(self) -> bool:
        return (
            not self.simulated
            and self.runtime_classification == "live"
            and self.status in SETTLED_STATUSES
            and bool(self.tx_hash)
        )


class TrailsClient(ImmutableRuntimeConfiguration):
    """OMS Trails API client with immutable effective runtime configuration."""

    _immutable_runtime_fields = frozenset(
        {
            "runtime_policy",
            "mock_mode",
            "api_url",
            "_api_key",
            "_transport",
            "timeout",
        }
    )

    def __init__(
        self,
        mock_mode: Optional[bool] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
        transport: Any = None,
        timeout: int = 10,
    ):
        source = os.environ if environ is None else environ
        self.runtime_policy = runtime_policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "TrailsClient",
            TRAILS_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        self.api_url = (api_url or source.get("TRAILS_API_URL", "")).rstrip("/")
        self._api_key = api_key or source.get("TRAILS_API_KEY", "")
        self._transport = requests if transport is None else transport
        self.timeout = timeout
        if not self.mock_mode:
            self._validate_live_configuration()
        self._freeze_runtime_configuration()
        logger.info(
            "TrailsClient initialized (%s, mock=%s)",
            self.runtime_policy.runtime_classification,
            self.mock_mode,
        )

    def _validate_live_configuration(self) -> None:
        if not self._api_key:
            raise TrailsError("TrailsClient requires TRAILS_API_KEY outside mock mode")
        if self._api_key.strip().lower() in PLACEHOLDER_KEYS:
            raise TrailsError("TrailsClient rejects placeholder TRAILS_API_KEY values")
        parsed = urlparse(self.api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise TrailsError("TrailsClient requires an explicit valid TRAILS_API_URL")
        if self.runtime_policy.is_live and parsed.scheme != "https":
            raise TrailsError("TrailsClient requires an HTTPS endpoint in live runtime modes")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _provider_error(operation: str) -> TrailsError:
        return TrailsError(f"TrailsClient provider {operation} failed")

    def submit_intent(
        self,
        source: str,
        dest: str,
        payload: bytes,
        value: int = 0,
    ) -> TrailsReceipt:
        if self.mock_mode:
            digest = hashlib.sha256(
                b"vams-trails-simulation-v1\x00"
                + source.encode("utf-8")
                + b"\x00"
                + dest.encode("utf-8")
                + b"\x00"
                + payload
                + b"\x00"
                + str(value).encode("ascii")
            ).hexdigest()
            logger.info("TrailsClient simulated intent created (non-authoritative)")
            return TrailsReceipt(
                f"simulated:{digest}",
                "submitted",
                int(time.time()) + 5,
                True,
                self.runtime_policy.runtime_classification,
                "non-authoritative",
            )

        try:
            body = {
                "source": source,
                "destination": dest,
                "payload": payload.hex(),
                "value": value,
            }
            resp = self._transport.post(
                f"{self.api_url}/intents",
                json=body,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.error("TrailsClient provider submission failed")
            raise self._provider_error("submission") from None
        if not isinstance(data, dict):
            raise TrailsError("TrailsClient provider returned a malformed submission")
        intent_id = data.get("intent_id")
        status = data.get("status")
        estimated = data.get("estimated_settlement_time")
        if not isinstance(intent_id, str) or not intent_id:
            raise TrailsError("TrailsClient provider omitted intent_id")
        if status not in KNOWN_STATUSES:
            raise TrailsError("TrailsClient provider returned an invalid status")
        if isinstance(estimated, bool) or not isinstance(estimated, int) or estimated < 0:
            raise TrailsError("TrailsClient provider omitted settlement time")
        return TrailsReceipt(
            intent_id,
            status,
            estimated,
            False,
            self.runtime_policy.runtime_classification,
            self.runtime_policy.evidence_classification,
        )

    def get_status(self, intent_id: str) -> TrailsStatus:
        if self.mock_mode:
            digest = hashlib.sha256(intent_id.encode("utf-8")).hexdigest()
            return TrailsStatus(
                intent_id,
                "settled",
                f"simulated:sha256:{digest}",
                True,
                self.runtime_policy.runtime_classification,
                "non-authoritative",
            )

        try:
            resp = self._transport.get(
                f"{self.api_url}/intents/{intent_id}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.error("TrailsClient provider status request failed")
            raise self._provider_error("status request") from None
        if not isinstance(data, dict) or data.get("intent_id") != intent_id:
            raise TrailsError("TrailsClient provider returned a mismatched intent")
        status = data.get("status")
        tx_hash = data.get("tx_hash")
        if status not in KNOWN_STATUSES:
            raise TrailsError("TrailsClient provider returned an invalid status")
        if not isinstance(tx_hash, str):
            raise TrailsError("TrailsClient provider returned an invalid transaction hash")
        if status in SETTLED_STATUSES and not tx_hash:
            raise TrailsError("TrailsClient settled status requires a transaction hash")
        return TrailsStatus(
            intent_id,
            status,
            tx_hash,
            False,
            self.runtime_policy.runtime_classification,
            "provider-asserted-live"
            if status in SETTLED_STATUSES
            else self.runtime_policy.evidence_classification,
        )

    @staticmethod
    def require_live_result(status: TrailsStatus) -> TrailsStatus:
        """Reject simulated or non-live status at an evidence consumer boundary."""
        if not isinstance(status, TrailsStatus) or not status.usable_as_live_result:
            raise TrailsError("TrailsClient status is not usable as a live result")
        return status
