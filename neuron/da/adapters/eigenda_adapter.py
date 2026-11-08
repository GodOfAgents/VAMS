"""
EigenDA Adapter — Stub
======================
Structured stub for future EigenDA integration.

EigenDA provides Ethereum-level economic security via restaked ETH.
Ideal for high-value fraud proofs and enterprise SLA reports.

Reference: https://docs.eigenlayer.xyz/eigenda/overview
Uses: DA_PROVIDERS["eigenda"]["rpc"] from config.py
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

logger = logging.getLogger("VAMS-DA-EigenDA")
EIGENDA_ADAPTER_MOCK_VARIABLE = "EIGENDA_ADAPTER_MOCK_MODE"


class EigenDAAdapter(ImmutableRuntimeConfiguration, DAAdapter):
    """
    Stub adapter for EigenDA.

    In production, blob dispersal would go through the EigenDA Disperser
    API. For now, returns mock receipts tagged with DAProtocol.EIGEN_DA.
    """

    protocol = DAProtocol.EIGEN_DA
    name = "EigenDA (High-Security)"
    _immutable_runtime_fields = frozenset(
        {"rpc_url", "namespace", "mock_mode", "runtime_policy"}
    )

    def __init__(
        self,
        rpc_url: str = "https://holesky.drpc.org",
        mock_mode: Optional[bool] = None,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
    ):
        policy = runtime_policy or load_runtime_policy(environ)
        resolved_mock = resolve_component_mock_mode(
            "EigenDAAdapter",
            EIGENDA_ADAPTER_MOCK_VARIABLE,
            mock_mode,
            policy=policy,
            environ=environ,
        )
        if not resolved_mock:
            raise LiveModeSafetyError(
                "EigenDAAdapter is a structured stub and cannot be selected for live submission"
            )
        super().__init__(rpc_url, namespace=b"vams-perf-v1", mock_mode=True)
        self.runtime_policy = policy
        self._mock_height = 100
        self._freeze_runtime_configuration()

    async def submit_blob(self, data: bytes, namespace: Optional[bytes] = None) -> DAReceipt:
        self._mock_height += 1
        digest = hashlib.sha256(data).hexdigest()
        commitment = f"simulated:sha256:{digest}"
        blob_id = f"simulated:eigenda:{self._mock_height}:{digest[:16]}"

        logger.info("EigenDAAdapter simulated submission completed (non-authoritative)")

        return DAReceipt(
            protocol=DAProtocol.EIGEN_DA,
            blob_id=blob_id,
            height=self._mock_height,
            commitment=commitment,
            verified=False,
            simulated=True,
            runtime_classification=self.runtime_policy.runtime_classification,
            evidence_classification="non-authoritative",
        )

    async def verify_blob(self, receipt: DAReceipt) -> bool:
        logger.info("EigenDAAdapter simulated receipts are never verified")
        return False

    async def get_blob(self, blob_id: str) -> Optional[bytes]:
        logger.info("EigenDAAdapter simulated retrieval is unavailable")
        return None
