import sys
import os
import time
import json
import unittest
from unittest import mock
from fastapi.testclient import TestClient

# Ensure root directory is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

os.environ["GATEWAY_ADMIN_PASSWORD"] = "SecureTestPassword123!"
os.environ["VAMS_ENV"] = "test"

from gateway.server import NodeInfo, app, nodes
from neuron.gateway.rate_limiter import RateLimiter
from neuron.secp256k1 import generate_private_key, public_key_bytes, sign_message
from neuron.tests.m2_gateway_helpers import (
    AUDIENCE,
    SIGNER,
    compact_json,
    signed_headers,
)

class TestGatewayCurrent(unittest.TestCase):
    
    def setUp(self):
        self.environment = mock.patch.dict(
            os.environ,
            {
                "VAMS_ENV": "test",
                "GATEWAY_ADMIN_PASSWORD": "SecureTestPassword123!",
                "GATEWAY_ADMIN_DID": SIGNER,
                "GATEWAY_AUTH_AUDIENCE": AUDIENCE,
            },
            clear=False,
        )
        self.environment.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        nodes.clear()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.environment.stop()
        
    def test_heartbeat_new_agent(self):
        """Test sending heartbeat with valid signature registers a new agent."""
        sk = generate_private_key()
        public_key_hex = public_key_bytes(sk).hex()
        
        node_id = "0x" + "01" * 32
        payload = {
            "node_id": node_id,
            "block_height": 100,
            "public_key": public_key_hex,
            "region": "us-east-1",
            "cost_per_hour": 0.15,
            "credit_score": 750,
            "passports": "ERC-8004 Phala TEE"
        }
        payload_str = json.dumps(payload)
        
        signature = sign_message(sk, payload_str.encode()).hex()
        
        hb_data = {
            "payload": payload_str,
            "signature": signature
        }
        body = compact_json(hb_data)
        response = self.client.post(
            "/heartbeat",
            content=body,
            headers=signed_headers("POST", "/heartbeat", body=body),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        
        self.assertIn(node_id, nodes)
        self.assertEqual(nodes[node_id].last_block, 100)
        self.assertEqual(nodes[node_id].public_key, public_key_hex)

    def test_heartbeat_invalid_signature(self):
        """Test sending heartbeat with invalid signature returns 403."""
        sk = generate_private_key()
        public_key_hex = public_key_bytes(sk).hex()
        
        node_id = "0x" + "02" * 32
        payload = {
            "node_id": node_id,
            "block_height": 100,
            "public_key": public_key_hex
        }
        payload_str = json.dumps(payload)
        
        # Invalid signature (wrong key)
        other_sk = generate_private_key()
        signature = sign_message(other_sk, payload_str.encode()).hex()
        
        hb_data = {
            "payload": payload_str,
            "signature": signature
        }
        body = compact_json(hb_data)
        response = self.client.post(
            "/heartbeat",
            content=body,
            headers=signed_headers("POST", "/heartbeat", body=body),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid heartbeat signature")

    def test_first_heartbeat_empty_or_nonstring_key_is_rejected_before_mutation(self):
        """Valid outer M2 does not replace the independent node body signature."""
        for nonce, key in enumerate(("", None, False, 0, [], {}), start=1):
            with self.subTest(key=key):
                payload = json.dumps({"node_id": "fixture-empty-node",
                                      "block_height": 100, "public_key": key})
                body = compact_json({"payload": payload, "signature": ""})
                with mock.patch("gateway.server.verify_heartbeat_client_certificate",
                                return_value="fixture-allowed-certificate") as certificate:
                    response = self.client.post(
                        "/heartbeat", content=body,
                        headers=signed_headers("POST", "/heartbeat", body=body, nonce=nonce),
                    )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"], "Invalid heartbeat signature")
                self.assertEqual(nodes, {})
                certificate.assert_called_once()

    def test_existing_empty_node_key_is_rejected_without_advancing_state(self):
        node = NodeInfo(node_id="fixture-existing-empty", public_key="",
                        last_block=7, last_seen=23.0, heartbeat_count=5)
        nodes[node.node_id] = node
        before = dict(vars(node))
        body = compact_json({"payload": json.dumps({"node_id": node.node_id,
                             "block_height": 100, "public_key": ""}), "signature": ""})
        with mock.patch("gateway.server.verify_heartbeat_client_certificate",
                        return_value="fixture-allowed-certificate") as certificate:
            response = self.client.post(
                "/heartbeat", content=body,
                headers=signed_headers("POST", "/heartbeat", body=body),
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid heartbeat signature")
        self.assertIs(nodes[node.node_id], node)
        self.assertEqual(vars(node), before)
        certificate.assert_called_once()

    def _register_dashboard_node(self, node_id):
        key = generate_private_key()
        payload = json.dumps({"node_id": node_id, "block_height": 1234,
                              "public_key": public_key_bytes(key).hex()})
        body = compact_json({"payload": payload,
                             "signature": sign_message(key, payload.encode()).hex()})
        response = self.client.post(
            "/heartbeat", content=body,
            headers=signed_headers("POST", "/heartbeat", body=body, nonce=101),
        )
        self.assertEqual(response.status_code, 200)

    # Each signed request needs a fresh nonce; durable replay protection
    # rejects a reused one.
    def test_dashboard_renders_registered_node_with_formatted_last_seen(self):
        self._register_dashboard_node("dashboard-valid-node")
        response = self.client.get("/", headers=signed_headers("GET", "/", nonce=102))
        self.assertEqual(response.status_code, 200)
        self.assertIn("dashboard-valid-node", response.text)
        self.assertIn("1,234", response.text)
        self.assertIn(nodes["dashboard-valid-node"].last_seen_formatted, response.text)

    def test_dashboard_escapes_signed_untrusted_node_identifier(self):
        from html import escape
        node_id = '<img src=x onerror="alert(1)"> & <svg onload=alert(2)>'
        self._register_dashboard_node(node_id)
        response = self.client.get("/", headers=signed_headers("GET", "/", nonce=102))
        self.assertEqual(response.status_code, 200)
        self.assertIn(escape(node_id), response.text)
        self.assertNotIn("<img", response.text)
        self.assertNotIn("<svg", response.text)
        self.assertEqual(nodes[node_id].node_id, node_id)

    def test_rate_limiter(self):
        """Test the gateway RateLimiter utility class limits requests properly."""
        limiter = RateLimiter(default_limit=2, window_sec=1)
        self.assertTrue(limiter.is_allowed("1.1.1.1"))
        self.assertTrue(limiter.is_allowed("1.1.1.1"))
        
        # Third request within 1 second should block
        self.assertFalse(limiter.is_allowed("1.1.1.1"))
        
        # Wait for window reset
        time.sleep(1.1)
        self.assertTrue(limiter.is_allowed("1.1.1.1"))

if __name__ == "__main__":
    unittest.main()
