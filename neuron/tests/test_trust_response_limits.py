"""Local body-consumer bounds, not real HTTP/resource/TEE qualification."""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from neuron import trust as T
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.tests.test_trust_boundary import PrivateError, Transport, environment
from neuron.tests import test_trust_boundary as H


VALID = b'{"jsonrpc":"2.0","id":1,"result":"0x9"}'


class Raw:
    def __init__(self, body=VALID, step=None, callback=None, error=None, result=None):
        self.body, self.step, self.callback, self.error, self.result = body, step, callback, error, result
        self.offset = 0
        self.calls = []
        self.eof = False
    def read(self, amount, decode_content=False):
        self.calls.append((amount, decode_content))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        if self.result is not None:
            return self.result
        count = min(amount, self.step) if self.step else amount
        chunk = self.body[self.offset:self.offset+count]
        self.offset += len(chunk)
        if not chunk:
            self.eof = True
        return chunk


class Response:
    def __init__(self, code=200, raw=None, headers=None, close_error=None, close_callback=None, status_callback=None):
        self.code, self.raw = code, raw if raw is not None else Raw()
        self.headers = {} if headers is None else headers
        self.close_error, self.close_callback, self.status_callback = close_error, close_callback, status_callback
        self.closed = 0
        self.body_helpers = []
    @property
    def status_code(self):
        if self.status_callback:
            self.status_callback()
        return self.code
    def close(self):
        self.closed += 1
        if self.close_callback:
            self.close_callback()
        if self.close_error:
            raise self.close_error
    def __getattr__(self, name):
        if name in ('json', 'content', 'text', 'iter_content'):
            self.body_helpers.append(name)
            raise AssertionError('Unbounded body helper used')
        raise AttributeError(name)


class TrustResponseLimitsTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.dict(os.environ, environment(), clear=True)
        self.mode.start()
        PrivateError.reads = 0
    def tearDown(self):
        self.mode.stop()
        self.assertEqual(PrivateError.reads, 0)
    def provider(self, response, cls=T.AutomataProvider, callback=None):
        p = cls(endpoint='https://fixture.invalid', timeout=17)
        p.session = Transport(response=response, callback=callback)
        return p
    def offline(self, response):
        info = self.provider(response).get_status()
        self.assertEqual(info.status, T.TrustStatus.OFFLINE)
        self.assertEqual(info.error, 'provider_error')
        self.assertIsNone(info.observations)
        self.assertEqual(response.closed, 1)
        self.assertEqual(response.body_helpers, [])
        return info
    def test_all_requests_stream_without_redirects(self):
        for cls in (T.PhalaProvider, T.MarlinProvider, T.AutomataProvider):
            with self.subTest(provider=cls.__name__):
                r = Response()
                p = self.provider(r, cls)
                info = p.get_status()
                self.assertEqual(info.status, T.TrustStatus.HEALTHY)
                self.assertEqual(r.closed, 1)
                method, args, kwargs = p.session.calls[0]
                self.assertEqual(len(p.session.calls), 1)
                self.assertEqual(args, ('https://fixture.invalid',))
                self.assertIs(kwargs['stream'], True)
                self.assertIs(kwargs['allow_redirects'], False)
                self.assertEqual(kwargs['timeout'], 17)
                if cls is T.AutomataProvider:
                    self.assertEqual(method, 'post')
                    self.assertEqual(kwargs['json'], {'jsonrpc':'2.0','id':1,'method':'eth_chainId','params':[]})
                    self.assertEqual(kwargs['headers'], {'Content-Type':'application/json','Accept-Encoding':'identity'})
                else:
                    self.assertEqual(method, 'get')
                    self.assertEqual(r.raw.calls, [])
                self.assertEqual(r.body_helpers, [])
    def test_non200_never_reads_body_or_follows_redirect(self):
        for cls in (T.PhalaProvider, T.MarlinProvider, T.AutomataProvider):
            for status in (201, 302, 404, 503):
                with self.subTest(provider=cls.__name__, status=status):
                    r = Response(code=status)
                    p = self.provider(r, cls)
                    self.assertEqual(p.get_status().status, T.TrustStatus.DEGRADED)
                    self.assertEqual(r.raw.calls, [])
                    self.assertEqual(r.body_helpers, [])
                    self.assertEqual(r.closed, 1)
                    self.assertEqual(len(p.session.calls), 1)
    def test_exact_body_limit_requires_empty_read(self):
        raw = Raw(VALID + b' ' * (65536-len(VALID)))
        r = Response(raw=raw)
        info = self.provider(r).get_status()
        self.assertEqual(info.status, T.TrustStatus.HEALTHY)
        self.assertEqual(info.observations, {'chain_id':9})
        self.assertTrue(raw.eof)
        self.assertEqual(raw.calls[-1], (1, False))
        self.assertTrue(all(0 < amount <= 8192 and decode is False for amount, decode in raw.calls))
        self.assertEqual(r.closed, 1)
        self.assertEqual(r.body_helpers, [])
    def test_limit_plus_one_rejects_with_no_observation(self):
        raw = Raw(VALID + b' ' * (65537-len(VALID)))
        self.offline(Response(raw=raw))
        self.assertEqual(raw.offset, 65537)
        self.assertTrue(all(amount <= 8192 and decode is False for amount, decode in raw.calls))
    def test_short_chunks_are_not_eof(self):
        raw = Raw(step=3)
        info = self.provider(Response(raw=raw)).get_status()
        self.assertEqual(info.observations, {'chain_id':9})
        self.assertTrue(raw.eof)
        self.assertGreater(len(raw.calls), 5)
    def test_content_length_does_not_control_acceptance(self):
        for length in ('0','999999999999999999999999','incorrect'):
            with self.subTest(length=length):
                r = Response(headers={'Content-Length':length})
                self.assertEqual(self.provider(r).get_status().observations, {'chain_id':9})
        self.offline(Response(raw=Raw(VALID+b' '*(65537-len(VALID))), headers={'Content-Length':'1'}))
    def test_identity_encoding_only_before_body(self):
        for headers in ({}, {'Content-Encoding':'identity'}, {'content-ENCODING':' IDENTITY '}):
            with self.subTest(headers=headers):
                self.assertEqual(self.provider(Response(headers=headers)).get_status().observations, {'chain_id':9})
        for headers in ({'Content-Encoding':'gzip'}, {'Content-Encoding':'identity,gzip'},
                        {'Content-Encoding':'identity','content-encoding':'identity'}, {'Content-Encoding':None}, []):
            with self.subTest(headers=headers):
                r = Response(headers=headers)
                self.offline(r)
                self.assertEqual(r.raw.calls, [])
    def test_malformed_readers_and_chunks_never_fallback(self):
        for raw in (object(), SimpleNamespace(read=None), Raw(result='text'), Raw(result=bytearray(b'x')),
                    Raw(result=b'x'*8193), Raw(error=PrivateError())):
            with self.subTest(raw=type(raw).__name__):
                self.offline(Response(raw=raw))
    def test_utf8_json_and_envelope_validation_remain_closed(self):
        for body in (b'\xff', b'{bad', b'[]', b'null', b'{"jsonrpc":"1.0","id":1,"result":"0x9"}',
                     b'{"jsonrpc":"2.0","id":true,"result":"0x9"}', b'{"jsonrpc":"2.0","id":1,"result":"no"}'):
            with self.subTest(body=body[:8]):
                self.offline(Response(raw=Raw(body)))
    def test_close_and_clock_failure_discard_parsed_chain_id(self):
        self.offline(Response(close_error=PrivateError()))
        r = Response()
        with patch.object(T.time, 'monotonic', side_effect=[1.0, PrivateError()]):
            self.offline(r)
    def test_drift_after_acquisition_or_read_still_closes(self):
        for stage in ('request', 'status', 'read', 'close'):
            for flag, value in (('VAMS_ENV','local'), ('NEURON_MOCK_MODE','true')):
                with self.subTest(stage=stage, flag=flag), patch.dict(os.environ, environment(), clear=True):
                    change = lambda: os.environ.__setitem__(flag, value)
                    r = Response(raw=Raw(callback=change if stage=='read' else None),
                                 status_callback=change if stage=='status' else None,
                                 close_callback=change if stage=='close' else None)
                    p = self.provider(r, callback=change if stage=='request' else None)
                    with self.assertRaises(RuntimeConfigurationError):
                        p.get_status()
                    self.assertEqual(r.closed, 1)
                    self.assertEqual(r.body_helpers, [])
                    if stage in ('request','status'):
                        self.assertEqual(r.raw.calls, [])
    def test_control_events_propagate_after_cleanup(self):
        for stage in ('read', 'close'):
            with self.subTest(stage=stage):
                r = Response(raw=Raw(error=KeyboardInterrupt() if stage=='read' else None),
                             close_error=KeyboardInterrupt() if stage=='close' else None)
                with self.assertRaises(KeyboardInterrupt):
                    self.provider(r).get_status()
                self.assertEqual(r.closed, 1)
    def test_runtime_drift_wins_over_close_control(self):
        r = Response(raw=Raw(callback=lambda: os.environ.__setitem__('VAMS_ENV','local')),
                     close_error=KeyboardInterrupt())
        caught = None
        try:
            self.provider(r).get_status()
        except BaseException as exc:
            caught = exc
        # A pre-repair wrong control outcome must fail this assertion without
        # terminating the campaign before its remaining results are captured.
        self.assertIsInstance(caught, RuntimeConfigurationError)
        self.assertEqual(r.closed, 1)
    def test_interface_private_drift_survives_wrapping_and_close_control(self):
        class HeaderMapping(dict):
            callback = None
            def items(self):
                if self.callback:
                    self.callback()
                return super().items()
        class InterfaceResponse(Response):
            raw_callback = None
            @property
            def raw(self):
                if self.raw_callback:
                    self.raw_callback()
                return self._fixture_raw
            @raw.setter
            def raw(self, value):
                self._fixture_raw = value
        for stage in ('headers','raw'):
            with self.subTest(stage=stage), patch.dict(os.environ, environment(), clear=True):
                headers = HeaderMapping()
                r = InterfaceResponse(headers=headers, close_callback=lambda: os.environ.__setitem__('VAMS_ENV','test'), close_error=KeyboardInterrupt())
                p = self.provider(r)
                def drift():
                    os.environ['VAMS_ENV'] = 'local'
                    p._assert_current_runtime()
                if stage == 'headers':
                    headers.callback = drift
                else:
                    r.raw_callback = drift
                caught = None
                try:
                    p.get_status()
                except BaseException as exc:
                    caught = exc
                self.assertIsInstance(caught, RuntimeConfigurationError)
                self.assertEqual(r.closed, 1)
    def test_invalid_body_cannot_enter_manager_cache_as_success(self):
        p = self.provider(Response(raw=Raw(b'private-body-marker')))
        manager = T.TrustManager(providers=[p])
        info = manager.check_all_status()['automata']
        self.assertEqual(info.status, T.TrustStatus.OFFLINE)
        self.assertIsNone(info.observations)
        self.assertNotIn('private-body-marker', str(info.to_dict()))
        self.assertEqual(manager.get_healthy_providers(), [])
    def test_valid_body_through_manager_and_actual_layer4_is_unverified(self):
        p = self.provider(Response())
        manager = T.TrustManager(providers=[p])
        self.assertEqual(manager.check_all_status()['automata'].observations, {'chain_id':9})
        # The actual panel performs a fresh observation, so use a fresh fixture.
        p.session.response = Response()
        output = H.TrustBoundaryTests().layer4(manager).lower()
        self.assertIn('http', output)
        self.assertIn('unverified', output)
        self.assertNotIn('[green]', output)


if __name__ == '__main__':
    unittest.main()
