"""Governed object-grant bytes and membership; not chain, custody or consent proof.

Consent signing belongs to a qualified actor/credential boundary. This codec
neither loads keys nor treats a grant witness as authenticated current policy.
"""
from dataclasses import dataclass
import hashlib

DOMAIN=b'VAMS:OBJECT-GRANT:v1\0'
LEAF_DOMAIN=b'VAMS:OBJECT-GRANT-LEAF:v1\0'
NODE_DOMAIN=b'VAMS:OBJECT-GRANT-NODE:v1\0'
MAX_INTEGER=(1<<63)-1
HASH_FIELDS=('actor_root','provider_id','runtime_id','workflow_id','intent_id','target',
             'authority_issuer','provider_issuer','nonce')
INT_FIELDS=('budget_limit','max_action_cost','max_scope_lifetime','valid_after','valid_until')

class ObjectGrantError(ValueError):pass

def _hash(value):
    if type(value) is not bytes or len(value)!=32 or value==b'\0'*32:
        raise ObjectGrantError('nonzero bytes32 required')
    return value

def _integer(value,positive=False):
    if type(value) is not int or not int(positive)<=value<=MAX_INTEGER:
        raise ObjectGrantError('bounded integer required')
    return value

def _word(value):return _integer(value).to_bytes(32,'big')

@dataclass(frozen=True)
class ObjectGrantDomainV1:
    policy_contract:bytes
    chain_id:int
    host_domain:bytes
    budget_unit:bytes

    def canonical_bytes(self):
        _hash(self.policy_contract);_hash(self.host_domain);_hash(self.budget_unit)
        _integer(self.chain_id,True)
        if self.policy_contract[:12]!=b'\0'*12:raise ObjectGrantError('canonical EVM policy address required')
        return self.policy_contract+_word(self.chain_id)+self.host_domain+self.budget_unit

@dataclass(frozen=True)
class GovernedObjectGrantV1:
    actor_root:bytes
    provider_id:bytes
    runtime_id:bytes
    workflow_id:bytes
    intent_id:bytes
    target:bytes
    authority_issuer:bytes
    provider_issuer:bytes
    nonce:bytes
    budget_limit:int
    max_action_cost:int
    max_scope_lifetime:int
    valid_after:int
    valid_until:int
    resources:tuple[bytes,...]

    def validate(self):
        for name in HASH_FIELDS:_hash(getattr(self,name))
        for name in INT_FIELDS:_integer(getattr(self,name))
        if self.actor_root[:12]!=b'\0'*12:raise ObjectGrantError('canonical EVM actor root required')
        if self.authority_issuer==self.provider_issuer:raise ObjectGrantError('issuer roles must differ')
        if not 0<self.budget_limit or self.max_action_cost>self.budget_limit:
            raise ObjectGrantError('invalid budget bounds')
        if not 0<self.max_scope_lifetime<=600 or not 0<self.valid_until-self.valid_after<=86400:
            raise ObjectGrantError('invalid grant lifetime')
        if type(self.resources) is not tuple or not 1<=len(self.resources)<=64:
            raise ObjectGrantError('bounded resource tuple required')
        for value in self.resources:_hash(value)
        if tuple(sorted(set(self.resources)))!=self.resources:raise ObjectGrantError('resources must be unique and sorted')

    def canonical_bytes(self,domain):
        self.validate()
        if type(domain) is not ObjectGrantDomainV1:raise ObjectGrantError('explicit host policy domain required')
        return (DOMAIN+domain.canonical_bytes()+b''.join(getattr(self,n) for n in HASH_FIELDS)+
                b''.join(_word(getattr(self,n)) for n in INT_FIELDS)+_word(len(self.resources))+b''.join(self.resources))

    def digest(self,domain):return hashlib.sha256(self.canonical_bytes(domain)).digest()
    def leaf(self,domain):return hashlib.sha256(LEAF_DOMAIN+self.digest(domain)).digest()

def membership_root(leaf,siblings,index):
    _hash(leaf)
    if type(siblings) is not tuple or len(siblings)>32 or type(index) is not int or not 0<=index<(1<<len(siblings)):
        raise ObjectGrantError('bounded positioned proof required')
    value=leaf
    for sibling in siblings:
        _hash(sibling)
        left,right=(sibling,value) if index&1 else (value,sibling)
        value=hashlib.sha256(NODE_DOMAIN+left+right).digest();index>>=1
    return value
