"""Synthetic public TrustManager boundaries; no provider or TEE qualification."""
import ast
import json
from io import BytesIO
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from neuron import trust as T
from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError


def environment(mode='test', mock=False):
    return {'VAMS_ENV': mode, 'NEURON_MOCK_MODE': str(mock).lower()}


class PrivateError(Exception):
    reads = 0
    def __str__(self):
        type(self).reads += 1
        return 'private-provider-marker'
    def __repr__(self):
        type(self).reads += 1
        return 'private-provider-marker'


class Response:
    def __init__(self, code=200, data=None, callback=None, error=None):
        self.code = code
        self.data = {'jsonrpc': '2.0', 'id': 1, 'result': '0x9'} if data is None else data
        self.callback = callback
        self.error = error
        self.closed = 0
        self.headers = {}
        class FixtureRaw:
            def __init__(self, data):
                self.body = BytesIO(json.dumps(data).encode('utf-8'))
            def read(self, amount, decode_content=False):
                return self.body.read(amount)
        self.raw = FixtureRaw(self.data)
    @property
    def status_code(self):
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return self.code
    def json(self):
        return self.data
    def close(self):
        self.closed += 1


class Transport:
    def __init__(self, response=None, callback=None, error=None):
        self.response = response or Response()
        self.callback = callback
        self.error = error
        self.calls = []
        self.headers = {}
    def get(self, *args, **kwargs):
        self.calls.append(('get', args, kwargs))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return self.response
    def post(self, *args, **kwargs):
        self.calls.append(('post', args, kwargs))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return self.response


class TrustBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.dict(os.environ, environment(), clear=True)
        self.mode.start()
        PrivateError.reads = 0
    def tearDown(self):
        self.mode.stop()
        self.assertEqual(PrivateError.reads, 0)
    def provider(self, cls=T.PhalaProvider, **kwargs):
        p = cls(endpoint='https://fixture.invalid')
        p.session = Transport(**kwargs)
        return p
    def assert_unverified(self, info, simulated=False, scope='http_reachability'):
        data = info.to_dict()
        self.assertIs(data['simulated'], simulated)
        self.assertEqual(data['verification_scope'], scope)
        self.assertEqual(data['evidence_classification'], 'non-authoritative')
        self.assertIs(data['usable_as_live_evidence'], False)

    def test_missing_and_malformed_process_mode_reject_before_sessions(self):
        for value in (None, '', 'TEST', ' test', 'unsupported'):
            for ctor in (T.TrustManager, T.PhalaProvider, T.MarlinProvider, T.AutomataProvider, T.create_trust_manager):
                with self.subTest(value=value, constructor=ctor.__name__), patch.dict(os.environ, {}, clear=True):
                    if value is not None:
                        os.environ['VAMS_ENV'] = value
                    with patch.object(T.requests, 'Session') as session:
                        with self.assertRaises(RuntimeConfigurationError):
                            ctor()
                        session.assert_not_called()

    def test_live_mock_reject_before_provider_sessions(self):
        for mode in ('staging', 'testnet', 'production'):
            for registered in (False, True):
                with self.subTest(mode=mode, registered=registered), patch.dict(os.environ, environment(mode, registered), clear=True):
                    with patch.object(T.requests, 'Session') as session:
                        with self.assertRaises(LiveModeSafetyError):
                            T.TrustManager(mock_mode=True)
                        session.assert_not_called()

    def test_truthy_non_boolean_selections_reject(self):
        for value in ('true', 'false', 1, 0, None, [], object()):
            with self.subTest(value=type(value).__name__), patch.object(T.requests, 'Session') as session:
                with self.assertRaises(RuntimeConfigurationError):
                    T.TrustManager(mock_mode=value)
                session.assert_not_called()

    def test_conflicting_and_malformed_registered_flag_reject(self):
        for raw in ('true', 'TRUE', '1', ''):
            with self.subTest(raw=raw), patch.dict(os.environ, {'NEURON_MOCK_MODE': raw}):
                with self.assertRaises(RuntimeConfigurationError):
                    T.TrustManager(mock_mode=False)

    def test_explicit_local_mock_without_registered_override(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            manager = T.create_trust_manager(mock_mode=True)
            self.assertEqual(len(manager.check_all_status()), 3)

    def test_local_mock_provenance_survives_all_outputs(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode), patch.dict(os.environ, environment(mode, True), clear=True):
                manager = T.TrustManager(mock_mode=True)
                statuses = manager.check_all_status()
                self.assertEqual(set(statuses), {'phala', 'marlin', 'automata'})
                for info in statuses.values():
                    self.assertEqual(info.status, T.TrustStatus.HEALTHY)
                    self.assert_unverified(info, True, 'fixture')
                for item in manager.list_providers():
                    self.assertIs(item['simulated'], True)
                    self.assertEqual(item['verification_scope'], 'fixture')
                    self.assertEqual(item['evidence_classification'], 'non-authoritative')
                    self.assertIs(item['usable_as_live_evidence'], False)
                self.assertEqual(manager.get_healthy_providers(), [])

    def test_fixture_latencies_are_preserved(self):
        with patch.dict(os.environ, environment(mock=True), clear=True):
            statuses = T.TrustManager(mock_mode=True).check_all_status()
            self.assertEqual([statuses[n].latency_ms for n in ('phala', 'marlin', 'automata')], [50.0, 45.0, 40.0])

    def test_manager_configuration_immutable(self):
        manager = T.TrustManager()
        for name, value in (('mock_mode', True), ('runtime_policy', None), ('_runtime_configuration_frozen', False)):
            with self.subTest(name=name), self.assertRaises(RuntimeConfigurationError):
                setattr(manager, name, value)

    def test_provider_configuration_immutable(self):
        provider = self.provider()
        with self.assertRaises(RuntimeConfigurationError):
            provider.runtime_policy = None

    def test_every_manager_surface_revalidates_process_mode(self):
        for method in ('check_all_status', '_get_mock_status', 'get_healthy_providers', 'list_providers', 'get_provider'):
            with self.subTest(method=method), patch.dict(os.environ, environment(mock=True), clear=True):
                manager = T.TrustManager(mock_mode=True)
                manager.check_all_status()
                os.environ['VAMS_ENV'] = 'production'
                with self.assertRaises(LiveModeSafetyError):
                    getattr(manager, method)(*(['phala'] if method == 'get_provider' else []))

    def test_mock_helper_cannot_bypass_nonmock_selection(self):
        with self.assertRaises(LiveModeSafetyError):
            T.TrustManager()._get_mock_status()

    def test_registered_flag_change_rejects_cached_observation(self):
        manager = T.TrustManager()
        os.environ['NEURON_MOCK_MODE'] = 'true'
        with self.assertRaises(RuntimeConfigurationError):
            manager.list_providers()

    def test_provider_mode_drift_prevents_transport(self):
        for cls in (T.PhalaProvider, T.MarlinProvider, T.AutomataProvider):
            p = self.provider(cls)
            os.environ['VAMS_ENV'] = 'local'
            with self.assertRaises(RuntimeConfigurationError):
                p.get_status()
            self.assertEqual(p.session.calls, [])
            os.environ['VAMS_ENV'] = 'test'

    def test_callback_drift_stops_manager_before_next_provider(self):
        first = self.provider()
        second = self.provider(T.MarlinProvider)
        first.session.callback = lambda: os.environ.__setitem__('VAMS_ENV', 'local')
        manager = T.TrustManager(providers=[first, second])
        with self.assertRaises(RuntimeConfigurationError):
            manager.check_all_status()
        self.assertEqual(second.session.calls, [])
        self.assertEqual(manager.status_cache, {})

    def test_mock_paths_do_not_call_providers(self):
        with patch.dict(os.environ, environment(mock=True), clear=True):
            p = self.provider(error=AssertionError('must not dispatch'))
            T.TrustManager(providers=[p], mock_mode=True).check_all_status()
            self.assertEqual(p.session.calls, [])

    def test_proof_placeholder_is_unavailable_without_transport(self):
        for mode in ('test', 'local', 'demo', 'staging', 'testnet', 'production'):
            with self.subTest(mode=mode), patch.dict(os.environ, environment(mode), clear=True):
                p = self.provider()
                with self.assertRaisesRegex(LiveModeSafetyError, '^authentic_verifier_unavailable$'):
                    p.generate_proof()
                self.assertEqual(p.session.calls, [])

    def test_old_positional_info_constructor_is_non_authoritative(self):
        info = T.TrustInfo('fixture', T.TrustStatus.HEALTHY, 'legacy descriptor', {'x': 1}, 4.0, None, 123.0)
        self.assertEqual(info.timestamp, 123.0)
        self.assertIs(info.to_dict()['usable_as_live_evidence'], False)
        self.assertEqual(info.to_dict()['evidence_classification'], 'non-authoritative')

    def test_websites_are_observations_without_capacity(self):
        for cls in (T.PhalaProvider, T.MarlinProvider):
            with self.subTest(cls=cls.__name__):
                p = self.provider(cls)
                info = p.get_status()
                self.assertEqual(info.status, T.TrustStatus.HEALTHY)
                self.assertIsNone(info.capacity)
                self.assert_unverified(info)

    def test_rpc_chain_id_is_observation_without_capacity(self):
        info = self.provider(T.AutomataProvider).get_status()
        self.assertEqual(info.status, T.TrustStatus.HEALTHY)
        self.assertIsNone(info.capacity)
        self.assertEqual(info.to_dict()['observations']['chain_id'], 9)
        self.assert_unverified(info)

    def test_observation_never_yields_eligible_names(self):
        p = self.provider()
        manager = T.TrustManager(providers=[p])
        manager.check_all_status()
        self.assertEqual(manager.get_healthy_providers(), [])
        self.assertEqual(manager.list_providers()[0]['evidence_classification'], 'non-authoritative')

    def test_custom_provider_cannot_supply_verified_provenance_or_capacity(self):
        forged = T.TrustInfo('phala', T.TrustStatus.HEALTHY, 'claimed TEE', {'capacity': 999})
        forged.simulated = False
        forged.verification_scope = 'authentic_quote'
        forged.evidence_classification = 'verified'
        p = self.provider()
        p.get_status = lambda: forged
        manager = T.TrustManager(providers=[p])
        info = manager.check_all_status()['phala']
        self.assert_unverified(info, False, 'http_reachability')
        self.assertIsNone(info.capacity)
        self.assertEqual(manager.list_providers()[0]['evidence_classification'], 'non-authoritative')
        self.assertEqual(manager.get_healthy_providers(), [])

    def test_failed_later_provider_does_not_publish_partial_pass(self):
        first = self.provider()
        second = self.provider(T.MarlinProvider)
        second.get_status = lambda: (_ for _ in ()).throw(RuntimeError('synthetic failure'))
        manager = T.TrustManager(providers=[first, second])
        manager.status_cache = {'old': T.TrustInfo('old', T.TrustStatus.HEALTHY, 'old')}
        with self.assertRaises(RuntimeError):
            manager.check_all_status()
        self.assertEqual(manager.status_cache, {})

    def test_later_current_policy_boundary_clears_cache(self):
        with patch.dict(os.environ, environment(mock=True), clear=True):
            manager = T.TrustManager(mock_mode=True)
            manager.check_all_status()
            os.environ['VAMS_ENV'] = 'production'
            with self.assertRaises(LiveModeSafetyError):
                manager.list_providers()
            self.assertEqual(manager.status_cache, {})

    def test_mutated_cache_cannot_make_listing_authoritative(self):
        manager = T.TrustManager(providers=[self.provider()])
        info = manager.check_all_status()['phala']
        info.evidence_classification = 'verified'
        info.verification_scope = 'authentic_quote'
        info.capacity = {'gpu': 999}
        entry = manager.list_providers()[0]
        self.assertEqual(entry['evidence_classification'], 'non-authoritative')
        self.assertIs(entry['usable_as_live_evidence'], False)
        self.assertEqual(manager.get_healthy_providers(), [])

    def test_acquired_response_closed_on_mode_drift(self):
        response = Response(callback=lambda: os.environ.__setitem__('VAMS_ENV', 'local'))
        p = self.provider(response=response)
        with self.assertRaises(RuntimeConfigurationError):
            p.get_status()
        self.assertEqual(response.closed, 1)

    def test_control_event_propagates_after_response_cleanup(self):
        response = Response(error=KeyboardInterrupt())
        p = self.provider(response=response)
        with self.assertRaises(KeyboardInterrupt):
            p.get_status()
        self.assertEqual(response.closed, 1)

    def test_listing_rechecks_policy_after_endpoint_property(self):
        class DriftProvider(T.PhalaProvider):
            drift = None
            @property
            def endpoint(self):
                if self.drift:
                    os.environ[self.drift[0]] = self.drift[1]
                return self._fixture_endpoint
            @endpoint.setter
            def endpoint(self, value):
                self._fixture_endpoint = value
            def get_status(self):
                return T.TrustInfo('phala', T.TrustStatus.HEALTHY, 'fixture')
        for drift in (('VAMS_ENV', 'local'), ('NEURON_MOCK_MODE', 'true')):
            with self.subTest(drift=drift), patch.dict(os.environ, environment(), clear=True):
                p = DriftProvider(endpoint='https://fixture.invalid')
                manager = T.TrustManager(providers=[p])
                manager.check_all_status()
                p.drift = drift
                with self.assertRaises(RuntimeConfigurationError):
                    manager.list_providers()
                self.assertEqual(manager.status_cache, {})

    def test_unknown_initial_listing_carries_no_qualification(self):
        for entry in T.TrustManager().list_providers():
            self.assertEqual(entry['status'], 'unknown')
            self.assertEqual(entry['evidence_classification'], 'non-authoritative')
            self.assertIs(entry['usable_as_live_evidence'], False)

    def test_provider_exception_text_is_not_disclosed(self):
        for cls in (T.PhalaProvider, T.MarlinProvider, T.AutomataProvider):
            with self.subTest(cls=cls.__name__):
                info = self.provider(cls, error=PrivateError()).get_status()
                self.assertEqual(info.status, T.TrustStatus.OFFLINE)
                self.assertEqual(info.error, 'provider_error')
                self.assert_unverified(info)

    def test_malformed_rpc_is_fixed_non_authoritative_failure(self):
        for data in ([], 'bad', {'result': 'bad'}, {'error': {'message': 'private-provider-marker'}}):
            with self.subTest(shape=type(data).__name__):
                p = self.provider(T.AutomataProvider, response=Response(data=data))
                info = p.get_status()
                self.assertNotEqual(info.status, T.TrustStatus.HEALTHY)
                self.assertNotIn('private-provider-marker', str(info.to_dict()))
                self.assert_unverified(info)

    def layer4(self, manager):
        source = Path(T.__file__).with_name('neuron.py')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VamsNeuron')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'check_l4_health')
        module = ast.Module(body=[method], type_ignores=[])
        colours = SimpleNamespace(CYAN='[cyan]', GREEN='[green]', YELLOW='[yellow]', RED='[red]')
        namespace = {'Fore': colours, 'Style': SimpleNamespace(RESET_ALL=''), 'TrustStatus': T.TrustStatus,
                     'LiveModeSafetyError': LiveModeSafetyError, 'RuntimeConfigurationError': RuntimeConfigurationError}
        exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), namespace)
        node = SimpleNamespace(trust_manager=manager, log=lambda text, *_: print(text))
        stream = StringIO()
        with redirect_stdout(stream):
            namespace['check_l4_health'](node)
        return stream.getvalue()

    def test_actual_layer4_labels_simulations_unverified(self):
        with patch.dict(os.environ, environment(mock=True), clear=True):
            output = self.layer4(T.TrustManager(mock_mode=True)).lower()
        self.assertIn('unverified', output)
        self.assertIn('simulated', output)
        self.assertNotIn('[green]', output)

    def test_actual_layer4_http_observation_is_unverified(self):
        output = self.layer4(T.TrustManager(providers=[self.provider()])).lower()
        self.assertIn('http', output)
        self.assertIn('unverified', output)
        self.assertNotIn('[green]', output)

    def test_actual_layer4_unknown_provenance_is_not_healthy(self):
        old = SimpleNamespace(status=T.TrustStatus.HEALTHY, latency_ms=1, technology='legacy')
        output = self.layer4(SimpleNamespace(check_all_status=lambda: {'phala': old})).lower()
        self.assertIn('unknown', output)
        self.assertIn('unverified', output)
        self.assertNotIn('[green]', output)


if __name__ == '__main__':
    unittest.main()
