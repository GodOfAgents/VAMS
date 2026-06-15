"""
Tests for Phase 1 Polygon OMS Backend Integration
=================================================
Validates OMSIdentityVerifier, CoinmeClient, and TrailsClient
under both mock_mode and simulated live HTTP modes.
"""

import unittest
from unittest.mock import patch, MagicMock
import requests
import json
import os
import sys

# Ensure neuron directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from sdk.oms_identity import OMSIdentityVerifier
    from payments.coinme_client import CoinmeClient
    from sdk.trails_client import TrailsClient, TrailsReceipt, TrailsStatus
except ImportError:
    from neuron.sdk.oms_identity import OMSIdentityVerifier
    from neuron.payments.coinme_client import CoinmeClient
    from neuron.sdk.trails_client import TrailsClient, TrailsReceipt, TrailsStatus


class TestOMSIdentityVerifier(unittest.TestCase):
    def test_mock_mode_verification(self):
        verifier = OMSIdentityVerifier(mock_mode=True)
        # Should verify address with 0x99 prefix
        self.assertTrue(verifier.is_verified("0x99AABBCCDDEEFF"))
        # Should reject address without 0x99 prefix
        self.assertFalse(verifier.is_verified("0x11AABBCCDDEEFF"))
        self.assertFalse(verifier.is_verified(""))

    @patch("requests.get")
    def test_live_mode_success(self, mock_get):
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_verified": True}
        mock_get.return_value = mock_response

        verifier = OMSIdentityVerifier(mock_mode=False, api_url="https://api.test/identity", api_key="test-key")
        self.assertTrue(verifier.is_verified("0x112233"))
        mock_get.assert_called_once_with("https://api.test/identity/v1/verification/0x112233", headers={"Authorization": "Bearer test-key"}, timeout=5)

    @patch("requests.get")
    def test_live_mode_unverified(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"is_verified": False}
        mock_get.return_value = mock_response

        verifier = OMSIdentityVerifier(mock_mode=False)
        self.assertFalse(verifier.is_verified("0x112233"))

    @patch("requests.get")
    def test_live_mode_fail_closed_on_error(self, mock_get):
        # Check fail closed on 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        verifier = OMSIdentityVerifier(mock_mode=False)
        self.assertFalse(verifier.is_verified("0x112233"))

        # Check fail closed on connection exception
        mock_get.side_effect = requests.RequestException("Connection failed")
        self.assertFalse(verifier.is_verified("0x112233"))


class TestCoinmeClient(unittest.TestCase):
    def test_mock_mode(self):
        client = CoinmeClient(mock_mode=True)
        # Checkout session
        checkout = client.create_checkout(100.0, "USD", "0x1234")
        self.assertEqual(checkout["amount_fiat"], 100.0)
        self.assertEqual(checkout["status"], "pending")
        self.assertTrue(checkout["checkout_url"].startswith("https://checkout.coinme.com"))

        # Rate
        rate = client.get_conversion_rate("USD", "VAMS")
        self.assertEqual(rate, 10.0)

        # KYC Status
        kyc = client.get_kyc_status("user_123")
        self.assertEqual(kyc["status"], "verified")

    @patch("requests.post")
    def test_live_create_checkout(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"checkout_id": "ch_123", "status": "created"}
        mock_post.return_value = mock_response

        client = CoinmeClient(api_key="test-key", base_url="https://api.coinme.test", mock_mode=False)
        res = client.create_checkout(50.0, "USD", "0xabc")
        self.assertEqual(res["checkout_id"], "ch_123")
        mock_post.assert_called_once_with(
            "https://api.coinme.test/checkouts",
            json={"amount": 50.0, "currency": "USD", "destination_address": "0xabc"},
            headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
            timeout=10
        )

    @patch("requests.get")
    def test_live_get_rate(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rate": 12.5}
        mock_get.return_value = mock_response

        client = CoinmeClient(mock_mode=False, base_url="https://api.coinme.test")
        rate = client.get_conversion_rate("USD", "VAMS")
        self.assertEqual(rate, 12.5)

    @patch("requests.get")
    def test_live_get_kyc_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "pending_manual_review"}
        mock_get.return_value = mock_response

        client = CoinmeClient(mock_mode=False, base_url="https://api.coinme.test")
        kyc = client.get_kyc_status("user_456")
        self.assertEqual(kyc["status"], "pending_manual_review")


class TestTrailsClient(unittest.TestCase):
    def test_mock_mode(self):
        client = TrailsClient(mock_mode=True)
        receipt = client.submit_intent("VAMS_L3", "Polygon", b"payload", 100)
        self.assertTrue(isinstance(receipt, TrailsReceipt))
        self.assertEqual(receipt.status, "submitted")

        status = client.get_status(receipt.intent_id)
        self.assertTrue(isinstance(status, TrailsStatus))
        self.assertEqual(status.status, "settled")
        self.assertTrue(status.tx_hash.startswith("0x"))

    @patch("requests.post")
    def test_live_submit_intent(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "intent_id": "int_999",
            "status": "in_transit",
            "estimated_settlement_time": 999999
        }
        mock_post.return_value = mock_response

        client = TrailsClient(mock_mode=False, api_url="https://api.trails.test", api_key="trails-key")
        receipt = client.submit_intent("VAMS_L3", "Polygon", b"\xaa\xbb\xcc", 50)
        self.assertEqual(receipt.intent_id, "int_999")
        self.assertEqual(receipt.status, "in_transit")
        self.assertEqual(receipt.estimated_settlement_time, 999999)
        mock_post.assert_called_once_with(
            "https://api.trails.test/intents",
            json={"source": "VAMS_L3", "destination": "Polygon", "payload": "aabbcc", "value": 50},
            headers={"Authorization": "Bearer trails-key", "Content-Type": "application/json"},
            timeout=10
        )

    @patch("requests.get")
    def test_live_get_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "intent_id": "int_999",
            "status": "completed",
            "tx_hash": "0x123abc456def"
        }
        mock_get.return_value = mock_response

        client = TrailsClient(mock_mode=False, api_url="https://api.trails.test")
        status = client.get_status("int_999")
        self.assertEqual(status.status, "completed")
        self.assertEqual(status.tx_hash, "0x123abc456def")


if __name__ == "__main__":
    unittest.main()
