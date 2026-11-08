"""Named wallet capability setup with local vendor/callback fixtures only."""
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


class OpaqueProviderError(Exception):
    reads = 0
    def __str__(self): type(self).reads += 1; return 'SYNTHETIC_WALLET_PROVIDER_DETAIL'
    def __repr__(self): type(self).reads += 1; return 'SYNTHETIC_WALLET_PROVIDER_REPR'


def fixture_backend(*, subtensor_callback=None, wallet_callback=None):
    events = Counter(); selections = []
    connection = SimpleNamespace(block=123, get_balance=lambda a: SimpleNamespace(tao=3.25))
    selected_wallet = SimpleNamespace(coldkeypub=SimpleNamespace(ss58_address='synthetic-public-address'))
    def subtensor(**kwargs):
        events['subtensor'] += 1
        if subtensor_callback: subtensor_callback()
        return connection
    def wallet(**kwargs):
        events['wallet'] += 1; selections.append(kwargs)
        if wallet_callback: wallet_callback()
        return selected_wallet
    return SimpleNamespace(subtensor=subtensor, wallet=wallet), events, selections, selected_wallet


def uninitialized_client(wallet_name='synthetic-wallet', wallet_hotkey='synthetic-hotkey'):
    # Use the actual constructor without invoking any unavailable vendor. This
    # preserves its internal state contract before explicitly testing setup.
    with patch.object(B, 'BITTENSOR_AVAILABLE', False):
        return B.BittensorSubnet(wallet_name=wallet_name, wallet_hotkey=wallet_hotkey)


class BittensorWalletBoundaryTests(unittest.TestCase):
    def test_live_named_wallet_constructor_rejects_before_vendor_setup(self):
        for mode in LIVE:
            backend, events, _, _ = fixture_backend()
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), \
                    patch.object(B, 'BITTENSOR_AVAILABLE', True), patch.object(B, 'bt', backend), redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(LiveModeSafetyError): B.BittensorSubnet(wallet_name='synthetic-wallet')
                self.assertEqual(events, Counter()); self.assertEqual(output.getvalue(), '')

    def test_missing_and_invalid_modes_reject_named_wallet_setup(self):
        for environment in ({}, {'VAMS_ENV': 'prod'}, {'VAMS_ENV': 'TEST'}):
            backend, events, _, _ = fixture_backend()
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True), \
                    patch.object(B, 'BITTENSOR_AVAILABLE', True), patch.object(B, 'bt', backend):
                with self.assertRaises(RuntimeConfigurationError): B.BittensorSubnet(wallet_name='synthetic-wallet')
                self.assertEqual(events, Counter())

    def test_direct_initializer_rechecks_live_mode(self):
        for mode in LIVE:
            backend, events, _, _ = fixture_backend(); client = uninitialized_client()
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), patch.object(B, 'bt', backend):
                with self.assertRaises(LiveModeSafetyError): client._init_subtensor()
                self.assertEqual(events, Counter()); self.assertIsNone(client._wallet)

    def test_no_wallet_read_only_setup_remains_available(self):
        for mode in LIVE + LOCAL + (None,):
            backend, events, _, _ = fixture_backend()
            environment = {} if mode is None else {'VAMS_ENV': mode}
            with self.subTest(mode=mode), patch.dict(os.environ, environment, clear=True), \
                    patch.object(B, 'BITTENSOR_AVAILABLE', True), patch.object(B, 'bt', backend):
                client = B.BittensorSubnet()
                self.assertTrue(client.is_connected); self.assertIsNone(client._wallet)
                self.assertEqual(client.check_health()['status'], 'healthy')
                self.assertEqual(client.get_balance('synthetic-public-address'), 3.25)
                self.assertEqual(events, Counter(subtensor=1))

    def test_local_named_wallet_preserves_exact_selection_and_default_hotkey(self):
        for mode in LOCAL:
            for hotkey in (None, 'synthetic-hotkey'):
                backend, events, selections, selected = fixture_backend()
                with self.subTest(mode=mode, hotkey=hotkey), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True), \
                        patch.object(B, 'BITTENSOR_AVAILABLE', True), patch.object(B, 'bt', backend):
                    client = B.BittensorSubnet(wallet_name='synthetic-wallet', wallet_hotkey=hotkey)
                    self.assertIs(client._wallet, selected)
                    self.assertEqual(client.get_balance(), 3.25)
                    self.assertEqual(selections, [{'name': 'synthetic-wallet', 'hotkey': hotkey or 'default'}])
                    self.assertEqual(events, Counter(subtensor=1, wallet=1))

    def test_setup_callback_drift_prevents_wallet_creation(self):
        for mutation in ('live', 'local', 'mock', 'name', 'hotkey', 'missing'):
            client = uninitialized_client()
            def change():
                if mutation == 'live': os.environ['VAMS_ENV'] = 'testnet'
                elif mutation == 'local': os.environ['VAMS_ENV'] = 'local'
                elif mutation == 'mock': os.environ['SENTINEL_MOCK_MODE'] = 'true'
                elif mutation == 'name': client.wallet_name = 'different-synthetic-wallet'
                elif mutation == 'hotkey': client.wallet_hotkey = 'different-synthetic-hotkey'
                else: os.environ.pop('VAMS_ENV')
            backend, events, _, _ = fixture_backend(subtensor_callback=change)
            with self.subTest(mutation=mutation), patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True), patch.object(B, 'bt', backend):
                with self.assertRaises(LiveModeSafetyError): client._init_subtensor()
                self.assertEqual(events, Counter(subtensor=1)); self.assertIsNone(client._wallet)

    def test_wallet_callback_drift_prevents_adoption_without_claiming_no_construction(self):
        for mutation in ('mode', 'name', 'mock'):
            for preserve_prior in (False, True):
                client = uninitialized_client(); prior = object() if preserve_prior else None; client._wallet = prior
                def change():
                    if mutation == 'mode': os.environ['VAMS_ENV'] = 'production'
                    elif mutation == 'name': client.wallet_name = 'different-synthetic-wallet'
                    else: os.environ['SENTINEL_MOCK_MODE'] = 'true'
                backend, events, _, _ = fixture_backend(wallet_callback=change)
                with self.subTest(mutation=mutation, preserve_prior=preserve_prior), \
                        patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True), patch.object(B, 'bt', backend):
                    with self.assertRaises(LiveModeSafetyError): client._init_subtensor()
                    self.assertEqual(events, Counter(subtensor=1, wallet=1))
                    self.assertIs(client._wallet, prior)

    def test_untrusted_provider_errors_remain_bounded_connection_failures(self):
        for phase in ('subtensor', 'wallet'):
            for error_type in (OpaqueProviderError, LiveModeSafetyError, RuntimeConfigurationError):
                client = uninitialized_client(); OpaqueProviderError.reads = 0
                def fail(): raise error_type('SYNTHETIC_PROVIDER_DETAIL')
                backend, _, _, _ = fixture_backend(**{phase+'_callback': fail})
                with self.subTest(phase=phase, error_type=error_type), patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True), \
                        patch.object(B, 'bt', backend), redirect_stdout(io.StringIO()) as output:
                    client._init_subtensor()
                    self.assertFalse(client.is_connected); self.assertIsNone(client._wallet)
                    self.assertEqual(OpaqueProviderError.reads, 0)
                    self.assertNotIn('SYNTHETIC_', output.getvalue())

    def test_unavailable_sdk_constructor_stays_harmless(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(B, 'BITTENSOR_AVAILABLE', False):
            client = B.BittensorSubnet(wallet_name='synthetic-wallet')
            self.assertFalse(client.is_connected); self.assertIsNone(client._wallet)

    def test_no_wallet_callback_cannot_promote_itself_to_wallet_creation(self):
        client = uninitialized_client(wallet_name=None, wallet_hotkey=None)
        def change(): client.wallet_name = 'injected-synthetic-wallet'
        backend, events, _, _ = fixture_backend(subtensor_callback=change)
        with patch.dict(os.environ, {'VAMS_ENV': 'production'}, clear=True), patch.object(B, 'bt', backend):
            client._init_subtensor()
            self.assertIsNone(client._wallet); self.assertEqual(events, Counter(subtensor=1))

    def test_health_wallet_label_tracks_bound_wallet_not_mutable_public_selectors(self):
        for selected_name in ('synthetic-wallet', None):
            backend, events, _, _ = fixture_backend()
            with self.subTest(selected_name=selected_name), patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True), \
                    patch.object(B, 'BITTENSOR_AVAILABLE', True), patch.object(B, 'bt', backend):
                client = B.BittensorSubnet(wallet_name=selected_name)
                prior_wallet = client._wallet
                client.wallet_name = 'different-synthetic-wallet'
                client.wallet_hotkey = 'different-synthetic-hotkey'
                result = client.check_health()
                self.assertEqual(result['status'], 'healthy')
                self.assertEqual(result['wallet'], selected_name or 'none')
                self.assertIs(client._wallet, prior_wallet)
                self.assertEqual(events['wallet'], int(selected_name is not None))


if __name__ == '__main__': unittest.main()
