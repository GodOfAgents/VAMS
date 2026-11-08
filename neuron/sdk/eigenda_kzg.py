"""Runtime-gated EigenDA proxy client."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse

import requests

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)


EIGENDA_MOCK_VARIABLE = "EIGENDA_MOCK_MODE"
HEX_IDENTIFIER = re.compile(r"^0x[0-9a-fA-F]+$")


class EigenDAError(Exception):
    pass


class EigenDASDK(ImmutableRuntimeConfiguration):
    """EigenDA proxy client with explicit mock and provider boundaries."""

    _immutable_runtime_fields = frozenset(
        {
            "runtime_policy",
            "mock_mode",
            "rpc_url",
            "timeout",
            "_transport",
            "_private_key_configured",
            "max_poll_attempts",
        }
    )

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: int = 15,
        mock_mode: Optional[bool] = None,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
        transport: Any = None,
        max_poll_attempts: int = 3,
    ):
        source = os.environ if environ is None else environ
        self.runtime_policy = runtime_policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "EigenDASDK",
            EIGENDA_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        self.rpc_url = rpc_url or source.get("EIGENDA_PROXY_URL", "")
        self.timeout = timeout
        self._transport = requests if transport is None else transport
        self._private_key_configured = bool(
            private_key or source.get("EIGENDA_PRIVATE_KEY", "")
        )
        if (
            isinstance(max_poll_attempts, bool)
            or not isinstance(max_poll_attempts, int)
            or max_poll_attempts < 1
        ):
            raise EigenDAError("EigenDASDK max_poll_attempts must be a positive integer")
        self.max_poll_attempts = max_poll_attempts
        if not self.mock_mode:
            self._validate_endpoint()
        self._freeze_runtime_configuration()

    def _validate_endpoint(self) -> None:
        parsed = urlparse(self.rpc_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise EigenDAError("EigenDASDK requires an explicit valid EIGENDA_PROXY_URL")
        if self.runtime_policy.is_live and parsed.scheme != "https":
            raise EigenDAError("EigenDASDK requires an HTTPS endpoint in live runtime modes")

    def _rpc(self, method: str, params: list[dict[str, Any]]) -> Dict[str, Any]:
        request = {"jsonrpc": "2.0", "method": method, "id": 1, "params": params}
        try:
            response = self._transport.post(
                self.rpc_url,
                json=request,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            raise EigenDAError("EigenDASDK provider request failed") from None
        if not isinstance(data, dict) or data.get("error") is not None:
            raise EigenDAError("EigenDASDK provider returned an invalid response")
        result = data.get("result")
        if not isinstance(result, dict):
            raise EigenDAError("EigenDASDK provider returned a malformed result")
        return result

    def submit_blob(self, payload: bytes) -> Dict[str, Any]:
        """Submit a raw blob without falling back to synthetic success."""
        if not isinstance(payload, bytes):
            raise EigenDAError("EigenDASDK payload must be bytes")
        if self.mock_mode:
            digest = hashlib.sha256(
                b"vams-eigenda-simulation-v1\x00" + payload
            ).hexdigest()
            return {
                "status": "simulated",
                "batch_header_hash": f"simulated:{digest}",
                "blob_index": 0,
                "verified": False,
                "simulated": True,
                "runtime_classification": self.runtime_policy.runtime_classification,
                "evidence_classification": "non-authoritative",
            }

        result = self._rpc("blob_submit", [{"data": "0x" + payload.hex()}])
        batch_hash = result.get("batchHeaderHash")
        blob_index = result.get("blobIndex")
        if not isinstance(batch_hash, str) or HEX_IDENTIFIER.fullmatch(batch_hash) is None:
            raise EigenDAError("EigenDASDK provider omitted a valid batch header hash")
        if isinstance(blob_index, bool) or not isinstance(blob_index, int) or blob_index < 0:
            raise EigenDAError("EigenDASDK provider omitted a valid blob index")
        return {
            "status": "pending",
            "batch_header_hash": batch_hash,
            "blob_index": blob_index,
            "verified": False,
            "simulated": False,
            "runtime_classification": self.runtime_policy.runtime_classification,
            "evidence_classification": self.runtime_policy.evidence_classification,
        }

    def retrieve_blob(self, batch_header_hash: str, blob_index: int) -> bytes:
        """Retrieve a blob through the selected EigenDA proxy."""
        if self.mock_mode:
            raise EigenDAError(
                "EigenDASDK simulated receipts do not support authoritative retrieval"
            )
        self._validate_reference(batch_header_hash, blob_index)
        result = self._rpc(
            "blob_get",
            [{"batchHeaderHash": batch_header_hash, "blobIndex": blob_index}],
        )
        raw_hex = result.get("data")
        if not isinstance(raw_hex, str) or not raw_hex.startswith("0x"):
            raise EigenDAError("EigenDASDK provider returned malformed blob data")
        encoded = raw_hex[2:]
        if not encoded or len(encoded) % 2:
            raise EigenDAError("EigenDASDK provider returned malformed blob data")
        try:
            return bytes.fromhex(encoded)
        except ValueError:
            raise EigenDAError("EigenDASDK provider returned malformed blob data") from None

    @staticmethod
    def _validate_reference(batch_header_hash: str, blob_index: int) -> None:
        if not isinstance(batch_header_hash, str) or HEX_IDENTIFIER.fullmatch(batch_header_hash) is None:
            raise EigenDAError("EigenDASDK requires a valid batch header hash")
        if isinstance(blob_index, bool) or not isinstance(blob_index, int) or blob_index < 0:
            raise EigenDAError("EigenDASDK requires a valid blob index")

    def wait_for_confirmation(
        self,
        batch_header_hash: str,
        blob_index: int,
        *,
        max_attempts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Poll a bounded number of times and fail when confirmation is absent."""
        if self.mock_mode:
            raise EigenDAError("EigenDASDK simulated receipts cannot be confirmed")
        self._validate_reference(batch_header_hash, blob_index)
        attempts = self.max_poll_attempts if max_attempts is None else max_attempts
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
            raise EigenDAError("EigenDASDK confirmation attempts must be a positive integer")
        for _ in range(attempts):
            result = self._rpc(
                "blob_status",
                [{"batchHeaderHash": batch_header_hash, "blobIndex": blob_index}],
            )
            status = result.get("status")
            if status == "confirmed":
                return {
                    "status": "confirmed",
                    "batch_header_hash": batch_header_hash,
                    "blob_index": blob_index,
                    "verified": False,
                    "simulated": False,
                    "runtime_classification": self.runtime_policy.runtime_classification,
                    "evidence_classification": "provider-asserted",
                }
            if status == "failed":
                raise EigenDAError("EigenDASDK provider reported submission failure")
            if status != "pending":
                raise EigenDAError("EigenDASDK provider returned malformed status")
        raise EigenDAError("EigenDASDK confirmation polling exhausted")
