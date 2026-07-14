"""Fail-closed regression coverage for live data-availability boundaries."""

from __future__ import annotations

import hashlib

import pytest

from neuron.da.adapters.base import DAAdapterError
from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.adapters.near_adapter import NearDAAdapter
from neuron.da.models import DAProtocol, DAReceipt
from neuron.da.performance_audit import DAConfigurationError, PerformanceAuditLog


class _Response:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self):
        return self.payload


class _Session:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def post(self, *_args, **_kwargs):
        return _Response(self.payload)


@pytest.mark.asyncio
async def test_celestia_rpc_error_never_falls_back_to_mock(monkeypatch):
    import aiohttp

    adapter = CelestiaDAAdapter(mock_mode=False)
    monkeypatch.setattr(
        aiohttp,
        "ClientSession",
        lambda: _Session({"jsonrpc": "2.0", "error": {"code": -1}}),
    )

    with pytest.raises(DAAdapterError, match="rejected blob submission"):
        await adapter.submit_blob(b"release-evidence")
    assert adapter._mock_height == 1000


@pytest.mark.asyncio
async def test_celestia_live_receipt_is_unverified_until_exact_retrieval(monkeypatch):
    import aiohttp

    payload = b"release-evidence"
    adapter = CelestiaDAAdapter(mock_mode=False)
    monkeypatch.setattr(
        aiohttp,
        "ClientSession",
        lambda: _Session({"jsonrpc": "2.0", "result": 12345}),
    )

    receipt = await adapter.submit_blob(payload)

    assert receipt.height == 12345
    assert receipt.verified is False
    assert receipt.blob_id == f"celestia:12345:{hashlib.sha256(payload).hexdigest()}"


@pytest.mark.asyncio
async def test_celestia_verification_requires_exact_retrieved_payload(monkeypatch):
    payload = b"release-evidence"
    adapter = CelestiaDAAdapter(mock_mode=False)
    receipt = DAReceipt(
        protocol=DAProtocol.CELESTIA,
        blob_id=f"celestia:12345:{hashlib.sha256(payload).hexdigest()}",
        height=12345,
        commitment="0x" + hashlib.sha256(payload).hexdigest(),
    )

    async def exact_blob(_blob_id):
        return payload

    monkeypatch.setattr(adapter, "get_blob", exact_blob)
    assert await adapter.verify_blob(receipt) is True

    async def wrong_blob(_blob_id):
        return b"different"

    monkeypatch.setattr(adapter, "get_blob", wrong_blob)
    assert await adapter.verify_blob(receipt) is False


@pytest.mark.asyncio
async def test_near_non_mock_mode_cannot_mint_unsigned_receipt():
    adapter = NearDAAdapter(mock_mode=False)

    with pytest.raises(DAAdapterError, match="signed blob-store transaction"):
        await adapter.submit_blob(b"release-evidence")


def test_non_mock_orchestrator_rejects_incomplete_da_routes():
    with pytest.raises(DAConfigurationError, match="not live-capable"):
        PerformanceAuditLog(
            mock_mode=False,
            config={"enabled_protocols": ["celestia", "near"]},
        )


@pytest.mark.asyncio
async def test_mock_receipts_are_never_marked_verified():
    for adapter in (CelestiaDAAdapter(mock_mode=True), NearDAAdapter(mock_mode=True)):
        receipt = await adapter.submit_blob(b"local-only")
        assert receipt.verified is False
        assert await adapter.verify_blob(receipt) is False

