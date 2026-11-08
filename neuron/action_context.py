"""Canonical action context v1. No authority is created by constructing this value.

Wire format: domain bytes followed by 21 fixed 32-byte ABI words. Integers are
unsigned big endian. No floats, implicit text conversion, JSON or SHA3 aliases.
"""
from dataclasses import dataclass, fields
import hashlib

DOMAIN = b"VAMS:ACTION-CONTEXT:v1\0"
HASH_FIELDS = ('actor_root','provider_id','runtime_id','model_id','host_domain',
    'workflow_id','intent_id','action_hash','input_hash','policy_root','target','nonce','budget_unit')
INT_FIELDS = ('root_scheme','authority_epoch','policy_version','capabilities','budget',
    'issued_at','expires_at','chain_id')
WIRE_FIELDS = HASH_FIELDS + INT_FIELDS
UINT256_MAX = (1 << 256) - 1

class ActionContextError(ValueError):pass

@dataclass(frozen=True)
class ActionContextV1:
    actor_root: bytes
    provider_id: bytes
    runtime_id: bytes
    model_id: bytes
    host_domain: bytes
    workflow_id: bytes
    intent_id: bytes
    action_hash: bytes
    input_hash: bytes
    policy_root: bytes
    target: bytes
    nonce: bytes
    budget_unit: bytes
    root_scheme: int
    authority_epoch: int
    policy_version: int
    capabilities: int
    budget: int
    issued_at: int
    expires_at: int
    chain_id: int

    def validate(self):
        for name in HASH_FIELDS:
            value=getattr(self,name)
            if type(value) is not bytes or len(value)!=32:
                raise ActionContextError('invalid '+name)
            if name!='model_id' and value==b'\0'*32:
                raise ActionContextError('missing '+name)
        for name in INT_FIELDS:
            value=getattr(self,name)
            if type(value) is not int or not 0 <= value <= UINT256_MAX:
                raise ActionContextError('invalid '+name)
        if self.root_scheme not in (1,2):raise ActionContextError('unsupported root scheme')
        prefix=12 if self.root_scheme==1 else 4
        if self.actor_root[:prefix]!=b'\0'*prefix:raise ActionContextError('noncanonical actor root')
        if not all((self.authority_epoch,self.policy_version,self.capabilities,self.chain_id)):
            raise ActionContextError('missing authority/domain')
        if self.expires_at<=self.issued_at:raise ActionContextError('invalid validity interval')

    def canonical_bytes(self):
        self.validate()
        return DOMAIN+b''.join(getattr(self,n) for n in HASH_FIELDS)+b''.join(
            getattr(self,n).to_bytes(32,'big') for n in INT_FIELDS)

    @property
    def digest(self):return hashlib.sha256(self.canonical_bytes()).digest()

    @property
    def workload_hash(self):
        return hashlib.sha256(self.runtime_id+self.model_id+self.workflow_id+self.input_hash).digest()

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or not raw.startswith(DOMAIN) or len(raw)!=len(DOMAIN)+32*len(WIRE_FIELDS):
            raise ActionContextError('invalid action encoding')
        words=[raw[len(DOMAIN)+32*i:len(DOMAIN)+32*(i+1)] for i in range(len(WIRE_FIELDS))]
        value=cls(**{n:words[i] if n in HASH_FIELDS else int.from_bytes(words[i],'big') for i,n in enumerate(WIRE_FIELDS)})
        value.validate()
        return value
