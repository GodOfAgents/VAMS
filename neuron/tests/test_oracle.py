import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chain_oracle import ChainMetrics, OracleManager, EthereumOracle, SolanaOracle

class TestChainOracle(unittest.TestCase):
    
    def setUp(self):
        self.mock_rpc = {"ethereum": "http://mock-eth", "solana": "http://mock-sol"}
        
    @patch('requests.post')
    def test_ethereum_oracle_fetch(self, mock_post):
        # Mock JSON-RPC response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"result": "0x4e20"}, # Gas Price (20000 wei)
            {"result": "0x1234"}  # Block Number (4660)
        ]
        mock_post.return_value = mock_response
        
        oracle = EthereumOracle(self.mock_rpc["ethereum"])
        metrics = oracle.fetch_metrics()
        
        self.assertIsInstance(metrics, ChainMetrics)
        self.assertEqual(metrics.chain, "Ethereum")
        self.assertGreater(metrics.last_block, 0)
        
    @patch('requests.post')
    def test_solana_oracle_fetch(self, mock_post):
        # Sol RPC response format
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"value": 100} 
        }
        mock_post.return_value = mock_response
        
        oracle = SolanaOracle(self.mock_rpc["solana"])
        metrics = oracle.fetch_metrics()
        
        self.assertEqual(metrics.chain, "Solana")

    @patch('chain_oracle.EthereumOracle.fetch_metrics')
    def test_oracle_manager_caching(self, mock_fetch):
        # Setup mock return
        mock_metrics = ChainMetrics(
            chain="Ethereum", last_block=100, gas_price_gwei=10.0,
            finality_ms=12000, congestion_pct=50.0,
            block_time_ms=12000, timestamp=time.time()
        )
        mock_fetch.return_value = mock_metrics
        
        manager = OracleManager()
        
        # 1. First fetch (cache miss)
        m1 = manager.get_metrics("Ethereum")
        
        # Check if m1 is None (if key mismatch) or the object
        self.assertIsNotNone(m1)
        self.assertEqual(m1.last_block, 100)
        mock_fetch.assert_called_once()
        
        # 2. Second fetch (cache hit)
        m2 = manager.get_metrics("Ethereum")
        mock_fetch.assert_called_once() # Call count should not increase
        
        # 3. Wait for TTL expiry (simulate)
        # Access _cache directly and modify timestamp on the object
        with manager._lock:
            if "Ethereum" in manager._cache:
                manager._cache["Ethereum"].timestamp = time.time() - 600
        
        # 4. Third fetch (cache expired)
        m3 = manager.get_metrics("Ethereum")
        self.assertEqual(mock_fetch.call_count, 2)

if __name__ == '__main__':
    unittest.main()
