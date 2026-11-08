"""Actual function AST with fixture collaborators, NOT an ASGI/framework test.

No package initialization, FastAPI/Pydantic, listener, provider or live authority
is exercised. The companion framework test covers the exported app separately.
"""
from __future__ import annotations

import __future__
import ast
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('_legacy_boundary_runtime', ROOT / 'neuron/runtime_safety.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNTIME
SPEC.loader.exec_module(RUNTIME)


class ResponseFixture:
    def __init__(self, status_code=200, content=None):
        self.status_code = status_code
        self.content = content


class LimiterFixture:
    def __init__(self):
        self.calls = 0

    def is_allowed(self, _client):
        self.calls += 1
        return True


class HttpErrorFixture(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


def functions():
    """Compile complete actual function bodies; do not rewrite their behavior."""
    wanted = {'_require_request_runtime_policy', 'rate_limit_middleware', 'home',
              'register_agent', 'heartbeat', 'get_pending_tasks', 'submit_result'}
    tree = ast.parse((ROOT / 'neuron/gateway/server.py').read_text(encoding='utf-8'))
    selected = []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in wanted:
            item.decorator_list = []  # Framework registration alone is outside this fixture.
            selected.append(item)
    messages = []
    limiter = LimiterFixture()
    ns = dict(app=SimpleNamespace(state=SimpleNamespace()), limiter=limiter,
              load_runtime_policy=RUNTIME.load_runtime_policy,
              LiveModeSafetyError=RUNTIME.LiveModeSafetyError,
              RuntimeConfigurationError=RUNTIME.RuntimeConfigurationError,
              AGENTS={}, TASKS={}, PENDING_TASKS={},
              time=SimpleNamespace(time=lambda: 42),
              AgentStatus=SimpleNamespace(ACTIVE='active'),
              GenericResponse=lambda **kw: SimpleNamespace(**kw),
              HTTPException=HttpErrorFixture, JSONResponse=ResponseFixture,
              logger=SimpleNamespace(info=lambda *a: messages.append(a), error=lambda *a: messages.append(a)))
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, str(ROOT / 'neuron/gateway/server.py'), 'exec',
                 flags=__future__.annotations.compiler_flag), ns)
    return ns, limiter, messages


def registration(node='node'):
    return SimpleNamespace(node_id=node, public_key='fixture', stake_amount=1, capabilities=[])


def state(ns):
    # Copy the nested state so in-place updates cannot make assertions vacuous.
    import copy
    return copy.deepcopy((ns['AGENTS'], ns['TASKS'], ns['PENDING_TASKS']))


def run_inline(coroutine):
    # Fixture collaborators complete inline. No event loop/socketpair is needed;
    # real ASGI suspension/streaming belongs to the separate framework campaign.
    try:
        coroutine.send(None)
    except StopIteration as complete:
        return complete.value
    finally:
        coroutine.close()
    raise AssertionError('fixture coroutine unexpectedly suspended')


class LegacyGatewayRequestBoundaryTests(unittest.TestCase):
    def http_registration(self, ns, request=None):
        async def dispatch(_request):
            ns['register_agent'](registration())
            return ResponseFixture()
        req = request or SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'))
        return run_inline(ns['rate_limit_middleware'](req, dispatch))

    def assert_http_denied(self, env, bound=None, startup=None):
        ns, limiter, messages = functions()
        if bound is not None:
            ns['app'].state.runtime_policy = RUNTIME.load_runtime_policy(bound)
        if startup is not None:
            ns['app'].state.startup_policy = RUNTIME.load_runtime_policy(startup)
        before = state(ns)
        with patch.dict(os.environ, env, clear=True):
            response = self.http_registration(ns)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(state(ns), before)
        self.assertEqual(limiter.calls, 0)
        self.assertEqual(messages, [])
        return response

    def test_http_live_denied_without_startup_before_effects(self):
        for mode in ('staging', 'testnet', 'production'):
            with self.subTest(mode=mode):
                self.assert_http_denied({'VAMS_ENV': mode})

    def test_http_missing_unknown_malformed_mode_and_mock_rejected(self):
        cases = [{}, {'VAMS_ENV': 'prod'}, {'VAMS_ENV': 'Testnet'},
                 {'VAMS_ENV': ' test'}, {'VAMS_ENV': ''},
                 {'VAMS_ENV': 'test', 'VAMS_MOCK_MODE': 'yes'},
                 {'VAMS_ENV': 'testnet', 'AVAIL_MOCK_MODE': 'true'}]
        for env in cases:
            with self.subTest(env=env):
                self.assert_http_denied(env)

    def test_http_both_bound_policies_and_mock_drift_checked(self):
        cases = [({'VAMS_ENV': 'local'}, {'VAMS_ENV': 'test'}, None),
                 ({'VAMS_ENV': 'test'}, None, {'VAMS_ENV': 'demo'}),
                 ({'VAMS_ENV': 'test'}, {'VAMS_ENV': 'test'}, {'VAMS_ENV': 'local'}),
                 ({'VAMS_ENV': 'test', 'VAMS_MOCK_MODE': 'true'}, {'VAMS_ENV': 'test'}, None)]
        for env, bound, startup in cases:
            with self.subTest(env=env, bound=bound, startup=startup):
                self.assert_http_denied(env, bound, startup)

    def test_http_local_modes_keep_existing_registration_behavior(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                ns, limiter, messages = functions()
                response = self.http_registration(ns)
                self.assertEqual(response.status_code, 200)
                self.assertIn('node', ns['AGENTS'])
                self.assertEqual(limiter.calls, 1)
                self.assertEqual(len(messages), 1)

    def mutation_calls(self, ns):
        return [lambda: ns['register_agent'](registration()),
                lambda: ns['heartbeat'](SimpleNamespace(payload='1|changed|existing')),
                lambda: ns['submit_result']('task', SimpleNamespace())]

    def seed(self, ns):
        ns['AGENTS']['existing'] = dict(status='active', last_seen=1)
        ns['TASKS']['task'] = 'fixture-task'
        ns['PENDING_TASKS']['existing'] = ['task']

    def test_direct_mutation_calls_reject_live_before_state_or_logs(self):
        for mode in ('staging', 'testnet', 'production'):
            for call_index in range(3):
                with self.subTest(mode=mode, call=call_index), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                    ns, _, messages = functions()
                    self.seed(ns)
                    before = state(ns)
                    with self.assertRaises(RUNTIME.LiveModeSafetyError):
                        self.mutation_calls(ns)[call_index]()
                    self.assertEqual(state(ns), before)
                    self.assertEqual(messages, [])

    def test_direct_mutation_calls_reject_missing_or_drifting_policy(self):
        for env, bound in (({}, None), ({'VAMS_ENV': 'local'}, {'VAMS_ENV': 'test'})):
            for call_index in range(3):
                with self.subTest(env=env, call=call_index), patch.dict(os.environ, env, clear=True):
                    ns, _, messages = functions()
                    self.seed(ns)
                    if bound is not None:
                        ns['app'].state.runtime_policy = RUNTIME.load_runtime_policy(bound)
                    before = state(ns)
                    with self.assertRaises(RUNTIME.LiveModeSafetyError):
                        self.mutation_calls(ns)[call_index]()
                    self.assertEqual(state(ns), before)
                    self.assertEqual(messages, [])

    def test_direct_reads_deny_live_before_accessing_state(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            ns, _, _ = functions()
            ns['app'].state.runtime_policy = RUNTIME.load_runtime_policy()
            for call in (ns['home'], lambda: ns['get_pending_tasks']('existing')):
                with self.subTest(call=call), self.assertRaises(RUNTIME.LiveModeSafetyError):
                    call()

    def test_direct_non_live_paths_keep_classification_and_results(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True):
            ns, _, _ = functions()
            ns['app'].state.runtime_policy = RUNTIME.load_runtime_policy()
            ns['register_agent'](registration())
            ns['heartbeat'](SimpleNamespace(payload='1|changed|node'))
            ns['TASKS']['task'] = 'fixture-task'
            ns['PENDING_TASKS']['node'] = ['task']
            self.assertEqual(ns['get_pending_tasks']('node')['tasks'], ['fixture-task'])
            self.assertTrue(ns['submit_result']('task', SimpleNamespace()).success)
            self.assertNotIn('task', ns['TASKS'])
            result = ns['home']()
            self.assertEqual(result['mode'], 'test')
            self.assertEqual(result['evidence_classification'], 'non-authoritative')

    def test_denial_body_does_not_reflect_invalid_mode(self):
        response = self.assert_http_denied({'VAMS_ENV': 'invalid-sensitive-marker'})
        self.assertEqual(response.content, {'detail': 'Legacy neuron gateway runtime is unavailable.'})
        self.assertNotIn('invalid-sensitive-marker', str(response.content))

    def test_same_process_followup_rechecks_effective_mode(self):
        ns, limiter, messages = functions()
        with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True):
            self.assertEqual(self.http_registration(ns).status_code, 200)
        before, log_count = state(ns), len(messages)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True):
            response = self.http_registration(ns)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(state(ns), before)
        self.assertEqual(limiter.calls, 1)
        self.assertEqual(len(messages), log_count)

    def test_denial_does_not_read_client_or_request_payload(self):
        class PoisonRequest:
            @property
            def client(self):
                raise AssertionError('client read before refusal')
        ns, limiter, _ = functions()
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            try:
                response = self.http_registration(ns, PoisonRequest())
            except AssertionError:
                self.fail('live request client was read before refusal')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(limiter.calls, 0)


if __name__ == '__main__':
    unittest.main()
