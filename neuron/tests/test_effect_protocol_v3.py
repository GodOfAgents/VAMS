"""Synthetic fixture keys, real ECDSA; no authentic custody or live evidence."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from cryptography.hazmat.primitives.asymmetric import ec
from neuron.action_context import ActionContextV1, ActionContextError, WIRE_FIELDS
from neuron.signed_receipts import ReceiptSignerV3, ReceiptError, ORDER
from neuron.effect_protocol_v3 import (
    ObjectEffectV3, ObjectFenceV3, SignedEffectReceiptV3, EffectV3Error,
    sign_receipt, verify_receipt, verify_admission, verify_effect,
    verify_fence_update, verify_fence_ack, effect_subject, fence_ack_subject,
)


def fixture_proposal(**changes):
    hashes = {name: bytes([i + 1]) * 32 for i, name in enumerate(WIRE_FIELDS[:13])}
    hashes.update(actor_root=b'\0' * 12 + b'\x11' * 20, target=b'\0' * 12 + b'\x22' * 20,
        model_id=b'\0' * 32, input_hash=hashlib.sha256(b'fixture-object').digest())
    values = dict(hashes, root_scheme=1, authority_epoch=3, policy_version=7,
        capabilities=1, budget=4096, issued_at=1000, expires_at=1100, chain_id=80002)
    values.update(changes)
    context = ActionContextV1(**values)
    proposal = ObjectEffectV3(context, b'r' * 32, 3, 9)
    return replace(proposal, context=replace(context, action_hash=proposal.action_hash))


def fixture_signer():
    return ReceiptSignerV3(ec.generate_private_key(ec.SECP256K1()))


def fixture_admission(proposal, signer, **changes):
    c = proposal.context
    values = dict(purpose=1, subject=proposal.digest, provider=c.provider_id,
        epoch=c.authority_epoch, policy=c.policy_version, fence=proposal.fencing_token,
        issued_at=c.issued_at, expires_at=c.expires_at)
    values.update(changes)
    return sign_receipt(signer, **values)


class ObjectProtocolV3Tests(unittest.TestCase):
    def setUp(self):
        self.proposal = fixture_proposal()
        self.authority, self.provider = fixture_signer(), fixture_signer()
        self.admission = fixture_admission(self.proposal, self.authority)

    def test_action_and_public_admission_roundtrip(self):
        p = self.proposal
        self.assertEqual(ObjectEffectV3.from_bytes(p.canonical_bytes()), p)
        self.assertEqual(SignedEffectReceiptV3.from_bytes(self.admission.canonical_bytes()), self.admission)
        verify_admission(p, self.admission, self.authority.verifier(), 1050)

    def test_frozen_object_and_fence_vector(self):
        vector = json.loads((Path(__file__).parents[2] / 'docs/remediation/repair_20261029/effect-v3-vector.json').read_text())
        p = self.proposal
        fence = ObjectFenceV3.from_context(p.context, p.fencing_token)
        self.assertEqual(p.canonical_bytes().hex(), vector['object_canonical_hex'])
        self.assertEqual(p.digest.hex(), vector['object_sha256'])
        self.assertEqual(p.operation_id.hex(), vector['operation_id'])
        self.assertEqual(p.postcondition.hex(), vector['postcondition'])
        self.assertEqual(fence.canonical_bytes().hex(), vector['fence_canonical_hex'])
        self.assertEqual(fence.digest.hex(), vector['fence_sha256'])

    def test_exact_wire_rejects_trailing_truncated_and_old_mac(self):
        for raw in (self.proposal.canonical_bytes() + b'\0', self.proposal.canonical_bytes()[:-1], b'{}', b'm' * 32):
            with self.subTest(raw_length=len(raw)), self.assertRaises((EffectV3Error, ActionContextError)):
                ObjectEffectV3.from_bytes(raw)
        for raw in (self.admission.canonical_bytes() + b'\0', self.admission.canonical_bytes()[:-1], b'm' * 32):
            with self.assertRaises(EffectV3Error): SignedEffectReceiptV3.from_bytes(raw)

    def test_stable_operation_across_provider_chain_and_authority_changes(self):
        p = self.proposal
        for field, value in dict(provider_id=b'P' * 32, chain_id=2, authority_epoch=4,
                policy_version=8, nonce=b'N' * 32, expires_at=1150).items():
            changed = fixture_proposal(**{field: value})
            self.assertEqual(p.operation_id, changed.operation_id)
            self.assertNotEqual(p.digest, changed.digest)
        self.assertNotEqual(p.operation_id, fixture_proposal(intent_id=b'I' * 32).operation_id)

    def test_resource_and_price_changes_cannot_reuse_old_action_commitment(self):
        for changes in ({'resource_id': b'z' * 32}, {'cost_units': 4}, {'fencing_token': 10}):
            with self.assertRaises(EffectV3Error): replace(self.proposal, **changes).validate()

    def test_payload_change_invalidates_context_action_hash(self):
        with self.assertRaises(EffectV3Error):
            replace(self.proposal, context=replace(self.proposal.context, input_hash=b'x' * 32)).validate()

    def test_context_fields_are_bound_by_admission_signature(self):
        mutations = dict(actor_root=b'\0' * 12 + b'\x33' * 20, provider_id=b'x' * 32,
            runtime_id=b'x' * 32, host_domain=b'x' * 32, workflow_id=b'x' * 32,
            intent_id=b'x' * 32, policy_root=b'x' * 32, target=b'x' * 32,
            nonce=b'x' * 32, budget_unit=b'x' * 32, authority_epoch=4, policy_version=8, budget=4097, chain_id=1)
        for name, value in mutations.items():
            changed = fixture_proposal(**{name: value})
            with self.subTest(field=name), self.assertRaises((EffectV3Error, ReceiptError)):
                verify_admission(changed, self.admission, self.authority.verifier(), 1050)

    def test_provider_signing_key_cannot_issue_authority(self):
        with self.assertRaises(ReceiptError):
            verify_admission(self.proposal, fixture_admission(self.proposal, self.provider), self.authority.verifier(), 1050)
        with self.assertRaises(EffectV3Error): fixture_admission(self.proposal, self.authority.verifier())
        self.assertFalse(hasattr(self.authority.verifier(), 'sign'))

    def test_no_other_capabilities_models_or_float_budget(self):
        for changes in ({'capabilities': 2}, {'capabilities': 3}, {'model_id': b'x' * 32},
                        {'budget': True}, {'budget': 3.0}, {'budget': -1}, {'budget': 2}, {'expires_at': 2000}):
            with self.subTest(changes=changes), self.assertRaises((EffectV3Error, ActionContextError)):
                fixture_proposal(**changes).validate()

    def test_current_time_and_admission_window_reject(self):
        for now in (999, 1100, True, 1050.0):
            with self.subTest(now=now), self.assertRaises((EffectV3Error, ReceiptError)):
                verify_admission(self.proposal, self.admission, self.authority.verifier(), now)
        for changes in ({'issued_at': 999}, {'expires_at': 1101}, {'purpose': 4}):
            with self.assertRaises((EffectV3Error, ReceiptError)):
                verify_admission(self.proposal, fixture_admission(self.proposal, self.authority, **changes), self.authority.verifier(), 1050)

    def test_high_s_and_wrong_length_signatures_reject(self):
        signature = self.admission.signature
        high = signature[:32] + (ORDER - int.from_bytes(signature[32:], 'big')).to_bytes(32, 'big')
        for invalid in (high, b'm' * 32, b'\0' * 64):
            with self.assertRaises((EffectV3Error, ReceiptError)):
                verify_admission(self.proposal, replace(self.admission, signature=invalid), self.authority.verifier(), 1050)

    def test_historical_effect_survives_expiry_but_does_not_admit(self):
        p, a = self.proposal, self.admission
        record = sign_receipt(self.provider, purpose=4, subject=effect_subject(p, a, 1050),
            provider=p.context.provider_id, epoch=3, policy=7, fence=9, issued_at=1050, expires_at=1100)
        verify_effect(p, a, record, self.provider.verifier(), 2000, authority=self.authority.verifier())
        with self.assertRaises((EffectV3Error, ReceiptError)): verify_admission(p, record, self.provider.verifier(), 2000)
        with self.assertRaises(ReceiptError): verify_effect(p, a, record, self.authority.verifier(), 2000, authority=self.authority.verifier())

    def test_historical_admission_verification_is_forbidden(self):
        with self.assertRaises(EffectV3Error):
            verify_receipt(self.admission, self.authority.verifier(), purpose=1,
                subject=self.proposal.digest, provider=self.proposal.context.provider_id,
                epoch=3, policy=7, fence=9, now=2000, historical=True)

    def test_fence_and_ack_bind_exact_update(self):
        p = self.proposal
        fence = ObjectFenceV3.from_context(p.context, p.fencing_token)
        self.assertEqual(ObjectFenceV3.from_bytes(fence.canonical_bytes()), fence)
        update = sign_receipt(self.authority, purpose=2, subject=fence.digest,
            provider=fence.provider_id, epoch=3, policy=7, fence=9, issued_at=1000, expires_at=1100)
        verify_fence_update(fence, update, self.authority.verifier(), 1050)
        ack = sign_receipt(self.provider, purpose=3, subject=fence_ack_subject(fence, update),
            provider=fence.provider_id, epoch=3, policy=7, fence=9, issued_at=1050, expires_at=1100)
        verify_fence_ack(fence, update, ack, self.provider.verifier(), 2000, authority=self.authority.verifier())
        with self.assertRaises((ReceiptError, EffectV3Error)):
            verify_fence_ack(replace(fence, fencing_token=10), update, ack, self.provider.verifier(), 2000, authority=self.authority.verifier())

    def test_wrong_fence_authority_and_validity_reject(self):
        fence = ObjectFenceV3.from_context(self.proposal.context, 9)
        for signer, expiry in ((self.provider, 1100), (self.authority, 1101)):
            update = sign_receipt(signer, purpose=2, subject=fence.digest, provider=fence.provider_id,
                epoch=3, policy=7, fence=9, issued_at=1000, expires_at=expiry)
            with self.assertRaises((EffectV3Error, ReceiptError)):
                verify_fence_update(fence, update, self.authority.verifier(), 1050)

    def test_effect_verification_authenticates_the_admission_issuer(self):
        p = self.proposal
        forged = fixture_admission(p, self.provider)
        record = sign_receipt(self.provider, purpose=4, subject=effect_subject(p, forged, 1050),
            provider=p.context.provider_id, epoch=3, policy=7, fence=9, issued_at=1050, expires_at=1100)
        with self.assertRaises((EffectV3Error, ReceiptError)):
            verify_effect(p, forged, record, self.provider.verifier(), 2000, authority=self.authority.verifier())

    def test_fence_ack_verification_authenticates_the_update_issuer(self):
        fence = ObjectFenceV3.from_context(self.proposal.context, 9)
        forged = sign_receipt(self.provider, purpose=2, subject=fence.digest,
            provider=fence.provider_id, epoch=3, policy=7, fence=9, issued_at=1000, expires_at=1100)
        ack = sign_receipt(self.provider, purpose=3, subject=fence_ack_subject(fence, forged),
            provider=fence.provider_id, epoch=3, policy=7, fence=9, issued_at=1050, expires_at=1100)
        with self.assertRaises((EffectV3Error, ReceiptError)):
            verify_fence_ack(fence, forged, ack, self.provider.verifier(), 2000, authority=self.authority.verifier())


if __name__ == '__main__': unittest.main()
