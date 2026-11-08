"""Actual cached transaction-cap verification; seeded state, never keys/signing."""
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import importlib.util
import math
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


def load_actual_wallet_module():
    source = Path(__file__).resolve().parents[1] / "sdk" / "sequence_wallet.py"
    spec = importlib.util.spec_from_file_location("vams_session_caps_under_test", source)
    module = importlib.util.module_from_spec(spec)
    if importlib.util.find_spec("eth_account") is not None:
        import eth_account
        account = eth_account.Account
        mode = "real dependency unused account API guarded"
        context = patch.dict(sys.modules, {})
    else:
        substitute = types.ModuleType("eth_account")
        class UnusedAccount:
            @staticmethod
            def from_key(*args, **kwargs):
                raise AssertionError("Account operations forbidden")
        substitute.Account = UnusedAccount
        account = UnusedAccount
        mode = "only missing unused eth_account import supplied"
        context = patch.dict(sys.modules, {"eth_account": substitute})
    with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True), context, patch.object(
        account, "from_key", side_effect=AssertionError("No key operations")
    ) as account_guard, patch("secrets.token_hex", side_effect=AssertionError("No entropy")) as entropy_guard, patch(
        "requests.sessions.Session.request", side_effect=AssertionError("No HTTP")
    ) as http_guard:
        spec.loader.exec_module(module)
        account_guard.assert_not_called(); entropy_guard.assert_not_called(); http_guard.assert_not_called()
    return module, mode


wallet_module, LOADER_MODE = load_actual_wallet_module()
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
CONTRACT = "0x" + "1" * 40
SESSION = "synthetic-non-signing-session"
OTHER = "synthetic-other-non-signing-session"


class FixedClock:
    calls = []
    @classmethod
    def now(cls, tz=None):
        cls.calls.append(tz)
        return NOW


class NoValueHooks:
    def __init__(self): self.calls = []
    def forbidden(self, name):
        self.calls.append(name)
        raise AssertionError("Input hook forbidden")
    def __str__(self): return self.forbidden("str")
    def __repr__(self): return self.forbidden("repr")
    def __float__(self): return self.forbidden("float")
    def __int__(self): return self.forbidden("int")
    def __lt__(self, other): return self.forbidden("lt")
    def __le__(self, other): return self.forbidden("le")
    def __gt__(self, other): return self.forbidden("gt")
    def __ge__(self, other): return self.forbidden("ge")
    def strip(self): return self.forbidden("strip")


class UnreadableSession(dict):
    def __init__(self, original):
        super().__init__(original)
        self.reads = []
    def __getitem__(self, key):
        self.reads.append(key)
        raise AssertionError("Session fields must not be inspected")
    def get(self, key, default=None):
        self.reads.append(key)
        raise AssertionError("Session fields must not be inspected")


class CapUnreadableSession(dict):
    def __init__(self, original):
        super().__init__(original)
        self.cap_reads = []
    def __getitem__(self, key):
        if key == "max_value_per_tx":
            self.cap_reads.append(key)
            raise AssertionError("Cap must not be inspected yet")
        return dict.__getitem__(self, key)
    def get(self, key, default=None):
        if key == "max_value_per_tx":
            self.cap_reads.append(key)
            raise AssertionError("Cap must not be inspected yet")
        return dict.get(self, key, default)


MALFORMED = {
    "nan": lambda: math.nan, "negative_infinity": lambda: -math.inf,
    "negative_integer": lambda: -1, "negative_float": lambda: -0.125,
    "true": lambda: True, "false": lambda: False, "none": lambda: None,
    "numeric_text": lambda: "100", "nan_text": lambda: "nan", "bytes": lambda: b"100",
    "list": lambda: [], "mapping": lambda: {}, "complex": lambda: complex(100, 0),
    "decimal": lambda: Decimal("100"), "fraction": lambda: Fraction(100, 1),
    "hooks": NoValueHooks, "datetime_object": lambda: NOW,
}


class SequenceSessionCapTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        env.start(); self.addCleanup(env.stop)
        self.guards = []
        for target, name in ((wallet_module.Account, "from_key"), (wallet_module.secrets, "token_hex"),
                             (wallet_module.SessionKeyManager, "create_session_key")):
            guard = patch.object(target, name, side_effect=AssertionError("Keys/creation/signing forbidden"))
            self.guards.append(guard.start()); self.addCleanup(guard.stop)
        guard = patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden"))
        self.guards.append(guard.start()); self.addCleanup(guard.stop)
        FixedClock.calls = []
        clock = patch.object(wallet_module, "datetime", FixedClock)
        clock.start(); self.addCleanup(clock.stop)
        self.manager = wallet_module.SessionKeyManager(types.SimpleNamespace())
        self.session = {"expires_at": NOW.timestamp() + 60,
            "max_value_per_tx": 100, "allowed_contracts": [CONTRACT]}
        self.other = {"expires_at": NOW.timestamp() + 120,
            "max_value_per_tx": 0, "allowed_contracts": [CONTRACT]}
        self.manager.active_sessions = {SESSION: self.session, OTHER: self.other}

    def tearDown(self):
        for guard in self.guards: guard.assert_not_called()

    def verify(self, expected, session_id=SESSION, contract=CONTRACT, value=0, clock_calls=1):
        sessions = self.manager.active_sessions
        entries = dict(sessions)
        snapshots = {key: dict(record) for key, record in entries.items()}
        allowlists = {key: list(record["allowed_contracts"]) for key, record in snapshots.items()}
        result = error = None
        with self.assertNoLogs(level="DEBUG"):
            try: result = self.manager.verify_session_scope(session_id, contract, value)
            except Exception as caught: error = caught
        self.assertIs(type(error), type(None))
        self.assertIs(result, expected)
        self.assertEqual(FixedClock.calls, [timezone.utc] * clock_calls)
        self.assertIs(self.manager.active_sessions, sessions)
        self.assertEqual(set(sessions), set(entries))
        for key, original in entries.items():
            self.assertIs(sessions[key], original)
            self.assertEqual(set(original), set(snapshots[key]))
            for field, old in snapshots[key].items():
                self.assertIs(dict.__getitem__(original, field), old)
                if isinstance(old, NoValueHooks): self.assertEqual(old.calls, [])
            self.assertEqual(dict.__getitem__(original, "allowed_contracts"), allowlists[key])
        for argument in (contract, value):
            if isinstance(argument, NoValueHooks): self.assertEqual(argument.calls, [])

    def test_actual_lane_module_and_guarded_loader_are_used(self):
        self.assertEqual(Path(wallet_module.__file__).resolve(),
                         Path(__file__).resolve().parents[1] / "sdk" / "sequence_wallet.py")
        self.assertIn(LOADER_MODE, ("only missing unused eth_account import supplied", "real dependency unused account API guarded"))
        self.assertEqual(self.manager.MAX_VALIDITY_HOURS, 24)
        self.assertEqual(FixedClock.calls, [])

    def test_missing_cap_denied(self):
        del self.session["max_value_per_tx"]
        self.verify(False)

    def test_malformed_cap_precedes_contract_hooks(self):
        self.session["max_value_per_tx"] = math.nan
        self.verify(False, contract=NoValueHooks())

    def test_unknown_session_precedes_cache_and_value_inspection(self):
        unreadable = UnreadableSession(self.session)
        self.manager.active_sessions[SESSION] = unreadable
        self.verify(False, session_id="synthetic-unknown-session", value=NoValueHooks(), clock_calls=0)
        self.assertEqual(unreadable.reads, [])

    def test_normalized_allowed_contract_still_passes(self):
        self.verify(True, contract="  " + CONTRACT.upper() + "  ", value=100)

    def test_unlisted_contract_still_denied_with_unbounded_cap(self):
        self.session["max_value_per_tx"] = math.inf
        self.verify(False, contract="0x" + "2" * 40)


def malformed_test(factory):
    def test(self):
        self.session["max_value_per_tx"] = factory()
        self.verify(False)
    return test


def cap_control_test(cap, value, accepted):
    def test(self):
        self.session["max_value_per_tx"] = cap
        self.verify(accepted, value=value)
    return test


def invalid_value_test(factory):
    def test(self):
        # Existing input-value checks must return before even expiry/cap lookup.
        unreadable = UnreadableSession(self.session)
        self.manager.active_sessions[SESSION] = unreadable
        self.verify(False, value=factory(), clock_calls=0)
        self.assertEqual(unreadable.reads, [])
    return test


def nonfinite_value_unbounded_test(value):
    def test(self):
        self.session["max_value_per_tx"] = math.inf
        self.verify(False, value=value, clock_calls=0)
    return test


def expiry_precedence_test(case):
    def test(self):
        unreadable = CapUnreadableSession(self.session)
        self.manager.active_sessions[SESSION] = unreadable
        if case == "missing":
            del unreadable["expires_at"]
        elif case == "nan": unreadable["expires_at"] = math.nan
        elif case == "infinity": unreadable["expires_at"] = math.inf
        elif case == "exact": unreadable["expires_at"] = NOW.timestamp()
        else: unreadable["expires_at"] = NOW.timestamp() - 1
        self.verify(False, clock_calls=1 if case in ("exact", "past") else 0)
        self.assertEqual(unreadable.cap_reads, [])
    return test


for _name, _factory in MALFORMED.items():
    setattr(SequenceSessionCapTests, "test_malformed_cap_" + _name, malformed_test(_factory))
for _name, _cap, _value, _accepted in (
    ("zero_integer", 0, 0, True), ("zero_float", 0.0, 0, True), ("negative_zero", -0.0, 0, True),
    ("zero_above", 0, math.nextafter(0.0, math.inf), False),
    ("integer_equal", 100, 100, True), ("integer_above", 100, 101, False),
    ("float_equal", 100.0, 100.0, True), ("float_above", 100.0, 100.25, False),
    ("fractional_equal", 0.125, 0.125, True), ("fractional_above", 0.125, 0.25, False),
    ("huge_integer_equal", 10**400, 10**400, True),
    ("huge_integer_above", 10**400, 10**400+1, False),
    ("unrounded_integer_equal", 2**53+1, 2**53+1, True),
    ("unrounded_integer_above", 2**53+1, 2**53+2, False),
    ("max_float_equal", sys.float_info.max, sys.float_info.max, True),
    ("platinum_zero", math.inf, 0, True), ("platinum_finite", math.inf, 100, True),
    ("platinum_large_float", math.inf, 1e300, True), ("platinum_huge_integer", math.inf, 10**400, True),
):
    setattr(SequenceSessionCapTests, "test_cap_control_" + _name, cap_control_test(_cap, _value, _accepted))
for _name, _factory in {"negative": lambda: -1, "nan": lambda: math.nan,
    "inf": lambda: math.inf, "negative_inf": lambda: -math.inf,
    "true": lambda: True, "false": lambda: False, "none": lambda: None,
    "text": lambda: "1", "hooks": NoValueHooks}.items():
    setattr(SequenceSessionCapTests, "test_invalid_value_precedes_cap_" + _name, invalid_value_test(_factory))
for _name, _value in (("nan", math.nan), ("positive_inf", math.inf), ("negative_inf", -math.inf)):
    setattr(SequenceSessionCapTests, "test_nonfinite_value_rejected_for_platinum_" + _name,
            nonfinite_value_unbounded_test(_value))
for _case in ("missing", "nan", "infinity", "exact", "past"):
    setattr(SequenceSessionCapTests, "test_expiry_precedes_cap_" + _case, expiry_precedence_test(_case))


if __name__ == "__main__": unittest.main()
