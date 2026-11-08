"""Scope-value regressions; no account, key or signing operation is performed."""
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch


def load_actual_wallet_module():
    source = Path(__file__).resolve().parents[1] / "sdk" / "sequence_wallet.py"
    spec = importlib.util.spec_from_file_location("vams_scope_values_under_test", source)
    module = importlib.util.module_from_spec(spec)
    if importlib.util.find_spec("eth_account") is not None:
        spec.loader.exec_module(module)
    else:
        # Only the unused account import is supplied. Verification code is real.
        substitute = types.ModuleType("eth_account")
        class UnusedAccount:
            @staticmethod
            def from_key(*args, **kwargs):
                raise AssertionError("Key creation is outside these scope tests")
        substitute.Account = UnusedAccount
        with patch.dict(sys.modules, {"eth_account": substitute}):
            spec.loader.exec_module(module)
    return module


wallet_module = load_actual_wallet_module()
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
CONTRACT = "0x" + "1" * 40


class FixedClock:
    @classmethod
    def now(cls, tz=None):
        return NOW


class SequenceSessionValueTests(unittest.TestCase):
    def setUp(self):
        self.manager = wallet_module.SessionKeyManager(types.SimpleNamespace())
        self.session_id = "synthetic-non-signing-session"
        self.session = {"expires_at": NOW.timestamp() + 60,
                        "max_value_per_tx": 100,
                        "allowed_contracts": [CONTRACT]}
        self.manager.active_sessions[self.session_id] = self.session
        clock_patch = patch.object(wallet_module, "datetime", FixedClock)
        clock_patch.start()
        self.addCleanup(clock_patch.stop)

    def accepts(self, value):
        return self.manager.verify_session_scope(self.session_id, CONTRACT, value)

    def test_nonfinite_float_values_rejected_for_bounded_and_unbounded_caps(self):
        for cap in (100, math.inf):
            self.session["max_value_per_tx"] = cap
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(cap=cap, value=value):
                    self.assertIs(self.accepts(value), False)

    def test_negative_boolean_and_nonnumeric_inputs_rejected(self):
        for value in (-1, -0.5, True, False, None, "1", object()):
            with self.subTest(input_type=type(value).__name__):
                self.assertIs(self.accepts(value), False)

    def test_existing_finite_cap_boundaries_preserved(self):
        for value in (0, 0.5, 99, 100):
            with self.subTest(value=value):
                self.assertIs(self.accepts(value), True)
        for value in (100.5, 101, 10**400):
            with self.subTest(value=value):
                self.assertIs(self.accepts(value), False)

    def test_existing_unbounded_cap_accepts_finite_values_without_conversion(self):
        self.session["max_value_per_tx"] = math.inf
        for value in (0, 100, 1e300, 10**400):
            with self.subTest(input_type=type(value).__name__):
                self.assertIs(self.accepts(value), True)

    def test_unknown_session_and_unlisted_contract_still_rejected(self):
        self.assertIs(self.manager.verify_session_scope("unknown", CONTRACT, 0), False)
        self.assertIs(self.manager.verify_session_scope(self.session_id, "0x" + "2" * 40, 0), False)

    def test_expired_and_exact_expiry_sessions_still_rejected(self):
        for expiry in (NOW.timestamp() - 1, NOW.timestamp()):
            self.session["expires_at"] = expiry
            with self.subTest(expiry=expiry):
                self.assertIs(self.accepts(0), False)

    def test_rejections_do_not_change_session_state(self):
        snapshot = {**self.session, "allowed_contracts": list(self.session["allowed_contracts"])}
        self.accepts(math.nan)
        self.accepts(-1)
        self.assertEqual(self.session, snapshot)
        self.assertIs(self.manager.active_sessions[self.session_id], self.session)

if __name__ == "__main__":
    unittest.main()
