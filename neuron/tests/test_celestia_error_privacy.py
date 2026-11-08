"""Local-only regression tests for Celestia retrieval warning privacy."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import logging
import os
import sys
import types
import unittest
from unittest.mock import patch

from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.models import DAProtocol, DAReceipt


_PAYLOAD = b"synthetic local Celestia payload"
_SENSITIVE_MARKERS = (
    "https://rpc.synthetic.invalid/v1?token=synthetic-token",
    "payload=synthetic-payload",
    "private_id=synthetic-private-id",
    "signature=synthetic-signature",
)
_SENSITIVE_EXCEPTION_TEXT = " ".join(_SENSITIVE_MARKERS)


class _SyntheticTransportFailure(Exception):
    """A local-only transport error carrying synthetic sensitive canaries."""


class _SyntheticResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class _SyntheticSession:
    """A local transport double; it never opens a socket or contacts a node."""

    def __init__(self, payload: dict | None = None, failure: Exception | None = None):
        self._payload = payload or {}
        self._failure = failure

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def post(self, *_args, **_kwargs):
        if self._failure is not None:
            raise self._failure
        return _SyntheticResponse(self._payload)


class _SyntheticAiohttp(types.ModuleType):
    """Narrow aiohttp import substitute used only inside a patched test scope."""

    def __init__(self, payload: dict | None = None, failure: Exception | None = None):
        super().__init__("aiohttp")
        self._payload = payload
        self._failure = failure

    def ClientSession(self):
        return _SyntheticSession(self._payload, self._failure)

    def ClientTimeout(self, *, total: int):
        return total


@contextlib.contextmanager
def _capture_warning_output(name: str):
    stream = io.StringIO()
    logger = logging.getLogger("VAMS-DA-Celestia")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    prior_level = logger.level
    prior_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        yield stream
    finally:
        captured = stream.getvalue()
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(prior_level)
        logger.propagate = prior_propagate

        # Optional evidence output stays outside the source tree. The run
        # command sets this only to the assigned evidence directory.
        evidence_dir = os.environ.get("VAMS_PRIVACY_DA_CAPTURE_DIR")
        if evidence_dir:
            os.makedirs(evidence_dir, exist_ok=True)
            with open(os.path.join(evidence_dir, f"{name}.log"), "w", encoding="utf-8") as capture_file:
                capture_file.write(captured)


def _blob_id(payload: bytes = _PAYLOAD) -> str:
    return f"celestia:123:{hashlib.sha256(payload).hexdigest()}"


def _receipt(payload: bytes = _PAYLOAD) -> DAReceipt:
    return DAReceipt(
        protocol=DAProtocol.CELESTIA,
        blob_id=_blob_id(payload),
        height=123,
        commitment="0x" + hashlib.sha256(payload).hexdigest(),
    )


class CelestiaRetrievalErrorPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_blob_failure_logs_fixed_message_and_returns_none(self):
        adapter = CelestiaDAAdapter(mock_mode=False)
        synthetic_aiohttp = _SyntheticAiohttp(
            failure=_SyntheticTransportFailure(_SENSITIVE_EXCEPTION_TEXT)
        )

        with _capture_warning_output("get_blob_failure") as output:
            with patch.dict(sys.modules, {"aiohttp": synthetic_aiohttp}):
                result = await adapter.get_blob(_blob_id())

        self.assertIsNone(result)
        captured = output.getvalue()
        self.assertEqual(
            captured,
            "WARNING:VAMS-DA-Celestia:Celestia blob retrieval failed\n",
        )
        for marker in _SENSITIVE_MARKERS:
            self.assertNotIn(marker, captured)

    async def test_verify_blob_failure_logs_fixed_message_and_returns_false(self):
        adapter = CelestiaDAAdapter(mock_mode=False)

        async def failed_retrieval(_blob_id: str):
            raise _SyntheticTransportFailure(_SENSITIVE_EXCEPTION_TEXT)

        # Local method override forces verify_blob's retrieval exception path.
        adapter.get_blob = failed_retrieval
        with _capture_warning_output("verify_blob_failure") as output:
            result = await adapter.verify_blob(_receipt())

        self.assertIs(result, False)
        captured = output.getvalue()
        self.assertEqual(
            captured,
            "WARNING:VAMS-DA-Celestia:Celestia exact retrieval failed\n",
        )
        for marker in _SENSITIVE_MARKERS:
            self.assertNotIn(marker, captured)

    async def test_get_blob_success_returns_synthetic_exact_bytes(self):
        adapter = CelestiaDAAdapter(mock_mode=False)
        synthetic_aiohttp = _SyntheticAiohttp(
            payload={
                "result": [
                    {"data": base64.b64encode(_PAYLOAD).decode("ascii")},
                ]
            }
        )

        with patch.dict(sys.modules, {"aiohttp": synthetic_aiohttp}):
            result = await adapter.get_blob(_blob_id())

        self.assertEqual(result, _PAYLOAD)

    async def test_verify_blob_accepts_matching_retrieved_bytes_but_stays_ineligible(self):
        adapter = CelestiaDAAdapter(mock_mode=False)

        async def exact_retrieval(_blob_id: str):
            return _PAYLOAD

        # Local method override supplies only synthetic bytes for hash comparison.
        adapter.get_blob = exact_retrieval
        receipt = _receipt()

        self.assertIs(await adapter.verify_blob(receipt), True)
        self.assertIs(receipt.verified, False)
        self.assertIs(adapter.release_evidence_eligible, False)

    async def test_mock_retrieval_remains_unavailable_and_unverified(self):
        adapter = CelestiaDAAdapter(mock_mode=True)
        receipt = await adapter.submit_blob(_PAYLOAD)

        self.assertIs(receipt.verified, False)
        self.assertIsNone(await adapter.get_blob(receipt.blob_id))
        self.assertIs(await adapter.verify_blob(receipt), False)
        self.assertIs(adapter.release_evidence_eligible, False)


if __name__ == "__main__":
    unittest.main()
