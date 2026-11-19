"""Unexecuted local policy regressions with public synthetic secp256k1 fixtures.

No PostgreSQL, network, token, payment, finality or custody qualification.
"""
from dataclasses import fields, replace
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from neuron.effect_attempts_v5 import ObjectAttemptV5, NativeObjectRowV1, authority_context_id
from neuron.effect_protocol_v3 import ObjectEffectV3, SignedEffectReceiptV3
from neuron.payments.intent_v1 import (
    PaymentIntentV1, PaymentCapabilityV1, PaymentApprovalV1, PaymentApprovalVerifierV1,
    PaymentPolicyBindingV1, PaymentPolicySourceV1, PaymentPolicyStateV1, PaymentPolicyError,
    INTENT_DOMAIN, APPROVAL_DOMAIN, INTENT_HASH_FIELDS, INTENT_INT_FIELDS,
    APPROVAL_HASH_FIELDS, APPROVAL_INT_FIELDS,
    UINT256_MAX, MAX_INTENT_SECONDS,
)
from neuron.signed_receipts import ReceiptSignerV3, ORDER


def h(value):
    return hashlib.sha256(value).digest()


def address(number):
    return number.to_bytes(32, 'big')


class FixturePolicy(PaymentPolicySourceV1):
    def __init__(self, state, *, after=None, unavailable=False):
        self.state, self.after, self.unavailable, self.reads = state, after, unavailable, 0

    def read_current(self):
        self.reads += 1
        if self.unavailable:
            raise OSError('SYNTHETIC unavailable policy backend')
        return self.after if self.reads > 1 and self.after is not None else self.state


class PaymentIntentV1Tests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'VAMS_ENV': 'test'}, clear=True)
        environment.start(); self.addCleanup(environment.stop)
        fixture = json.loads(Path(__file__).with_name('effect_attempt_v5_fixture.json').read_text(encoding='utf8'))
        proposal = ObjectEffectV3.from_bytes(bytes.fromhex(fixture['proposal']))
        admission = SignedEffectReceiptV3.from_bytes(bytes.fromhex(fixture['receipts']['admission']['bytes']))
        c = proposal.context
        self.attempt = ObjectAttemptV5(NativeObjectRowV1(c.chain_id, c.target, h(b'SYNTHETIC allocation'), 0),
                                       proposal, admission, 1, None)
        self.authority = ReceiptSignerV3(ec.derive_private_key(1, ec.SECP256K1())).verifier()
        # Public test-only signing key; production module has no signing API.
        self.key = ec.derive_private_key(3, ec.SECP256K1())
        self.verifier = PaymentApprovalVerifierV1(self.key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        self.capability = PaymentCapabilityV1(actor_root=c.actor_root, provider_id=c.provider_id,
            host_domain=c.host_domain, budget_unit=c.budget_unit, policy_root=c.policy_root,
            asset=address(11), token_domain=h(b'SYNTHETIC token EIP712 domain'), payer=c.actor_root,
            payee=c.target, facilitator=address(12), budget_identity=h(b'SYNTHETIC monetary budget'),
            service_block_id=h(b'SYNTHETIC service'), registry_terms_hash=h(b'SYNTHETIC registry terms'),
            builder=address(13), authority_epoch=c.authority_epoch, policy_version=c.policy_version,
            chain_id=c.chain_id, decimals=6, max_per_call=100, max_aggregate=1000,
            valid_after=c.issued_at, valid_before=c.expires_at, builder_bps=1000)
        self.intent = self.make_intent()
        self.now = c.issued_at + 1

    def make_intent(self, *, capability=None, attempt=None, amount=100, **changes):
        c = capability or self.capability
        values = {name: getattr(c, name) for name in ('asset', 'token_domain', 'decimals', 'payer',
            'payee', 'facilitator', 'valid_after', 'valid_before', 'service_block_id', 'registry_terms_hash',
            'builder', 'builder_bps', 'budget_identity')}
        values.update(amount=amount, nonce=h(b'SYNTHETIC transfer nonce'), capability_digest=c.digest)
        values.update(changes)
        return PaymentIntentV1.for_attempt(attempt or self.attempt, **values)

    def state(self, capability=None):
        c = capability or self.capability
        return PaymentPolicyStateV1(True, c.digest, c.actor_root, c.provider_id, c.host_domain,
                                    c.policy_root, c.authority_epoch, c.policy_version)

    def binding(self, *, capability=None, source=None, authority=None, verifier=None):
        c = capability or self.capability
        return PaymentPolicyBindingV1(authority or self.authority, verifier or self.verifier, c,
                                      source or FixturePolicy(self.state(c)))

    def approval(self, intent=None):
        intent = intent or self.intent
        placeholder = (1).to_bytes(32, 'big') * 2
        value = PaymentApprovalV1(intent.digest, intent.capability_digest, intent.nonce, intent.actor_root,
            intent.provider_id, intent.host_domain, intent.policy_root, self.verifier.issuer_id,
            intent.authority_epoch, intent.policy_version, intent.valid_after, intent.valid_before, placeholder)
        raw = self.key.sign(value.digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        r, s = utils.decode_dss_signature(raw)
        return replace(value, signature=r.to_bytes(32, 'big') + min(s, ORDER - s).to_bytes(32, 'big'))

    def test_real_fixture_admission_and_new_payment_signature_validate(self):
        source = FixturePolicy(self.state())
        intent, approval = self.intent, self.approval()
        self.assertEqual(self.binding(source=source).validate_new(intent, self.attempt, approval, self.now), intent.digest)
        self.assertEqual(source.reads, 2)
        self.assertEqual(intent.operation_id, self.attempt.proposal.operation_id)
        self.assertEqual(intent.attempt_id, self.attempt.attempt_id)
        self.assertEqual(intent.authority_context_id, authority_context_id(self.attempt.proposal))
        self.assertNotEqual(approval.digest, self.attempt.admission.digest)
        self.assertFalse(hasattr(self.verifier, 'sign'))

    def test_canonical_fixed_word_roundtrips_and_signature_exclusion(self):
        intent, approval = self.intent, self.approval()
        self.assertEqual(PaymentIntentV1.from_bytes(intent.canonical_bytes()), intent)
        self.assertEqual(len(intent.canonical_bytes()), len(INTENT_DOMAIN) + 32 * (len(INTENT_HASH_FIELDS) + len(INTENT_INT_FIELDS)))
        self.assertEqual(PaymentApprovalV1.from_bytes(approval.canonical_bytes()), approval)
        alternative = replace(approval, signature=(1).to_bytes(32, 'big') * 2)
        self.assertEqual(alternative.digest, approval.digest)
        self.assertNotEqual(alternative.canonical_bytes(), approval.canonical_bytes())

    def test_parsers_reject_trailing_short_wrong_domain_and_version(self):
        for cls, value, domain, hash_names, int_names in (
            (PaymentIntentV1, self.intent, INTENT_DOMAIN, INTENT_HASH_FIELDS, INTENT_INT_FIELDS),
            (PaymentApprovalV1, self.approval(), APPROVAL_DOMAIN, APPROVAL_HASH_FIELDS, APPROVAL_INT_FIELDS),
        ):
            raw = value.canonical_bytes()
            for bad in (raw + b'\0', raw[:-1], b'X' + raw[1:], bytearray(raw), self.attempt.admission.canonical_bytes()):
                with self.subTest(cls=cls.__name__, bad_type=type(bad)), self.assertRaises(ValueError):
                    cls.from_bytes(bad)
            offset = len(domain) + 32 * (len(hash_names) + int_names.index('schema_version'))
            wrong_version = raw[:offset] + (2).to_bytes(32, 'big') + raw[offset + 32:]
            with self.assertRaises(ValueError): cls.from_bytes(wrong_version)
        with self.assertRaises(ValueError): replace(self.intent, schema_version=2).canonical_bytes()
        with self.assertRaises(ValueError): replace(self.approval(), purpose=2).canonical_bytes()

    def test_all_intent_fields_are_bound_and_mutation_denies(self):
        approval = self.approval()
        addresses = {'actor_root', 'asset', 'payer', 'payee', 'facilitator', 'builder'}
        for f in fields(self.intent):
            old = getattr(self.intent, f.name)
            value = address(99) if f.name in addresses else h(f.name.encode()) if type(old) is bytes else old + 1
            changed = replace(self.intent, **{f.name: value})
            with self.subTest(field=f.name), self.assertRaises(ValueError):
                self.binding().validate_new(changed, self.attempt, approval, self.now)

    def test_non_evm_root_scheme_is_not_reinterpreted_as_an_evm_payer(self):
        proposal = replace(self.attempt.proposal, context=replace(self.attempt.proposal.context, root_scheme=2))
        proposal = replace(proposal, context=replace(proposal.context, action_hash=proposal.action_hash))
        proposal.validate()
        other = replace(self.attempt, proposal=proposal)
        with self.assertRaisesRegex(ValueError, 'EVM|root'):
            self.make_intent(attempt=other)

    def test_all_approval_fields_and_signature_are_authenticated(self):
        approval = self.approval()
        for f in fields(approval):
            old = getattr(approval, f.name)
            if f.name == 'signature': value = (1).to_bytes(32, 'big') * 2
            elif f.name == 'actor_root': value = address(99)
            else: value = h(f.name.encode()) if type(old) is bytes else old + 1
            with self.subTest(field=f.name), self.assertRaises(ValueError):
                self.binding().validate_new(self.intent, self.attempt, replace(approval, **{f.name: value}), self.now)
        high_s = approval.signature[:32] + (ORDER - int.from_bytes(approval.signature[32:], 'big')).to_bytes(32, 'big')
        with self.assertRaises(ValueError): PaymentApprovalV1.from_bytes(approval.canonical_bytes()[:-64] + high_s)

    def test_floats_booleans_negative_and_overflow_never_coerce(self):
        for name in INTENT_INT_FIELDS:
            for value in (True, False, 1.0, '1', -1, UINT256_MAX + 1):
                with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                    replace(self.intent, **{name: value}).canonical_bytes()
        for name in ('amount', 'chain_id', 'decimals'):
            with self.subTest(field=name), self.assertRaises(ValueError):
                replace(self.intent, **{name: None}).validate()

    def test_uint256_money_maximum_and_budget_fingerprint(self):
        cap = replace(self.capability, max_per_call=UINT256_MAX, max_aggregate=UINT256_MAX)
        intent = self.make_intent(capability=cap, amount=UINT256_MAX)
        self.assertEqual(self.binding(capability=cap).validate_new(intent, self.attempt, self.approval(intent), self.now), intent.digest)
        self.assertEqual(intent.budget_fingerprint, cap.budget_fingerprint)
        self.assertEqual(cap.budget_fingerprint, replace(cap, policy_version=cap.policy_version + 1,
                          policy_root=h(b'new policy'), max_aggregate=UINT256_MAX - 1, max_per_call=1).budget_fingerprint)
        for name, value in (('asset', address(31)), ('decimals', 18), ('token_domain', h(b'other domain')),
                            ('host_domain', h(b'other host')), ('chain_id', cap.chain_id + 1),
                            ('budget_unit', h(b'other unit'))):
            with self.subTest(field=name): self.assertNotEqual(cap.budget_fingerprint, replace(cap, **{name: value}).budget_fingerprint)

    def test_capability_exact_terms_limits_and_validity(self):
        for name, value in (('asset', address(40)), ('facilitator', address(41)), ('registry_terms_hash', h(b'changed terms')),
                            ('builder_bps', 999), ('decimals', 18), ('budget_identity', h(b'other budget')),
                            ('max_per_call', 99), ('max_validity_seconds', 1)):
            cap = replace(self.capability, **{name: value})
            with self.subTest(field=name), self.assertRaises(ValueError):
                cap.permits(replace(self.intent, capability_digest=cap.digest))
        for changes in ({'builder_bps': 5001}, {'protocol_bps': 6}, {'max_aggregate': 99},
                        {'max_validity_seconds': MAX_INTENT_SECONDS + 1}, {'max_per_call': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(self.capability, **changes).validate()

    def test_exact_attempt_and_evm_address_constraints(self):
        bad = replace(self.attempt, row=replace(self.attempt.row, allocation_id=h(b'another allocation')))
        with self.assertRaises(ValueError): self.intent.validate_for(bad)
        for value in (bytes(32), b'\1' * 32, b'\1' * 20, '0x' + '01' * 20):
            with self.subTest(value=value), self.assertRaises(ValueError): replace(self.intent, payer=value).validate()
        with self.assertRaises(ValueError): self.make_intent(payee=address(88))
        with self.assertRaises(ValueError): self.make_intent(valid_before=self.attempt.proposal.context.expires_at + 1)

    def test_admission_signature_is_not_payment_approval_and_bad_admission_denies(self):
        with self.assertRaises(ValueError):
            self.binding().validate_new(self.intent, self.attempt, self.attempt.admission, self.now)
        bad = replace(self.attempt, admission=replace(self.attempt.admission, signature=(1).to_bytes(32, 'big') * 2))
        intent = self.make_intent(attempt=bad)
        with self.assertRaises(ValueError): self.binding().validate_new(intent, bad, self.approval(intent), self.now)
        other = PaymentApprovalVerifierV1(ec.derive_private_key(4, ec.SECP256K1()).public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        with self.assertRaises(ValueError): self.binding(verifier=other).validate_new(self.intent, self.attempt, self.approval(), self.now)
        # Even the SAME public key cannot reinterpret its object admission
        # signature as a new-domain payment approval.
        same_key = PaymentApprovalVerifierV1(self.authority.public_key_bytes)
        reused = replace(self.approval(), issuer_id=same_key.issuer_id, signature=self.attempt.admission.signature)
        with self.assertRaises(ValueError):
            self.binding(verifier=same_key).validate_new(self.intent, self.attempt, reused, self.now)

    def test_unavailable_unknown_disabled_or_changed_current_policy_denies(self):
        states = (None, False, replace(self.state(), enabled=False), replace(self.state(), enabled=1),
                  replace(self.state(), policy_version=self.state().policy_version + 1),
                  replace(self.state(), policy_root=h(b'changed root')), replace(self.state(), authority_epoch=99))
        for state in states:
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.binding(source=FixturePolicy(state)).validate_new(self.intent, self.attempt, self.approval(), self.now)
        with self.assertRaisesRegex(PaymentPolicyError, 'unavailable'):
            self.binding(source=FixturePolicy(self.state(), unavailable=True)).validate_new(self.intent, self.attempt, self.approval(), self.now)

    def test_current_policy_change_between_before_after_rejects(self):
        source = FixturePolicy(self.state(), after=replace(self.state(), enabled=False))
        with self.assertRaises(ValueError): self.binding(source=source).validate_new(self.intent, self.attempt, self.approval(), self.now)
        self.assertEqual(source.reads, 2)

    def test_expiry_and_runtime_live_containment(self):
        for now in (self.intent.valid_after, self.intent.valid_before, self.intent.valid_before + 1, True, 1.0):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.binding().validate_new(self.intent, self.attempt, self.approval(), now)
        binding = self.binding()
        with patch.dict(os.environ, {'VAMS_ENV': 'testnet'}, clear=True):
            with self.assertRaises(ValueError): self.binding()
            with self.assertRaises(ValueError): binding.validate_new(self.intent, self.attempt, self.approval(), self.now)


if __name__ == '__main__':
    unittest.main()
