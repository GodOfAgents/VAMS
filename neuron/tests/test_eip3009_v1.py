"""Local codec tests; synthetic public scalars only, no custody/token/provider.

Unexecuted preparation. Published constants: ERC-3009 specification opened by
root on 15 November 2026, lines 66–69 and 206–207. No live token is implied.
"""
from dataclasses import replace
import hashlib
import unittest

from eth_abi import decode
from eth_account.messages import encode_typed_data
from eth_keys import keys
from eth_keys.constants import SECPK1_N
from web3 import Web3

from neuron.payments.eip3009_v1 import (
    EIP3009AuthorizationV1 as Authorization, EIP3009DomainV1 as Domain,
    EIP3009Error, DOMAIN_TYPEHASH, TRANSFER_TYPEHASH, RECEIVE_TYPEHASH,
)
from neuron.payments.intent_v1 import UINT256_MAX, APPROVAL_DOMAIN
from neuron.signed_receipts import DOMAIN as SIGNED_RECEIPT_DOMAIN
from neuron.effect_protocol_v3 import OBJECT_DOMAIN
from neuron.tests import test_payment_intent_v1 as payment_fixtures


def address(number):
    return number.to_bytes(32, 'big')


class EIP3009CodecV1Tests(unittest.TestCase):
    def setUp(self):
        # Public, test-only scalar. No production module contains a signing API.
        self.key = keys.PrivateKey((1).to_bytes(32, 'big'))
        self.payer = bytes(12) + self.key.public_key.to_canonical_address()
        self.domain = Domain('Synthetic Dollar', '2', 80002, address(11))
        self.auth = Authorization(self.payer, address(12), 100, 1000, 1100, bytes(32), 'transfer')

    def signature(self, authorization=None, domain=None):
        value = self.key.sign_msg_hash((authorization or self.auth).digest(domain or self.domain))
        return value.r.to_bytes(32, 'big') + value.s.to_bytes(32, 'big') + bytes([value.v + 27])

    def test_published_typehashes_and_distinct_methods(self):
        self.assertEqual(DOMAIN_TYPEHASH.hex(), '8b73c3c69bb8fe3d512ecc4cf759cc79239f7b179b0ffacaa9a75d522b39400f')
        self.assertEqual(TRANSFER_TYPEHASH.hex(), '7c7c6cdb67a18743f49ec6fa9b35f50d52ed05cbed4cc592e13b44501c1a2267')
        self.assertEqual(RECEIVE_TYPEHASH.hex(), 'd099cc98ef71107a616c4f0f941f04c322d8e254fe26b3c6668db87aae413de8')
        self.assertNotEqual(self.auth.struct_hash, replace(self.auth, method='receive').struct_hash)

    def test_reference_eth_account_typed_encoder_matches_both_methods(self):
        for method in ('transfer', 'receive'):
            with self.subTest(method=method):
                auth = replace(self.auth, method=method)
                message = encode_typed_data(full_message=auth.typed_data(self.domain))
                self.assertEqual(bytes(message.version), b'\x01')
                self.assertEqual(bytes(message.header), self.domain.separator)
                self.assertEqual(bytes(message.body), auth.struct_hash)
                self.assertEqual(bytes(Web3.keccak(b'\x19' + message.version + message.header + message.body)),
                                 auth.digest(self.domain))
                auth.verify_eoa(self.domain, self.signature(auth), 1050)

    def test_genuine_eoa_signature_and_domain_field_mutations(self):
        signature = self.signature()
        self.assertIsNone(self.auth.verify_eoa(self.domain, signature, 1050))
        for field, value in (('name', 'Other Dollar'), ('version', '1'), ('chain_id', 1), ('token', address(99))):
            with self.subTest(field=field):
                with self.assertRaises(EIP3009Error):
                    self.auth.verify_eoa(replace(self.domain, **{field: value}), signature, 1050)

    def test_every_authorization_field_mutation_rejects_original_signature(self):
        changes = {'payer': address(21), 'payee': address(22), 'value': 101, 'valid_after': 1001,
                   'valid_before': 1099, 'nonce': bytes(31) + b'\x01', 'method': 'receive'}
        for field, value in changes.items():
            with self.subTest(field=field):
                with self.assertRaises(EIP3009Error):
                    replace(self.auth, **{field: value}).verify_eoa(self.domain, self.signature(), 1050)

    def test_strict_time_boundaries_no_boolean_clock(self):
        for now in (999, 1000, 1100, 1101, True, 1050.0, -1):
            with self.subTest(now=now):
                with self.assertRaises(EIP3009Error):
                    self.auth.verify_eoa(self.domain, self.signature(), now)
        for now in (1001, 1099):
            self.auth.verify_eoa(self.domain, self.signature(), now)

    def test_canonical_low_s_v_and_signature_width(self):
        signature = self.signature()
        high_s = signature[:32] + (SECPK1_N - int.from_bytes(signature[32:64], 'big')).to_bytes(32, 'big') + signature[64:]
        cases = [b'', signature[:64], signature + b'\x00', bytearray(signature), high_s,
                 signature[:64] + b'\x00', signature[:64] + b'\x01', signature[:64] + b'\x1d',
                 bytes(32) + signature[32:], signature[:32] + bytes(32) + signature[64:],
                 SECPK1_N.to_bytes(32, 'big') + signature[32:]]
        for raw in cases:
            with self.subTest(raw_type=type(raw).__name__, length=len(raw)):
                with self.assertRaises(EIP3009Error):
                    self.auth.verify_eoa(self.domain, raw, 1050)
                with self.assertRaises(EIP3009Error):
                    self.auth.calldata(raw)

    def test_non_eoa_payer_modes_are_explicitly_unsupported(self):
        for kind in ('smart-account', 'session', 'eip1271', True, None):
            with self.subTest(kind=kind):
                with self.assertRaises(EIP3009Error):
                    self.auth.verify_eoa(self.domain, self.signature(), 1050, payer_kind=kind)

    def test_abi_calldata_selectors_and_all_words(self):
        for method, selector in (('transfer', 'e3ee160e'), ('receive', 'ef55bec6')):
            with self.subTest(method=method):
                auth = replace(self.auth, method=method)
                signature = self.signature(auth)
                raw = auth.calldata(signature, caller=auth.payee if method == 'receive' else None)
                self.assertEqual(raw[:4].hex(), selector)
                self.assertEqual(len(raw), 4 + 9 * 32)
                fields = decode(['address', 'address', 'uint256', 'uint256', 'uint256', 'bytes32',
                                 'uint8', 'bytes32', 'bytes32'], raw[4:])
                self.assertEqual(fields, ('0x' + self.payer[12:].hex(), '0x' + auth.payee[12:].hex(),
                    100, 1000, 1100, bytes(32), signature[64], signature[:32], signature[32:64]))

    def test_receive_requires_payee_caller_transfer_is_not_exclusive_facilitator(self):
        receive = replace(self.auth, method='receive')
        for caller in (None, address(91)):
            with self.assertRaises(EIP3009Error):
                receive.calldata(self.signature(receive), caller=caller)
        self.assertEqual(self.auth.calldata(self.signature(), caller=address(91)),
                         self.auth.calldata(self.signature(), caller=address(92)))

    def test_uint256_exact_extremes_and_invalid_types(self):
        maximum = replace(self.auth, value=UINT256_MAX, valid_before=UINT256_MAX)
        maximum.verify_eoa(self.domain, self.signature(maximum), 1050)
        fields = decode(['address', 'address', 'uint256', 'uint256', 'uint256', 'bytes32',
                         'uint8', 'bytes32', 'bytes32'], maximum.calldata(self.signature(maximum))[4:])
        self.assertEqual(fields[2], UINT256_MAX)
        self.assertEqual(fields[4], UINT256_MAX)
        for field in ('value', 'valid_after', 'valid_before'):
            for value in (True, 1.0, -1, UINT256_MAX + 1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(EIP3009Error):
                        replace(self.auth, **{field: value})
        self.assertEqual(replace(self.auth, value=0).value, 0)

    def test_domain_and_address_and_nonce_shape_rejections(self):
        for field, bad in (('name', ''), ('version', ''), ('name', 'a\n'), ('name', 'a' * 129),
                           ('chain_id', 0), ('chain_id', True), ('chain_id', 1.0),
                           ('token', bytes(32)), ('token', bytes(20)), ('token', b'\x01' + bytes(31))):
            with self.subTest(field=field):
                with self.assertRaises(EIP3009Error):
                    replace(self.domain, **{field: bad})
        for field in ('payer', 'payee'):
            for bad in (bytes(32), bytes(20), b'\x01' + bytes(31), bytearray(address(2))):
                with self.assertRaises(EIP3009Error):
                    replace(self.auth, **{field: bad})
        for bad in (bytes(31), bytes(33), bytearray(32), '00' * 32):
            with self.assertRaises(EIP3009Error):
                replace(self.auth, nonce=bad)
        for bad in ('', 'permit', 'Transfer', True):
            with self.assertRaises(EIP3009Error):
                replace(self.auth, method=bad)
        with self.assertRaises(EIP3009Error):
            replace(self.auth, valid_before=self.auth.valid_after)

    def test_v1_intent_projection_exact_bindings_and_transfer_only(self):
        fixture = payment_fixtures.PaymentIntentV1Tests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        domain = Domain('Fixture Token', '1', fixture.intent.chain_id, fixture.intent.asset)
        intent = replace(fixture.intent, token_domain=domain.separator)
        auth = Authorization.from_intent(domain, intent, method='transfer')
        self.assertIsNone(auth.validate_for_intent(domain, intent))
        for method in ('receive', 'permit'):
            with self.assertRaises(EIP3009Error):
                Authorization.from_intent(domain, intent, method=method)
        with self.assertRaises(EIP3009Error):
            replace(auth, method='receive').validate_for_intent(domain, intent)
        for field, value in (('payer', address(91)), ('payee', address(92)), ('value', auth.value - 1),
                             ('nonce', bytes(32)), ('valid_after', auth.valid_after + 1),
                             ('valid_before', auth.valid_before - 1)):
            with self.subTest(field=field):
                with self.assertRaises(EIP3009Error):
                    replace(auth, **{field: value}).validate_for_intent(domain, intent)
        for bad in (replace(domain, chain_id=1), replace(domain, token=address(93)), replace(domain, version='2')):
            with self.assertRaises(EIP3009Error):
                auth.validate_for_intent(bad, intent)

    def test_standard_authorization_does_not_commit_job_context_or_replay_state(self):
        fixture = payment_fixtures.PaymentIntentV1Tests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        domain = Domain('Fixture Token', '1', fixture.intent.chain_id, fixture.intent.asset)
        intent = replace(fixture.intent, token_domain=domain.separator)
        other = replace(intent, service_block_id=bytes(Web3.keccak(text='Other synthetic job')))
        self.assertNotEqual(intent.digest, other.digest)
        self.assertEqual(Authorization.from_intent(domain, intent, method='transfer'),
                         Authorization.from_intent(domain, other, method='transfer'))
        # A pure verifier has no nonce database: repeat verification is not consumption.
        self.auth.verify_eoa(self.domain, self.signature(), 1050)
        self.auth.verify_eoa(self.domain, self.signature(), 1050)

    def test_actual_vams_domains_are_not_token_authority(self):
        # Genuine EOA signatures over wrong messages using actual source domain
        # tags; not a claim to construct complete VAMS receipt/approval objects.
        for prefix in (APPROVAL_DOMAIN, SIGNED_RECEIPT_DOMAIN, OBJECT_DOMAIN):
            with self.subTest(domain=prefix):
                value = self.key.sign_msg_hash(hashlib.sha256(prefix + self.auth.struct_hash).digest())
                signature = value.r.to_bytes(32, 'big') + value.s.to_bytes(32, 'big') + bytes([value.v + 27])
                with self.assertRaises(EIP3009Error):
                    self.auth.verify_eoa(self.domain, signature, 1050)


if __name__ == '__main__':
    unittest.main()
