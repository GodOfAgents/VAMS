import sys
import os
import time
import json
import unittest
from fastapi.testclient import TestClient
from ecdsa import SigningKey, SECP256k1

# Ensure root directory is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

# Clear any already loaded 'gateway' modules from sys.modules to prevent cross-contamination
for mod in list(sys.modules.keys()):
    if mod.startswith("gateway"):
        del sys.modules[mod]

os.environ["GATEWAY_ADMIN_PASSWORD"] = "SecureTestPassword123!"

from gateway.server import app, nodes
from neuron.gateway.rate_limiter import RateLimiter

class TestGatewayCurrent(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        nodes.clear()
        
    def test_heartbeat_new_agent(self):
        """Test sending heartbeat with valid signature registers a new agent."""
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.verifying_key
        public_key_hex = vk.to_string().hex()
        
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
        
        signature = sk.sign(payload_str.encode()).hex()
        
        headers = {
            "X-VAMS-DID": "did:key:" + public_key_hex,
            "X-VAMS-Signature": signature,
            "X-VAMS-Timestamp": str(int(time.time()))
        }
        
        hb_data = {
            "payload": payload_str,
            "signature": signature
        }
        
        response = self.client.post("/heartbeat", json=hb_data, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        
        self.assertIn(node_id, nodes)
        self.assertEqual(nodes[node_id].last_block, 100)
        self.assertEqual(nodes[node_id].public_key, public_key_hex)

    def test_heartbeat_invalid_signature(self):
        """Test sending heartbeat with invalid signature returns 403."""
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.verifying_key
        public_key_hex = vk.to_string().hex()
        
        node_id = "0x" + "02" * 32
        payload = {
            "node_id": node_id,
            "block_height": 100,
            "public_key": public_key_hex
        }
        payload_str = json.dumps(payload)
        
        # Invalid signature (wrong key)
        other_sk = SigningKey.generate(curve=SECP256k1)
        signature = other_sk.sign(payload_str.encode()).hex()
        
        hb_data = {
            "payload": payload_str,
            "signature": signature
        }
        
        response = self.client.post("/heartbeat", json=hb_data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid heartbeat signature")

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
