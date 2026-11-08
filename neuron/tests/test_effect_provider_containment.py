"""Local provider route containment; spies observe zero storage/authentication work.

These are in-process fixture checks, not PostgreSQL/provider independence or a
production v3 execution qualification. No real credential or service is used.
"""
import hashlib
import io
import json
import os
import types
import unittest
from unittest.mock import patch

from neuron import effect_provider as subject
from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError


class StorageProbe(RuntimeError):
    pass


class LocalProviderContainmentTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        events = self.events

        class PathSpy:
            def __init__(self, *args): events.append('path')
            @property
            def parent(self): return self
            def mkdir(self, *args, **kwargs): events.append('mkdir')
            def stat(self): return types.SimpleNamespace(st_mode=0o700)

        self.patches = [
            patch.object(subject, 'Path', PathSpy),
            patch.object(subject.ObjectProvider, '_initialize_database', side_effect=lambda: events.append('initialize')),
            patch.object(subject.os, 'umask', side_effect=lambda value: events.append('umask') or 0o077),
            patch.object(subject.os, 'chmod', side_effect=lambda *args: events.append('chmod')),
        ]
        for item in self.patches:
            item.start(); self.addCleanup(item.stop)
        self.operation = '00000000-0000-0000-0000-000000000001'
        self.content = b'synthetic local object'

    def provider(self):
        return subject.ObjectProvider('synthetic-unused.sqlite', b'w' * 32, b'o' * 32,
                                      'fixture-provider', 'ab' * 32)

    def retained(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True):
            value = self.provider()
        self.events.clear()
        return value

    def payload(self):
        return {'operation_id': self.operation, 'principal_id': 'principal-a', 'task_id': 'task-a',
            'target': 'fixture-provider', 'implementation_digest': 'ab' * 32,
            'object_key': 'principal-a/object', 'content_hash': hashlib.sha256(self.content).hexdigest(),
            'action_digest': 'cd' * 32, 'authority_epoch': 1, 'policy_revision': 1,
            'expires_at': 2**31, 'content_hex': self.content.hex()}

    def storage_probe(self, *args, **kwargs):
        self.events.append('storage-access')
        raise StorageProbe('protected storage callback was reached')

    def assertRejected(self, operation):
        blocked = False
        observed = None
        try:
            operation()
        except LiveModeSafetyError:
            blocked = True
        except Exception as error:
            observed = type(error).__name__
        self.assertTrue(blocked, f'Runtime boundary did not reject; callback={observed}; events={self.events}')
        self.assertEqual(self.events, [])

    def test_direct_live_constructor_has_zero_storage_effects(self):
        for mode in ('staging', 'testnet', 'production'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.events.clear()
                self.assertRejected(self.provider)

    def test_missing_malformed_unknown_mode_has_zero_storage_effects(self):
        for mode in (None, '', 'TEST', 'test ', 'unknown'):
            env = {} if mode is None else {'VAMS_ENV': mode}
            with self.subTest(mode=mode), patch.dict(os.environ, env, clear=True):
                self.events.clear()
                self.assertRejected(self.provider)

    def test_invalid_registered_mock_flag_rejects_before_storage(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'test', 'AVAIL_MOCK_MODE': 'sometimes'}, clear=True):
            self.assertRejected(self.provider)

    def test_explicit_nonlive_constructor_still_initializes(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                self.events.clear()
                value = self.provider()
                self.assertEqual(value.target_id, 'fixture-provider')
                self.assertEqual(self.events.count('initialize'), 1)

    def test_retained_put_rejects_before_database(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(lambda: value.put(self.payload()))

    def test_retained_lookup_rejects_before_database(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(lambda: value.lookup(self.operation))

    def test_retained_observe_rejects_before_database(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'staging'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(lambda: value.observe(self.operation))

    def test_retained_connect_rejects_before_sqlite(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.object(subject.sqlite3, 'connect', side_effect=self.storage_probe):
            self.assertRejected(value._connect)

    def test_retained_connection_context_rejects_before_connect(self):
        value = self.retained()
        def enter():
            with value._connection(): pass
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(enter)

    def test_retained_authentication_rejects_before_key_use(self):
        value = self.retained()
        environment = {'HTTP_X_VAMS_TIME': str(int(subject.time.time())), 'HTTP_X_VAMS_NONCE': 'a' * 32,
                       'HTTP_X_VAMS_SIGNATURE': '0' * 64}
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.object(subject.hmac, 'new', side_effect=self.storage_probe):
            self.assertRejected(lambda: value._authenticate(environment, 'PUT', '/v1/objects', b'{}', observer=False))

    def test_wsgi_reclassification_denies_before_body_auth_or_storage(self):
        value = self.retained()
        events = self.events
        class InputSpy:
            def read(self, size): events.append('read-body'); return b'{}'
        environment = {'PATH_INFO': '/v1/objects', 'REQUEST_METHOD': 'PUT',
                       'CONTENT_LENGTH': '2', 'wsgi.input': InputSpy()}
        responses = []
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.object(value, '_authenticate', side_effect=self.storage_probe), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            body = b''.join(value.app(environment, lambda status, headers: responses.append((status, headers))))
        self.assertEqual(self.events, [])
        self.assertEqual(responses[0][0], '403 Error')
        self.assertNotIn(b'production', body)

    def test_local_mode_cannot_change_in_place(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(lambda: value.lookup(self.operation))

    def test_mock_configuration_cannot_drift_in_place(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'test', 'VAMS_MOCK_MODE': 'true'}, clear=True), \
             patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(lambda: value.lookup(self.operation))

    def test_runtime_snapshot_is_immutable(self):
        value = self.retained()
        with self.assertRaises(RuntimeConfigurationError): value.runtime_policy = None

    def test_missing_mode_on_retained_object_cannot_open_database(self):
        value = self.retained()
        with patch.dict(os.environ, {}, clear=True), patch.object(value, '_connect', side_effect=self.storage_probe):
            self.assertRejected(lambda: value.lookup(self.operation))

    def test_unrelated_environment_does_not_disable_local_pure_rejection(self):
        value = self.retained()
        with patch.dict(os.environ, {'VAMS_ENV': 'test', 'UNRELATED_FIXTURE_LABEL': 'changed'}, clear=True):
            self.assertIsNone(value.lookup('not-an-operation'))

    def test_cli_flags_are_checked_before_credentials_or_constructor(self):
        env = {'VAMS_ENV': 'test', 'AVAIL_MOCK_MODE': 'sometimes',
            'VAMS_EFFECT_PROVIDER_DB': 'synthetic-unused.sqlite', 'VAMS_EFFECT_WRITER_KEY': '11' * 32,
            'VAMS_EFFECT_OBSERVER_KEY': '22' * 32, 'VAMS_EFFECT_TARGET_ID': 'fixture-provider',
            'VAMS_EFFECT_IMPLEMENTATION_DIGEST': 'ab' * 32}
        with patch.dict(os.environ, env, clear=True), patch.object(subject, 'ObjectProvider', side_effect=self.storage_probe):
            self.assertRejected(subject.from_environment)

    def test_main_live_rejection_precedes_umask_and_server_creation(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), \
             patch.object(subject, 'make_server', side_effect=self.storage_probe):
            self.assertRejected(subject.main)


if __name__ == '__main__':
    unittest.main()
