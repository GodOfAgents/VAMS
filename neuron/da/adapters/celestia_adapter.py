"""
Celestia DA Adapter — Live API
==============================
Submits and verifies blobs on Celestia (Mocha testnet) using the
Celestia Node HTTP API.

Reference: https://docs.celestia.org/developers/node-api
Uses: DA_PROVIDERS["celestia"]["rpc"] from config.py
"""

import base64
import binascii
import hashlib
import logging
from typing import Optional

from neuron.da.adapters.base import DAAdapter, DAAdapterError
from neuron.da.models import DAProtocol, DAReceipt

logger = logging.getLogger("VAMS-DA-Celestia")

# Default namespace for VAMS performance audit data
VAMS_PERF_NAMESPACE = b"vams-perf-v1"


class CelestiaDAAdapter(DAAdapter):
    """
    Live API adapter for Celestia Mocha testnet.

    Uses the Celestia Node API:
    - POST /blob.Submit   — Submit blobs
    - POST /blob.Get      — Retrieve blobs
    - POST /header.GetByHeight — Get block header for verification

    Mock behavior is available only when ``mock_mode`` is explicitly enabled.
    Live RPC failures never fall back to locally generated receipts.
    """

    protocol = DAProtocol.CELESTIA
    name = "Celestia (DAS)"
    supports_live_submission = True
    supports_exact_retrieval = True
    # Release evidence additionally requires an independently operated observer.
    release_evidence_eligible = False

    def __init__(self, rpc_url: str = "https://rpc-mocha.pops.one", mock_mode: bool = False):
        super().__init__(rpc_url, namespace=VAMS_PERF_NAMESPACE, mock_mode=mock_mode)
        self._mock_height = 1000

    async def submit_blob(self, data: bytes, namespace: Optional[bytes] = None) -> DAReceipt:
        ns = namespace or self.namespace
        ns_b64 = base64.b64encode(ns).decode("ascii")
        data_b64 = base64.b64encode(data).decode("ascii")
        commitment = "0x" + hashlib.sha256(data).hexdigest()

        if self.mock_mode:
            return self._mock_submit(data, commitment)

        try:
            import aiohttp

            # Celestia Node API: blob.Submit
            payload = {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "blob.Submit",
                "params": [
                    [{"namespace": ns_b64, "data": data_b64, "share_version": 0}],
                    0.002  # gas price
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    result = await resp.json()

                    if "error" in result:
                        raise DAAdapterError(
                            f"Celestia RPC rejected blob submission: {result['error']}"
                        )

                    height = result.get("result")
                    if (
                        isinstance(height, bool)
                        or not isinstance(height, int)
                        or height <= 0
                    ):
                        raise DAAdapterError(
                            "Celestia submission response lacks a positive integer height"
                        )
                    payload_hash = hashlib.sha256(data).hexdigest()
                    blob_id = f"celestia:{height}:{payload_hash}"

                    logger.info(f"Blob submitted to Celestia at height {height}")

                    return DAReceipt(
                        protocol=DAProtocol.CELESTIA,
                        blob_id=blob_id,
                        height=height,
                        commitment=commitment,
                        verified=False,
                        raw_response=result,
                    )

        except ImportError as exc:
            raise DAAdapterError(
                "aiohttp is required for live Celestia submission"
            ) from exc
        except DAAdapterError:
            raise
        except Exception as e:
            raise DAAdapterError("Celestia live submission failed") from e

    async def verify_blob(self, receipt: DAReceipt) -> bool:
        if self.mock_mode:
            return False
        if receipt.protocol is not self.protocol:
            return False
        if not isinstance(receipt.commitment, str):
            return False
        try:
            retrieved = await self.get_blob(receipt.blob_id)
        except Exception as exc:
            logger.warning("Celestia exact retrieval failed: %s", exc)
            return False
        if not isinstance(retrieved, bytes):
            return False
        expected = "0x" + hashlib.sha256(retrieved).hexdigest()
        return expected == receipt.commitment.lower()

    async def get_blob(self, blob_id: str) -> Optional[bytes]:
        # Parse blob_id format: "celestia:{height}:{hash_prefix}"
        parts = blob_id.split(":")
        if len(parts) != 3 or parts[0] != "celestia":
            return None
        expected_hash = parts[2].lower()
        if len(expected_hash) not in {16, 64} or any(
            char not in "0123456789abcdef" for char in expected_hash
        ):
            return None

        if self.mock_mode:
            return None

        try:
            import aiohttp
            height = int(parts[1])
            if height <= 0:
                return None
            ns_b64 = base64.b64encode(self.namespace).decode("ascii")

            payload = {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "blob.GetAll",
                "params": [height, [ns_b64]],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
                    if "error" in result:
                        return None
                    blobs = result.get("result", [])
                    if not isinstance(blobs, list):
                        return None
                    for blob in blobs:
                        if not isinstance(blob, dict):
                            continue
                        try:
                            data = base64.b64decode(blob.get("data", ""), validate=True)
                        except (TypeError, ValueError, binascii.Error):
                            continue
                        if hashlib.sha256(data).hexdigest().startswith(expected_hash):
                            return data
                    return None

        except Exception as e:
            logger.warning(f"Celestia blob retrieval failed: {e}")
            return None

    def _mock_submit(self, data: bytes, commitment: str) -> DAReceipt:
        """Simulated submission for local development."""
        self._mock_height += 1
        blob_id = f"celestia:{self._mock_height}:{hashlib.sha256(data).hexdigest()}"
        logger.info(f"[MOCK] Celestia blob at height {self._mock_height}")
        return DAReceipt(
            protocol=DAProtocol.CELESTIA,
            blob_id=blob_id,
            height=self._mock_height,
            commitment=commitment,
            verified=False,
        )
