"""Actual requests redirect handling over bounded in-memory adapters only."""
import io
import json
import logging
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import requests
from requests.adapters import BaseAdapter
from requests.models import Response
from requests.structures import CaseInsensitiveDict

from neuron.gateway import client as gateway

BASE = "https://synthetic-gateway.invalid"
MARKER = "SYNTHETIC_ONLY_PRIVATE_MARKER"
NODE = "synthetic-node-id"
AGENT = "synthetic-agent-id"
RETURNED_AGENT = "synthetic-returned-agent"
PUBLIC_KEY = "synthetic-public-key-placeholder"
SIGNATURE = "synthetic-signature-placeholder"
PAYLOAD = "synthetic-payload"
TASK = "synthetic-task-id"
RESULT = {"output": "synthetic-output"}
CAPABILITIES = {"compute": False, "storage": True}
OPERATIONS = ("registration", "deregistration", "heartbeat", "poll", "result")
LOCATIONS = {
    "cross_https": "https://synthetic-target.invalid/" + MARKER,
    "cross_plaintext": "http://synthetic-target.invalid/" + MARKER,
    "same_origin_https": BASE + "/" + MARKER,
}
REAL_SESSION = requests.sessions.Session


class MemoryAdapter(BaseAdapter):
    """At most two local dispatches; never delegates to HTTPAdapter or sockets."""
    def __init__(self):
        self.status = 200
        self.location = None
        self.data = {"agent_id": RETURNED_AGENT, "tasks": [{"task_id": TASK}]}
        self.calls = []

    def send(self, request, **kwargs):
        if len(self.calls) >= 2:
            raise AssertionError("Synthetic adapter dispatch budget exceeded")
        self.calls.append((request, dict(kwargs)))
        first = len(self.calls) == 1
        response = Response()
        response.request = request
        response.url = request.url
        response.status_code = self.status if first else 200
        response.headers = CaseInsensitiveDict()
        if first and self.location is not None:
            response.headers["Location"] = self.location
        data = {"synthetic_body": MARKER} if first and self.status != 200 else self.data
        response._content = json.dumps(data).encode("utf-8")
        response._content_consumed = True
        response.encoding = "utf-8"
        response.raw = io.BytesIO(response._content)
        return response

    def close(self):
        pass


class GatewayClientRedirectContainmentTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.guards = []
        for target in ("requests.sessions.get_netrc_auth", "requests.sessions.get_environ_proxies",
                       "requests.adapters.HTTPAdapter.send"):
            guard = patch(target, side_effect=AssertionError("External transport/environment access forbidden"))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)
        self.session = REAL_SESSION()
        self.session.trust_env = False
        self.session.auth = None
        self.session.proxies = {}
        self.adapter = MemoryAdapter()
        self.session.mount("https://", self.adapter)
        self.session.mount("http://", self.adapter)
        self.addCleanup(self.session.close)
        factory = patch.object(gateway.requests, "Session", return_value=self.session)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = gateway.GatewayClient(BASE)
        self.factory.assert_called_once_with()
        self.assertIs(self.client.session, self.session)
        self.assertIsInstance(self.session, REAL_SESSION)
        self.assertFalse(self.session.trust_env)
        self.assertIsNone(self.session.auth)
        self.assertEqual(self.session.proxies, {})
        self.assertIs(self.session.get_adapter("https://synthetic-target.invalid"), self.adapter)
        self.assertIs(self.session.get_adapter("http://synthetic-target.invalid"), self.adapter)
        self.client.agent_id = AGENT
        self.client.registered = True

    def tearDown(self):
        self.assertLessEqual(len(self.adapter.calls), 2)
        for guard in self.guards:
            guard.assert_not_called()

    def invoke(self, operation):
        if operation == "registration":
            return self.client.register_agent(NODE, PUBLIC_KEY, 0.0, CAPABILITIES)
        if operation == "deregistration":
            return self.client.deregister_agent(SIGNATURE)
        if operation == "heartbeat":
            return self.client.send_heartbeat(PAYLOAD, SIGNATURE)
        if operation == "poll":
            return self.client.poll_tasks(NODE)
        return self.client.submit_result(TASK, RESULT, SIGNATURE)

    def expected_request(self, operation, base=BASE):
        if operation == "registration":
            return (base + "/agents/register", {"node_id": NODE, "public_key": PUBLIC_KEY,
                "stake_amount": 0.0, "capabilities": CAPABILITIES, "version": "1.0.0"}, 10)
        if operation == "deregistration":
            return base + "/agents/" + AGENT + "/deregister", {"signature": SIGNATURE}, 10
        if operation == "heartbeat":
            return base + "/heartbeat", {"payload": PAYLOAD, "signature": SIGNATURE}, 5
        if operation == "poll":
            return base + "/tasks/pending?node_id=" + NODE, None, 5
        return base + "/tasks/" + TASK + "/result", {"result": RESULT, "signature": SIGNATURE}, 10

    def assert_only_canonical_dispatch(self, operation, base=BASE):
        # The assertion observes actual Session dispatch, not just call kwargs.
        self.assertEqual(len(self.adapter.calls), 1)
        request, kwargs = self.adapter.calls[0]
        url, data, timeout = self.expected_request(operation, base)
        self.assertEqual(request.url, url)
        self.assertEqual(request.method, "GET" if operation == "poll" else "POST")
        if data is None:
            self.assertIsNone(request.body)
        else:
            self.assertEqual(request.body, json.dumps(data, allow_nan=False).encode("utf-8"))
            self.assertEqual(json.loads(request.body), data)
        self.assertEqual(request.headers["User-Agent"], "VAMS-Neuron/1.0")
        self.assertEqual(request.headers["Content-Type"], "application/json")
        for name in ("Authorization", "Proxy-Authorization", "Cookie"):
            self.assertNotIn(name, request.headers)
        self.assertEqual(kwargs["timeout"], timeout)
        self.assertIs(kwargs["verify"], True)
        self.assertEqual(kwargs["proxies"], {})
        self.assertNotIn(MARKER, request.url)

    def assert_failure_result_and_state(self, operation, result):
        if operation == "registration":
            self.assertIsNone(result)
        elif operation == "poll":
            self.assertEqual(result, [])
        else:
            self.assertIs(result, False)
        self.assertTrue(self.client.registered)
        self.assertEqual(self.client.agent_id, AGENT)

    def run_rejection_case(self, operation):
        capture = self.assertLogs(gateway.logger, level="DEBUG") if operation == "registration" else self.assertNoLogs(gateway.logger, level="DEBUG")
        with capture as logged:
            result = self.invoke(operation)
        self.assert_only_canonical_dispatch(operation)
        self.assert_failure_result_and_state(operation, result)
        if operation == "registration":
            self.assertEqual(len(logged.records), 1)
            record = logged.records[0]
            self.assertEqual(record.msg, "Registration failed")
            self.assertEqual(record.levelno, logging.ERROR)
            self.assertEqual(record.args, ())
            self.assertIsNone(record.exc_info)
            self.assertNotIn(MARKER, "\n".join(logged.output))

    def test_actual_lane_client_and_requests_session_source_are_used(self):
        self.assertEqual(Path(gateway.__file__).resolve(),
                         Path(__file__).resolve().parents[1] / "gateway" / "client.py")
        self.assertIs(type(self.session), REAL_SESSION)
        self.assertEqual(REAL_SESSION.__module__, "requests.sessions")
        self.assertEqual(self.adapter.calls, [])

    def test_registration409_retains_existing_identity_without_redirect_or_body_use(self):
        self.adapter.status = 409
        result = self.invoke("registration")
        self.assert_only_canonical_dispatch("registration")
        self.assertEqual(result, NODE)
        self.assertEqual(self.client.agent_id, NODE)
        self.assertTrue(self.client.registered)

    def test_registration200_missing_id_retains_existing_node_fallback(self):
        self.adapter.data = {}
        result = self.invoke("registration")
        self.assert_only_canonical_dispatch("registration")
        self.assertEqual(result, NODE)
        self.assertEqual(self.client.agent_id, NODE)
        self.assertTrue(self.client.registered)

    def test_nonlive_loopback_normal_heartbeat_remains_available(self):
        base = "http://127.0.0.1:8000"
        self.client = gateway.GatewayClient(base + "/", environ={"VAMS_ENV": "test"})
        self.assertTrue(self.invoke("heartbeat"))
        self.assert_only_canonical_dispatch("heartbeat", base)
        self.assertEqual(self.client.base_url, base)


def redirect_test(operation, status, location):
    def test(self):
        self.adapter.status = status
        self.adapter.location = location
        self.run_rejection_case(operation)
    return test


def normal_status_test(operation, status):
    def test(self):
        self.adapter.status = status
        if status != 200:
            self.run_rejection_case(operation)
            return
        result = self.invoke(operation)
        self.assert_only_canonical_dispatch(operation)
        if operation == "registration":
            self.assertEqual(result, RETURNED_AGENT)
            self.assertEqual(self.client.agent_id, RETURNED_AGENT)
            self.assertTrue(self.client.registered)
        elif operation == "deregistration":
            self.assertIs(result, True)
            self.assertFalse(self.client.registered)
            self.assertEqual(self.client.agent_id, AGENT)
        elif operation == "poll":
            self.assertEqual(result, [{"task_id": TASK}])
        else:
            self.assertIs(result, True)
    return test


# Separate unittest methods keep every case within the two-dispatch budget.
for _operation in OPERATIONS:
    for _status in (301, 302, 303, 307, 308):
        for _variant, _location in LOCATIONS.items():
            setattr(GatewayClientRedirectContainmentTests,
                    "test_redirect_" + _operation + "_" + str(_status) + "_" + _variant,
                    redirect_test(_operation, _status, _location))
    for _status in (200, 503):
        setattr(GatewayClientRedirectContainmentTests,
                "test_normal_" + _operation + "_" + str(_status),
                normal_status_test(_operation, _status))


if __name__ == "__main__":
    unittest.main()
