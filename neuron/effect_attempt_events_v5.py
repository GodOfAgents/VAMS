"""Bounded append-only event encoding, not evidence or a dispatch permission.

The storage consumer must independently authenticate funding, current authority,
completion and absence. A well-formed hash chain cannot make a caller's claim true.
"""
from dataclasses import dataclass

from neuron.effect_protocol_v3 import EffectV3Error, commitment, hash32, integer, word

EVENT_DOMAIN = b'VAMS:AUTHORITY-ATTEMPT-EVENT:v5\0'
UNKNOWN_DOMAIN = b'VAMS:OUTCOME-UNKNOWN:v5\0'
RESERVED_DOMAIN = b'VAMS:RESERVED-ATTEMPT:v5\0'
MAX_EVENT_BYTES = 65_536
MAX_EVENTS = 8
KINDS = {'reserved':1,'funding_unknown':2,'funded':3,'dispatched':4,
    'indeterminate':5,'completed':6,'absent':7}
NEXT = {
    # Authenticated completion is a retained fact even when a local funding
    # observation was lost. It grants no new effect, payment or dispatch right.
    'reserved':frozenset(('funding_unknown','funded','completed','absent')),
    'funding_unknown':frozenset(('funded','completed','absent')),
    'funded':frozenset(('dispatched','indeterminate','completed','absent')),
    'dispatched':frozenset(('indeterminate','completed','absent')),
    'indeterminate':frozenset(('completed','absent')),
    'completed':frozenset(),
    'absent':frozenset(),
}


def reserved_payload(link_digest, scope_generation_id):
    # The separately authenticated canonical scope is not authority_context_id.
    return RESERVED_DOMAIN+hash32(link_digest)+hash32(scope_generation_id)


def unknown_payload(attempt_id, *, funding):
    if type(funding) is not bool:
        raise EffectV3Error('explicit unknown outcome phase required')
    # No driver exception, SQLSTATE, endpoint, private ID or raw diagnostic.
    return UNKNOWN_DOMAIN+hash32(attempt_id)+word(1 if funding else 2)


@dataclass(frozen=True)
class AttemptEventV5:
    attempt_id:bytes
    sequence:int
    previous_event:bytes|None
    kind:str
    payload:bytes

    def validate(self):
        hash32(self.attempt_id)
        integer(self.sequence,positive=True)
        if self.sequence>MAX_EVENTS or type(self.kind) is not str or self.kind not in KINDS:
            raise EffectV3Error('invalid bounded attempt event')
        if type(self.payload) is not bytes or not 0<len(self.payload)<=MAX_EVENT_BYTES:
            raise EffectV3Error('invalid bounded event payload')
        if (self.sequence==1)!=(self.previous_event is None):
            raise EffectV3Error('event predecessor does not match sequence')
        if self.previous_event is not None:hash32(self.previous_event)
        if (self.sequence==1)!=(self.kind=='reserved'):
            raise EffectV3Error('only initial event may reserve this attempt')
        if self.kind in ('funding_unknown','indeterminate') and self.payload!=unknown_payload(
                self.attempt_id,funding=self.kind=='funding_unknown'):
            raise EffectV3Error('unknown outcome payload must be a fixed phase marker')

    @property
    def payload_digest(self):
        import hashlib
        self.validate()
        return hashlib.sha256(self.payload).digest()

    def canonical_bytes(self):
        self.validate()
        return EVENT_DOMAIN+self.attempt_id+word(self.sequence)+(self.previous_event or b'\0'*32)+\
            word(KINDS[self.kind])+self.payload_digest

    @property
    def digest(self):
        import hashlib
        return hashlib.sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls,raw,payload):
        if type(raw) is not bytes or len(raw)!=len(EVENT_DOMAIN)+160 or not raw.startswith(EVENT_DOMAIN):
            raise EffectV3Error('unsupported attempt event encoding')
        body=raw[len(EVENT_DOMAIN):]
        fields=[body[i:i+32] for i in range(0,160,32)]
        code=int.from_bytes(fields[3],'big')
        names={number:name for name,number in KINDS.items()}
        if code not in names:raise EffectV3Error('unsupported attempt event kind')
        event=cls(fields[0],int.from_bytes(fields[1],'big'),
            None if fields[2]==b'\0'*32 else fields[2],names[code],payload)
        if event.canonical_bytes()!=raw:
            raise EffectV3Error('event payload/hash or canonical bytes mismatch')
        return event

    def follows(self,previous):
        self.validate()
        if type(previous) is not AttemptEventV5:
            raise EffectV3Error('typed retained previous event required')
        previous.validate()
        if (self.attempt_id!=previous.attempt_id or self.sequence!=previous.sequence+1 or
                self.previous_event!=previous.digest or self.kind not in NEXT[previous.kind]):
            raise EffectV3Error('invalid attempt event transition or retained lineage')


def next_event(previous,kind,payload):
    if type(previous) is not AttemptEventV5:
        raise EffectV3Error('typed retained event required')
    event=AttemptEventV5(previous.attempt_id,previous.sequence+1,previous.digest,kind,payload)
    event.follows(previous)
    return event
