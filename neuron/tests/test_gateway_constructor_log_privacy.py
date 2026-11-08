"""Constructor diagnostic redaction on actual GatewayClient; mocked Session only."""
import logging
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from neuron.gateway import client as gateway
from neuron.runtime_safety import RuntimeConfigurationError

BASE = "https://synthetic-gateway.invalid"
MARKER = "SYNTHETIC_ONLY_PRIVATE_MARKER"


class GatewayConstructorLogTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        env.start(); self.addCleanup(env.stop)
        self.session = Mock(name="explicit-synthetic-session")
        self.session.headers = {}
        factory = patch.object(gateway.requests, "Session", return_value=self.session)
        self.factory = factory.start(); self.addCleanup(factory.stop)
        network = patch("requests.sessions.Session.request",
                        side_effect=AssertionError("Actual HTTP forbidden"))
        self.network = network.start(); self.addCleanup(network.stop)

    def tearDown(self):
        self.network.assert_not_called()

    def construct(self, url, mode="test"):
        with self.assertLogs(gateway.logger, level="INFO") as capture:
            client = gateway.GatewayClient(url, environ={"VAMS_ENV": mode})
        self.factory.assert_called_once_with()
        self.assertIs(client.session, self.session)
        self.session.post.assert_not_called()
        self.session.get.assert_not_called()
        self.assertEqual(client.base_url, url.strip().rstrip("/"))
        self.assertEqual(client.runtime_policy.mode.value, mode)
        self.assertEqual(self.session.headers, {"User-Agent": "VAMS-Neuron/1.0",
                                               "Content-Type": "application/json"})
        self.assertFalse(client.registered); self.assertIsNone(client.agent_id)
        self.assertEqual(len(capture.records), 1)
        record = capture.records[0]
        self.assertEqual(record.msg, "Gateway Client initialized")
        self.assertEqual(record.getMessage(), "Gateway Client initialized")
        self.assertEqual(record.levelno, logging.INFO)
        self.assertEqual(record.args, ())
        self.assertIsNone(record.exc_info)
        self.assertIsNone(record.stack_info)
        self.assertNotIn(MARKER, "\n".join(capture.output))
        self.assertNotIn(url.strip().rstrip("/"), "\n".join(capture.output))
        return client

    def test_actual_lane_source_loaded(self):
        self.assertEqual(Path(gateway.__file__).resolve(),
                         Path(__file__).resolve().parents[1] / "gateway" / "client.py")
        self.factory.assert_not_called()

    def test_invalid_mode_rejects_before_transport_or_constructor_log(self):
        with self.assertNoLogs(gateway.logger, level="INFO"):
            with self.assertRaises(RuntimeConfigurationError):
                gateway.GatewayClient(BASE, environ={"VAMS_ENV": "unknown"})
        self.factory.assert_not_called()

    def test_live_plaintext_rejects_before_transport_or_constructor_log(self):
        with self.assertNoLogs(gateway.logger, level="INFO"):
            with self.assertRaises(ValueError):
                gateway.GatewayClient("http://synthetic-gateway.invalid", environ={"VAMS_ENV": "testnet"})
        self.factory.assert_not_called()

    def test_transport_url_json_timeout_and_redirect_policy_unchanged(self):
        # Capture the original diagnostic without asserting the repair here.
        with self.assertLogs(gateway.logger, level="INFO"):
            client = gateway.GatewayClient(BASE + "/prefix/", environ={"VAMS_ENV": "test"})
        self.session.post.return_value.status_code = 200
        self.session.post.return_value.json.return_value = {"agent_id": "synthetic-public-agent"}
        client.register_agent("synthetic-public-node", "synthetic-public-key-placeholder", 0.0)
        self.session.post.assert_called_once_with(BASE + "/prefix/agents/register",
            json={"node_id": "synthetic-public-node", "public_key": "synthetic-public-key-placeholder",
                  "stake_amount": 0.0, "capabilities": {"compute": True, "storage": True},
                  "version": "1.0.0"}, timeout=10, allow_redirects=False)
        self.session.get.assert_not_called()
        self.assertTrue(client.registered)
        self.assertEqual(client.agent_id, "synthetic-public-agent")

    def test_effective_configuration_stays_frozen(self):
        with self.assertLogs(gateway.logger, level="INFO"):
            client = gateway.GatewayClient(BASE, environ={"VAMS_ENV": "test"})
        with self.assertRaises(RuntimeConfigurationError):
            client.base_url = "https://other-synthetic.invalid"
        self.assertEqual(client.base_url, BASE)
        self.session.post.assert_not_called(); self.session.get.assert_not_called()


def constructor_case(url, mode):
    def test(self):
        self.construct(url, mode)
    return test


for mode in ("local", "demo", "test", "staging", "testnet", "production"):
    setattr(GatewayConstructorLogTests, "test_https_fixed_diagnostic_" + mode,
            constructor_case(BASE, mode))
for name, url in {
    "path": BASE + "/" + MARKER,
    "query": BASE + "/?operator_hint=" + MARKER,
    "fragment": BASE + "/#" + MARKER,
    "newline": BASE + "/" + MARKER + "\nFORGED_SYNTHETIC_EVENT",
}.items():
    setattr(GatewayConstructorLogTests, "test_no_endpoint_reflection_" + name,
            constructor_case(url, "test"))
for name, url in (("localhost", "http://localhost:8000/"),
                  ("ipv4", "http://127.0.0.1:8000/"),
                  ("ipv6", "http://[::1]:8000/")):
    setattr(GatewayConstructorLogTests, "test_local_plaintext_fixed_diagnostic_" + name,
            constructor_case(url, "test"))


if __name__ == "__main__":
    unittest.main()

