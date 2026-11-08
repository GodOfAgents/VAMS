"""Actual lifecycle helpers/methods with memory-only keys, files and dispatch."""
import ast
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
from types import SimpleNamespace
import types
from typing import Tuple
import unittest
from unittest.mock import patch

from neuron import runtime_safety as R
from neuron import trust as T
from neuron.tests import test_neuron_constructor_boundary as H

IDENTITY = 'fixture-identity-memory-only'
KEY_BYTES = b'fixture-key:existing'


class PublicSecretError(R.RuntimeConfigurationError):
    reads = 0
    def __str__(self):
        type(self).reads += 1
        return 'synthetic-private-diagnostic'
    def __repr__(self):
        type(self).reads += 1
        return 'synthetic-private-diagnostic'


class FakeKey:
    def __init__(self, name): self.name = name
    def public_key(self): return self.name


class FakeStream:
    def __init__(self, fs, path, mode):
        self.fs, self.path, self.mode = fs, path, mode
        self.close_calls = 0
    def __enter__(self): return self
    def __exit__(self, *args): self.close(); return False
    def read(self, *args):
        self.fs.event('read')
        value = self.fs.files[self.path]
        return value if 'b' in self.mode else value.decode('utf-8')
    def write(self, data):
        self.fs.event('write')
        count = len(data)-1 if self.fs.short_write else len(data)
        self.fs.files[self.path] = data[:count]
        return count
    def flush(self): self.fs.event('flush')
    def fileno(self): return 17
    def close(self):
        self.close_calls += 1
        self.fs.event('close')


class MemoryFiles:
    def __init__(self):
        self.files = {IDENTITY: KEY_BYTES}
        self.events = []
        self.callbacks, self.errors = {}, {}
        self.streams = []
        self.short_write = False
        self.owner_modes = []
    def event(self, name):
        self.events.append(name)
        callback = self.callbacks.get(name)
        if callback: callback()
        error = self.errors.get(name)
        if error: raise error
    def open(self, path, mode='r', *, opener=None):
        self.event('open:'+mode)
        if mode in ('r','rb'):
            if path not in self.files: raise FileNotFoundError(2,'fixture missing',path)
        elif 'x' in mode:
            self.event('exclusive-check')
            if path in self.files: raise FileExistsError(17,'fixture collision',path)
            if opener: opener(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
            self.files[path] = b''
        elif 'w' in mode:
            self.files[path] = b''
        else:
            raise AssertionError('Unsupported fixture file mode')
        stream = FakeStream(self,path,mode);self.streams.append(stream)
        return stream
    def os_open(self, path, flags, mode):
        self.event('descriptor-open')
        self.owner_modes.append((flags,mode))
        return 17
    def remove(self, path): self.event('remove'); self.files.pop(path,None)


class LifecycleBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'VAMS_ENV':'test'}, clear=True)
        self.env.start()
        self.events, self.logs = [], []
        self.callbacks, self.errors = {}, {}
        self.fs = MemoryFiles()
        PublicSecretError.reads = 0
    def tearDown(self):
        self.env.stop()
        self.assertEqual(PublicSecretError.reads,0,'callback diagnostic was formatted')
    def event(self, name):
        self.events.append(name)
        callback=self.callbacks.get(name)
        if callback: callback()
        error=self.errors.get(name)
        if error: raise error
    @contextmanager
    def node(self):
        holder = H.ConstructorBoundaryTests()
        holder.calls=[]
        with holder.actual_constructor() as cls:
            # Establish a legitimate non-live object with the actual constructor
            # before substituting only the downstream effect collaborators.
            node=cls()
            namespace=holder.namespace
            source=Path(T.__file__).with_name('neuron.py')
            tree=ast.parse(source.read_text(encoding='utf-8'))
            original=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='VamsNeuron')
            namespace.update(__file__=str(source),Tuple=Tuple,HEARTBEAT_INTERVAL=1,json=json,VERSION='fixture-version')
            private_nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name.startswith('_Neuron')]
            private_nodes += [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('_NEURON') for t in n.targets)]
            methods=[n for n in original.body if isinstance(n,ast.FunctionDef) and n.name!='__init__']
            exec(compile(ast.fix_missing_locations(ast.Module(body=private_nodes+methods,type_ignores=[])),str(source),'exec'),namespace)
            for method in methods: setattr(cls,method.name,namespace[method.name])
            cls.log=lambda _node,message,*args:self.logs.append(message)
            cls.print_banner=lambda _node:self.event('banner')
            colours=['GREEN','WHITE','LIGHTBLUE_EX','LIGHTGREEN_EX','LIGHTYELLOW_EX','LIGHTMAGENTA_EX','LIGHTCYAN_EX']
            namespace['Fore']=SimpleNamespace(**{name:'' for name in colours})
            namespace['Style']=SimpleNamespace(RESET_ALL='')
            namespace['IDENTITY_PATH']=IDENTITY
            namespace['open']=self.fs.open
            namespace['os']=SimpleNamespace(environ=os.environ,
                path=SimpleNamespace(dirname=os.path.dirname,abspath=os.path.abspath,join=os.path.join,
                    exists=lambda p:p in self.fs.files,lexists=lambda p:p in self.fs.files),
                urandom=lambda n:b'\0'*n,open=self.fs.os_open,fsync=lambda fd:self.fs.event('fsync'),remove=self.fs.remove)
            def generate(): self.event('generate'); return FakeKey('new')
            def serialize(key): self.event('serialize'); return ('fixture-key:'+key.name).encode()
            def parse(data):
                self.event('parse')
                if not data.startswith(b'fixture-key:'): raise ValueError('fixture invalid key')
                return FakeKey(data.split(b':',1)[1].decode())
            def public(key): self.event('public-key'); return b'P'*64
            def sign(*args): self.event('sign'); return b'S'*64
            namespace.update(generate_private_key=generate,private_key_pem=serialize,load_private_key_pem=parse,
                public_key_bytes=public,sign_message=sign,run_demo_workflow=lambda *args:self.event('workflow'),
                destroy_dbos=lambda:self.event('destroy-engine'))
            def sleep(seconds):
                self.event('sleep')
                node.running=False
            namespace['time']=SimpleNamespace(time=lambda:1.0,sleep=sleep)
            namespace['_DBOS_AVAILABLE']=False
            def send(*args): self.event('gateway'); return True
            node.storage=SimpleNamespace(set_node_info=lambda *args:self.event('node-store'),
                store_heartbeat=lambda *args:self.event('heartbeat-store'),get_stats=lambda:{'pending_sync':0})
            node.gateway=SimpleNamespace(send_heartbeat=send)
            node.breaker=SimpleNamespace(is_active=lambda:True,trip_reason='fixture')
            node.provider_manager=SimpleNamespace(check_all_health=lambda:self.event('provider-health'),
                get_latest_block=lambda:(self.event('provider-block') or SimpleNamespace(height=7,provider='celestia',network='fixture')))
            node._dbos_active=False
            self.node_object,self.namespace=node,namespace
            with redirect_stdout(StringIO()):yield node
    def invoke(self,node,name):
        if name=='sign_telemetry':return node.sign_telemetry(7,'celestia')
        if name=='send_heartbeat':return node.send_heartbeat(SimpleNamespace(height=7,provider='celestia',network='fixture'))
        if name=='run':return node.run(1)
        return getattr(node,name)()
    def capture(self,call):
        try:call()
        except BaseException as exc:return exc
        return None
    def assert_guard(self,error):
        self.assertIsNotNone(error,'runtime denial was absent')
        self.assertEqual(type(error).__name__,'_NeuronRuntimeDriftError','own private runtime signal was lost')

    def test_stale_direct_effect_routes_reject_before_collaborators(self):
        for name in ('load_or_generate_identity','_generate_new_identity','sign_telemetry','send_heartbeat','run_workflow_demo','run'):
            with self.subTest(method=name),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True),self.node() as node:
                os.environ['VAMS_ENV']='production'
                self.events.clear();self.fs.events.clear()
                self.assert_guard(self.capture(lambda:self.invoke(node,name)))
                self.assertEqual(self.events,[])
                self.assertEqual(self.fs.events,[])

    def test_mode_or_flag_change_after_sign_prevents_storage_and_gateway(self):
        with self.node() as node:
            node.sk=FakeKey('existing')
            for key,value in (('VAMS_ENV','production'),('NEURON_MOCK_MODE','true')):
                with self.subTest(key=key),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True):
                    self.events.clear();self.callbacks['sign']=lambda:os.environ.__setitem__(key,value)
                    self.assert_guard(self.capture(lambda:self.invoke(node,'send_heartbeat')))
                    self.assertNotIn('heartbeat-store',self.events);self.assertNotIn('gateway',self.events)

    def test_storage_callback_drift_prevents_gateway(self):
        with self.node() as node:
            self.callbacks['heartbeat-store']=lambda:os.environ.__setitem__('VAMS_ENV','production')
            self.assert_guard(self.capture(lambda:self.invoke(node,'send_heartbeat')))
            self.assertNotIn('gateway',self.events)

    def test_guard_observed_inside_callback_survives_environment_restore(self):
        with self.node() as node:
            def drift():
                os.environ['VAMS_ENV']='production'
                try:
                    guard=getattr(node,'_assert_current_runtime',None)
                    if guard:guard()
                finally:os.environ['VAMS_ENV']='test'
            self.callbacks['sign']=drift
            self.assert_guard(self.capture(lambda:self.invoke(node,'send_heartbeat')))
            self.assertNotIn('heartbeat-store',self.events);self.assertNotIn('gateway',self.events)

    def test_ordinary_gateway_failure_remains_offline_without_raw_diagnostic(self):
        with self.node() as node:
            self.errors['gateway']=OSError('fixture unavailable')
            self.assertFalse(self.invoke(node,'send_heartbeat'))
            self.assertFalse(node.gateway_available)

    def test_public_safety_callback_is_not_the_private_guard_or_raw_error(self):
        with self.node() as node:
            self.errors['gateway']=PublicSecretError()
            error=self.capture(lambda:self.invoke(node,'send_heartbeat'))
            if error is not None:
                self.assertIsNot(type(error),PublicSecretError)
                self.assertNotEqual(type(error).__name__,'_NeuronRuntimeDriftError')
            self.assertEqual(PublicSecretError.reads,0)

    def test_valid_local_heartbeat_preserves_wire_and_stage_order(self):
        with self.node() as node:
            self.assertTrue(self.invoke(node,'send_heartbeat'))
            self.assertLess(self.events.index('sign'),self.events.index('heartbeat-store'))
            self.assertLess(self.events.index('heartbeat-store'),self.events.index('gateway'))
            payload,signature=node.sign_telemetry(7,'celestia')
            self.assertEqual(json.loads(payload),{'type':'VAMS_HEARTBEAT','version':'fixture-version','node_id':'','block_height':7,'provider':'celestia','timestamp':1.0,'nonce':'00'*8})
            self.assertEqual(signature,(b'S'*64).hex())

    def test_existing_invalid_identity_never_generates_or_overwrites(self):
        with self.node() as node:
            self.fs.files[IDENTITY]=b'fixture-invalid-key'
            before=self.fs.files[IDENTITY]
            self.assertIsNotNone(self.capture(node.load_or_generate_identity))
            self.assertNotIn('generate',self.events)
            self.assertEqual(self.fs.files[IDENTITY],before)
            self.assertFalse(any(name.startswith('open:w') or name.startswith('open:x') for name in self.fs.events))

    def test_permission_or_read_missing_error_never_authorizes_creation(self):
        for stage,error in (('open:rb',PermissionError('fixture denied')),('read',FileNotFoundError(2,'fixture read failure','different-fixture'))):
            with self.subTest(stage=stage),self.node() as node:
                self.events.clear();self.fs.errors={stage:error}
                self.assertIsNotNone(self.capture(node.load_or_generate_identity))
                self.assertNotIn('generate',self.events)
                self.assertEqual(self.fs.files[IDENTITY],KEY_BYTES)

    def test_valid_existing_identity_load_is_preserved(self):
        with self.node() as node:
            node.load_or_generate_identity()
            self.assertEqual(node.sk.name,'existing')
            self.assertEqual(node.node_id,(b'P'*64).hex()[:16])
            self.assertEqual(self.fs.files[IDENTITY],KEY_BYTES)
            self.assertNotIn('generate',self.events)

    def test_first_missing_identity_is_exclusive_owner_mode_and_delayed_adoption(self):
        with self.node() as node:
            self.fs.files.pop(IDENTITY)
            def check_unadopted(): self.assertIsNone(node.sk)
            self.fs.callbacks['close']=check_unadopted
            node.load_or_generate_identity()
            self.assertEqual(node.sk.name,'new')
            self.assertIn('open:xb',self.fs.events)
            self.assertTrue(self.fs.owner_modes)
            self.assertTrue(all(mode==0o600 and flags&os.O_EXCL for flags,mode in self.fs.owner_modes))
            self.assertEqual(self.fs.files[IDENTITY],b'fixture-key:new')

    def test_missing_file_does_not_rotate_initialized_identity(self):
        with self.node() as node:
            original=FakeKey('existing');node.sk=original;node.node_id='fixture-existing'
            self.fs.files.pop(IDENTITY)
            self.assertIsNotNone(self.capture(node.load_or_generate_identity))
            self.assertIs(node.sk,original);self.assertNotIn('generate',self.events)

    def test_concurrent_identity_winner_is_not_overwritten_or_deleted(self):
        with self.node() as node:
            self.fs.files.pop(IDENTITY)
            self.fs.callbacks['exclusive-check']=lambda:self.fs.files.__setitem__(IDENTITY,b'fixture-winner')
            self.assertIsNotNone(self.capture(node._generate_new_identity))
            self.assertEqual(self.fs.files[IDENTITY],b'fixture-winner')
            self.assertNotIn('write',self.fs.events);self.assertNotIn('remove',self.fs.events)
            self.assertIsNone(node.sk)

    def test_failed_writes_flush_close_and_short_write_do_not_adopt_or_unlink(self):
        for stage in ('write','flush','close','short-write'):
            with self.subTest(stage=stage),self.node() as node:
                self.fs.files.pop(IDENTITY,None)
                self.fs.errors={} if stage=='short-write' else {stage:OSError('fixture persistence failure')}
                self.fs.short_write=stage=='short-write'
                self.assertIsNotNone(self.capture(node._generate_new_identity))
                self.assertIsNone(node.sk)
                self.assertNotIn('remove',self.fs.events)
                self.assertTrue(all(s.close_calls==1 for s in self.fs.streams))
                self.fs.errors={};self.fs.short_write=False;self.fs.streams.clear()

    def test_generation_callback_drift_stops_serialization_and_file_creation(self):
        with self.node() as node:
            self.fs.files.pop(IDENTITY)
            self.callbacks['generate']=lambda:os.environ.__setitem__('VAMS_ENV','production')
            self.assert_guard(self.capture(node._generate_new_identity))
            self.assertNotIn('serialize',self.events)
            self.assertNotIn('open:xb',self.fs.events)

    def test_write_callback_drift_stops_flush_and_adoption(self):
        with self.node() as node:
            self.fs.files.pop(IDENTITY)
            self.fs.callbacks['write']=lambda:os.environ.__setitem__('VAMS_ENV','production')
            self.assert_guard(self.capture(node._generate_new_identity))
            self.assertNotIn('flush',self.fs.events)
            self.assertIsNone(node.sk)

    def test_read_guard_priority_survives_restoring_close_control(self):
        with self.node() as node:
            self.fs.callbacks['read']=lambda:os.environ.__setitem__('VAMS_ENV','production')
            self.fs.callbacks['close']=lambda:os.environ.__setitem__('VAMS_ENV','test')
            self.fs.errors['close']=KeyboardInterrupt()
            self.assert_guard(self.capture(node.load_or_generate_identity))
            self.assertNotIn('generate',self.events)
            self.assertEqual(self.fs.streams[-1].close_calls,1)

    def test_private_guard_prevents_loop_sleep_retry(self):
        with self.node() as node:
            self.callbacks['provider-block']=lambda:os.environ.__setitem__('VAMS_ENV','production')
            self.assert_guard(self.capture(lambda:node.run(1)))
            self.assertNotIn('sign',self.events)
            self.assertNotIn('sleep',self.events)

    def test_loop_callback_drift_does_not_increment_progress(self):
        with self.node() as node:
            calls=[0]
            def block():
                calls[0]+=1
                if calls[0]==2:os.environ['VAMS_ENV']='production'
                return SimpleNamespace(height=7,provider='celestia',network='fixture')
            node.provider_manager.get_latest_block=block
            self.assert_guard(self.capture(lambda:node.run(1)))
            self.assertEqual(node.blocks_seen,0)
            self.assertNotIn('sign',self.events);self.assertNotIn('sleep',self.events)

    def test_breaker_callback_drift_stops_provider_sleep_and_progress(self):
        for active in (True, False):
            for variable,value in (('VAMS_ENV','production'),('NEURON_MOCK_MODE','true')):
                with self.subTest(active=active,variable=variable),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True),self.node() as node:
                    self.events.clear()
                    def breaker():
                        self.event('breaker')
                        os.environ[variable]=value
                        return active
                    node.breaker.is_active=breaker
                    self.assert_guard(self.capture(lambda:node.run(1)))
                    self.assertEqual(self.events.count('provider-block'),1,'next provider call followed breaker drift')
                    self.assertNotIn('sleep',self.events)
                    self.assertNotIn('gateway',self.events)
                    self.assertEqual(node.blocks_seen,0)

    def test_manually_restored_live_state_is_not_admissible(self):
        with self.node() as node:
            with patch.dict(os.environ,{'VAMS_ENV':'production'},clear=True):
                # Simulate an unsupported old/restored instance; normal current
                # construction already rejects this state before collaborators.
                object.__setattr__(node,'runtime_policy',R.load_runtime_policy())
                self.assert_guard(self.capture(lambda:self.invoke(node,'send_heartbeat')))
                self.assertNotIn('sign',self.events)

    def test_owned_shutdown_remains_available_after_policy_change(self):
        with self.node() as node:
            node._dbos_active=True;self.namespace['_DBOS_AVAILABLE']=True
            os.environ['VAMS_ENV']='production'
            node._signal_handler(2,None)
            self.assertFalse(node.running)
            self.assertIn('destroy-engine',self.events)

    @contextmanager
    def demo_engine(self):
        outer=self
        class Engine:
            def __call__(self,**kwargs):outer.event('engine-config');return self
            def destroy(self):outer.event('engine-destroy')
            def reset_system_database(self):outer.event('engine-reset')
            def launch(self):outer.event('engine-launch')
        module=types.ModuleType('sqlalchemy');module.NullPool=object()
        self.namespace['_DBOS_AVAILABLE']=True
        self.namespace['DBOS']=Engine()
        with patch.dict('sys.modules',{'sqlalchemy':module}):yield

    def test_demo_engine_stages_and_owned_shutdown_with_local_policy(self):
        with self.node() as node,self.demo_engine():
            node.run_workflow_demo()
            self.assertEqual(self.events.count('engine-config'),1)
            self.assertEqual(self.events.count('engine-reset'),1)
            self.assertEqual(self.events.count('engine-launch'),1)
            self.assertEqual(self.events.count('workflow'),1)
            self.assertEqual(self.events.count('engine-destroy'),2)
            self.assertFalse(node._dbos_active)

    def test_demo_stage_drift_blocks_next_effect_and_cleans_owned_engine(self):
        for phase,forbidden in (('engine-config','engine-reset'),('engine-reset','engine-launch'),('engine-launch','workflow')):
            with self.subTest(phase=phase),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True),self.node() as node,self.demo_engine():
                self.events.clear();self.callbacks={phase:lambda:os.environ.__setitem__('VAMS_ENV','production')}
                self.assert_guard(self.capture(node.run_workflow_demo))
                self.assertNotIn(forbidden,self.events)
                self.assertFalse(node._dbos_active)
                self.assertEqual(self.events.count('engine-destroy'),2)

    def test_demo_private_denial_survives_restoring_cleanup_control(self):
        with self.node() as node,self.demo_engine():
            self.callbacks['workflow']=lambda:os.environ.__setitem__('VAMS_ENV','production')
            calls=[0]
            def cleanup():
                calls[0]+=1
                if calls[0]==2:
                    os.environ['VAMS_ENV']='test'
                    raise KeyboardInterrupt()
            self.callbacks['engine-destroy']=cleanup
            self.assert_guard(self.capture(node.run_workflow_demo))
            self.assertEqual(self.events.count('workflow'),1)
            self.assertEqual(self.events.count('engine-destroy'),2)


if __name__=='__main__':unittest.main()
