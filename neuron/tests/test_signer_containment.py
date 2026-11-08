"""SDK route containment with spy dependencies; no keys or signatures are used.

These unit fixtures observe calls before key loading, encoding, compliance and
signing. They do not verify eth-account, wallet behavior or a production broker.
"""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from neuron.runtime_safety import (
    LiveModeSafetyError, RuntimeConfigurationError, RuntimePolicy,
)


SIGNER_PATH = Path(__file__).resolve().parents[1] / 'sdk/signer.py'
OWNER = '0x' + '11' * 20
WALLET = '0x' + '22' * 20
TARGET = '0x' + '33' * 20
LIVE_MODES = ('staging', 'testnet', 'production')
LOCAL_MODES = ('test', 'local', 'demo')


class SignerContainmentTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        events = self.events

        class SpyAccount:
            address = OWNER

            @classmethod
            def from_key(cls, value):
                events.append('load-key')
                return cls()

            def sign_transaction(self, transaction):
                events.append('sign-transaction')
                return 'fixture-transaction-signature'

            def sign_message(self, message):
                events.append('sign-message')
                return types.SimpleNamespace(signature=b'fixture-signature')

        class SpyWeb3:
            @staticmethod
            def to_checksum_address(value):
                events.append('checksum')
                return value

        class SpyIdentity:
            def __init__(self, **kwargs):
                events.append('identity-create')

            def is_compliance_verified(self, value):
                events.append('compliance-read')
                return True

        def encode_defunct(*args, **kwargs):
            events.append('encode-message')
            return 'fixture-encoded-message'

        account_module = types.ModuleType('eth_account')
        account_module.Account = SpyAccount
        signers_module = types.ModuleType('eth_account.signers')
        local_module = types.ModuleType('eth_account.signers.local')
        local_module.LocalAccount = SpyAccount
        messages_module = types.ModuleType('eth_account.messages')
        messages_module.encode_defunct = encode_defunct
        web3_module = types.ModuleType('web3')
        web3_module.Web3 = SpyWeb3
        identity_module = types.ModuleType('neuron.sdk.oms_identity')
        identity_module.OMSIdentityVerifier = SpyIdentity
        self.identity_type = SpyIdentity
        self.account_type = SpyAccount
        module_patch = patch.dict(sys.modules, {
            'eth_account': account_module, 'eth_account.signers': signers_module,
            'eth_account.signers.local': local_module,
            'eth_account.messages': messages_module, 'web3': web3_module,
            'neuron.sdk.oms_identity': identity_module,
        })
        module_patch.start()
        self.addCleanup(module_patch.stop)
        spec = importlib.util.spec_from_file_location('_vams_signer_containment_subject', SIGNER_PATH)
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)

    def test_live_eoa_rejects_before_key_loading(self):
        for mode in LIVE_MODES:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                with self.assertRaises(LiveModeSafetyError):
                    self.subject.EOASigner('synthetic-key-placeholder')
                self.assertEqual(self.events, [])

    def test_live_session_rejects_before_checksum_or_key_loading(self):
        for mode in LIVE_MODES:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                with self.assertRaises(LiveModeSafetyError):
                    self.subject.SessionKeySigner(WALLET, 'synthetic-key-placeholder')
                self.assertEqual(self.events, [])

    def test_live_oms_wrapper_rejects_before_identity_or_signer_calls(self):
        for mode in LIVE_MODES:
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                with self.assertRaises(LiveModeSafetyError):
                    self.subject.OMSSigner(self.account_type())
                self.assertEqual(self.events, [])

    def test_live_factory_rejects_all_raw_key_routes_before_effects(self):
        configs = (
            {'private_key': 'synthetic-key-placeholder'},
            {'session_key': 'synthetic-key-placeholder', 'smart_wallet_address': WALLET},
            {'private_key': 'synthetic-key-placeholder', 'oms_compliance': True},
        )
        for mode in LIVE_MODES:
            for config in configs:
                with self.subTest(mode=mode, keys=tuple(config)), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                    with self.assertRaises(LiveModeSafetyError):
                        self.subject.SignerFactory.create(config)
                    self.assertEqual(self.events, [])

    def test_missing_or_malformed_mode_rejects_before_key_loading(self):
        for source in ({}, {'VAMS_ENV': ''}, {'VAMS_ENV': 'prod'},
                       {'VAMS_ENV': 'Test'}, {'VAMS_ENV': ' local'}):
            with self.subTest(source=source), patch.dict(os.environ, source, clear=True):
                with self.assertRaises(RuntimeConfigurationError):
                    self.subject.EOASigner('synthetic-key-placeholder')
                self.assertEqual(self.events, [])

    def test_nonlive_eoa_retains_fixture_delegation(self):
        for mode in LOCAL_MODES:
            self.events.clear()
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                signer = self.subject.EOASigner('synthetic-key-placeholder')
                self.assertEqual(signer.address, OWNER)
                self.assertEqual(signer.sign_transaction({'to': TARGET}), 'fixture-transaction-signature')
                self.assertEqual(signer.sign_message(b'fixture').signature, b'fixture-signature')
                self.assertEqual(self.events, ['load-key', 'sign-transaction', 'encode-message', 'sign-message'])

    def test_nonlive_session_remains_explicitly_synthetic(self):
        for mode in LOCAL_MODES:
            self.events.clear()
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                signer = self.subject.SessionKeySigner(WALLET, 'synthetic-key-placeholder')
                operation = signer.sign_transaction({'sender': WALLET})
                self.assertEqual(operation['signature'], b'fixture-signature'.hex())
                self.assertEqual(signer.address, WALLET)
                self.assertEqual(self.events, ['checksum', 'load-key', 'encode-message', 'sign-message'])

    def test_nonlive_oms_still_requires_compliance_before_delegation(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True):
            signer = self.subject.OMSSigner(self.account_type())
            signer.sign_transaction({'to': TARGET})
            signer.sign_message(b'fixture')
            self.assertEqual(self.events, ['identity-create', 'compliance-read', 'sign-transaction',
                                           'compliance-read', 'sign-message'])

    def test_retained_eoa_rechecks_mode_before_transaction_and_message(self):
        for mode in LIVE_MODES:
            with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
                signer = self.subject.EOASigner('synthetic-key-placeholder')
            self.events.clear()
            with self.subTest(mode=mode), patch.dict(os.environ, {'VAMS_ENV': mode}, clear=True):
                for invoke in (lambda: signer.sign_transaction({'to': TARGET}), lambda: signer.sign_message(b'fixture')):
                    with self.assertRaises(LiveModeSafetyError):
                        invoke()
                self.assertEqual(self.events, [])

    def test_retained_session_rejects_before_user_operation_mutation(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            signer = self.subject.SessionKeySigner(WALLET, 'synthetic-key-placeholder')
        self.events.clear()
        operation = {'sender': WALLET, 'signature': 'unchanged'}
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            with self.assertRaises(LiveModeSafetyError):
                signer.sign_transaction(operation)
            with self.assertRaises(LiveModeSafetyError):
                signer.sign_message(b'fixture')
        self.assertEqual(operation, {'sender': WALLET, 'signature': 'unchanged'})
        self.assertEqual(self.events, [])

    def test_retained_oms_rejects_before_compliance_request(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            signer = self.subject.OMSSigner(self.account_type())
        self.events.clear()
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            with self.assertRaises(LiveModeSafetyError):
                signer.sign_transaction({'to': TARGET})
            with self.assertRaises(LiveModeSafetyError):
                signer.sign_message(b'fixture')
        self.assertEqual(self.events, [])

    def test_nonlive_mode_drift_does_not_reclassify_existing_signer(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            signer = self.subject.EOASigner('synthetic-key-placeholder')
        self.events.clear()
        with patch.dict(os.environ, {'VAMS_ENV': 'demo'}, clear=True):
            with self.assertRaises(RuntimeConfigurationError):
                signer.sign_transaction({'to': TARGET})
        self.assertEqual(self.events, [])

    def test_mock_configuration_drift_rejects_before_encoding(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            signer = self.subject.EOASigner('synthetic-key-placeholder')
        self.events.clear()
        with patch.dict(os.environ, {'VAMS_ENV': 'local', 'OMS_MOCK_MODE': 'true'}, clear=True):
            with self.assertRaises(RuntimeConfigurationError):
                signer.sign_message(b'fixture')
        self.assertEqual(self.events, [])

    def test_missing_mode_after_construction_rejects_before_signing(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            signer = self.subject.EOASigner('synthetic-key-placeholder')
        self.events.clear()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeConfigurationError):
                signer.sign_transaction({'to': TARGET})
        self.assertEqual(self.events, [])

    def test_runtime_configuration_is_immutable(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'local'}, clear=True):
            signer = self.subject.EOASigner('synthetic-key-placeholder')
            with self.assertRaises(RuntimeConfigurationError):
                signer.runtime_policy = RuntimePolicy.from_environment({'VAMS_ENV': 'demo'})

    def test_local_factory_routes_remain_available(self):
        with patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True):
            eoa = self.subject.SignerFactory.create({'private_key': 'synthetic-key-placeholder'})
            session = self.subject.SignerFactory.create({'session_key': 'synthetic-key-placeholder', 'smart_wallet_address': WALLET})
            oms = self.subject.SignerFactory.create({'private_key': 'synthetic-key-placeholder', 'oms_compliance': True})
            self.assertEqual((eoa.address, session.address, oms.address), (OWNER, WALLET, OWNER))


if __name__ == '__main__':
    unittest.main()
