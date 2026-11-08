"""Canonical history/state tests; no outcome is authenticated by these events."""
from dataclasses import replace
import hashlib
import unittest
from neuron.effect_protocol_v3 import EffectV3Error
from neuron.effect_attempt_events_v5 import (
    AttemptEventV5,EVENT_DOMAIN,MAX_EVENT_BYTES,next_event,reserved_payload,unknown_payload,
)


def h(value):return hashlib.sha256(value).digest()


class AttemptEventV5Test(unittest.TestCase):
    def setUp(self):
        self.attempt=h(b'public-attempt-fixture')
        self.reserved=AttemptEventV5(self.attempt,1,None,'reserved',
            reserved_payload(h(b'link'),h(b'canonical-lease-generation')))

    def funded(self):return next_event(self.reserved,'funded',b'fixture funding facts, not authentic proof')

    def test_roundtrip_binds_payload_and_exact_canonical_bytes(self):
        event=self.reserved
        self.assertEqual(AttemptEventV5.from_bytes(event.canonical_bytes(),event.payload),event)
        with self.assertRaises(EffectV3Error):AttemptEventV5.from_bytes(event.canonical_bytes(),b'altered')
        with self.assertRaises(EffectV3Error):AttemptEventV5.from_bytes(event.canonical_bytes()+b'\0',event.payload)

    def test_ordered_unknown_funding_dispatch_and_completion_keeps_original_events(self):
        unknown=next_event(self.reserved,'funding_unknown',unknown_payload(self.attempt,funding=True))
        funded=next_event(unknown,'funded',b'fixture current native facts')
        dispatched=next_event(funded,'dispatched',b'fixture dispatch claim')
        uncertain=next_event(dispatched,'indeterminate',unknown_payload(self.attempt,funding=False))
        completed=next_event(uncertain,'completed',b'fixture receipt')
        self.assertEqual(completed.sequence,6)
        self.assertEqual(self.reserved.sequence,1)
        self.assertEqual(dispatched.previous_event,funded.digest)

    def test_terminal_completed_and_absent_never_reopen(self):
        for terminal in ('completed','absent'):
            event=next_event(self.funded(),terminal,b'fixture terminal facts')
            for kind in ('reserved','funded','dispatched','completed','absent'):
                with self.subTest(terminal=terminal,kind=kind),self.assertRaises(EffectV3Error):
                    next_event(event,kind,b'cannot replace terminal history')

    def test_unknown_outcome_cannot_dispatch_without_verified_funding_step(self):
        event=next_event(self.reserved,'funding_unknown',unknown_payload(self.attempt,funding=True))
        with self.assertRaises(EffectV3Error):next_event(event,'dispatched',b'unsupported')
        with self.assertRaises(EffectV3Error):next_event(self.reserved,'dispatched',b'unsupported')
        # A completion-shaped record is allowed structurally for reconciliation;
        # the journal must still authenticate its exact provider signature.
        for predecessor in (self.reserved,event):
            self.assertEqual(next_event(predecessor,'completed',b'unverified claim').kind,'completed')

    def test_old_writer_cannot_redispatch_indeterminate_effect(self):
        event=next_event(self.funded(),'dispatched',b'fixture claim')
        event=next_event(event,'indeterminate',unknown_payload(self.attempt,funding=False))
        with self.assertRaises(EffectV3Error):next_event(event,'dispatched',b'duplicate effect')
        with self.assertRaises(EffectV3Error):next_event(event,'funded',b'stale observation')

    def test_previous_attempt_event_sequence_and_digest_must_match(self):
        event=self.funded()
        for change in ({'attempt_id':h(b'other')},{'sequence':3},{'previous_event':h(b'wrong')}):
            with self.subTest(change=change),self.assertRaises(EffectV3Error):replace(event,**change).follows(self.reserved)

    def test_unknown_marker_has_fixed_phase_and_no_raw_error_payload(self):
        for kind,funding in (('funding_unknown',True),('indeterminate',False)):
            raw=unknown_payload(self.attempt,funding=funding)
            event=AttemptEventV5(self.attempt,2,self.reserved.digest,kind,raw)
            event.validate()
            with self.assertRaises(EffectV3Error):replace(event,payload=b'raw driver error').validate()
            with self.assertRaises(EffectV3Error):replace(event,payload=unknown_payload(self.attempt,funding=not funding)).validate()

    def test_bounds_types_and_initial_reservation_reject(self):
        for change in ({'sequence':True},{'sequence':0},{'sequence':9},{'kind':'unknown'},
                {'payload':b''},{'payload':b'x'*(MAX_EVENT_BYTES+1)},{'previous_event':h(b'wrong')},
                {'kind':'funded'}):
            with self.subTest(change=change),self.assertRaises(EffectV3Error):replace(self.reserved,**change).validate()
        with self.assertRaises(EffectV3Error):unknown_payload(self.attempt,funding=1)

    def test_malformed_domains_codes_and_predecessor_encodings_reject(self):
        raw=self.reserved.canonical_bytes()
        with self.assertRaises(EffectV3Error):AttemptEventV5.from_bytes(b'X'+raw[1:],self.reserved.payload)
        body=bytearray(raw);start=len(EVENT_DOMAIN)+96;body[start:start+32]=(99).to_bytes(32,'big')
        with self.assertRaises(EffectV3Error):AttemptEventV5.from_bytes(bytes(body),self.reserved.payload)

    def test_event_hash_is_commitment_not_outcome_evidence(self):
        # A caller can encode this claim. The future storage consumer MUST verify
        # actual funding and provider evidence before accepting the transition.
        event=next_event(self.funded(),'completed',b'not a real provider signature')
        self.assertEqual(len(event.digest),32)
        self.assertEqual(event.kind,'completed')


if __name__=='__main__':unittest.main()
