import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingDecision
from chain_oracle import ChainMetrics

class TestCLRouter(unittest.TestCase):
    
    def setUp(self):
        self.router = CLRouter()
        
        # Mock Metrics
        self.eth_metrics = ChainMetrics(
            chain="Ethereum",  gas_price_gwei=50.0,
            finality_ms=780000, congestion_pct=80.0,
            block_time_ms=12000, timestamp=1000.0, last_block=100
        )
        self.sol_metrics = ChainMetrics(
            chain="Solana", gas_price_gwei=0.001, # Cheap
            finality_ms=400, congestion_pct=20.0,
            block_time_ms=400, timestamp=1000.0, last_block=100 # Fast
        )
        self.midnight_metrics = ChainMetrics(
            chain="Midnight", gas_price_gwei=5.0,
            finality_ms=60000, congestion_pct=10.0,
            block_time_ms=60000, timestamp=1000.0, last_block=100
        )
        
        self.router.oracle.get_all_metrics = MagicMock(return_value={
            "Ethereum": self.eth_metrics,
            "Solana": self.sol_metrics,
            "Midnight": self.midnight_metrics
        })

    def test_routing_latency_sensitive(self):
        # User wants FAST execution
        intent = TransactionIntent(value_usd=10.0, max_latency_ms=2000, requires_privacy=False)
        decision = self.router.route(intent, TrustTier.BRONZE)
        
        self.assertEqual(decision.chain, "Solana")
        self.assertLess(decision.metrics.block_time_ms, 2000)

    def test_routing_privacy_sensitive(self):
        # User wants PRIVACY
        intent = TransactionIntent(value_usd=100.0, max_latency_ms=60000, requires_privacy=True, requires_compliance_privacy=True)
        decision = self.router.route(intent, TrustTier.SILVER)
        
        self.assertEqual(decision.chain, "Midnight")

    def test_routing_high_value_security(self):
        # User sending $1M -> Needs Ethereum security
        intent = TransactionIntent(value_usd=1_000_000.0, max_latency_ms=60000, requires_privacy=False)
        decision = self.router.route(intent, TrustTier.PLATINUM)
        
        self.assertEqual(decision.chain, "Ethereum")

    def test_tier_constraints(self):
        # Unverified user trying to send too much
        intent = TransactionIntent(value_usd=2000.0, max_latency_ms=60000, requires_privacy=False) # Limit is 1000 for unverified
        
        with self.assertRaises(PermissionError):
            self.router.route(intent, TrustTier.UNVERIFIED)

if __name__ == '__main__':
    unittest.main()
