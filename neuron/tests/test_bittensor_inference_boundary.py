"""Direct SDK dispatch containment; observers and providers here are local fixtures."""
import io
import os
import unittest
from collections import Counter
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from neuron.sdk import bittensor_subnet as B

LIVE = ('staging', 'testnet', 'production')
LOCAL = ('test', 'local', 'demo')


class LocalEffectObserver:
    def __init__(self): self.events = Counter()
    def record(self, name): self.events[name] += 1


class PromptTripwire:
    def __init__(self, observer): self.observer = observer
    def __str__(self): self.observer.record('prompt_conversion'); return 'synthetic-prompt'
    def __repr__(self): self.observer.record('prompt_conversion'); return 'synthetic-prompt'
    def encode(self, *a, **kw): self.observer.record('prompt_conversion'); return b'synthetic-prompt'


class ObservedClient(B.BittensorSubnet):
    def __getattribute__(self, name):
        if name in ('_subtensor', '_wallet'):
            object.__getattribute__(self, 'observer').record('credential_or_provider_read')
        return super().__getattribute__(name)


def fixture_client(observer, *, disconnected=False, provider_failure=False):
    client = ObservedClient.__new__(ObservedClient)
    client.observer = observer; client._metagraph_cache = {}; client.network = 'test'; client.wallet_name = None
    def metagraph(netuid):
        observer.record('metagraph')
        if provider_failure: raise ValueError('synthetic-provider-error')
        return SimpleNamespace(axons=['fixture-axon'])
    client._subtensor = None if disconnected else SimpleNamespace(metagraph=metagraph)
    client._wallet = None if disconnected else object()
    def synapse(**kwargs): observer.record('prompt_release'); return kwargs
    def query(*a, **kw): observer.record('provider_effect'); return 'fixture-response'
    def dendrite(**kwargs): observer.record('dendrite'); return SimpleNamespace(query=query)
    return client, SimpleNamespace(Synapse=synapse, dendrite=dendrite)


class BittensorInferenceBoundaryTests(unittest.TestCase):
    def denied(self, environment, error, **configuration):
        observer = LocalEffectObserver(); client, backend = fixture_client(observer, **configuration)
        prompt = PromptTripwire(observer)
        with patch.dict(os.environ, environment, clear=True), patch.object(B, 'bt', backend), redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(error): client.query_miner(1, 0, prompt)
        self.assertEqual(observer.events, Counter())
        self.assertEqual(output.getvalue(), '')

    def test_direct_live_calls_reject_before_credentials_or_prompt_release(self):
        for mode in LIVE:
            with self.subTest(mode=mode): self.denied({'VAMS_ENV': mode}, LiveModeSafetyError)

    def test_live_unavailable_connections_cannot_bypass_the_dispatch_boundary(self):
        for mode in LIVE:
            with self.subTest(mode=mode): self.denied({'VAMS_ENV': mode}, LiveModeSafetyError, disconnected=True)

    def test_missing_or_invalid_runtime_rejects_before_provider_callbacks(self):
        for environment in ({}, {'VAMS_ENV': 'prod'}, {'VAMS_ENV': 'TEST'}, {'VAMS_ENV': 'testnet '}):
            with self.subTest(environment=environment): self.denied(environment, RuntimeConfigurationError)

    def test_live_provider_failure_is_not_consulted_before_admission(self):
        for mode in LIVE:
            with self.subTest(mode=mode): self.denied({'VAMS_ENV': mode}, LiveModeSafetyError, provider_failure=True)

    def test_environment_change_after_client_creation_cannot_enable_dispatch(self):
        observer = LocalEffectObserver()
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True): client, backend = fixture_client(observer)
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True), patch.object(B, 'bt', backend):
            with self.assertRaises(LiveModeSafetyError): client.query_miner(1, 0, PromptTripwire(observer))
        self.assertEqual(observer.events, Counter())

    def test_caller_supplied_allow_metadata_is_not_authority(self):
        observer = LocalEffectObserver(); client, backend = fixture_client(observer)
        client.approved = True
        client.action_context = {'decision': 'ALLOW', 'policy_version': 1, 'authority_epoch': 1}
        client.verification_key = b'local-unverified-fixture'
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(B, 'bt', backend):
            with self.assertRaises(LiveModeSafetyError): client.query_miner(1, 0, PromptTripwire(observer))
        self.assertEqual(observer.events, Counter())

    def test_local_controlled_dispatch_retains_response_and_observation_classification(self):
        for mode in LOCAL:
            with self.subTest(mode=mode):
                observer = LocalEffectObserver(); client, backend = fixture_client(observer)
                with patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), patch.object(B, 'bt', backend):
                    result = client.query_miner(1, 0, 'synthetic-prompt', timeout=2)
                self.assertTrue(result.success); self.assertEqual(result.response, 'fixture-response')
                self.assertEqual(result.evidence_classification, 'provider-observation')
                self.assertEqual(observer.events['provider_effect'], 1)
                self.assertEqual(observer.events['prompt_release'], 1)
                self.assertEqual(observer.events['dendrite'], 1)

    def test_local_disconnected_call_preserves_failure_result(self):
        for mode in LOCAL:
            with self.subTest(mode=mode):
                observer = LocalEffectObserver(); client, backend = fixture_client(observer, disconnected=True)
                with patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), patch.object(B, 'bt', backend):
                    result = client.query_miner(1, 0, 'synthetic-prompt')
                self.assertFalse(result.success); self.assertIsNone(result.response)
                self.assertEqual(observer.events['provider_effect'], 0)

    def test_runtime_drift_during_callbacks_prevents_the_next_protected_stage(self):
        for phase in ('metagraph', 'dendrite', 'Synapse'):
            for changes in ({'VAMS_ENV': 'testnet'}, {'VAMS_ENV': 'local'}, {'SENTINEL_MOCK_MODE': 'true'}):
                with self.subTest(phase=phase, changes=changes):
                    observer = LocalEffectObserver(); client, backend = fixture_client(observer)
                    target = object.__getattribute__(client, '_subtensor') if phase == 'metagraph' else backend
                    original = getattr(target, phase)
                    def change(*args, **kwargs):
                        result = original(*args, **kwargs)
                        os.environ.update(changes)
                        return result
                    setattr(target, phase, change)
                    with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True), patch.object(B, 'bt', backend):
                        with self.assertRaises(LiveModeSafetyError): client.query_miner(1, 0, 'synthetic-prompt')
                    self.assertEqual(observer.events['provider_effect'], 0)
                    # A Synapse callback may already have consumed the locally
                    # permitted prompt. The check only prevents the next effect.
                    self.assertEqual(observer.events['prompt_release'], int(phase == 'Synapse'))
                    self.assertEqual(observer.events['dendrite'], int(phase != 'metagraph'))

    def test_provider_safety_typed_errors_do_not_escape_as_trusted_policy_diagnostics(self):
        for error_type in (LiveModeSafetyError, RuntimeConfigurationError):
            observer = LocalEffectObserver(); client, backend = fixture_client(observer)
            def fail(**kwargs): raise error_type('SYNTHETIC_PROVIDER_DETAIL_MUST_NOT_ESCAPE')
            backend.dendrite = fail
            with self.subTest(error_type=error_type), patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True), patch.object(B, 'bt', backend):
                result = client.query_miner(1, 0, 'synthetic-prompt')
            self.assertFalse(result.success)
            self.assertNotIn('SYNTHETIC_PROVIDER_DETAIL', result.error)
            self.assertEqual(observer.events['provider_effect'], 0)


if __name__ == '__main__': unittest.main()
