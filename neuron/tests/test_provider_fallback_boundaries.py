"""Provider fallback boundaries. Controlled collaborators are not provider qualification."""
import ast
import hashlib
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from neuron.sdk import bittensor_subnet as B
from neuron.sdk import hardware_registry as H

LIVE = ('staging', 'testnet', 'production')
LOCAL = ('test', 'local', 'demo')
VECTOR_PATH = Path(__file__).parent / 'fixtures' / 'hardware_keccak_vectors50.json'
VECTORS = json.loads(VECTOR_PATH.read_text())['values']


class OpaqueDiagnostic(Exception):
    reads = 0
    def __str__(self):
        type(self).reads += 1
        return 'SYNTHETIC_UPSTREAM_DIAGNOSTIC_MUST_NOT_ESCAPE'
    def __repr__(self):
        type(self).reads += 1
        return 'SYNTHETIC_UPSTREAM_REPR_MUST_NOT_ESCAPE'


class Scalar:
    def __init__(self, value): self.value = value
    def item(self): return self.value


def metagraph():
    return SimpleNamespace(n=Scalar(2), validator_permit=[True, False],
        S=[Scalar(100), Scalar(200)], T=[Scalar(.8), Scalar(.9)],
        C=[Scalar(.7), Scalar(.75)], I=[Scalar(.01), Scalar(.02)],
        E=[Scalar(.001), Scalar(.002)], active=[Scalar(True), Scalar(False)],
        hotkeys=['fixture-hot-0', 'fixture-hot-1'], coldkeys=['fixture-cold-0', 'fixture-cold-1'],
        axons=['fixture-axon-0', 'fixture-axon-1'])


def connected_subtensor():
    return SimpleNamespace(block=321, metagraph=lambda n: metagraph(),
        get_subnet_hyperparameters=lambda n: SimpleNamespace(emission_value=.25),
        burn=lambda n: SimpleNamespace(tao=.125), get_balance=lambda a: SimpleNamespace(tao=7.5))


def client():
    with patch.object(B, 'BITTENSOR_AVAILABLE', False): return B.BittensorSubnet()


class ProviderFallbackBoundariesTest(unittest.TestCase):
    def test_live_disconnected_bittensor_rejects_all_fixture_routes(self):
        for mode in LIVE:
            for method in ('get_subnet_info', 'get_active_miners', '_mock_subnet_info', '_mock_miners', 'list_subnets'):
                with self.subTest(mode=mode, method=method), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                    c = client()
                    with self.assertRaises(LiveModeSafetyError):
                        getattr(c, method)(*(() if method == 'list_subnets' else (1,)))

    def test_live_bittensor_read_errors_reject_instead_of_returning_fixtures(self):
        def fail(*a): raise OpaqueDiagnostic()
        for mode in LIVE:
            for method in ('get_subnet_info', 'get_active_miners'):
                with self.subTest(mode=mode, method=method), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), redirect_stdout(io.StringIO()):
                    c = client(); c._subtensor = SimpleNamespace(get_subnet_hyperparameters=fail, metagraph=fail)
                    with self.assertRaises(LiveModeSafetyError): getattr(c, method)(1)

    def test_unknown_environment_rejects_bittensor_fixtures(self):
        for env in ({}, {'VAMS_ENV': 'prod'}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeConfigurationError): client().get_subnet_info(1)
                with self.assertRaises(RuntimeConfigurationError): client().get_active_miners(1)

    def test_local_bittensor_records_and_dicts_label_simulation(self):
        for mode in LOCAL:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                c = client(); info = c.get_subnet_info(1); miners = c.get_active_miners(1)
                self.assertEqual((info.miners, info.validators, info.emission), (500, 100, .05))
                self.assertEqual(len(miners), 5)
                for record in [info] + miners:
                    self.assertIs(getattr(record, 'simulated', None), True)
                    self.assertEqual(record.to_dict().get('evidence_classification'), 'non-authoritative')
                    self.assertIs(record.to_dict().get('simulated'), True)

    def test_connected_bittensor_read_results_are_preserved_as_observations(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            c = client(); c._subtensor = connected_subtensor()
            info = c.get_subnet_info(1); miners = c.get_active_miners(1, min_stake=150)
            self.assertEqual((info.miners, info.validators, info.emission, info.registration_cost), (2, 1, .25, .125))
            self.assertEqual([(m.uid, m.stake, m.active) for m in miners], [(1, 200, False)])
            self.assertEqual(c.get_balance('fixture-address'), 7.5)
            for record in [info] + miners:
                self.assertIs(getattr(record, 'simulated', None), False)
                self.assertEqual(record.to_dict().get('evidence_classification'), 'provider-observation')

    def test_health_does_not_promote_failed_block_read_to_healthy(self):
        class FailedBlock:
            @property
            def block(self): raise OpaqueDiagnostic()
        c = client(); c._subtensor = FailedBlock(); OpaqueDiagnostic.reads = 0
        with patch.object(B, 'BITTENSOR_AVAILABLE', True):
            self.assertEqual(c.get_block_number(), 0)
            result = c.check_health()
        self.assertEqual(result['status'], 'degraded')
        self.assertNotIn('block', result); self.assertEqual(OpaqueDiagnostic.reads, 0)

    def test_successful_block_health_remains_available(self):
        c = client(); c._subtensor = connected_subtensor()
        with patch.object(B, 'BITTENSOR_AVAILABLE', True): result = c.check_health()
        self.assertEqual((result['status'], result['block']), ('healthy', 321))

    def test_upstream_errors_are_not_formatted_in_bittensor_diagnostics(self):
        def fail(*a, **kw): raise OpaqueDiagnostic()
        c = client(); c._subtensor = SimpleNamespace(get_subnet_hyperparameters=fail, metagraph=fail, get_balance=fail)
        OpaqueDiagnostic.reads = 0
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True), redirect_stdout(io.StringIO()) as output:
            c.get_subnet_info(1); c.get_active_miners(1); c.get_balance('fixture-address')
            with patch.object(B, 'bt', SimpleNamespace(subtensor=fail)): c._init_subtensor()
        self.assertEqual(OpaqueDiagnostic.reads, 0)
        self.assertNotIn('SYNTHETIC_UPSTREAM', output.getvalue())

    def test_inference_unavailable_and_failure_statuses_remain_failure(self):
        c = client(); self.assertFalse(c.query_miner(1, 0, 'fixture-input').success)
        c._subtensor = connected_subtensor(); c._wallet = object()
        def fail(**kw): raise OpaqueDiagnostic()
        OpaqueDiagnostic.reads = 0
        with patch.object(B, 'bt', SimpleNamespace(dendrite=fail)):
            result = c.query_miner(1, 0, 'fixture-input')
        self.assertFalse(result.success); self.assertIsNone(result.response)
        self.assertEqual(OpaqueDiagnostic.reads, 0)
        self.assertNotIn('SYNTHETIC_UPSTREAM', result.error)

    def test_controlled_inference_success_is_only_provider_observation(self):
        c = client(); c._subtensor = connected_subtensor(); c._wallet = object(); calls = []
        def query(*args, **kw): calls.append((args, kw)); return 'fixture-response'
        with patch.object(B, 'bt', SimpleNamespace(dendrite=lambda **kw: SimpleNamespace(query=query), Synapse=lambda **kw: kw)):
            result = c.query_miner(1, 0, 'fixture-input', timeout=2)
        self.assertTrue(result.success); self.assertEqual(result.response, 'fixture-response'); self.assertEqual(len(calls), 1)
        self.assertIs(getattr(result, 'simulated', None), False)
        self.assertEqual(getattr(result, 'evidence_classification', None), 'provider-observation')

    def test_live_hardware_rejects_before_fixture_hashing(self):
        for mode in LIVE:
            for operation in ('get_all_classes', '_offline_classes', 'get_summary'):
                with self.subTest(mode=mode, operation=operation), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), patch.object(H, '_class_id') as digest:
                    with self.assertRaises(LiveModeSafetyError): getattr(H.HardwareRegistryClient(), operation)()
                    digest.assert_not_called()

    def test_unknown_environment_rejects_hardware_fixtures(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(H, '_class_id') as digest:
            with self.assertRaises(RuntimeConfigurationError): H.HardwareRegistryClient().get_all_classes()
            digest.assert_not_called()

    def test_local_hardware_ids_and_collateral_match_frozen_integer_vectors(self):
        nominal = [50000, 25000, 20000, 10000, 10000, 10000, 15000, 5000, 8000, 30000, 30000]
        for mode in LOCAL:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                records = H.HardwareRegistryClient().get_all_classes()
                self.assertEqual([r.name for r in records], H.HardwareClass.ALL)
                self.assertEqual([r.min_collateral for r in records], [n * 10**18 for n in nominal])
                for r in records:
                    self.assertEqual('0x' + r.class_id.hex(), VECTORS[r.name]); self.assertEqual(len(r.class_id), 32)
                    self.assertNotEqual(r.class_id, hashlib.sha3_256(r.name.encode()).digest())
                    self.assertEqual(r.class_id, H._class_id(r.name))
                    self.assertIs(getattr(r, 'simulated', None), True)
                    self.assertEqual(r.to_dict().get('evidence_classification'), 'non-authoritative')

    def test_local_hardware_summary_preserves_provenance(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'demo'}, clear=True): result = H.HardwareRegistryClient().get_summary()
        self.assertEqual((result['total_classes'], result['active_classes'], result['total_nodes']), (11, 11, 0))
        self.assertIs(result.get('simulated'), True)
        self.assertEqual(result.get('evidence_classification'), 'non-authoritative')
        for c in result['classes']:
            self.assertIs(c.get('simulated'), True)
            self.assertEqual(c.get('evidence_classification'), 'non-authoritative')

    def test_connected_hardware_preserves_contract_data_and_observation_labels(self):
        key = bytes.fromhex(VECTORS['GPU_H100'][2:]); calls = []
        class Functions:
            def __getattr__(self, name):
                def invoke(*args):
                    calls.append((name, args))
                    values = {'getRegisteredClassCount': 1, 'getRegisteredClassId': key,
                        'getHardwareClass': (key, 'Fixture observed class', 'GPU', 123, 456, True), 'getTotalNodeCount': 9}
                    return SimpleNamespace(call=lambda: values[name])
                return invoke
        c = H.HardwareRegistryClient(); c.contract = SimpleNamespace(functions=Functions())
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            records = c.get_all_classes(); result = c.get_summary()
        self.assertEqual((records[0].min_collateral, records[0].min_benchmark_score), (123, 456))
        self.assertEqual((result['total_classes'], result['total_nodes']), (1, 9))
        self.assertEqual(sum(n == 'getRegisteredClassCount' for n, a in calls), 1)
        self.assertIs(result.get('simulated'), False)
        self.assertEqual(result.get('evidence_classification'), 'provider-observation')
        self.assertEqual(records[0].to_dict().get('evidence_classification'), 'provider-observation')

    def test_existing_positional_record_construction_remains_supported(self):
        self.assertEqual(B.SubnetInfo(1, 'fixture', .1, 2, 3, .2, 100).miners, 3)
        self.assertTrue(B.MinerInfo(1, 'h', 'c', 1, .2, .3, .4, .5, True).active)
        self.assertFalse(B.InferenceResult(False, None, 1, 0, 'failure').success)
        self.assertEqual(H.HardwareClassInfo(b'x'*32, 'fixture', 'GPU', 1, 2, False).min_collateral, 1)

    def panel(self, status, fail=False):
        tree = ast.parse((Path(B.__file__).parents[1] / 'neuron.py').read_text(encoding='utf8'))
        methods = [n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body if isinstance(n, ast.FunctionDef) and n.name == 'check_sdk_health']
        self.assertEqual(len(methods), 1)
        calls = []
        def subnet(n):
            calls.append(n)
            if fail: raise OpaqueDiagnostic()
            return SimpleNamespace(name='fixture', miners=12, validators=3, simulated=False)
        fake = SimpleNamespace(check_health=lambda: {'status': status}, get_subnet_info=subnet)
        blank = SimpleNamespace(**{n: '' for n in ('CYAN','GREEN','YELLOW','RED','MAGENTA','RESET_ALL')})
        namespace = dict(SDK_AVAILABLE=True, Fore=blank, Style=blank, BittensorSubnet=lambda: fake,
            CelestiaDA=lambda: SimpleNamespace(check_health=lambda: {'status': 'offline'}), check_all_tee_health=lambda: {})
        exec(compile(ast.Module(body=methods, type_ignores=[]), '<actual-neuron-health-method>', 'exec'), namespace)  # nosec B102 # test-only exec of AST-extracted repository source
        with redirect_stdout(io.StringIO()) as output: namespace['check_sdk_health'](SimpleNamespace(log=lambda *a: None))
        return calls, output.getvalue()

    def test_actual_health_panel_does_not_query_counts_when_unhealthy(self):
        for status in ('unavailable', 'offline', 'degraded'):
            with self.subTest(status=status):
                calls, output = self.panel(status)
                self.assertEqual(calls, []); self.assertNotIn('miners', output)

    def test_actual_health_panel_labels_healthy_observations_and_bounds_errors(self):
        calls, output = self.panel('healthy')
        self.assertEqual(calls, [1]); self.assertIn('12 miners, 3 validators', output)
        self.assertIn('provider observation; unverified', output)
        OpaqueDiagnostic.reads = 0
        calls, output = self.panel('healthy', fail=True)
        self.assertEqual(calls, [1]); self.assertEqual(OpaqueDiagnostic.reads, 0)
        self.assertNotIn('SYNTHETIC_UPSTREAM', output)


if __name__ == '__main__': unittest.main()
