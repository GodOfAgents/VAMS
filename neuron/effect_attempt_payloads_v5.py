"""Exact retained absence payload; old V3 receipt/fence encodings stay unchanged."""
from dataclasses import dataclass
from neuron.effect_protocol_v3 import (
    ObjectFenceV3,SignedEffectReceiptV3,EffectV3Error,FENCE_DOMAIN,SIGNED_DOMAIN,RECEIPT_SIZE,
)
from neuron.effect_attempts_v5 import authenticate_fenced_absence_v5

ABSENCE_DOMAIN=b'VAMS:RETAINED-FENCED-ABSENCE:v5\0'
FENCE_SIZE=len(FENCE_DOMAIN)+11*32
SIGNED_SIZE=len(SIGNED_DOMAIN)+RECEIPT_SIZE+64
ABSENCE_SIZE=len(ABSENCE_DOMAIN)+FENCE_SIZE+3*SIGNED_SIZE


@dataclass(frozen=True)
class FencedAbsencePayloadV5:
    fence:ObjectFenceV3
    update:SignedEffectReceiptV3
    acknowledgement:SignedEffectReceiptV3
    absence:SignedEffectReceiptV3

    def canonical_bytes(self):
        if type(self.fence) is not ObjectFenceV3 or any(type(r) is not SignedEffectReceiptV3
                for r in (self.update,self.acknowledgement,self.absence)):
            raise EffectV3Error('typed signed V3 fencing facts required')
        return ABSENCE_DOMAIN+self.fence.canonical_bytes()+self.update.canonical_bytes()+\
            self.acknowledgement.canonical_bytes()+self.absence.canonical_bytes()

    @classmethod
    def from_bytes(cls,raw):
        if type(raw) is not bytes or len(raw)!=ABSENCE_SIZE or not raw.startswith(ABSENCE_DOMAIN):
            raise EffectV3Error('unsupported bounded absence payload encoding')
        offset=len(ABSENCE_DOMAIN)
        fence=ObjectFenceV3.from_bytes(raw[offset:offset+FENCE_SIZE]);offset+=FENCE_SIZE
        receipts=[]
        for _ in range(3):
            receipts.append(SignedEffectReceiptV3.from_bytes(raw[offset:offset+SIGNED_SIZE]));offset+=SIGNED_SIZE
        result=cls(fence,*receipts)
        if result.canonical_bytes()!=raw:raise EffectV3Error('noncanonical absence payload')
        return result

    def authenticate(self,proposal,admission,*,authority,provider,now):
        # Parsing/hash chaining alone grants neither a refund nor another attempt.
        # The authority must additionally resolve exact native funding state.
        self.canonical_bytes()
        return authenticate_fenced_absence_v5(proposal,admission,self.fence,self.update,
            self.acknowledgement,self.absence,authority=authority,provider=provider,now=now)
