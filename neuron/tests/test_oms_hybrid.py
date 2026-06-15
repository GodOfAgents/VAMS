"""
Tests for Phase 3 Polygon OMS Hybrid Compliance Model
=====================================================
Validates CLR Router enforcement, OMSSigner compliance checks,
and GasAbstractionPremiumCalculator calculations.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure neuron directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
from sdk.signer import SignerFactory, OMSSigner, EOASigner
from economics.gas_premium import GasAbstractionPremiumCalculator
from sdk.oms_identity import OMSIdentityVerifier


class TestOMSRoutingEnforcement(unittest.TestCase):
    def test_p3_requires_oms_block(self):
        router = CLRouter()
        verified_address = "0x99aabbccddeeff001122334455667788990011aa"
        
        # Scenario 1: Request compliance without loading OMS service block -> Blocked
        intent_no_block = TransactionIntent(
            value_usd=5000,
            max_latency_ms=30000,
            requires_privacy=False,
            requires_institutional_compliance=True,
            agent_address=verified_address,
            loaded_service_blocks=[] # No OMS block loaded
        )
        
        with self.assertRaises(PermissionError) as context:
            router.route(intent_no_block, TrustTier.PLATINUM)
        self.assertIn("requires the OMS service block", str(context.exception))
        
        # Scenario 2: Request compliance with OMS block loaded -> Allowed to pass route check
        intent_with_block = TransactionIntent(
            value_usd=5000,
            max_latency_ms=30000,
            requires_privacy=False,
            requires_institutional_compliance=True,
            agent_address=verified_address,
            loaded_service_blocks=["ServiceBlock_OMS_v1"]
        )
        
        decision = router.route(intent_with_block, TrustTier.PLATINUM)
        self.assertEqual(decision.chain, "Polygon")
        self.assertEqual(decision.priority, RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE)


class TestOMSSigner(unittest.TestCase):
    @patch("sdk.oms_identity.OMSIdentityVerifier.is_verified")
    def test_oms_signer_compliance_checks(self, mock_is_verified):
        # Setup signer
        private_key = "0x" + "11" * 32
        base_signer = SignerFactory.create({"private_key": private_key})
        
        # Mock verifier: 0x99 is verified, others are not
        def mock_verify(address):
            return address.lower().startswith("0x99")
        mock_is_verified.side_effect = mock_verify
        
        # Instantiate verifier and compliant signer
        verifier = OMSIdentityVerifier(mock_mode=False)
        compliant_signer = OMSSigner(inner_signer=base_signer, identity_verifier=verifier)
        
        # Check factory wrapping
        factory_signer = SignerFactory.create({
            "private_key": private_key,
            "oms_compliance": True
        })
        self.assertIsInstance(factory_signer, OMSSigner)
        
        # Test 1: Sign transaction to verified address -> Succeeds
        tx_verified = {
            "to": "0x9911223344556677889900112233445566778899",
            "value": 1000,
            "gas": 21000,
            "gasPrice": 1000000000,
            "nonce": 0,
            "chainId": 1
        }
        # Base signer's address isn't 0x99, but recipient is. So it should succeed.
        signed = compliant_signer.sign_transaction(tx_verified)
        self.assertIsNotNone(signed)
        
        # Test 2: Sign transaction to unverified address (where sender is also unverified) -> Blocked
        tx_unverified = {
            "to": "0x1111223344556677889900112233445566778899",
            "value": 1000,
            "gas": 21000,
            "gasPrice": 1000000000,
            "nonce": 0,
            "chainId": 1
        }
        with self.assertRaises(PermissionError) as context:
            compliant_signer.sign_transaction(tx_unverified)
        self.assertIn("Compliance check failed", str(context.exception))
        
        # Test 3: Sign message from unverified sender -> Blocked
        with self.assertRaises(PermissionError) as context:
            compliant_signer.sign_message("hello")
        self.assertIn("is not OMS-verified", str(context.exception))


class TestGasAbstractionPremium(unittest.TestCase):
    def test_premium_rates(self):
        calc = GasAbstractionPremiumCalculator(base_premium_bps=200)
        
        # Empty list -> 0%
        self.assertEqual(calc.calculate_premium_rate([]), 0.0)
        
        # OMS service block -> 2% + 5% = 7%
        self.assertEqual(calc.calculate_premium_rate(["ServiceBlock_OMS_v1"]), 0.07)
        
        # TEE wrapper + MEV protection -> 2% + 3% + 2% = 7%
        self.assertEqual(calc.calculate_premium_rate(["tee_wrapper", "mev_protection"]), 0.07)
        
        # All blocks loaded -> 2% + 5% (OMS) + 3% (TEE) + 2% (MEV) = 12%
        self.assertEqual(calc.calculate_premium_rate(["ServiceBlock_OMS_v1", "tee_wrapper", "mev_protection"]), 0.12)
        
        # Surcharges capped at 15%
        large_blocks = ["ServiceBlock_OMS_v1", "tee_wrapper", "mev_protection", "other_block_1", "other_block_2"]
        # Explicitly make sure cap triggers (we cap at 1500 BPS = 15%)
        # Let's verify rate
        self.assertLessEqual(calc.calculate_premium_rate(large_blocks), 0.15)
        
    def test_premium_costs(self):
        calc = GasAbstractionPremiumCalculator(base_premium_bps=200)
        base_cost = 100.0
        
        # With OMS block (7% rate)
        blocks = ["ServiceBlock_OMS_v1"]
        self.assertEqual(calc.calculate_premium_cost(base_cost, blocks), 7.0)
        self.assertEqual(calc.calculate_total_cost(base_cost, blocks), 107.0)


if __name__ == "__main__":
    unittest.main()
