"""
Near DA Adapter — Live API
==========================
Submits and verifies blobs on Near DA using the Near RPC.

Near DA stores blobs via a dedicated blob_store smart contract
on the Near blockchain. Cost is ~85,000x cheaper than Ethereum,
making it ideal for high-frequency ephemeral Sentinel probes.

Reference: https://docs.near.org/api/rpc
Uses: DA_PROVIDERS["near"]["rpc"] from config.py
"""

import hashlib
import logging
from typing import Optional

from neuron.da.adapters.base import DAAdapter, DAAdapterError
from neuron.da.models import DAProtocol, DAReceipt

logger = logging.getLogger("VAMS-DA-Near")


class NearDAAdapter(DAAdapter):
    """
    Live API adapter for Near DA.

    Near DA uses a function call to the `da-blob-store.near` contract
    to persist arbitrary blobs. For testnet, we use `da-blob-store.testnet`.

    Ideal for:
    - High-frequency latency pings
    - Heartbeat liveness checks
    - Ephemeral IoT/gaming Sentinel data
    """

    protocol = DAProtocol.NEAR_DA
    name = "Near DA (High-Velocity)"

    BLOB_STORE_CONTRACT = "da-blob-store.testnet"

    def __init__(self, rpc_url: str = "https://rpc.testnet.near.org", mock_mode: bool = False):
        super().__init__(rpc_url, namespace=b"vams-perf-v1", mock_mode=mock_mode)
        self._mock_height = 500_000

    async def submit_blob(self, data: bytes, namespace: Optional[bytes] = None) -> DAReceipt:
        commitment = "0x" + hashlib.sha256(data).hexdigest()

        if self.mock_mode:
            return self._mock_submit(data, commitment)
        raise DAAdapterError(
            "Near live submission is disabled until a signed blob-store transaction "
            "and exact retrieval implementation are available"
        )

    async def verify_blob(self, receipt: DAReceipt) -> bool:
        return False

    async def get_blob(self, blob_id: str) -> Optional[bytes]:
        # Parse blob_id format: "near:{height}:{hash_prefix}"
        parts = blob_id.split(":")
        if len(parts) != 3 or parts[0] != "near":
            return None

        # Near DA blob retrieval would use the blob_store contract's view method
        # For now, return None (blobs are write-only audit records)
        logger.info(f"Near DA blob retrieval not yet implemented for {blob_id}")
        return None

    def _mock_submit(self, data: bytes, commitment: str) -> DAReceipt:
        self._mock_height += 1
        blob_id = f"near:{self._mock_height}:{hashlib.sha256(data).hexdigest()[:16]}"
        logger.info(f"[MOCK] Near DA blob at block {self._mock_height}")
        return DAReceipt(
            protocol=DAProtocol.NEAR_DA,
            blob_id=blob_id,
            height=self._mock_height,
            commitment=commitment,
            verified=False,
        )
