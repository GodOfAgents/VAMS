"""Actual cached session verification; seeded state only, never keys or signing."""
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
    spec = importlib.util.spec_from_file_location("vams_session_expiry_under_test", source)
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


MALFORMED = {
    "nan": lambda: math.nan, "positive_infinity": lambda: math.inf,
    "negative_infinity": lambda: -math.inf, "true": lambda: True,
    "false": lambda: False, "none": lambda: None,
    "numeric_text": lambda: "1893456060", "nan_text": lambda: "nan",
    "bytes": lambda: b"1893456060", "list": lambda: [], "mapping": lambda: {},
    "complex": lambda: complex(1893456060, 0),
    "decimal": lambda: Decimal("1893456060"), "fraction": lambda: Fraction(1893456060, 1),
    "hooks": NoValueHooks, "datetime_object": lambda: NOW,
}


class SequenceSessionExpiryTests(unittest.TestCase):
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
            # Use dict access to observe a deliberately unreadable fixture safely.
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

    def test_missing_expiry_denied_without_clock_or_later_scope_access(self):
        del self.session["expires_at"]
        self.verify(False, clock_calls=0)

    def test_unknown_session_does_not_inspect_cache_or_invalid_value(self):
        unreadable = UnreadableSession(self.session)
        self.manager.active_sessions[SESSION] = unreadable
        value = NoValueHooks()
        self.verify(False, session_id="synthetic-unknown-session", value=value, clock_calls=0)
        self.assertEqual(unreadable.reads, [])

    def test_malformed_expiry_precedes_value_cap_and_contract_hooks(self):
        self.session["expires_at"] = math.nan
        self.session["max_value_per_tx"] = NoValueHooks()
        contract = NoValueHooks()
        self.verify(False, contract=contract, clock_calls=0)


def malformed_test(factory):
    def test(self):
        self.session["expires_at"] = factory()
        self.verify(False, clock_calls=0)
    return test


def expiry_test(expiry, expected):
    def test(self):
        self.session["expires_at"] = expiry
        self.verify(expected)
    return test


def value_precedence_test(factory):
    def test(self):
        unreadable = UnreadableSession(self.session)
        self.manager.active_sessions[SESSION] = unreadable
        self.verify(False, value=factory(), clock_calls=0)
        self.assertEqual(unreadable.reads, [])
    return test


def scope_control_test(name):
    def test(self):
        if name == "cap_equal": self.verify(True, value=100)
        elif name == "cap_above": self.verify(False, value=100.25)
        elif name == "zero_cap":
            self.session["max_value_per_tx"] = 0
            self.verify(True, value=0)
        elif name == "unbounded_finite_float":
            self.session["max_value_per_tx"] = math.inf
            self.verify(True, value=1e300)
        elif name == "unbounded_huge_integer":
            self.session["max_value_per_tx"] = math.inf
            self.verify(True, value=10**400)
        elif name == "unlisted_contract": self.verify(False, contract="0x" + "2" * 40)
        else: self.verify(True, contract="  " + CONTRACT.upper() + "  ", value=0.5)
    return test


for _name, _factory in MALFORMED.items():
    setattr(SequenceSessionExpiryTests, "test_malformed_expiry_" + _name, malformed_test(_factory))
for _name, _expiry, _accepted in (
    ("future_integer", int(NOW.timestamp()) + 60, True),
    ("future_float", NOW.timestamp() + 0.5, True),
    ("huge_integer", 10**400, True),
    ("max_float", sys.float_info.max, True),
    ("exact_integer", int(NOW.timestamp()), False),
    ("exact_float", NOW.timestamp(), False),
    ("past_fractional", NOW.timestamp() - 0.5, False),
    ("zero_integer", 0, False), ("zero_float", 0.0, False), ("negative_zero", -0.0, False),
    ("negative_integer", -1, False), ("negative_float", -0.125, False),
    ("negative_huge_integer", -(10**400), False),
):
    setattr(SequenceSessionExpiryTests, "test_finite_expiry_" + _name, expiry_test(_expiry, _accepted))
for _name, _factory in {"negative": lambda: -1, "negative_float": lambda: -0.5,
    "nan": lambda: math.nan, "inf": lambda: math.inf, "negative_inf": lambda: -math.inf,
    "true": lambda: True, "false": lambda: False, "none": lambda: None,
    "text": lambda: "1", "hooks": NoValueHooks}.items():
    setattr(SequenceSessionExpiryTests, "test_invalid_value_precedes_expiry_" + _name, value_precedence_test(_factory))
for _name in ("cap_equal", "cap_above", "zero_cap", "unbounded_finite_float", "unbounded_huge_integer", "unlisted_contract", "normalized_contract"):
    setattr(SequenceSessionExpiryTests, "test_scope_control_" + _name, scope_control_test(_name))


if __name__ == "__main__": unittest.main()
