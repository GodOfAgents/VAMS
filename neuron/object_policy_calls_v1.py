"""Typed calldata for two RestrictedTestnetPolicyV1 read-only methods.

Construction authenticates nothing. No RPC response is consumed, no policy
backend is implemented and no effect/credential route is enabled. In particular,
the grant's custom signed bytes are NOT the Solidity function-call ABI.
"""
from dataclasses import dataclass,field

from neuron.action_context import DOMAIN as ACTION_DOMAIN
from neuron.effect_authority_v3 import ObjectAuthorityScopeV3
from neuron.effect_protocol_v3 import ObjectEffectV3
from neuron.effect_provider_v3 import ObjectProviderIdentityV3
from neuron.object_grant_v1 import (
    GovernedObjectGrantV1, ObjectGrantDomainV1, ObjectGrantError,
    HASH_FIELDS, INT_FIELDS, membership_root,
)
from neuron.signed_receipts import ORDER

# Pinned solc 0.8.24 methodIdentifiers, independently checked with abi.encodeCall.
OBJECT_SELECTOR=bytes.fromhex('c76d3f1f')
SCOPE_SELECTOR=bytes.fromhex('c6a79e78')


def _word(value):
    if type(value) is not int or not 0<=value<1<<256:
        raise ObjectGrantError('ABI uint256 required')
    return value.to_bytes(32,'big')


def _array(values):
    return _word(len(values))+b''.join(values)


def _tuple(*parts):
    """Only internal, already validated (dynamic, encoded value) segments."""
    offset=sum(32 if dynamic else len(value) for dynamic,value in parts)
    head=[]; tail=[]
    for dynamic,value in parts:
        if dynamic:
            head.append(_word(offset)); tail.append(value); offset+=len(value)
        else:head.append(value)
    return b''.join(head+tail)


@dataclass(frozen=True)
class ObjectGrantWitnessV1:
    grant:GovernedObjectGrantV1
    consent:bytes=field(repr=False)
    siblings:tuple[bytes,...]
    index:int

    def _abi(self,domain):
        if type(self.grant) is not GovernedObjectGrantV1:
            raise ObjectGrantError('typed governed grant required')
        g=self.grant; g.validate()
        # Structural signature validation is NOT actor-consent verification.
        if type(self.consent) is not bytes or len(self.consent)!=65:
            raise ObjectGrantError('canonical 65-byte EVM consent required')
        r=int.from_bytes(self.consent[:32],'big'); s=int.from_bytes(self.consent[32:64],'big')
        if not 0<r<ORDER or not 0<s<=ORDER//2 or self.consent[64] not in (27,28):
            raise ObjectGrantError('canonical low-S EVM consent required')
        # Validates positioned proof shape; its result is not accepted as policy.
        membership_root(g.leaf(domain),self.siblings,self.index)
        grant=_tuple((False,b''.join(getattr(g,n) for n in HASH_FIELDS)),
            (False,b''.join(_word(getattr(g,n)) for n in INT_FIELDS)),
            (True,_array(g.resources)))
        consent=_word(len(self.consent))+self.consent+b'\0'*31
        return _tuple((True,grant),(True,consent),(True,_array(self.siblings)),(False,_word(self.index)))


@dataclass(frozen=True)
class ObjectPolicyReadCallV1:
    """Unsigned call description. Fields/bytes do not authenticate a host."""
    domain:ObjectGrantDomainV1
    calldata:bytes=field(repr=False)


@dataclass(frozen=True)
class ObjectPolicyCallsV1:
    domain:ObjectGrantDomainV1
    identity:ObjectProviderIdentityV3

    def __post_init__(self):
        self._configuration()

    def _configuration(self):
        if type(self.domain) is not ObjectGrantDomainV1 or type(self.identity) is not ObjectProviderIdentityV3:
            raise ObjectGrantError('typed host domain and configured provider identity required')
        self.domain.canonical_bytes(); self.identity.digest
        if self.domain.chain_id!=self.identity.chain_id or self.domain.host_domain!=self.identity.host_domain:
            raise ObjectGrantError('host domain differs from configured identity')

    def _witness(self,context,witness):
        self._configuration()
        if type(witness) is not ObjectGrantWitnessV1:
            raise ObjectGrantError('typed grant witness required')
        encoded=witness._abi(self.domain)
        i=self.identity; g=witness.grant
        if (context.provider_id!=i.provider_id or context.runtime_id!=i.runtime_id or
                context.target!=i.target or context.chain_id!=i.chain_id or
                context.host_domain!=i.host_domain or context.budget_unit!=self.domain.budget_unit):
            raise ObjectGrantError('context differs from configured runtime domain')
        # Expected issuer IDs are always from configuration, never from the witness.
        if g.authority_issuer!=i.authority.issuer_id or g.provider_issuer!=i.provider.issuer_id:
            raise ObjectGrantError('grant issuers differ from configured identity')
        if context.root_scheme!=1:
            raise ObjectGrantError('object consent requires EVM root identity')
        return encoded,i.authority.issuer_id+i.provider.issuer_id

    def object_call(self,proposal,witness):
        if type(proposal) is not ObjectEffectV3:
            raise ObjectGrantError('typed object proposal required')
        proposal.validate()
        w,issuers=self._witness(proposal.context,witness)
        p=proposal.context.canonical_bytes()[len(ACTION_DOMAIN):]+proposal.resource_id+_word(proposal.cost_units)+_word(proposal.fencing_token)
        return ObjectPolicyReadCallV1(self.domain,OBJECT_SELECTOR+_tuple((False,p),(True,w),(False,issuers)))

    def scope_call(self,scope,witness):
        if type(scope) is not ObjectAuthorityScopeV3:
            raise ObjectGrantError('typed object authority scope required')
        scope.validate()
        w,issuers=self._witness(scope.template,witness)
        s=_tuple((False,scope.template.canonical_bytes()[len(ACTION_DOMAIN):]),
            (True,_array(scope.resources)),(False,b''.join(_word(v) for v in
                (scope.budget_limit,scope.max_action_cost,scope.fencing_token))))
        return ObjectPolicyReadCallV1(self.domain,SCOPE_SELECTOR+_tuple((True,s),(True,w),(False,issuers)))
