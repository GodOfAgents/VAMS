"""Legacy local client/repository boundary spies; no driver/network is executed."""
import hashlib
import os
import sys
import types
import unittest
from unittest.mock import patch

from neuron import effect_canary as subject
from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError


class LegacyEffectContainmentTests(unittest.TestCase):
    def setUp(self):
        self.events = []

    def probe(self, *args, **kwargs):
        self.events.append('protected-callback')
        raise RuntimeError('protected callback reached')

    def repository(self):
        return subject.PostgresAuthorityRepository('postgresql://synthetic-unused')

    def client(self):
        return subject.HttpObjectProvider('http://127.0.0.1:8765', b'w' * 32, b'o' * 32)

    def retained(self, factory):
        with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True): value = factory()
        self.events.clear()
        return value

    def action(self):
        return subject.ApprovedAction('principal-a', 'task-a', '00000000-0000-0000-0000-000000000001',
            'fixture-provider', subject.ResolvedImplementation('fixture', '1.0.0', 'ab' * 32),
            'principal-a/object', hashlib.sha256(b'fixture').hexdigest(), 1, 1, 1, 2**31)

    def assertRejected(self, operation):
        blocked = False
        observed = None
        try: operation()
        except LiveModeSafetyError: blocked = True
        except Exception as error: observed = type(error).__name__
        self.assertTrue(blocked, f'Boundary did not reject; callback={observed}; events={self.events}')
        self.assertEqual(self.events, [])

    def test_repository_live_constructor_rejects(self):
        for mode in ('staging', 'testnet', 'production'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.assertRejected(self.repository)

    def test_client_live_constructor_precedes_opener_or_key_use(self):
        for mode in ('staging', 'testnet', 'production'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), \
                 patch.object(subject, 'build_opener', side_effect=self.probe):
                self.events.clear(); self.assertRejected(self.client)

    def test_repository_connect_rejects_before_driver(self):
        value = self.retained(self.repository)
        driver = types.ModuleType('psycopg2'); driver.connect = self.probe
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.dict(sys.modules, {'psycopg2': driver}):
            self.assertRejected(value._connect)

    def test_repository_connection_rejects_before_connect(self):
        value = self.retained(self.repository)
        def enter():
            with value._connection(): pass
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(enter)

    def test_repository_initialize_rejects_before_driver(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(value.initialize)

    def test_repository_reserve_rejects_before_driver(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(lambda: value.reserve(self.action(), 100))

    def test_repository_commit_rejects_before_driver_or_effect(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(lambda: value.commit_if_current(self.action(), self.probe))

    def test_repository_revoke_rejects_before_driver(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(lambda: value.revoke('principal-a', 2, 2))

    def test_repository_indeterminate_rejects_before_driver(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(lambda: value.mark_indeterminate(self.action().operation_id))

    def test_repository_provision_rejects_before_input_or_driver(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(lambda: value.provision_capability(None, 1))

    def test_repository_observation_rejects_before_input_or_driver(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(lambda: value.record_observation(None))

    def test_repository_v2_factory_rejects_before_authority_construction(self):
        value = self.retained(self.repository)
        authority = types.ModuleType('neuron.effect_authority_v2')
        authority.PostgresEffectAuthorityV2 = self.probe
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.dict(sys.modules, {'neuron.effect_authority_v2': authority}):
            self.assertRejected(lambda: value.versioned_effects(None, None, None))

    def test_both_constructors_reject_unknown_mode_or_flag_before_opener(self):
        for environment in ({}, {'VAMS_ENV': 'TEST'}, {'VAMS_ENV': 'test', 'VAMS_MOCK_MODE': 'sometimes'}):
            for factory in (self.repository, self.client):
                with self.subTest(environment=environment, factory=factory.__name__), \
                     patch.dict(os.environ, environment, clear=True), patch.object(subject, 'build_opener', side_effect=self.probe):
                    self.events.clear(); self.assertRejected(factory)

    def test_repository_snapshot_cannot_rebind(self):
        value = self.retained(self.repository)
        with self.assertRaises(RuntimeConfigurationError): value.runtime_policy = None

    def test_repository_flag_drift_rejects(self):
        value = self.retained(self.repository)
        with patch.dict(os.environ, {'VAMS_ENV': 'test', 'VAMS_MOCK_MODE': 'true'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.probe):
            self.assertRejected(value.initialize)

    def test_client_request_rejects_before_hmac_or_network(self):
        value = self.retained(self.client)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(subject.hmac, 'new', side_effect=self.probe):
            self.assertRejected(lambda: value._request('POST', '/v1/lookup', {}))

    def test_client_put_rejects_before_request(self):
        value = self.retained(self.client)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_request', side_effect=self.probe):
            self.assertRejected(lambda: value.put(self.action(), b'fixture'))

    def test_client_lookup_rejects_before_request(self):
        value = self.retained(self.client)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_request', side_effect=self.probe):
            self.assertRejected(lambda: value.lookup(self.action().operation_id))

    def test_client_observe_rejects_before_request(self):
        value = self.retained(self.client)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(value, '_request', side_effect=self.probe):
            self.assertRejected(lambda: value.observe(self.action().operation_id))

    def test_client_snapshot_cannot_rebind(self):
        value = self.retained(self.client)
        with self.assertRaises(RuntimeConfigurationError): value.runtime_policy = None

    def test_client_nonlive_mode_drift_rejects(self):
        value = self.retained(self.client)
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True), patch.object(value, '_request', side_effect=self.probe):
            self.assertRejected(lambda: value.lookup(self.action().operation_id))

    def test_explicit_nonlive_construction_remains_supported(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.assertEqual(self.repository().dsn, 'postgresql://synthetic-unused')
                self.assertEqual(self.client().base_url, 'http://127.0.0.1:8765')


if __name__ == '__main__': unittest.main()
