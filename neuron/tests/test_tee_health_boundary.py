"""Synthetic HTTP-only health probes and their actual CLI display consumer."""
import ast
import os
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from neuron.sdk import phala_tee as P


def local_environment():
    return {
        "VAMS_ENV": "test",
        "PHALA_MOCK_MODE": "false",
        "PHALA_RPC_URL": "https://provider.invalid",
        "VAMS_PHAT_PYTHON_RUNTIME": "synthetic-runtime",
    }


class Response:
    def __init__(self, status=200, close_error=None, status_callback=None, close_callback=None):
        self._status = status
        self.close_error = close_error
        self.status_callback = status_callback
        self.close_callback = close_callback
        self.close_calls = 0
        self.body_accesses = []

    @property
    def status_code(self):
        if self.status_callback:
            self.status_callback()
        return self._status

    def close(self):
        self.close_calls += 1
        if self.close_callback:
            self.close_callback()
        if self.close_error:
            raise self.close_error

    def __getattr__(self, name):
        if name in {"content", "text", "json", "iter_content", "raw"}:
            self.body_accesses.append(name)
            raise AssertionError("health check must not inspect a body")
        raise AttributeError(name)


class Transport:
    def __init__(self, response=None, error=None):
        self.response = response or Response()
        self.error = error
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        if self.error:
            raise self.error
        return self.response

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        if self.error:
            raise self.error
        return self.response


class SecretError(Exception):
    reads = 0
    def __str__(self):
        type(self).reads += 1
        return "synthetic-provider-private marker"
    def __repr__(self):
        type(self).reads += 1
        return "synthetic-provider-private marker"


class TeeHealthBoundaryTests(unittest.TestCase):
    def setUp(self):
        SecretError.reads = 0

    def tearDown(self):
        self.assertEqual(SecretError.reads, 0, "provider exception text was formatted")

    def phala(self, transport):
        return P.PhalaTEE(transport=transport)

    def marlin(self, transport):
        client = P.MarlinOyster()
        client._session = transport
        return client

    def automata(self, transport):
        client = P.AutomataMultiProver()
        client._session = transport
        return client

    def test_three_probes_are_streamed_status_only_and_close_once(self):
        for factory, method in ((self.phala, "get"), (self.marlin, "get"), (self.automata, "post")):
            with self.subTest(method=method), patch.dict(os.environ, local_environment(), clear=True):
                response = Response(200 if method == "post" else 204)
                transport = Transport(response)
                result = factory(transport).check_health()
                self.assertEqual(response.close_calls, 1)
                self.assertEqual(response.body_accesses, [])
                verb, _, kwargs = transport.calls[0]
                self.assertEqual(verb, method)
                self.assertIs(kwargs["stream"], True)
                self.assertIs(kwargs["allow_redirects"], False)
                self.assertEqual(kwargs["timeout"], 15)
                self.assertEqual(result["status"], "healthy")
                self.assertEqual(result["verification_scope"], "http_reachability")
                self.assertEqual(result["evidence_classification"], "non-authoritative")

    def test_http_status_success_rules_and_redirects(self):
        for factory in (self.phala, self.marlin):
            for status, expected in ((199, "degraded"), (200, "healthy"), (299, "healthy"),
                                     (300, "degraded"), (399, "degraded"), (400, "degraded"),
                                     (599, "degraded")):
                with self.subTest(provider=factory.__name__, status=status), patch.dict(os.environ, local_environment(), clear=True):
                    self.assertEqual(factory(Transport(Response(status))).check_health()["status"], expected)
        for status, expected in ((200, "healthy"), (201, "degraded"), (301, "degraded"), (599, "degraded")):
            with self.subTest(provider="automata", status=status):
                self.assertEqual(self.automata(Transport(Response(status))).check_health()["status"], expected)

    def test_no_response_means_no_close_and_errors_are_fixed(self):
        for factory in (self.phala, self.marlin, self.automata):
            with self.subTest(provider=factory.__name__), patch.dict(os.environ, local_environment(), clear=True):
                result = factory(Transport(error=SecretError("marker"))).check_health()
                self.assertEqual(result["status"], "offline")
                self.assertEqual(result["error"], "provider_error")
                self.assertNotIn("marker", repr(result))

    def test_close_failure_is_bounded_and_prevents_healthy_status(self):
        for factory in (self.phala, self.marlin, self.automata):
            with self.subTest(provider=factory.__name__), patch.dict(os.environ, local_environment(), clear=True):
                response = Response(close_error=SecretError("marker"))
                result = factory(Transport(response)).check_health()
                self.assertEqual(response.close_calls, 1)
                self.assertEqual(result["status"], "offline")
                self.assertEqual(result["error"], "provider_error")

    def test_control_exception_closes_acquired_response_and_propagates(self):
        response = Response(status_callback=lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        with patch.dict(os.environ, local_environment(), clear=True):
            with self.assertRaises(KeyboardInterrupt):
                self.phala(Transport(response)).check_health()
        self.assertEqual(response.close_calls, 1)

    def test_close_control_exception_propagates_after_one_close(self):
        response = Response(close_error=KeyboardInterrupt())
        with patch.dict(os.environ, local_environment(), clear=True):
            with self.assertRaises(KeyboardInterrupt):
                self.phala(Transport(response)).check_health()
        self.assertEqual(response.close_calls, 1)

    def test_runtime_drift_during_close_precedes_cleanup_control(self):
        response = Response(
            close_callback=lambda: os.environ.update(VAMS_ENV="production"),
            close_error=KeyboardInterrupt(),
        )
        with patch.dict(os.environ, local_environment(), clear=True):
            with self.assertRaises(P.RuntimeConfigurationError):
                self.phala(Transport(response)).check_health()
        self.assertEqual(response.close_calls, 1)

    def test_malformed_status_is_fixed_and_closes_once(self):
        class BadStatus:
            def __str__(self):
                raise AssertionError("untrusted status must not be formatted")

        for value in (True, 99, 600, BadStatus()):
            with self.subTest(status=type(value).__name__), patch.dict(os.environ, local_environment(), clear=True):
                response = Response(value)
                result = self.phala(Transport(response)).check_health()
                self.assertEqual(response.close_calls, 1)
                self.assertEqual(result["status"], "offline")
                self.assertEqual(result["error"], "provider_error")

    def test_phala_runtime_drift_closes_response_and_precedes_close_error(self):
        response = Response(
            status_callback=lambda: os.environ.update(VAMS_ENV="production"),
            close_error=RuntimeError("cleanup marker"),
        )
        with patch.dict(os.environ, local_environment(), clear=True):
            with self.assertRaises(P.RuntimeConfigurationError):
                self.phala(Transport(response)).check_health()
        self.assertEqual(response.close_calls, 1)

    def test_latency_stops_at_status_before_close(self):
        response = Response()
        with patch.dict(os.environ, local_environment(), clear=True), patch.object(P.time, "monotonic", side_effect=[10.0, 10.25]):
            result = self.phala(Transport(response)).check_health()
        self.assertEqual(result["latency_ms"], 250.0)

    def test_consumer_uses_actual_neuron_method_and_rejects_unmarked_health(self):
        source = Path(P.__file__).parents[1] / "neuron.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        method = next(
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "check_sdk_health"
        )
        namespace = {
            "SDK_AVAILABLE": True,
            "Fore": SimpleNamespace(CYAN="CYAN", YELLOW="YELLOW", MAGENTA="MAGENTA", RED="RED", GREEN="GREEN"),
            "Style": SimpleNamespace(RESET_ALL=""),
            "CelestiaDA": lambda: SimpleNamespace(check_health=lambda: {"status": "offline"}),
            "BittensorSubnet": lambda: SimpleNamespace(check_health=lambda: {"status": "unavailable"}),
            "check_all_tee_health": lambda: {
                "phala": {"status": "healthy", "technology": "Intel SGX"},
                "marlin": {
                    "status": "healthy", "technology": "AWS Nitro",
                    "verification_scope": "http_reachability",
                    "evidence_classification": "non-authoritative",
                },
            },
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)  # nosec B102 # test-only exec of AST-extracted repository source
        output = StringIO()
        with redirect_stdout(output):
            namespace["check_sdk_health"](SimpleNamespace(log=lambda *args: None))
        rendered = output.getvalue()
        self.assertIn("Provider HTTP Reachability (Unverified)", rendered)
        self.assertIn("unknown/unverified", rendered)
        self.assertIn("HTTP reachable; non-authoritative", rendered)
        self.assertIn("GREEN[OK]", rendered)
        self.assertIn("YELLOW[??]", rendered)
        self.assertNotIn("Trust (TEE)", rendered)

    def test_consumer_errors_do_not_format_provider_exceptions(self):
        source = Path(P.__file__).parents[1] / "neuron.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "check_sdk_health")
        def fail():
            raise SecretError("private marker")
        namespace = {
            "SDK_AVAILABLE": True,
            "Fore": SimpleNamespace(CYAN="", YELLOW="", MAGENTA="", RED="", GREEN=""),
            "Style": SimpleNamespace(RESET_ALL=""),
            "CelestiaDA": lambda: SimpleNamespace(check_health=fail),
            "BittensorSubnet": lambda: SimpleNamespace(check_health=lambda: {"status": "unavailable"}),
            "check_all_tee_health": fail,
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)  # nosec B102 # test-only exec of AST-extracted repository source
        output = StringIO()
        with redirect_stdout(output):
            namespace["check_sdk_health"](SimpleNamespace(log=lambda *args: None))
        self.assertNotIn("private marker", output.getvalue())
        self.assertIn("Provider data unavailable", output.getvalue())
        self.assertIn("Provider HTTP status unavailable", output.getvalue())


    def test_status_and_clock_failure_cannot_bypass_acquired_response_cleanup(self):
        def fail_status():
            raise RuntimeError("synthetic-status-error")
        response = Response(status_callback=fail_status)
        caught = None
        result = None
        with patch.dict(os.environ, local_environment(), clear=True), patch.object(
            P.time, "monotonic", side_effect=[0.0, RuntimeError("synthetic-clock-error")]
        ):
            try:
                result = self.phala(Transport(response)).check_health()
            except Exception as exc:
                caught = exc
        self.assertEqual(response.close_calls, 1)
        self.assertIsNone(caught)
        self.assertEqual(result["status"], "offline")
        self.assertEqual(result["error"], "provider_error")
        self.assertIsInstance(result["latency_ms"], (int, float))

    def test_post_request_runtime_check_precedes_status_accessor(self):
        accessed = []
        response = Response(status_callback=lambda: accessed.append("status"))
        transport = Transport(response)
        original_get = transport.get
        def change_mode(*args, **kwargs):
            returned = original_get(*args, **kwargs)
            os.environ["VAMS_ENV"] = "production"
            return returned
        transport.get = change_mode
        with patch.dict(os.environ, local_environment(), clear=True):
            with self.assertRaises(P.RuntimeConfigurationError):
                self.phala(transport).check_health()
        self.assertEqual(accessed, [])
        self.assertEqual(response.close_calls, 1)

    def test_private_drift_from_close_wins_even_after_ambient_restore(self):
        response = Response()
        with patch.dict(os.environ, local_environment(), clear=True):
            client = self.phala(Transport(response))
            def drift_then_restore():
                os.environ["VAMS_ENV"] = "production"
                try:
                    client._assert_current_runtime()
                finally:
                    os.environ["VAMS_ENV"] = "test"
            response.close_callback = drift_then_restore
            with self.assertRaises(P.RuntimeConfigurationError):
                client.check_health()
        self.assertEqual(response.close_calls, 1)

    def test_actual_sdk_aggregate_feeds_actual_panel_as_http_observations(self):
        source = Path(P.__file__).parents[1] / "neuron.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "check_sdk_health")
        responses = [Response(200) for _ in range(3)]
        transports = [Transport(response) for response in responses]
        logs = []
        namespace = dict(
            SDK_AVAILABLE=True,
            Fore=SimpleNamespace(CYAN="", YELLOW="", MAGENTA="", RED="", GREEN=""),
            Style=SimpleNamespace(RESET_ALL=""),
            CelestiaDA=lambda: SimpleNamespace(check_health=lambda: {"status": "offline"}),
            BittensorSubnet=lambda: SimpleNamespace(check_health=lambda: {"status": "unavailable"}),
            check_all_tee_health=P.check_all_tee_health,
        )
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)  # nosec B102 # test-only exec of AST-extracted repository source
        output = StringIO()
        with patch.dict(os.environ, local_environment(), clear=True), patch.object(
            P.requests, "Session", side_effect=transports
        ), redirect_stdout(output):
            namespace["check_sdk_health"](SimpleNamespace(log=lambda message, *args: logs.append(message)))
        self.assertIn("SDK Endpoint Observations (Unverified)", logs)
        self.assertIn("Provider HTTP Reachability (Unverified)", output.getvalue())
        self.assertEqual(output.getvalue().count("HTTP reachable; non-authoritative"), 3)
        for response, transport in zip(responses, transports):
            self.assertEqual(response.body_accesses, [])
            self.assertEqual(response.close_calls, 1)
            self.assertEqual(len(transport.calls), 1)
            self.assertIs(transport.calls[0][2]["stream"], True)
            self.assertIs(transport.calls[0][2]["allow_redirects"], False)


if __name__ == "__main__":
    unittest.main()
