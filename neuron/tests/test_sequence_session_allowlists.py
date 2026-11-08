"""Cached session allowlist shape and exact target membership; no signing."""
from datetime import timezone
import math
import os
import sys
import types
import unittest
from unittest.mock import patch

from neuron.tests import test_sequence_session_caps as prior

wallet_module = prior.wallet_module
CONTRACT = prior.CONTRACT
SESSION = "synthetic-allowlist-session"
NOW = prior.NOW


class NoCoercion:
    def __init__(self):
        self.calls = []
    def forbidden(self, name):
        self.calls.append(name)
        raise AssertionError("Input coercion forbidden")
    def __str__(self): return self.forbidden("str")
    def strip(self): return self.forbidden("strip")
    def __iter__(self): return self.forbidden("iter")
    def __contains__(self, other): return self.forbidden("contains")


class AllowlistUnreadable(dict):
    def __init__(self, original):
        super().__init__(original)
        self.reads = []
    def get(self, name, default=None):
        if name == "allowed_contracts":
            self.reads.append(name)
            raise AssertionError("Allowlist inspected before earlier denial")
        return super().get(name, default)
    def __getitem__(self, name):
        if name == "allowed_contracts":
            self.reads.append(name)
            raise AssertionError("Allowlist inspected before earlier denial")
        return super().__getitem__(name)


class SessionAllowlistShapeTests(unittest.TestCase):
    def setUp(self):
        self.guards = []
        for obj, name in (
            (wallet_module.Account, "from_key"),
            (wallet_module.secrets, "token_hex"),
            (wallet_module.SessionKeyManager, "create_session_key"),
        ):
            guard = patch.object(obj, name, side_effect=AssertionError("Key/entropy/creation forbidden"))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)
        guard = patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden"))
        self.guards.append(guard.start()); self.addCleanup(guard.stop)
        env = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        env.start(); self.addCleanup(env.stop)
        clock = patch.object(wallet_module, "datetime", prior.FixedClock)
        clock.start(); self.addCleanup(clock.stop)
        prior.FixedClock.calls = []
        self.manager = wallet_module.SessionKeyManager(types.SimpleNamespace(core_contracts={CONTRACT}))
        self.session = {"expires_at": NOW.timestamp() + 60, "max_value_per_tx": 100,
                        "allowed_contracts": [CONTRACT]}
        self.manager.active_sessions = {SESSION: self.session}

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def verify(self, expected, target=CONTRACT, value=0):
        sessions = self.manager.active_sessions
        record = self.session
        snapshot = dict(record)
        result = error = None
        with self.assertNoLogs(level="DEBUG"):
            try:
                result = self.manager.verify_session_scope(SESSION, target, value)
            except Exception as caught:
                error = caught
        self.assertIs(type(error), type(None), "Malformed metadata must deny without an exception")
        self.assertIs(result, expected)
        self.assertIs(self.manager.active_sessions, sessions)
        self.assertIs(sessions[SESSION], record)
        self.assertEqual(set(record), set(snapshot))
        for name, original in snapshot.items():
            self.assertIs(dict.__getitem__(record, name), original)
        for item in (target, snapshot.get("allowed_contracts")):
            if isinstance(item, NoCoercion):
                self.assertEqual(item.calls, [])

    def test_missing_allowlist_denied(self):
        del self.session["allowed_contracts"]
        self.verify(False)

    def test_string_allowlist_cannot_authorize_empty_target(self):
        self.session["allowed_contracts"] = CONTRACT
        self.verify(False, "")

    def test_string_allowlist_cannot_authorize_partial_target(self):
        self.session["allowed_contracts"] = CONTRACT
        self.verify(False, CONTRACT[:10])

    def test_string_allowlist_cannot_authorize_full_target(self):
        self.session["allowed_contracts"] = CONTRACT
        self.verify(False)

    def test_normalized_requested_target_with_valid_list_passes(self):
        self.verify(True, "  " + CONTRACT.upper() + "  ", 100)

    def test_member_of_multiple_valid_targets_passes(self):
        self.session["allowed_contracts"] = ["0x" + "2" * 40, CONTRACT]
        self.verify(True)

    def test_partial_target_rejected_for_valid_list(self):
        self.verify(False, CONTRACT[:10])

    def test_unknown_target_rejected_for_valid_list(self):
        self.verify(False, "0x" + "2" * 40)

    def test_empty_target_rejected_for_valid_list(self):
        self.verify(False, "   ")

    def test_empty_allowlist_denied(self):
        self.session["allowed_contracts"] = []
        self.verify(False)

    def test_value_cap_still_enforced(self):
        self.verify(False, value=101)

    def test_platinum_unbounded_cap_does_not_expand_contract_scope(self):
        self.session["max_value_per_tx"] = math.inf
        self.verify(False, "0x" + "2" * 40, 10**400)

    def test_platinum_allowed_finite_value_passes(self):
        self.session["max_value_per_tx"] = math.inf
        self.verify(True, value=10**400)


def malformed_allowlist_test(factory):
    def test(self):
        self.session["allowed_contracts"] = factory()
        self.verify(False)
    return test


def malformed_target_test(factory):
    def test(self):
        self.verify(False, factory())
    return test


def earlier_denial_test(kind):
    def test(self):
        record = AllowlistUnreadable(self.session)
        self.session = record
        self.manager.active_sessions[SESSION] = record
        value = 0
        if kind == "invalid_value": value = math.nan
        elif kind == "expired": record["expires_at"] = NOW.timestamp()
        elif kind == "missing_expiry": del record["expires_at"]
        elif kind == "bad_cap": record["max_value_per_tx"] = math.nan
        elif kind == "over_cap": value = 101
        self.verify(False, NoCoercion(), value)
        self.assertEqual(record.reads, [])
    return test


for name, factory in {
    "none": lambda: None, "boolean": lambda: True, "integer": lambda: 1,
    "mapping": lambda: {CONTRACT: True}, "tuple": lambda: (CONTRACT,),
    "set": lambda: {CONTRACT}, "bytes": lambda: CONTRACT.encode(),
    "object": NoCoercion,
    "list_none_entry": lambda: [CONTRACT, None],
    "list_empty_entry": lambda: [CONTRACT, ""],
    "list_whitespace_entry": lambda: [CONTRACT, "   "],
    "list_integer_entry": lambda: [CONTRACT, 1],
    "list_object_entry": lambda: [CONTRACT, NoCoercion()],
}.items():
    setattr(SessionAllowlistShapeTests, "test_malformed_allowlist_" + name,
            malformed_allowlist_test(factory))
for name, factory in {
    "none": lambda: None, "boolean": lambda: False, "integer": lambda: 1,
    "bytes": lambda: CONTRACT.encode(), "list": lambda: [CONTRACT],
    "object": NoCoercion,
}.items():
    setattr(SessionAllowlistShapeTests, "test_malformed_target_" + name,
            malformed_target_test(factory))
for kind in ("invalid_value", "expired", "missing_expiry", "bad_cap", "over_cap"):
    setattr(SessionAllowlistShapeTests, "test_earlier_denial_" + kind, earlier_denial_test(kind))


if __name__ == "__main__":
    unittest.main()

