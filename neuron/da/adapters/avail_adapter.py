"""
Avail DA Adapter — Stub
=======================
Structured stub for future Avail integration.

Avail provides KZG Polynomial Commitment-based DA guarantees.
Ideal as a backup DA layer for ZK rollup validity proofs.

Reference: https://docs.availproject.org/
Uses: DA_PROVIDERS["avail"]["rpc"] from config.py
"""

import hashlib
import logging
from typing import Mapping, Optional

from neuron.da.adapters.base import DAAdapter
from neuron.da.models import DAProtocol, DAReceipt
from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)

logger = logging.getLogger("VAMS-DA-Avail")
AVAIL_ADAPTER_MOCK_VARIABLE = "AVAIL_ADAPTER_MOCK_MODE"


class AvailDAAdapter(ImmutableRuntimeConfiguration, DAAdapter):
    """
    Stub adapter for Avail.

    In production, blob submission would go through the Avail
    Light Client API with KZG commitment verification. For now,
    returns mock receipts tagged with DAProtocol.AVAIL.
    """

    protocol = DAProtocol.AVAIL
    name = "Avail (KZG Backup)"
    _immutable_runtime_fields = frozenset(
        {"rpc_url", "namespace", "mock_mode", "runtime_policy"}
    )

    def __init__(
        self,
        rpc_url: str = "https://avail-turing.api.onfinality.io/public",
        mock_mode: Optional[bool] = None,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
    ):
        policy = runtime_policy or load_runtime_policy(environ)
        resolved_mock = resolve_component_mock_mode(
            "AvailDAAdapter",
            AVAIL_ADAPTER_MOCK_VARIABLE,
            mock_mode,
            policy=policy,
            environ=environ,
        )
        if not resolved_mock:
            raise LiveModeSafetyError(
                "AvailDAAdapter is a structured stub and cannot be selected for live submission"
            )
        super().__init__(rpc_url, namespace=b"vams-perf-v1", mock_mode=True)
        self.runtime_policy = policy
        self._mock_height = 200
        self._freeze_runtime_configuration()

    async def submit_blob(self, data: bytes, namespace: Optional[bytes] = None) -> DAReceipt:
        self._mock_height += 1
        digest = hashlib.sha256(data).hexdigest()
        commitment = f"simulated:sha256:{digest}"
        blob_id = f"simulated:avail:{self._mock_height}:{digest[:16]}"

        logger.info("AvailDAAdapter simulated submission completed (non-authoritative)")

        return DAReceipt(
            protocol=DAProtocol.AVAIL,
            blob_id=blob_id,
            height=self._mock_height,
            commitment=commitment,
            verified=False,
            simulated=True,
            runtime_classification=self.runtime_policy.runtime_classification,
            evidence_classification="non-authoritative",
        )

    async def verify_blob(self, receipt: DAReceipt) -> bool:
        logger.info("AvailDAAdapter simulated receipts are never verified")
        return False

    async def get_blob(self, blob_id: str) -> Optional[bytes]:
        logger.info("AvailDAAdapter simulated retrieval is unavailable")
        return None
