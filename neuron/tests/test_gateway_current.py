import sys
import os
import time
import unittest
from fastapi.testclient import TestClient

# Ensure sys.path resolves 'gateway' as 'neuron/gateway' when run inside 'neuron/' or 'neuron/tests/'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.server import app, AGENTS
from gateway.rate_limiter import RateLimiter

class TestGatewayCurrent(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        # Clear in-memory node registry
        AGENTS.clear()
        
    def test_register_agent(self):
        """Test agent registration adds the node to in-memory AGENTS state."""
        node_id = "0x" + "01" * 32
        payload = {
            "node_id": node_id,
            "public_key": "0xPub123",
            "stake_amount": 1000.0,
            "capabilities": {"compute": "gpu"},
            "version": "1.0.0"
        }
        response = self.client.post("/agents/register", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn(node_id, AGENTS)
        self.assertEqual(AGENTS[node_id]["stake"], 1000.0)

    def test_heartbeat_unknown_agent(self):
        """Test heartbeat from unregistered agent returns success=False."""
        unknown_id = "0x" + "ff" * 32
        payload = {
            "payload": f"{time.time()}|active|{unknown_id}",
            "signature": "0xSig"
        }
        response = self.client.post("/heartbeat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])

    def test_heartbeat_success(self):
        """Test heartbeat from registered agent returns success=True."""
        node_id = "0x" + "02" * 32
        # 1. Register
        self.client.post("/agents/register", json={
            "node_id": node_id, "public_key": "0xPub", "stake_amount": 500
        })
        
        # 2. Heartbeat
        payload = {
            "payload": f"{time.time()}|active|{node_id}",
            "signature": "0xSig"
        }
        response = self.client.post("/heartbeat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(AGENTS[node_id]["status"], "active")

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
