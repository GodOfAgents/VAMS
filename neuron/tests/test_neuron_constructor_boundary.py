"""Actual constructor body with counted collaborators; no full Neuron import."""
import ast
from contextlib import contextmanager
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Mapping, Optional
import unittest
from unittest.mock import patch

from neuron import runtime_safety as R
from neuron import trust as T


def environment(mode='test', **flags):
    return {'VAMS_ENV': mode, **flags}


class ConstructorBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.dict(os.environ, environment(), clear=True)
        self.patch.start()
        self.calls = []
        self.namespace = None
    def tearDown(self):
        self.patch.stop()
    def factory(self, name):
        calls = self.calls
        class Collaborator:
            def __init__(self, *args, **kwargs):
                calls.append((name, args, kwargs))
            def set_primary(self, *args): pass
            def enable_failover(self, *args): pass
        return Collaborator
    @contextmanager
    def actual_constructor(self):
        source = Path(T.__file__).with_name('neuron.py')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VamsNeuron')
        # Keep the exact constructor and its immutable-field declaration. Other
        # methods and package imports are outside this isolated collaborator test.
        body = [n for n in node.body if (isinstance(n, ast.FunctionDef) and n.name == '__init__')
                or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_immutable_runtime_fields' for t in n.targets))]
        shell = ast.ClassDef(name='VamsNeuron', bases=[ast.Name(id='ImmutableRuntimeConfiguration', ctx=ast.Load())], keywords=[], body=body, decorator_list=[])
        namespace = dict(__name__='neuron.constructor_fixture', __package__='neuron',
            os=os, time=SimpleNamespace(time=lambda: 1.0), Optional=Optional, Mapping=Mapping,
            RuntimePolicy=R.RuntimePolicy, RuntimeConfigurationError=R.RuntimeConfigurationError,
            LiveModeSafetyError=R.LiveModeSafetyError, ImmutableRuntimeConfiguration=R.ImmutableRuntimeConfiguration,
            load_runtime_policy=R.load_runtime_policy, resolve_component_mock_mode=R.resolve_component_mock_mode,
            NEURON_MOCK_VARIABLE='NEURON_MOCK_MODE', SDK_AVAILABLE=False, AGENTOS_AVAILABLE=False,
            _DBOS_AVAILABLE=False, VAMS_GATEWAY='https://fixture.invalid',
            NeuronStorage=self.factory('storage'), ProviderManager=self.factory('providers'),
            ComputeManager=self.factory('compute'), LogicLayerMonitor=self.factory('logic'),
            TrustManager=self.factory('trust'), signal=SimpleNamespace(SIGINT=2, SIGTERM=15,
                signal=lambda *args: self.calls.append(('signal_fixture', (), {}))))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[shell], type_ignores=[])), str(source), 'exec'), namespace)
        cls = namespace['VamsNeuron']
        cls.log = lambda *_args, **_kwargs: None
        cls._signal_handler = lambda *_args: None
        replacements = {}
        modules = {
            'neuron.storage': {'ArweaveStorage':'arweave','KwilStorage':'kwil'},
            'neuron.request_queue': {'RequestQueue':'queue'},
            'neuron.sdk.sequence_wallet': {'SequenceWalletManager':'wallet'},
            'neuron.gateway.client': {'GatewayClient':'gateway'},
            'neuron.payments.x402': {'X402Client':'payment'},
            'neuron.economic.circuit_breaker': {'CircuitBreaker':'breaker'},
            'neuron.compute': {name:name for name in ('BittensorProvider','IoNetProvider','AkashProvider','RenderProvider','PhalaComputeProvider')},
        }
        for name, members in modules.items():
            module = ModuleType(name)
            for member, label in members.items():
                setattr(module, member, self.factory(label))
            replacements[name] = module
        self.namespace = namespace
        with patch.dict('sys.modules', replacements):
            yield cls
    def denied(self, cls, **kwargs):
        self.calls.clear()
        with self.assertRaises(R.LiveModeSafetyError):
            cls(**kwargs)
        self.assertEqual(self.calls, [], 'collaborator initialized before policy rejection')

    def test_live_process_cannot_be_masked_by_local_map_or_policy(self):
        with self.actual_constructor() as cls:
            for live in ('staging','testnet','production'):
                for local in ('test','local','demo'):
                    config = environment(local)
                    for supplied_policy in (None, R.load_runtime_policy(config)):
                        with self.subTest(live=live, local=local, policy=supplied_policy is not None), patch.dict(os.environ, environment(live), clear=True):
                            self.denied(cls, environ=config, policy=supplied_policy, mock_mode=False)

    def test_direct_live_startup_stays_disabled(self):
        with self.actual_constructor() as cls:
            for mode in ('staging','testnet','production'):
                with self.subTest(mode=mode), patch.dict(os.environ, environment(mode), clear=True):
                    self.denied(cls, mock_mode=False)

    def test_missing_malformed_actual_mode_cannot_be_supplied_by_map(self):
        with self.actual_constructor() as cls:
            for mode in (None,'','Test',' test','unknown'):
                with self.subTest(mode=mode), patch.dict(os.environ, {}, clear=True):
                    if mode is not None: os.environ['VAMS_ENV'] = mode
                    self.denied(cls, environ=environment('test'))

    def test_supplied_policy_is_typed_and_must_match_process(self):
        with self.actual_constructor() as cls:
            for policy in (object(), False, 'test', R.load_runtime_policy(environment('local')),
                           R.load_runtime_policy(environment('production'))):
                with self.subTest(type=type(policy).__name__):
                    self.denied(cls, policy=policy)

    def test_supplied_map_is_complete_and_must_match_mode(self):
        with self.actual_constructor() as cls:
            for config in ({}, {'endpoint':'fixture'}, environment('local'), environment('production'),
                           environment('test', AKASH_MOCK_MODE='true')):
                with self.subTest(config=config):
                    self.denied(cls, environ=config)

    def test_malformed_flags_in_process_or_supplied_map_reject(self):
        with self.actual_constructor() as cls:
            for variable in ('NEURON_MOCK_MODE','AKASH_MOCK_MODE','PHALA_MOCK_MODE'):
                for raw in ('TRUE','1',''):
                    with self.subTest(variable=variable, raw=raw):
                        with patch.dict(os.environ, {variable:raw}):
                            self.denied(cls, environ=environment())
                        self.denied(cls, environ=environment(**{variable:raw}))

    def test_nonboolean_explicit_mock_selection_rejects(self):
        with self.actual_constructor() as cls:
            for value in (0,1,'true','false',[],object()):
                with self.subTest(value=type(value).__name__):
                    self.denied(cls, mock_mode=value)

    def test_actual_explicit_mock_conflict_rejects(self):
        with self.actual_constructor() as cls:
            with patch.dict(os.environ, environment(NEURON_MOCK_MODE='false'), clear=True):
                self.denied(cls, mock_mode=True)
            with patch.dict(os.environ, environment(NEURON_MOCK_MODE='true'), clear=True):
                self.denied(cls, mock_mode=False)

    def test_supplied_false_flag_cannot_weaken_explicit_local_selection(self):
        with self.actual_constructor() as cls:
            self.denied(cls, mock_mode=True, environ=environment(NEURON_MOCK_MODE='false'))

    def test_live_registered_mock_rejects_even_with_safe_map(self):
        with self.actual_constructor() as cls:
            for mode in ('staging','testnet','production'):
                with self.subTest(mode=mode), patch.dict(os.environ, environment(mode, NEURON_MOCK_MODE='true'), clear=True):
                    self.denied(cls, environ=environment(), mock_mode=False)

    def test_matching_local_modes_complete_constructor_with_fixture_children(self):
        with self.actual_constructor() as cls:
            for mode in ('test','local','demo'):
                with self.subTest(mode=mode), patch.dict(os.environ, environment(mode), clear=True):
                    self.calls.clear()
                    node = cls(environ=environment(mode), policy=R.load_runtime_policy())
                    self.assertEqual(node.runtime_policy, R.load_runtime_policy())
                    self.assertFalse(node.mock_mode)
                    self.assertEqual(sum(name=='storage' for name,_,_ in self.calls), 1)
                    self.assertTrue(any(name=='payment' for name,_,_ in self.calls))

    def test_implicit_registered_mock_remains_available_only_locally(self):
        with self.actual_constructor() as cls, patch.dict(os.environ, environment('demo',NEURON_MOCK_MODE='true'), clear=True):
            node = cls(environ=dict(os.environ))
            self.assertTrue(node.mock_mode)
            self.assertTrue(any(name=='BittensorProvider' for name,_,_ in self.calls))

    def test_explicit_local_mock_without_flag_is_preserved(self):
        with self.actual_constructor() as cls:
            node = cls(mock_mode=True, environ=environment())
            self.assertTrue(node.mock_mode)

    def test_nonpolicy_configuration_is_forwarded_without_environment_mutation(self):
        with self.actual_constructor() as cls:
            config = environment(VAMS_SMART_WALLET_ADDRESS='fixture-public-wallet')
            ambient = dict(os.environ)
            supplied = R.load_runtime_policy(config)
            node = cls(environ=config, policy=supplied)
            payment = next(kwargs for name,_,kwargs in self.calls if name=='payment')
            self.assertEqual(payment['smart_wallet_address'], 'fixture-public-wallet')
            self.assertEqual(payment['environ'], config)
            self.assertEqual(payment['policy'], R.load_runtime_policy())
            self.assertIsNot(node.runtime_policy, supplied, 'caller policy reference became authority')
            self.assertEqual(dict(os.environ), ambient)

    def test_constructor_effective_configuration_remains_immutable(self):
        with self.actual_constructor() as cls:
            node = cls()
            for name, value in (('runtime_policy',None),('mock_mode',True),('use_sdk',True)):
                with self.subTest(name=name), self.assertRaises(R.RuntimeConfigurationError):
                    setattr(node,name,value)

    def test_map_callback_mode_or_flag_drift_rejects_before_storage(self):
        class DriftMap(dict):
            callback = None
            def get(self, key, default=None):
                if self.callback and key=='VAMS_ENV':
                    callback,self.callback=self.callback,None
                    callback()
                return super().get(key,default)
        with self.actual_constructor() as cls:
            for key,value in (('VAMS_ENV','production'),('AKASH_MOCK_MODE','true')):
                with self.subTest(key=key), patch.dict(os.environ, environment(), clear=True):
                    config = DriftMap(environment())
                    config.callback = lambda: os.environ.__setitem__(key,value)
                    self.denied(cls,environ=config)

    def test_mode_change_during_prefix_boolean_evaluation_rejects(self):
        class DriftBoolean:
            def __bool__(self):
                os.environ['VAMS_ENV'] = 'production'
                return False
        with self.actual_constructor() as cls:
            self.denied(cls, use_sdk=DriftBoolean())

    def test_added_false_flag_conflicts_with_explicit_selection_before_storage(self):
        class DriftBoolean:
            def __bool__(self):
                os.environ['NEURON_MOCK_MODE'] = 'false'
                return False
        with self.actual_constructor() as cls:
            self.denied(cls, mock_mode=True, use_sdk=DriftBoolean())


if __name__ == '__main__':
    unittest.main()
