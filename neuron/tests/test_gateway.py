from fastapi.testclient import TestClient
import unittest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.server import app, AGENTS
from gateway.rate_limiter import RateLimiter

class TestGatewayServer(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        # Clear state
        AGENTS.clear()
        
    def test_register_agent(self):
        valid_node_id = "0x" + "1" * 64
        payload = {
            "node_id": valid_node_id,
            "public_key": "0xPub123",
            "stake_amount": 500.0,
            "capabilities": {"ai": "gpt4"}
        }
        response = self.client.post("/agents/register", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn(valid_node_id, AGENTS)

    def test_heartbeat_unknown_agent(self):
        payload = {
            "payload": "time|active|unknown_agent",
            "signature": "0xSig"
        }
        response = self.client.post("/heartbeat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"]) # Should fail logic, but 200 OK HTTP

    def test_heartbeat_success(self):
        valid_node_id = "0x" + "2" * 64
        # 1. Register
        self.client.post("/agents/register", json={
            "node_id": valid_node_id, "public_key": "x", "stake_amount": 100
        })
        
        # 2. Heartbeat
        payload = {
            "payload": f"{time.time()}|active|{valid_node_id}",
            "signature": "0xSig"
        }
        response = self.client.post("/heartbeat", json=payload)
        self.assertTrue(response.json()["success"])
        
    def test_rate_limiter(self):
        limiter = RateLimiter(default_limit=2, window_sec=1)
        self.assertTrue(limiter.is_allowed("1.1.1.1"))
        self.assertTrue(limiter.is_allowed("1.1.1.1"))
        
        # Should fail now
        self.assertFalse(limiter.is_allowed("1.1.1.1"))
        
        # Wait for refill
        time.sleep(1.1)
        self.assertTrue(limiter.is_allowed("1.1.1.1"))

if __name__ == '__main__':
    unittest.main()
