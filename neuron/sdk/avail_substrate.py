"""Explicitly simulated Avail SDK boundary.

The direct signed Substrate submission path is not implemented or audited, so
this client is a structured stub and can only be selected explicitly in a
non-live runtime mode.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, Mapping, Optional

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)


AVAIL_MOCK_VARIABLE = "AVAIL_MOCK_MODE"


class AvailDAError(Exception):
    pass


class AvailDASDK(ImmutableRuntimeConfiguration):
    """Structured Avail stub with explicitly non-authoritative output."""

    _immutable_runtime_fields = frozenset(
        {"rpc_url", "timeout", "mock_mode", "runtime_policy"}
    )

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        seed_phrase: Optional[str] = None,
        timeout: int = 15,
        mock_mode: Optional[bool] = None,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
    ):
        source = os.environ if environ is None else environ
        policy = runtime_policy or load_runtime_policy(source)
        resolved_mock = resolve_component_mock_mode(
            "AvailDASDK",
            AVAIL_MOCK_VARIABLE,
            mock_mode,
            policy=policy,
            environ=source,
        )
        if not resolved_mock:
            raise LiveModeSafetyError(
                "AvailDASDK is a structured stub without an audited signed submission path"
            )
        self.rpc_url = rpc_url or source.get("AVAIL_RPC_URL", "")
        self.timeout = timeout
        self.mock_mode = True
        self.runtime_policy = policy
        self._submission_counter = 0
        self._freeze_runtime_configuration()

    def submit_data(self, payload: bytes) -> Dict[str, Any]:
        """Return a deterministic, visibly simulated result."""
        if not isinstance(payload, bytes):
            raise AvailDAError("AvailDASDK payload must be bytes")
        self._submission_counter += 1
        digest = hashlib.sha256(
            b"vams-avail-simulation-v1\x00"
            + self._submission_counter.to_bytes(8, "big")
            + payload
        ).hexdigest()
        return {
            "status": "simulated",
            "block_hash": f"simulated:{digest}",
            "extrinsic_index": self._submission_counter,
            "network": "avail-simulation",
            "verified": False,
            "simulated": True,
            "runtime_classification": self.runtime_policy.runtime_classification,
            "evidence_classification": "non-authoritative",
        }

    def retrieve_data(self, block_hash: str, extrinsic_index: int) -> bytes:
        """Structured stubs cannot provide authoritative retrieval proof."""
        raise AvailDAError(
            "AvailDASDK simulated receipts do not support authoritative retrieval"
        )
