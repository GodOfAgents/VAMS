"""
VAMS Neuron - SDK Unit Tests
=============================
Tests for the protocol SDK integrations.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.celestia import CelestiaDA, CelestiaBlock, BlobSubmission, CelestiaNetwork
from sdk.bittensor_subnet import BittensorSubnet, SubnetInfo, MinerInfo, SUBNET_NAMES
from sdk.phala_tee import PhalaTEE, MarlinOyster, AutomataMultiProver, TEEProvider, AttestationReport


# ============================================================================
# Celestia DA Tests
# ============================================================================

class TestCelestiaDA:
    """Tests for Celestia Data Availability SDK."""
    
    def test_init_default(self):
        """Test default initialization."""
        da = CelestiaDA()
        assert da.network == CelestiaNetwork.MOCHA
        assert da.timeout == 30
        assert "localhost" in da.rpc_url
    
    def test_init_custom_rpc(self):
        """Test custom RPC URL."""
        da = CelestiaDA(rpc_url="https://custom.rpc.com")
        assert da.rpc_url == "https://custom.rpc.com"
    
    def test_init_with_auth_token(self):
        """Test initialization with auth token."""
        da = CelestiaDA(auth_token="test_token")
        assert da.auth_token == "test_token"
        assert "Authorization" in da._session.headers
    
    def test_namespace_constants(self):
        """Test VAMS namespace is correctly configured."""
        da = CelestiaDA()
        assert da.NAMESPACE_VERSION == 0
        assert len(da.NAMESPACE_ID) == 25  # VAMS namespace size (21 zero bytes + 'vams')
        assert da.NAMESPACE_ID.endswith(b"vams")
    
    def test_simulate_submission(self):
        """Test simulated blob submission."""
        da = CelestiaDA()
        test_data = b"test agent state data"
        
        result = da._simulate_submission(test_data)
        
        assert isinstance(result, BlobSubmission)
        assert result.size_bytes == len(test_data)
        assert result.commitment is not None
        assert result.namespace is not None
        assert result.height > 0
    
    def test_health_check_structure(self):
        """Test health check returns correct structure."""
        da = CelestiaDA()
        health = da.check_health()
        
        assert "status" in health
        assert "latency_ms" in health
        assert "network" in health
        assert "rpc_url" in health
        assert health["status"] in ["healthy", "degraded", "offline"]
    
    def test_celestia_block_dataclass(self):
        """Test CelestiaBlock dataclass."""
        block = CelestiaBlock(
            height=12345,
            hash="abc123",
            time="2026-01-28T00:00:00Z",
            data_hash="def456"
        )
        
        assert block.height == 12345
        assert block.hash == "abc123"
    
    def test_blob_submission_to_dict(self):
        """Test BlobSubmission serialization."""
        submission = BlobSubmission(
            height=100,
            commitment="abc",
            namespace="ns",
            size_bytes=50,
            timestamp=time.time()
        )
        
        d = submission.to_dict()
        assert d["height"] == 100
        assert d["commitment"] == "abc"
        assert "timestamp" in d


# ============================================================================
# Bittensor Subnet Tests
# ============================================================================

class TestBittensorSubnet:
    """Tests for Bittensor Subnet SDK."""
    
    def test_init_default(self):
        """Test default initialization."""
        bt = BittensorSubnet()
        assert bt.network == "test"
        assert bt.wallet_name is None
    
    def test_init_with_wallet(self):
        """Test initialization with wallet."""
        bt = BittensorSubnet(wallet_name="my_wallet", wallet_hotkey="my_key")
        assert bt.wallet_name == "my_wallet"
        assert bt.wallet_hotkey == "my_key"
    
    def test_known_subnet_names(self):
        """Test known subnet names are defined."""
        assert 1 in SUBNET_NAMES
        assert 24 in SUBNET_NAMES  # BitAgent
        assert "Text" in SUBNET_NAMES[1]
    
    def test_get_subnet_info_mock(self):
        """Test subnet info retrieval (mock mode)."""
        bt = BittensorSubnet()
        info = bt.get_subnet_info(1)
        
        assert isinstance(info, SubnetInfo)
        assert info.netuid == 1
        assert info.name == SUBNET_NAMES[1]
        assert info.miners > 0
        assert info.validators > 0
    
    def test_get_active_miners_mock(self):
        """Test active miners retrieval (mock mode)."""
        bt = BittensorSubnet()
        miners = bt.get_active_miners(1)
        
        assert isinstance(miners, list)
        assert len(miners) > 0
        assert all(isinstance(m, MinerInfo) for m in miners)
    
    def test_miner_info_to_dict(self):
        """Test MinerInfo serialization."""
        miner = MinerInfo(
            uid=1,
            hotkey="5xxx",
            coldkey="5yyy",
            stake=100.0,
            trust=0.8,
            consensus=0.7,
            incentive=0.01,
            emission=0.001,
            active=True
        )
        
        d = miner.to_dict()
        assert d["uid"] == 1
        assert d["stake"] == 100.0
        assert d["active"] == True
    
    def test_health_check_structure(self):
        """Test health check returns correct structure."""
        bt = BittensorSubnet()
        health = bt.check_health()
        
        assert "status" in health
        assert "network" in health
        assert health["status"] in ["healthy", "unavailable", "degraded", "offline"]
    
    def test_list_subnets(self):
        """Test listing all subnets."""
        bt = BittensorSubnet()
        subnets = bt.list_subnets()
        
        assert isinstance(subnets, list)
        assert len(subnets) > 0
        # Check SN1 is in list
        sn1 = next((s for s in subnets if s.netuid == 1), None)
        assert sn1 is not None


# ============================================================================
# Phala TEE Tests
# ============================================================================

class TestPhalaTEE:
    """Tests for Phala TEE SDK."""
    
    def test_init_default(self):
        """Test default initialization."""
        tee = PhalaTEE()
        assert tee.network == "testnet"
        assert "phala" in tee.phala_rpc
    
    def test_init_mainnet(self):
        """Test mainnet initialization."""
        tee = PhalaTEE(network="mainnet")
        assert tee.network == "mainnet"
    
    def test_simulate_attestation_sgx(self):
        """Test simulated SGX attestation."""
        tee = PhalaTEE()
        fake_quote = b"fake_sgx_quote_data"
        
        report = tee._simulate_attestation(fake_quote, TEEProvider.PHALA)
        
        assert isinstance(report, AttestationReport)
        assert report.provider == TEEProvider.PHALA
        assert report.is_valid == True
        assert report.quote_hash is not None
        assert report.mrenclave is not None
    
    def test_simulate_attestation_nitro(self):
        """Test simulated Nitro attestation."""
        tee = PhalaTEE()
        fake_doc = b"fake_nitro_attestation_document"
        
        report = tee._simulate_attestation(fake_doc, TEEProvider.MARLIN)
        
        assert report.provider == TEEProvider.MARLIN
        assert report.is_valid == True
    
    def test_attestation_report_to_dict(self):
        """Test AttestationReport serialization."""
        report = AttestationReport(
            provider=TEEProvider.PHALA,
            is_valid=True,
            quote_hash="abc123def456",
            mrenclave="mrenc123",
            timestamp=time.time()
        )
        
        d = report.to_dict()
        assert d["provider"] == "phala"
        assert d["is_valid"] == True
        assert "abc123" in d["quote_hash"]
    
    def test_health_check_structure(self):
        """Test health check returns correct structure."""
        tee = PhalaTEE()
        health = tee.check_health()
        
        assert "status" in health
        assert "provider" in health
        assert health["provider"] == "phala"
    
    def test_verify_multi_tee_all_valid(self):
        """Test multi-TEE verification with all valid quotes."""
        tee = PhalaTEE()
        quotes = {
            TEEProvider.PHALA: b"quote1",
            TEEProvider.MARLIN: b"quote2",
            TEEProvider.AUTOMATA: b"quote3"
        }
        
        is_valid, reports = tee.verify_multi_tee(quotes, required=2)
        
        # Simulated mode returns all valid
        assert is_valid == True
        assert len(reports) == 3


class TestMarlinOyster:
    """Tests for Marlin Oyster SDK."""
    
    def test_init_default(self):
        """Test default initialization."""
        marlin = MarlinOyster()
        assert marlin.network == "testnet"
    
    def test_health_check_structure(self):
        """Test health check returns correct structure."""
        marlin = MarlinOyster()
        health = marlin.check_health()
        
        assert "status" in health
        assert "provider" in health
        assert health["provider"] == "marlin"


class TestAutomataMultiProver:
    """Tests for Automata Multi-Prover SDK."""
    
    def test_init(self):
        """Test initialization."""
        automata = AutomataMultiProver()
        assert "1rpc" in automata.endpoint
    
    def test_health_check_structure(self):
        """Test health check returns correct structure."""
        automata = AutomataMultiProver()
        health = automata.check_health()
        
        assert "status" in health
        assert "provider" in health
        assert health["provider"] == "automata"


# ============================================================================
# Integration Tests
# ============================================================================

class TestSDKIntegration:
    """Integration tests across SDK modules."""
    
    def test_all_sdks_importable(self):
        """Test all SDK modules can be imported."""
        from sdk.celestia import CelestiaDA
        from sdk.bittensor_subnet import BittensorSubnet
        from sdk.phala_tee import PhalaTEE
        
        assert CelestiaDA is not None
        assert BittensorSubnet is not None
        assert PhalaTEE is not None
    
    def test_all_health_functions_exist(self):
        """Test convenience health check functions."""
        from sdk.celestia import check_celestia_health
        from sdk.bittensor_subnet import check_bittensor_health
        from sdk.phala_tee import check_all_tee_health
        
        assert callable(check_celestia_health)
        assert callable(check_bittensor_health)
        assert callable(check_all_tee_health)

# ============================================================================
# Signer Tests
# ============================================================================

class TestSigner:
    """Tests for Signer abstraction."""
    
    def test_eoa_signer_init(self):
        from sdk.signer import EOASigner
        # 64 char hex string
        pk = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        signer = EOASigner(pk)
        assert signer.address is not None
        assert signer.address.startswith("0x")

    def test_signer_factory(self):
        from sdk.signer import SignerFactory, EOASigner, SessionKeySigner
        pk = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        signer = SignerFactory.create({"private_key": pk})
        assert isinstance(signer, EOASigner)
        
        session_signer = SignerFactory.create({
            "smart_wallet_address": "0x1234567890123456789012345678901234567890",
            "session_key": pk
        })
        assert isinstance(session_signer, SessionKeySigner)
        assert session_signer.address == "0x1234567890123456789012345678901234567890"

# ============================================================================
# Trust Plugin Tests
# ============================================================================

class TestTrustPlugins:
    def test_tee_attestation_root_binding(self):
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from trust_plugins.tee_plugin import TEEProofPlugin
        
        plugin = TEEProofPlugin()
        root_addr = b"\x01" * 20
        session_addr = b"\x02" * 20
        
        result = plugin.generate_proof(
            b"service", 
            b"delivery", 
            root_address=root_addr, 
            agent_address=session_addr
        )
        # Verify the encoded proof data ends with the root address, not session address
        assert result.proof_data.endswith(root_addr)
        assert session_addr not in result.proof_data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
