"""
Tests: DA Adapters
==================
Covers: Individual DA adapter logic — blob submission, verification,
receipt structure, error handling.
"""

import pytest
import asyncio
import hashlib

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from neuron.da.models import DAProtocol, DAReceipt
from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.adapters.near_adapter import NearDAAdapter
from neuron.da.adapters.eigenda_adapter import EigenDAAdapter
from neuron.da.adapters.avail_adapter import AvailDAAdapter


# --- Fixtures ---

@pytest.fixture
def sample_data():
    return b'{"nodeId":"test","metricsScore":9500,"timestamp":1700000000}'


@pytest.fixture
def celestia_adapter():
    return CelestiaDAAdapter(mock_mode=True)


@pytest.fixture
def near_adapter():
    return NearDAAdapter(mock_mode=True)


@pytest.fixture
def eigenda_adapter():
    return EigenDAAdapter(mock_mode=True)


@pytest.fixture
def avail_adapter():
    return AvailDAAdapter(mock_mode=True)


# --- Celestia Adapter Tests ---

class TestCelestiaAdapter:
    @pytest.mark.asyncio
    async def test_submit_blob_returns_receipt(self, celestia_adapter, sample_data):
        receipt = await celestia_adapter.submit_blob(sample_data)
        assert isinstance(receipt, DAReceipt)
        assert receipt.protocol == DAProtocol.CELESTIA
        assert receipt.blob_id.startswith("celestia:")
        assert receipt.verified is False

    @pytest.mark.asyncio
    async def test_submit_blob_increments_height(self, celestia_adapter, sample_data):
        r1 = await celestia_adapter.submit_blob(sample_data)
        r2 = await celestia_adapter.submit_blob(sample_data)
        assert r2.height > r1.height

    @pytest.mark.asyncio
    async def test_commitment_is_sha256(self, celestia_adapter, sample_data):
        receipt = await celestia_adapter.submit_blob(sample_data)
        expected = "0x" + hashlib.sha256(sample_data).hexdigest()
        assert receipt.commitment == expected

    @pytest.mark.asyncio
    async def test_verify_blob_mock(self, celestia_adapter, sample_data):
        receipt = await celestia_adapter.submit_blob(sample_data)
        verified = await celestia_adapter.verify_blob(receipt)
        assert verified is False

    @pytest.mark.asyncio
    async def test_get_blob_returns_none_in_mock(self, celestia_adapter, sample_data):
        receipt = await celestia_adapter.submit_blob(sample_data)
        blob = await celestia_adapter.get_blob(receipt.blob_id)
        assert blob is None  # Mock mode doesn't store

    @pytest.mark.asyncio
    async def test_blob_id_format(self, celestia_adapter, sample_data):
        receipt = await celestia_adapter.submit_blob(sample_data)
        parts = receipt.blob_id.split(":")
        assert len(parts) == 3
        assert parts[0] == "celestia"
        assert parts[1].isdigit()


# --- Near DA Adapter Tests ---

class TestNearDAAdapter:
    @pytest.mark.asyncio
    async def test_submit_blob_returns_receipt(self, near_adapter, sample_data):
        receipt = await near_adapter.submit_blob(sample_data)
        assert isinstance(receipt, DAReceipt)
        assert receipt.protocol == DAProtocol.NEAR_DA
        assert receipt.blob_id.startswith("near:")

    @pytest.mark.asyncio
    async def test_submit_blob_increments_height(self, near_adapter, sample_data):
        r1 = await near_adapter.submit_blob(sample_data)
        r2 = await near_adapter.submit_blob(sample_data)
        assert r2.height > r1.height

    @pytest.mark.asyncio
    async def test_verify_blob_mock(self, near_adapter, sample_data):
        receipt = await near_adapter.submit_blob(sample_data)
        verified = await near_adapter.verify_blob(receipt)
        assert verified is False

    @pytest.mark.asyncio
    async def test_get_blob_not_implemented(self, near_adapter):
        blob = await near_adapter.get_blob("near:500001:abc123")
        assert blob is None


# --- EigenDA Stub Tests ---

class TestEigenDAAdapter:
    @pytest.mark.asyncio
    async def test_submit_blob_returns_receipt(self, eigenda_adapter, sample_data):
        receipt = await eigenda_adapter.submit_blob(sample_data)
        assert isinstance(receipt, DAReceipt)
        assert receipt.protocol == DAProtocol.EIGEN_DA
        assert receipt.blob_id.startswith("eigenda:")

    @pytest.mark.asyncio
    async def test_verify_stub_never_qualifies_as_evidence(self, eigenda_adapter, sample_data):
        receipt = await eigenda_adapter.submit_blob(sample_data)
        assert await eigenda_adapter.verify_blob(receipt) is False

    @pytest.mark.asyncio
    async def test_get_blob_returns_none(self, eigenda_adapter):
        blob = await eigenda_adapter.get_blob("eigenda:101:abc")
        assert blob is None


# --- Avail Stub Tests ---

class TestAvailAdapter:
    @pytest.mark.asyncio
    async def test_submit_blob_returns_receipt(self, avail_adapter, sample_data):
        receipt = await avail_adapter.submit_blob(sample_data)
        assert isinstance(receipt, DAReceipt)
        assert receipt.protocol == DAProtocol.AVAIL
        assert receipt.blob_id.startswith("avail:")

    @pytest.mark.asyncio
    async def test_verify_stub_never_qualifies_as_evidence(self, avail_adapter, sample_data):
        receipt = await avail_adapter.submit_blob(sample_data)
        assert await avail_adapter.verify_blob(receipt) is False


# --- Cross-Adapter Tests ---

class TestCrossAdapter:
    @pytest.mark.asyncio
    async def test_all_adapters_produce_valid_receipts(self, sample_data):
        adapters = [
            CelestiaDAAdapter(mock_mode=True),
            NearDAAdapter(mock_mode=True),
            EigenDAAdapter(mock_mode=True),
            AvailDAAdapter(mock_mode=True),
        ]
        for adapter in adapters:
            receipt = await adapter.submit_blob(sample_data)
            assert receipt.commitment.startswith("0x")
            assert receipt.height > 0
            assert receipt.blob_id != ""
            assert receipt.verified is False

    @pytest.mark.asyncio
    async def test_receipt_to_dict_format(self, celestia_adapter, sample_data):
        receipt = await celestia_adapter.submit_blob(sample_data)
        d = receipt.to_dict()
        assert d["protocol"] == "celestia"
        assert isinstance(d["height"], int)
        assert isinstance(d["timestamp"], float)
