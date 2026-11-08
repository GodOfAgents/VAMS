"""Actual SDK facade containment; synthetic identifiers only, no keys/signing."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from neuron.runtime_safety import (
    LiveModeSafetyError, RuntimeConfigurationError, load_runtime_policy,
)


def load_actual_wallet_module():
    source = Path(__file__).resolve().parents[1] / "sdk" / "sequence_wallet.py"
    spec = importlib.util.spec_from_file_location("vams_wallet_containment_under_test", source)
    module = importlib.util.module_from_spec(spec)
    if importlib.util.find_spec("eth_account") is not None:
        spec.loader.exec_module(module)
    else:
        substitute = types.ModuleType("eth_account")
        class UnusedAccount:
            @staticmethod
            def from_key(*args, **kwargs):
                raise AssertionError("Key operations are outside facade containment tests")
        substitute.Account = UnusedAccount
        with patch.dict(sys.modules, {"eth_account": substitute}):
            spec.loader.exec_module(module)
    return module


wallet_module = load_actual_wallet_module()
MODES = ("test", "local", "demo", "staging", "testnet", "production")
OWNER = "0x" + "1" * 40
TARGET = "0x" + "2" * 40


def facade_calls(manager):
    return (
        ("create_wallet", lambda: manager.create_wallet(OWNER)),
        ("build_user_operation", lambda: manager.build_user_operation(OWNER, TARGET, "0x1234", 0)),
        ("send_user_operation", lambda: manager.send_user_operation({"sender": OWNER})),
    )


class WalletContainmentTests(unittest.TestCase):
    def setUp(self):
        # Even dependency-complete environments cannot perform a key operation.
        account_patch = patch.object(wallet_module.Account, "from_key", side_effect=AssertionError("No key operations"))
        account_patch.start()
        self.addCleanup(account_patch.stop)

    def test_nonmock_facades_reject_in_every_mode_before_entropy_or_mutation(self):
        for mode in MODES:
            with patch.dict(os.environ, {"VAMS_ENV": mode}, clear=True):
                for operation in range(3):
                    manager = wallet_module.SequenceWalletManager()
                    name, invoke = facade_calls(manager)[operation]
                    with self.subTest(mode=mode, method=name):
                        with patch.object(wallet_module.secrets, "token_hex", side_effect=AssertionError("No synthetic success entropy")) as entropy:
                            with self.assertRaises(LiveModeSafetyError):
                                invoke()
                            entropy.assert_not_called()
                        self.assertEqual(manager.wallets, {})

    def test_explicit_nonlive_mock_retains_synthetic_shapes(self):
        for mode in ("test", "local", "demo"):
            with self.subTest(mode=mode):
                manager = wallet_module.SequenceWalletManager(mock_mode=True, environ={"VAMS_ENV": mode})
                with patch.object(wallet_module.secrets, "token_hex", side_effect=lambda n: "5" * (2*n)):
                    address = manager.create_wallet(OWNER)
                    operation = manager.build_user_operation(address, TARGET, "0x1234", 0)
                    op_hash = manager.send_user_operation(operation)
                self.assertEqual(address, "0x" + "5" * 40)
                self.assertEqual(manager.wallets, {OWNER: address})
                self.assertEqual(operation["sender"], address)
                self.assertEqual(operation["callData"], "0x1234")
                self.assertEqual(operation["signature"], "0x")
                self.assertEqual(op_hash, "0x" + "5" * 64)

    def test_mock_request_rejected_at_startup_in_every_live_mode(self):
        for mode in ("staging", "testnet", "production"):
            with self.subTest(mode=mode), patch.dict(os.environ, {"VAMS_ENV": mode}, clear=True):
                with self.assertRaises(LiveModeSafetyError):
                    wallet_module.SequenceWalletManager(mock_mode=True)

    def test_missing_or_invalid_runtime_mode_rejected(self):
        for source in ({}, {"VAMS_ENV": ""}, {"VAMS_ENV": "prod"}, {"VAMS_ENV": "Test"}, {"VAMS_ENV": " test"}, {"VAMS_ENV": 1}):
            with self.subTest(source=source):
                with self.assertRaises(RuntimeConfigurationError):
                    wallet_module.SequenceWalletManager(environ=source)

    def test_mock_selection_must_be_boolean(self):
        for value in (None, 0, 1, "false", "true", [], {}):
            with self.subTest(selection_type=type(value).__name__):
                with self.assertRaises(RuntimeConfigurationError):
                    wallet_module.SequenceWalletManager(mock_mode=value, environ={"VAMS_ENV": "test"})

    def test_matching_supplied_policy_is_retained(self):
        source = {"VAMS_ENV": "local"}
        policy = load_runtime_policy(source)
        manager = wallet_module.SequenceWalletManager(runtime_policy=policy, environ=source)
        self.assertIs(manager.runtime_policy, policy)
        self.assertIs(manager.mock_mode, False)

    def test_conflicting_mode_or_registered_mock_policy_rejected(self):
        policy = load_runtime_policy({"VAMS_ENV": "test"})
        for source in ({"VAMS_ENV": "local"}, {"VAMS_ENV": "test", "NEURON_MOCK_MODE": "true"}):
            with self.subTest(source=source):
                with self.assertRaises(RuntimeConfigurationError):
                    wallet_module.SequenceWalletManager(runtime_policy=policy, environ=source)

    def test_effective_runtime_fields_cannot_be_relabelled_or_thawed(self):
        source = {"VAMS_ENV": "test"}
        manager = wallet_module.SequenceWalletManager(mock_mode=True, environ=source)
        for name, value in (("mock_mode", False), ("runtime_policy", load_runtime_policy({"VAMS_ENV": "production"})), ("_runtime_configuration_frozen", False), ("_immutable_runtime_fields", frozenset())):
            with self.subTest(field=name):
                with self.assertRaises(RuntimeConfigurationError):
                    setattr(manager, name, value)
        source["VAMS_ENV"] = "production"
        self.assertEqual(manager.runtime_policy.mode.value, "test")
        with self.assertRaises(LiveModeSafetyError):
            wallet_module.SequenceWalletManager(mock_mode=True, environ=source)

    def test_nonmock_session_manager_access_and_configuration_preserved(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                manager = wallet_module.SequenceWalletManager(config={"core_contracts": [" 0xCore ", "0xCORE"]}, environ={"VAMS_ENV": mode})
                self.assertIs(manager.get_session_manager(), manager.session_manager)
                self.assertIsInstance(manager.get_session_manager(), wallet_module.SessionKeyManager)
                self.assertEqual(manager.core_contracts, {"0xcore"})
                self.assertEqual(manager.get_session_manager().MAX_VALIDITY_HOURS, 24)
                self.assertEqual(manager.get_session_manager().active_sessions, {})

    def test_other_mock_flags_or_config_do_not_enable_wallet_simulation(self):
        manager = wallet_module.SequenceWalletManager(config={"mock_mode": True}, environ={"VAMS_ENV": "test", "NEURON_MOCK_MODE": "true"})
        self.assertIs(manager.mock_mode, False)
        for name, invoke in facade_calls(manager):
            with self.subTest(method=name), self.assertRaises(LiveModeSafetyError):
                invoke()

    def test_registered_mock_flags_are_validated_at_component_boundary(self):
        for source in ({"VAMS_ENV": "test", "NEURON_MOCK_MODE": "yes"}, {"VAMS_ENV": "production", "NEURON_MOCK_MODE": "true"}):
            with self.subTest(source=source), self.assertRaises(RuntimeConfigurationError):
                wallet_module.SequenceWalletManager(environ=source)


if __name__ == "__main__":
    unittest.main()
