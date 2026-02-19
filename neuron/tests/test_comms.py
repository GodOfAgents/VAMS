import unittest
from unittest.mock import patch, mock_open
import sys
import os
from ecdsa import SigningKey, SECP256k1
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_comms import AgentCommunicator, SignedMessage

class TestAgentComms(unittest.TestCase):
    
    def setUp(self):
        self.sk = SigningKey.generate(curve=SECP256k1)
        self.vk = self.sk.verifying_key
        self.node_id = self.vk.to_string().hex()[:16]
        self.comms = AgentCommunicator(self.sk, self.node_id)
        
    def test_message_signing_verification(self):
        recipient = "recipient_node"
        payload = {"data": "secret"}
        
        # 1. Create
        msg = self.comms.create_message(recipient, payload)
        
        self.assertIsInstance(msg, SignedMessage)
        self.assertIsNotNone(msg.signature)
        
        # 2. Verify
        # We need the VK in hex for verification
        vk_hex = self.vk.to_string().hex()
        is_valid = self.comms.verify_message(msg, vk_hex)
        
        self.assertTrue(is_valid)

    def test_tampered_message(self):
        recipient = "recipient_node"
        msg = self.comms.create_message(recipient, {"data": "clean"})
        
        # Tamper payload
        msg.payload = json.dumps({"data": "hacked"})
        
        vk_hex = self.vk.to_string().hex()
        is_valid = self.comms.verify_message(msg, vk_hex)
        
        self.assertFalse(is_valid)

    @patch("builtins.open", new_callable=mock_open)
    def test_audit_logging(self, mock_file):
        # Override the audit logger's file access
        self.comms.audit.log_file = "mock_audit.log"
        
        msg = self.comms.create_message("recipient", {"test": 1})
        
        # Check if write was called
        mock_file().write.assert_called()
        args, _ = mock_file().write.call_args
        log_entry = json.loads(args[0])
        
        self.assertEqual(log_entry["direction"], "OUTGOING")
        self.assertTrue(log_entry["verified"])

if __name__ == '__main__':
    unittest.main()
