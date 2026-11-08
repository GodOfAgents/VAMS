"""GatewayClient failure records using a fully mocked Session; no HTTP or signing."""
import logging
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from neuron.gateway import client as gateway


BASE_URL = "https://synthetic-gateway.invalid"
MARKER = "SYNTHETIC_ONLY_PRIVATE_MARKER"
NODE = "synthetic-node-id"
AGENT = "synthetic-agent-id"
PUBLIC_KEY = "synthetic-public-key-placeholder"
SIGNATURE = "synthetic-signature-placeholder"
PAYLOAD = "synthetic-payload"
TASK = "synthetic-task-id"
RESULT = {"output": "synthetic-output"}
CAPABILITIES = {"compute": False, "storage": True}


class SyntheticResponse:
    def __init__(self, status, data=None, forbid_body=False):
        self.status_code = status
        self.json = Mock(return_value=data if data is not None else {})
        self.body_reads = 0
        self.forbid_body = forbid_body

    @property
    def text(self):
        self.body_reads += 1
        if self.forbid_body:
            raise AssertionError("Failure logging must not read response.text")
        return MARKER


class NeverStringifyError(RuntimeError):
    def __init__(self):
        super().__init__(MARKER)
        self.string_calls = 0

    def __str__(self):
        self.string_calls += 1
        raise AssertionError("Failure logging must not stringify exceptions")


class GatewayClientErrorPrivacyTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.session = Mock(name="explicit-synthetic-session")
        self.session.headers = {}
        factory = patch.object(gateway.requests, "Session", return_value=self.session)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = gateway.GatewayClient(BASE_URL)
        self.factory.assert_called_once_with()
        self.assertIs(self.client.session, self.session)

    def seed_registered_state(self):
        self.client.agent_id = AGENT
        self.client.registered = True

    def registration_payload(self, capabilities=CAPABILITIES):
        return {"node_id": NODE, "public_key": PUBLIC_KEY, "stake_amount": 0.0,
                "capabilities": capabilities, "version": "1.0.0"}

    def invoke(self, operation):
        if operation == "registration":
            return self.client.register_agent(NODE, PUBLIC_KEY, 0.0, CAPABILITIES)
        if operation == "deregistration":
            return self.client.deregister_agent(SIGNATURE)
        if operation == "heartbeat":
            return self.client.send_heartbeat(PAYLOAD, SIGNATURE)
        return self.client.submit_result(TASK, RESULT, SIGNATURE)

    def assert_request(self, operation):
        if operation == "registration":
            args = (BASE_URL + "/agents/register",)
            kwargs = {"json": self.registration_payload(), "timeout": 10, "allow_redirects": False}
        elif operation == "deregistration":
            args = (BASE_URL + "/agents/" + AGENT + "/deregister",)
            kwargs = {"json": {"signature": SIGNATURE}, "timeout": 10, "allow_redirects": False}
        elif operation == "heartbeat":
            args = (BASE_URL + "/heartbeat",)
            kwargs = {"json": {"payload": PAYLOAD, "signature": SIGNATURE}, "timeout": 5, "allow_redirects": False}
        else:
            args = (BASE_URL + "/tasks/" + TASK + "/result",)
            kwargs = {"json": {"result": RESULT, "signature": SIGNATURE}, "timeout": 10, "allow_redirects": False}
        self.session.post.assert_called_once_with(*args, **kwargs)
        self.session.get.assert_not_called()

    def assert_fixed_record(self, capture, message, level):
        self.assertEqual(len(capture.records), 1)
        record = capture.records[0]
        self.assertEqual(record.msg, message)
        self.assertEqual(record.getMessage(), message)
        self.assertEqual(record.levelno, level)
        self.assertEqual(record.args, ())
        self.assertIsNone(record.exc_info)
        self.assertIsNone(record.stack_info)
        self.assertNotIn(MARKER, "\n".join(capture.output))

    def test_actual_lane_and_mock_transport_headers_initial_state(self):
        self.assertEqual(Path(gateway.__file__).resolve(),
                         Path(__file__).resolve().parents[1] / "gateway" / "client.py")
        self.assertIsInstance(self.session, Mock)
        self.assertEqual(self.session.headers, {"User-Agent": "VAMS-Neuron/1.0",
                                                "Content-Type": "application/json"})
        self.assertFalse(self.client.registered)
        self.assertIsNone(self.client.agent_id)
        self.session.post.assert_not_called()
        self.session.get.assert_not_called()

    def test_registration_non200_logs_fixed_message_without_reading_body(self):
        for forbid_body in (False, True):
            with self.subTest(forbid_body=forbid_body):
                self.session.post.reset_mock()
                response = SyntheticResponse(503, forbid_body=forbid_body)
                self.session.post.return_value = response
                with self.assertLogs(gateway.logger, level="ERROR") as logged:
                    result = self.invoke("registration")
                self.assertIsNone(result)
                self.assertFalse(self.client.registered)
                self.assertIsNone(self.client.agent_id)
                self.assertEqual(response.body_reads, 0)
                response.json.assert_not_called()
                self.assert_request("registration")
                self.assert_fixed_record(logged, "Registration failed", logging.ERROR)

    def test_four_exception_paths_emit_only_fixed_messages_preserving_requests_state(self):
        for operation, message, level in (
            ("registration", "Registration error", logging.ERROR),
            ("deregistration", "Deregistration failed", logging.ERROR),
            ("heartbeat", "Heartbeat failed", logging.DEBUG),
            ("result", "Result submission failed", logging.ERROR),
        ):
            with self.subTest(operation=operation):
                self.seed_registered_state()
                self.session.post.reset_mock()
                self.session.post.side_effect = RuntimeError(MARKER)
                with self.assertLogs(gateway.logger, level="DEBUG") as logged:
                    result = self.invoke(operation)
                self.assertIs(result, None if operation == "registration" else False)
                self.assertTrue(self.client.registered)
                self.assertEqual(self.client.agent_id, AGENT)
                self.assert_request(operation)
                self.assert_fixed_record(logged, message, level)

    def test_four_exception_paths_do_not_invoke_exception_str(self):
        for operation, message, level in (
            ("registration", "Registration error", logging.ERROR),
            ("deregistration", "Deregistration failed", logging.ERROR),
            ("heartbeat", "Heartbeat failed", logging.DEBUG),
            ("result", "Result submission failed", logging.ERROR),
        ):
            with self.subTest(operation=operation):
                self.seed_registered_state()
                self.session.post.reset_mock()
                error = NeverStringifyError()
                self.session.post.side_effect = error
                with self.assertLogs(gateway.logger, level="DEBUG") as logged:
                    result = self.invoke(operation)
                self.assertIs(result, None if operation == "registration" else False)
                self.assertEqual(error.string_calls, 0)
                self.assertTrue(self.client.registered)
                self.assertEqual(self.client.agent_id, AGENT)
                self.assert_request(operation)
                self.assert_fixed_record(logged, message, level)

    def test_registration200_preserves_id_fallback_and_default_capabilities(self):
        for data, expected in (({"agent_id": AGENT}, AGENT), ({}, NODE)):
            with self.subTest(returned_id=expected):
                self.session.post.reset_mock()
                response = SyntheticResponse(200, data)
                self.session.post.return_value = response
                result = self.client.register_agent(NODE, PUBLIC_KEY, 0.0)
                self.assertEqual(result, expected)
                self.assertEqual(self.client.agent_id, expected)
                self.assertTrue(self.client.registered)
                self.session.post.assert_called_once_with(BASE_URL + "/agents/register",
                    json=self.registration_payload({"compute": True, "storage": True}), timeout=10, allow_redirects=False)
                response.json.assert_called_once_with()
                self.assertEqual(response.body_reads, 0)

    def test_registration409_preserves_node_identity_without_reading_body_or_json(self):
        response = SyntheticResponse(409, forbid_body=True)
        self.session.post.return_value = response
        self.assertEqual(self.invoke("registration"), NODE)
        self.assertEqual(self.client.agent_id, NODE)
        self.assertTrue(self.client.registered)
        self.assert_request("registration")
        response.json.assert_not_called()
        self.assertEqual(response.body_reads, 0)

    def test_registration_json_failure_uses_same_fixed_catch_and_preserves_state(self):
        self.seed_registered_state()
        response = SyntheticResponse(200)
        response.json.side_effect = ValueError(MARKER)
        self.session.post.return_value = response
        with self.assertLogs(gateway.logger, level="ERROR") as logged:
            self.assertIsNone(self.invoke("registration"))
        self.assertTrue(self.client.registered)
        self.assertEqual(self.client.agent_id, AGENT)
        self.assert_request("registration")
        self.assert_fixed_record(logged, "Registration error", logging.ERROR)

    def test_deregistration200_preserves_agent_id_and_clears_registered_flag(self):
        self.seed_registered_state()
        self.session.post.return_value = SyntheticResponse(200)
        self.assertIs(self.invoke("deregistration"), True)
        self.assertFalse(self.client.registered)
        self.assertEqual(self.client.agent_id, AGENT)
        self.assert_request("deregistration")

    def test_deregistration_non200_preserves_failure_state_and_no_new_log(self):
        self.seed_registered_state()
        self.session.post.return_value = SyntheticResponse(503)
        with self.assertNoLogs(gateway.logger, level="DEBUG"):
            self.assertIs(self.invoke("deregistration"), False)
        self.assertTrue(self.client.registered)
        self.assertEqual(self.client.agent_id, AGENT)
        self.assert_request("deregistration")

    def test_no_agent_deregistration_warning_returns_false_without_http(self):
        with self.assertLogs(gateway.logger, level="WARNING") as logged:
            self.assertIs(self.invoke("deregistration"), False)
        self.assert_fixed_record(logged, "Cannot deregister: No agent_id", logging.WARNING)
        self.session.post.assert_not_called()
        self.assertFalse(self.client.registered)
        self.assertIsNone(self.client.agent_id)

    def test_heartbeat200_and_non200_return_bool_with_same_payload_timeout_state(self):
        for status, expected in ((200, True), (503, False)):
            with self.subTest(status=status):
                self.seed_registered_state()
                self.session.post.reset_mock()
                self.session.post.return_value = SyntheticResponse(status)
                self.assertIs(self.invoke("heartbeat"), expected)
                self.assert_request("heartbeat")
                self.assertTrue(self.client.registered)
                self.assertEqual(self.client.agent_id, AGENT)

    def test_result200_and_non200_return_bool_with_same_payload_timeout_state(self):
        for status, expected in ((200, True), (503, False)):
            with self.subTest(status=status):
                self.seed_registered_state()
                self.session.post.reset_mock()
                self.session.post.return_value = SyntheticResponse(status)
                self.assertIs(self.invoke("result"), expected)
                self.assert_request("result")
                self.assertTrue(self.client.registered)
                self.assertEqual(self.client.agent_id, AGENT)

    def test_poll_tasks_success_missing_tasks_non200_and_exception_are_unchanged(self):
        for status, data, expected, error in (
            (200, {"tasks": [{"task_id": TASK}]}, [{"task_id": TASK}], None),
            (200, {}, [], None),
            (503, {}, [], None),
            (None, {}, [], RuntimeError(MARKER)),
        ):
            with self.subTest(status=status, error=error is not None):
                self.session.get.reset_mock()
                self.session.get.return_value = SyntheticResponse(status, data)
                self.session.get.side_effect = error
                with self.assertNoLogs(gateway.logger, level="DEBUG"):
                    self.assertEqual(self.client.poll_tasks(NODE), expected)
                self.session.get.assert_called_once_with(BASE_URL + "/tasks/pending?node_id=" + NODE, timeout=5, allow_redirects=False)
                self.session.post.assert_not_called()
                self.assertFalse(self.client.registered)
                self.assertIsNone(self.client.agent_id)


if __name__ == "__main__":
    unittest.main()
