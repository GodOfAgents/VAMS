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
from typing import Optional

from neuron.da.adapters.base import DAAdapter
from neuron.da.models import DAProtocol, DAReceipt
from neuron.runtime_safety import require_not_live_mock

logger = logging.getLogger("VAMS-DA-Avail")


class AvailDAAdapter(DAAdapter):
    """
    Stub adapter for Avail.

    In production, blob submission would go through the Avail
    Light Client API with KZG commitment verification. For now,
    returns mock receipts tagged with DAProtocol.AVAIL.
    """

    protocol = DAProtocol.AVAIL
    name = "Avail (KZG Backup)"

    def __init__(self, rpc_url: str = "https://avail-turing.api.onfinality.io/public", mock_mode: bool = True):
        require_not_live_mock("AvailDAAdapter", True)
        super().__init__(rpc_url, namespace=b"vams-perf-v1", mock_mode=True)  # Always mock for now
        self._mock_height = 200

    async def submit_blob(self, data: bytes, namespace: Optional[bytes] = None) -> DAReceipt:
        self._mock_height += 1
        commitment = "0x" + hashlib.sha256(data).hexdigest()
        blob_id = f"avail:{self._mock_height}:{hashlib.sha256(data).hexdigest()[:16]}"

        logger.info(f"[STUB] Avail blob at block {self._mock_height}")

        return DAReceipt(
            protocol=DAProtocol.AVAIL,
            blob_id=blob_id,
            height=self._mock_height,
            commitment=commitment,
            verified=True,
        )

    async def verify_blob(self, receipt: DAReceipt) -> bool:
        logger.info(f"[STUB] Avail verification for {receipt.blob_id}")
        return True

    async def get_blob(self, blob_id: str) -> Optional[bytes]:
        logger.info(f"[STUB] Avail blob retrieval not implemented for {blob_id}")
        return None
