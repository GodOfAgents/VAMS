"""Real exported-ASGI regressions; requires the frozen framework dependencies.

HTTP scopes are sent directly to the app, without any lifespan scope, listener,
HTTP client/network, or provider. These tests must not be replaced by AST passes.
"""
import asyncio
import copy
import importlib
import json
import os
import unittest
from unittest.mock import patch


async def http_without_lifespan(app, method, path):
    messages = []
    complete = asyncio.Event()
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {'type': 'http.request', 'body': b'{}', 'more_body': False}
        await complete.wait()
        return {'type': 'http.disconnect'}

    async def send(message):
        messages.append(message)
        if message['type'] == 'http.response.body' and not message.get('more_body', False):
            complete.set()

    scope = dict(type='http', asgi={'version':'3.0','spec_version':'2.3'},
                 http_version='1.1', method=method, scheme='http', path=path,
                 raw_path=path.encode('ascii'), query_string=b'', root_path='',
                 headers=[(b'host',b'fixture.invalid'),(b'content-type',b'application/json'),(b'content-length',b'2')],
                 client=('127.0.0.1',12345), server=('fixture.invalid',80))
    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    start = [m for m in messages if m['type'] == 'http.response.start']
    if len(start) != 1:
        raise AssertionError('Expected exactly one ASGI response start')
    body = b''.join(m.get('body',b'') for m in messages if m['type'] == 'http.response.body')
    return start[0]['status'], json.loads(body)


class LegacyGatewayAsgiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'VAMS_ENV':'test'}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.legacy = importlib.import_module('neuron.gateway.server')
        legacy = self.legacy
        saved_state = dict(legacy.app.state._state)
        saved_maps = [copy.deepcopy(m) for m in (legacy.AGENTS,legacy.TASKS,legacy.PENDING_TASKS)]
        def restore():
            legacy.app.state._state.clear()
            legacy.app.state._state.update(saved_state)
            for target, saved in zip((legacy.AGENTS,legacy.TASKS,legacy.PENDING_TASKS),saved_maps):
                target.clear()
                target.update(saved)
        self.addCleanup(restore)
        legacy.app.state._state.clear()
        for target in (legacy.AGENTS,legacy.TASKS,legacy.PENDING_TASKS):
            target.clear()
        legacy.AGENTS['existing'] = dict(status='active',last_seen=1)
        legacy.TASKS['task'] = 'fixture-task'
        legacy.PENDING_TASKS['existing'] = ['task']
        self.limiter_patch = patch.object(legacy.limiter,'is_allowed',return_value=True)
        self.limiter = self.limiter_patch.start()
        self.addCleanup(self.limiter_patch.stop)

    def maps(self):
        return copy.deepcopy((self.legacy.AGENTS,self.legacy.TASKS,self.legacy.PENDING_TASKS))

    def assert_denied(self, env):
        before = self.maps()
        routes = [('GET','/'),('POST','/agents/register'),('POST','/heartbeat'),
                  ('GET','/tasks/pending'),('POST','/tasks/task/result')]
        with patch.dict(os.environ,env,clear=True):
            for method,path in routes:
                with self.subTest(method=method,path=path,env=env):
                    status,body = asyncio.run(http_without_lifespan(self.legacy.app,method,path))
                    self.assertEqual(status,503)
                    self.assertEqual(body,{'detail':'Legacy neuron gateway runtime is unavailable.'})
                    self.assertEqual(self.maps(),before)
        self.limiter.assert_not_called()

    def test_exported_asgi_denies_live_without_lifespan(self):
        for mode in ('staging','testnet','production'):
            self.assert_denied({'VAMS_ENV':mode})

    def test_exported_asgi_denies_invalid_modes_and_mock_flags(self):
        for env in ({},{'VAMS_ENV':'prod'},{'VAMS_ENV':'Testnet'},
                    {'VAMS_ENV':'test','VAMS_MOCK_MODE':'yes'},
                    {'VAMS_ENV':'testnet','AVAIL_MOCK_MODE':'true'}):
            self.assert_denied(env)

    def test_exported_asgi_denies_changed_bound_mode_and_flags(self):
        from neuron.runtime_safety import load_runtime_policy
        self.legacy.app.state.runtime_policy = load_runtime_policy({'VAMS_ENV':'test'})
        self.assert_denied({'VAMS_ENV':'local'})
        self.assert_denied({'VAMS_ENV':'test','VAMS_MOCK_MODE':'true'})
        self.legacy.app.state.startup_policy = load_runtime_policy({'VAMS_ENV':'demo'})
        self.assert_denied({'VAMS_ENV':'test'})

    def test_exported_asgi_non_live_home_keeps_sanitized_classification(self):
        for mode in ('test','local','demo'):
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True):
                status,body = asyncio.run(http_without_lifespan(self.legacy.app,'GET','/'))
                self.assertEqual(status,200)
                self.assertEqual(body['mode'],mode)
                self.assertEqual(body['runtime_classification'],'non-live')
                self.assertEqual(body['evidence_classification'],'non-authoritative')
        self.assertEqual(self.limiter.call_count,3)

    def test_direct_handlers_refuse_before_reading_poison_arguments(self):
        from neuron.runtime_safety import LiveModeSafetyError
        class Poison:
            def __getattr__(self,name):
                raise AssertionError('Denied handler observed its request')
        before = self.maps()
        with patch.dict(os.environ,{'VAMS_ENV':'testnet'},clear=True):
            for call in (lambda:self.legacy.register_agent(Poison()),
                         lambda:self.legacy.heartbeat(Poison()),
                         lambda:self.legacy.submit_result('task',Poison()),
                         lambda:self.legacy.get_pending_tasks('existing'),self.legacy.home):
                with self.subTest(call=call),self.assertRaises(LiveModeSafetyError):
                    call()
        self.assertEqual(self.maps(),before)
        self.limiter.assert_not_called()
