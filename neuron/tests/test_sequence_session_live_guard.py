"""Public SDK calls with non-signing Account/entropy doubles; never real keys."""
from datetime import datetime, timezone
import os
import types
import unittest
from unittest.mock import patch

from neuron.tests import test_sequence_wallet_containment as fixtures
from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError

wallet = fixtures.wallet_module
TARGET = '0x' + '2' * 40
SESSION = 'synthetic-non-signing-session'
LIVE = ('staging', 'testnet', 'production')
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


class FixedClock:
    calls = 0

    @classmethod
    def now(cls, tz=None):
        cls.calls += 1
        return NOW


class SessionCredentialContainmentTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        entropy = patch.object(wallet.secrets, 'token_hex', return_value='synthetic-not-a-private-key')
        account = patch.object(wallet.Account, 'from_key', return_value=types.SimpleNamespace(address=SESSION))
        self.entropy = entropy.start()
        self.account = account.start()
        self.addCleanup(entropy.stop)
        self.addCleanup(account.stop)
        FixedClock.calls = 0
        clock = patch.object(wallet, 'datetime', FixedClock)
        clock.start()
        self.addCleanup(clock.stop)

    def manager(self, mode='test'):
        return wallet.SequenceWalletManager(config={'core_contracts': [TARGET]}, environ={'VAMS_ENV': mode})

    def issue(self, session):
        return session.create_session_key(wallet.TrustTier.SILVER, [TARGET], 24)

    def seed(self, session):
        session.active_sessions[SESSION] = {
            'expires_at': NOW.timestamp() + 60,
            'max_value_per_tx': 1000,
            'allowed_contracts': [TARGET],
        }

    def denied(self, session):
        with self.assertRaises(LiveModeSafetyError):
            self.issue(session)
        self.entropy.assert_not_called()
        self.account.assert_not_called()
        self.assertEqual(session.active_sessions, {})

    def test_live_wallet_cannot_issue_session_credentials(self):
        for mode in LIVE:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.denied(self.manager(mode).get_session_manager())

    def test_direct_session_constructor_cannot_bypass_live_denial(self):
        for mode in LIVE:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.denied(wallet.SessionKeyManager(types.SimpleNamespace(core_contracts={TARGET})))

    def test_local_manager_cannot_issue_after_environment_promotes(self):
        for mode in LIVE:
            session = self.manager().get_session_manager()
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.denied(session)

    def test_live_manager_cannot_be_relabelled_by_nonlive_environment(self):
        for mode in LIVE:
            with self.subTest(mode=mode):
                self.denied(self.manager(mode).get_session_manager())

    def test_live_cached_scope_cannot_authorize(self):
        for mode in LIVE:
            session = self.manager(mode).get_session_manager()
            self.seed(session)
            with self.subTest(mode=mode):
                self.assertIs(session.verify_session_scope(SESSION, TARGET, 0), False)
        self.assertEqual(FixedClock.calls, 0)
        self.entropy.assert_not_called()
        self.account.assert_not_called()

    def test_live_environment_denies_before_reading_untrusted_cache(self):
        class UnreadableCache(dict):
            def __contains__(self, key):
                raise AssertionError('live cache must not be read')
        session = self.manager().get_session_manager()
        session.active_sessions = UnreadableCache()
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True):
            self.assertIs(session.verify_session_scope(SESSION, TARGET, 0), False)

    def test_local_creation_retains_shape_with_non_signing_doubles(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                session = self.manager(mode).get_session_manager()
                record = self.issue(session)
                self.assertEqual(record['session_key_address'], SESSION)
                self.assertEqual(record['allowed_contracts'], [TARGET])
                self.assertEqual(record['max_value_per_tx'], 1000)
                self.assertEqual(record['expires_at'], NOW.timestamp() + 86400)
                self.assertIs(session.active_sessions[SESSION], record)

    def test_runtime_change_during_input_normalization_prevents_entropy(self):
        class PromotingTarget(str):
            def strip(self):
                os.environ['VAMS_ENV'] = 'production'
                return TARGET
        session = self.manager().get_session_manager()
        with self.assertRaises(LiveModeSafetyError):
            session.create_session_key(wallet.TrustTier.SILVER, [PromotingTarget(TARGET)])
        self.entropy.assert_not_called()
        self.account.assert_not_called()
        self.assertEqual(session.active_sessions, {})

    def test_runtime_change_during_factory_prevents_cache_and_credential_release(self):
        session = self.manager().get_session_manager()
        def promote(_):
            os.environ['VAMS_ENV'] = 'production'
            return types.SimpleNamespace(address=SESSION)
        self.account.side_effect = promote
        with self.assertRaises(LiveModeSafetyError):
            self.issue(session)
        self.assertEqual(self.entropy.call_count, 1)
        self.assertEqual(self.account.call_count, 1)
        self.assertEqual(session.active_sessions, {})

    def test_unknown_runtime_neither_issues_nor_authorizes(self):
        for source in ({}, {'VAMS_ENV': 'prod'}, {'VAMS_ENV': 'TEST'}):
            session = self.manager().get_session_manager()
            self.seed(session)
            with self.subTest(source=source), patch.dict(os.environ, source, clear=True):
                with self.assertRaises(RuntimeConfigurationError):
                    self.issue(session)
                self.assertIs(session.verify_session_scope(SESSION, TARGET, 0), False)
        self.entropy.assert_not_called()
        self.account.assert_not_called()


if __name__ == '__main__':
    unittest.main()
