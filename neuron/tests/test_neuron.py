"""
VAMS Neuron - Unit Tests
========================
Tests for the neuron core modules.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compute import (
    BittensorProvider, 
    ComputeManager, 
    ComputeStatus, 
    ComputeInfo,
    IoNetProvider,
    AkashProvider,
    RenderProvider
)
from trust import (
    TrustManager, 
    TrustStatus, 
    TrustInfo,
    PhalaProvider,
    MarlinProvider,
    AutomataProvider
)


class TestBittensorProvider:
    """Tests for BittensorProvider."""
    
    def test_mock_mode_returns_healthy(self):
        """Test that mock mode returns healthy status without network calls."""
        provider = BittensorProvider(mock_mode=True)
        status = provider.get_status()
        
        assert status.status == ComputeStatus.HEALTHY
        assert status.provider == "bittensor"
        assert status.capacity.get("mock") is True
        assert status.latency_ms == 50.0  # Mock latency
    
    def test_http_mode_default(self):
        """Test that default mode uses HTTP checking."""
        provider = BittensorProvider(mock_mode=False, use_sdk=False)
        
        assert provider.mock_mode is False
        assert provider.use_sdk is False
        assert provider._sdk_available is False
    
    def test_sdk_mode_unavailable_gracefully(self):
        """Test that SDK mode fails gracefully when bittensor not installed."""
        provider = BittensorProvider(use_sdk=True)
        
        # bittensor is not installed in test environment
        assert provider._sdk_available is False
        # Should fall back to HTTP mode
        status = provider.get_status()
        # Will either be healthy (if HTTP works) or offline
        assert status.status in [ComputeStatus.HEALTHY, ComputeStatus.OFFLINE]
    
    def test_subnet_info_structure(self):
        """Test get_subnet_info returns correct structure."""
        provider = BittensorProvider(mock_mode=True)
        
        # Subnet info uses HTTP even in mock mode
        # Just verify the method exists and has correct return type
        result = provider.get_subnet_info(1)
        # May be None if API not reachable
        assert result is None or hasattr(result, 'netuid')
    
    def test_set_wallet(self):
        """Test that set_wallet stores the wallet."""
        provider = BittensorProvider(mock_mode=True)
        mock_wallet = MagicMock()
        
        provider.set_wallet(mock_wallet)
        
        assert provider._wallet == mock_wallet


class TestComputeManager:
    """Tests for ComputeManager."""
    
    def test_default_providers(self):
        """Test that default providers are created."""
        manager = ComputeManager()
        
        assert "io.net" in manager.providers
        assert "akash" in manager.providers
        assert "render" in manager.providers
        assert "bittensor" in manager.providers
    
    def test_custom_providers(self):
        """Test that custom providers can be passed."""
        bt = BittensorProvider(mock_mode=True)
        manager = ComputeManager(providers=[bt])
        
        assert "bittensor" in manager.providers
        assert len(manager.providers) == 1
    
    def test_get_healthy_providers_empty_initially(self):
        """Test that healthy providers list is empty before check."""
        manager = ComputeManager()
        
        assert manager.get_healthy_providers() == []
    
    def test_check_all_status_with_mock(self):
        """Test check_all_status with mock providers."""
        bt = BittensorProvider(mock_mode=True)
        manager = ComputeManager(providers=[bt])
        
        statuses = manager.check_all_status()
        
        assert "bittensor" in statuses
        assert statuses["bittensor"].status == ComputeStatus.HEALTHY


class TestTrustManager:
    """Tests for TrustManager."""
    
    def test_mock_mode_all_healthy(self):
        """Test that mock mode returns all healthy providers."""
        manager = TrustManager(mock_mode=True)
        statuses = manager.check_all_status()
        
        assert "phala" in statuses
        assert "marlin" in statuses
        assert "automata" in statuses
        
        for name, info in statuses.items():
            assert info.status == TrustStatus.HEALTHY
            assert info.capacity.get("mock") is True
    
    def test_mock_latencies(self):
        """Test that mock mode has fast latencies."""
        manager = TrustManager(mock_mode=True)
        statuses = manager.check_all_status()
        
        assert statuses["phala"].latency_ms == 50.0
        assert statuses["marlin"].latency_ms == 45.0
        assert statuses["automata"].latency_ms == 40.0
    
    def test_default_providers(self):
        """Test that default providers are created."""
        manager = TrustManager()
        
        assert "phala" in manager.providers
        assert "marlin" in manager.providers
        assert "automata" in manager.providers
    
    def test_get_healthy_providers_after_mock_check(self):
        """Test healthy providers after mock check."""
        manager = TrustManager(mock_mode=True)
        manager.check_all_status()
        
        healthy = manager.get_healthy_providers()
        
        assert len(healthy) == 3
        assert set(healthy) == {"phala", "marlin", "automata"}
    
    def test_list_providers_format(self):
        """Test list_providers returns correct format."""
        manager = TrustManager(mock_mode=True)
        manager.check_all_status()
        
        providers = manager.list_providers()
        
        assert len(providers) == 3
        for p in providers:
            assert "name" in p
            assert "technology" in p
            assert "description" in p
            assert "endpoint" in p
            assert "status" in p


class TestTrustInfo:
    """Tests for TrustInfo dataclass."""
    
    def test_to_dict(self):
        """Test TrustInfo.to_dict() method."""
        info = TrustInfo(
            provider="test",
            status=TrustStatus.HEALTHY,
            technology="Test TEE",
            capacity={"foo": "bar"},
            latency_ms=100.0
        )
        
        d = info.to_dict()
        
        assert d["provider"] == "test"
        assert d["status"] == "healthy"
        assert d["technology"] == "Test TEE"
        assert d["capacity"] == {"foo": "bar"}
        assert d["latency_ms"] == 100.0


class TestComputeInfo:
    """Tests for ComputeInfo dataclass."""
    
    def test_to_dict(self):
        """Test ComputeInfo.to_dict() method."""
        info = ComputeInfo(
            provider="test",
            status=ComputeStatus.HEALTHY,
            capacity={"gpu": "H100"},
            latency_ms=150.0
        )
        
        d = info.to_dict()
        
        assert d["provider"] == "test"
        assert d["status"] == "healthy"
        assert d["capacity"] == {"gpu": "H100"}
        assert d["latency_ms"] == 150.0


# Run with: python -m pytest tests/test_neuron.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
