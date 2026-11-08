"""Actual GatewayClient runtime/TLS boundary; Mock Session, parent wiring is AST-only."""
import ast
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from neuron.gateway import client as gateway
from neuron.runtime_safety import (
    REGISTERED_MOCK_VARIABLES, LiveModeSafetyError, RuntimeConfigurationError, RuntimeMode,
    load_runtime_policy,
)

BASE = "https://synthetic-gateway.invalid"
LOOPBACKS = ("http://localhost:8000/", "http://127.0.0.1:8000/", "http://[::1]:8000/")
NONLIVE = (RuntimeMode.TEST, RuntimeMode.LOCAL, RuntimeMode.DEMO)
LIVE = (RuntimeMode.STAGING, RuntimeMode.TESTNET, RuntimeMode.PRODUCTION)


class GatewayClientRuntimeContainmentTests(unittest.TestCase):
    def setUp(self):
        self.transport = Mock(name="explicit-synthetic-session")
        self.transport.headers = {}
        self.transport.post.return_value.status_code = 200
        factory = patch.object(gateway.requests, "Session", return_value=self.transport)
        self.factory = factory.start()
        self.addCleanup(factory.stop)

    def assert_context_rejected_before_session(self, ambient, **kwargs):
        self.factory.reset_mock()
        if any(not isinstance(value, str) for value in ambient.values()):
            # Type-malformed inputs belong in the supplied mapping, because
            # the OS environment only accepts strings. Keep ambient valid.
            self.assertNotIn("environ", kwargs)
            kwargs["environ"] = dict(ambient)
            ambient = {"VAMS_ENV": "test"}
        with patch.dict(os.environ, ambient, clear=True):
            with self.assertRaises(RuntimeConfigurationError):
                gateway.GatewayClient(BASE, **kwargs)
        self.factory.assert_not_called()
        self.transport.post.assert_not_called()
        self.transport.get.assert_not_called()

    def test_actual_lane_source_is_loaded(self):
        self.assertEqual(Path(gateway.__file__).resolve(),
                         Path(__file__).resolve().parents[1] / "gateway" / "client.py")
        self.factory.assert_not_called()

    def test_missing_unknown_malformed_uppercase_and_whitespace_modes_reject_before_session(self):
        environments = [{}] + [{"VAMS_ENV": mode} for mode in
            (None, "", "unknown", "TEST", "Testnet", " test", "test ", "test\n", 1, False)]
        for index, env in enumerate(environments):
            with self.subTest(case=index):
                self.assert_context_rejected_before_session(env)

    def test_each_registered_malformed_flag_is_validated_even_for_https(self):
        for flag in REGISTERED_MOCK_VARIABLES:
            with self.subTest(flag=flag):
                self.assert_context_rejected_before_session({"VAMS_ENV": "test", flag: "TRUE"})
        for value in ("yes", "1", "", " false", True, False):
            with self.subTest(malformed=value):
                self.assert_context_rejected_before_session({"VAMS_ENV": "test", REGISTERED_MOCK_VARIABLES[0]: value})

    def test_each_registered_true_mock_flag_rejects_in_every_live_mode_before_session(self):
        for mode in LIVE:
            for flag in REGISTERED_MOCK_VARIABLES:
                with self.subTest(mode=mode.value, flag=flag):
                    self.assert_context_rejected_before_session({"VAMS_ENV": mode.value, flag: "true"})

    def test_https_and_normalization_remain_valid_in_nonlive_modes(self):
        for mode in NONLIVE:
            with self.subTest(mode=mode.value):
                env = {"VAMS_ENV": mode.value, **{flag: "false" for flag in REGISTERED_MOCK_VARIABLES}}
                self.factory.reset_mock()
                with patch.dict(os.environ, env, clear=True):
                    client = gateway.GatewayClient("  " + BASE + "/  ")
                self.assertEqual(client.base_url, BASE)
                self.assertIs(client.session, self.transport)
                self.factory.assert_called_once_with()

    def test_loopback_http_is_preserved_in_all_nonlive_modes(self):
        for mode in NONLIVE:
            for url in LOOPBACKS:
                with self.subTest(mode=mode.value, url=url):
                    self.factory.reset_mock()
                    with patch.dict(os.environ, {"VAMS_ENV": mode.value}, clear=True):
                        client = gateway.GatewayClient(url)
                    self.assertEqual(client.base_url, url.rstrip("/"))
                    self.factory.assert_called_once_with()

    def test_loopback_and_remote_plaintext_reject_in_all_live_modes_before_session(self):
        for mode in LIVE:
            for url in (*LOOPBACKS, "http://synthetic-remote.invalid"):
                with self.subTest(mode=mode.value, url=url):
                    self.factory.reset_mock()
                    with patch.dict(os.environ, {"VAMS_ENV": mode.value}, clear=True):
                        with self.assertRaisesRegex(LiveModeSafetyError, "Legacy GatewayClient"):
                            gateway.GatewayClient(url)
                    self.factory.assert_not_called()

    def test_missinghost_userinfo_unsupported_scheme_and_nonloopback_http_still_reject(self):
        for url in ("", "synthetic-gateway.invalid", "https:///path",
                    "https://synthetic-user@synthetic-gateway.invalid",
                    "ftp://synthetic-gateway.invalid", "http://synthetic-remote.invalid"):
            with self.subTest(url=url):
                self.factory.reset_mock()
                with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True):
                    with self.assertRaises(ValueError):
                        gateway.GatewayClient(url)
                self.factory.assert_not_called()

    def test_matching_explicit_context_cannot_mask_conflicting_actual_mode_and_flags(self):
        source = {"VAMS_ENV": "local", "OMS_MOCK_MODE": "true"}
        policy = load_runtime_policy(source)
        with patch.dict(os.environ, {"VAMS_ENV": "production", "VAMS_MOCK_MODE": "true"}, clear=True):
            with self.assertRaises(RuntimeConfigurationError):
                gateway.GatewayClient(LOOPBACKS[0], runtime_policy=policy, environ=source)
        self.factory.assert_not_called()
        self.transport.post.assert_not_called()
        self.transport.get.assert_not_called()

    def test_supplied_policy_mode_or_registered_flag_mismatch_rejects_before_session(self):
        cases = (
            (load_runtime_policy({"VAMS_ENV": "test"}), {"VAMS_ENV": "testnet"}),
            (load_runtime_policy({"VAMS_ENV": "test", "VAMS_MOCK_MODE": "true"}), {"VAMS_ENV": "test"}),
            (load_runtime_policy({"VAMS_ENV": "test", "OMS_MOCK_MODE": "true"}), {"VAMS_ENV": "test"}),
            (load_runtime_policy({"VAMS_ENV": "test", "OMS_MOCK_MODE": "true"}), {"VAMS_ENV": "test", "TRAILS_MOCK_MODE": "true"}),
        )
        for index, (policy, source) in enumerate(cases):
            with self.subTest(case=index):
                self.assert_context_rejected_before_session({"VAMS_ENV": "test"}, runtime_policy=policy, environ=source)

    def test_supplied_policy_does_not_bypass_invalid_effective_environment(self):
        policy = load_runtime_policy({"VAMS_ENV": "test"})
        for source in ({}, {"VAMS_ENV": "unknown"}, {"VAMS_ENV": "testnet", "OMS_MOCK_MODE": "true"}):
            with self.subTest(source=source):
                self.assert_context_rejected_before_session({"VAMS_ENV": "test"}, runtime_policy=policy, environ=source)

    def test_supplied_policy_without_environ_must_match_ambient_context(self):
        policy = load_runtime_policy({"VAMS_ENV": "test"})
        with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True):
            client = gateway.GatewayClient(BASE, runtime_policy=policy)
        self.assertIs(client.runtime_policy, policy)
        self.assert_context_rejected_before_session({"VAMS_ENV": "testnet"}, runtime_policy=policy)

    def test_nonlive_registered_mock_choices_remain_valid(self):
        for mode in NONLIVE:
            with self.subTest(mode=mode.value):
                source = {"VAMS_ENV": mode.value, **{flag: "true" for flag in REGISTERED_MOCK_VARIABLES}}
                with patch.dict(os.environ, source, clear=True):
                    client = gateway.GatewayClient(BASE, environ=source)
                self.assertEqual(client.runtime_policy.enabled_mock_variables, REGISTERED_MOCK_VARIABLES)
                self.assertFalse(client.runtime_policy.is_live)

    def test_captured_policy_is_immutable_and_url_decisions_ignore_later_source_ambient_drift(self):
        source = {"VAMS_ENV": "local"}
        policy = load_runtime_policy(source)
        with patch.dict(os.environ, source, clear=True):
            client = gateway.GatewayClient(BASE, runtime_policy=policy, environ=source)
        source.update({"VAMS_ENV": "production", "OMS_MOCK_MODE": "true"})
        with patch.dict(os.environ, {"VAMS_ENV": "unknown"}, clear=True):
            self.assertEqual(client._validated_base_url(LOOPBACKS[0]), LOOPBACKS[0].rstrip("/"))
        self.assertIs(client.runtime_policy, policy)
        self.assertIs(client.runtime_policy.mode, RuntimeMode.LOCAL)
        with self.assertRaises(FrozenInstanceError):
            client.runtime_policy.mode = RuntimeMode.PRODUCTION

    def test_frozen_url_and_policy_cannot_be_rebound_before_mocked_heartbeat(self):
        with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True):
            client = gateway.GatewayClient(BASE)
        for field, value in (("base_url", "http://synthetic-remote.invalid"),
                             ("runtime_policy", load_runtime_policy({"VAMS_ENV": "test"})),
                             ("_runtime_configuration_frozen", False),
                             ("_immutable_runtime_fields", frozenset())):
            with self.subTest(field=field), self.assertRaises(RuntimeConfigurationError):
                setattr(client, field, value)
        self.assertTrue(client.send_heartbeat("synthetic-payload", "synthetic-signature-placeholder"))
        self.transport.post.assert_called_once_with(BASE + "/heartbeat",
            json={"payload": "synthetic-payload", "signature": "synthetic-signature-placeholder"}, timeout=5, allow_redirects=False)

    def test_operational_state_and_session_remain_mutable_without_changing_bound_configuration(self):
        with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True):
            client = gateway.GatewayClient(BASE)
        client.agent_id = "synthetic-agent"
        client.registered = True
        replacement = Mock(name="replacement-synthetic-session")
        replacement.post.return_value.status_code = 200
        client.session = replacement
        self.assertTrue(client.send_heartbeat("synthetic-payload", "synthetic-signature-placeholder"))
        replacement.post.assert_called_once_with(BASE + "/heartbeat",
            json={"payload": "synthetic-payload", "signature": "synthetic-signature-placeholder"}, timeout=5, allow_redirects=False)
        self.assertTrue(client.registered)
        self.assertEqual(client.agent_id, "synthetic-agent")
        self.assertIs(client.session, replacement)
        self.assertEqual(client.base_url, BASE)

    def test_parent_runtime_context_forwarding_is_static_ast_evidence_only(self):
        # Never import/execute VamsNeuron: .env/key/signing/dependency effects are outside scope.
        parent = Path(__file__).resolve().parents[1] / "neuron.py"
        calls = [node for node in ast.walk(ast.parse(parent.read_text(encoding="utf-8")))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "GatewayClient"]
        self.assertEqual(len(calls), 1)
        values = {kw.arg: kw.value for kw in calls[0].keywords}
        self.assertEqual(set(values), {"base_url", "runtime_policy", "environ"})
        self.assertEqual(ast.dump(values["runtime_policy"]), ast.dump(ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="runtime_policy", ctx=ast.Load())))
        self.assertEqual(ast.dump(values["environ"]), ast.dump(ast.Name(id="source", ctx=ast.Load())))
        self.assertEqual(ast.dump(values["base_url"]), ast.dump(ast.Name(id="VAMS_GATEWAY", ctx=ast.Load())))


if __name__ == "__main__":
    unittest.main()
