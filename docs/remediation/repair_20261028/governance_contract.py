"""Independent byte/value oracle for the governance-v2 candidate.

No Aiken, signatures, RPC, ledger or execution authority. This is an executable
specification aid; passing it is not native validator or live qualification.
"""
from dataclasses import dataclass, replace
import hashlib
import math

DELAY_MS = 172_800_000
LIFETIME_MS = 604_800_000
MAX_LOCK = 1_000_000_000
MAX_VOTERS = 8
DOMAINS = {name: ('VAMS/' + name + '/v2\0').encode('ascii') for name in
           ('authority', 'proposal', 'receipt', 'proposal-state', 'intent')}


class ContractError(ValueError):
    pass


def fixed(value, length):
    if type(value) is not bytes or len(value) != length:
        raise ContractError('wrong byte width')
    return value


def uint(value, size):
    if type(value) is not int or not 0 <= value < 1 << (8 * size):
        raise ContractError('invalid unsigned integer')
    return value.to_bytes(size, 'big')


def domain(value):
    if type(value) is not bytes or not 1 <= len(value) <= 32:
        raise ContractError('invalid target domain')
    return uint(len(value), 1) + value


def flag(value):
    if type(value) is not bool:
        raise ContractError('boolean required')
    return b'\1' if value else b'\0'


def digest(preimage):
    return hashlib.blake2b(preimage, digest_size=32).digest()


@dataclass(frozen=True)
class Config:
    network_id: int
    policy_epoch: int
    seed_tx_id: bytes
    seed_index: int
    authority_policy_id: bytes
    governor_script_hash: bytes
    timelock_script_hash: bytes
    proposal_policy_id: bytes
    receipt_policy_id: bytes
    intent_policy_id: bytes
    vams_policy_id: bytes
    vams_asset_name: bytes
    members: tuple[bytes, ...]
    authority_state_lovelace: int
    proposal_base_lovelace: int
    per_voter_refund_lovelace: int
    next_proposal_nonce: int
    next_intent_nonce: int
    target_domains: tuple[bytes, ...]

    def validate(self):
        uint(self.network_id, 1)
        if self.network_id > 15:
            raise ContractError('network out of range')
        uint(self.policy_epoch, 4)
        fixed(self.seed_tx_id, 32)
        uint(self.seed_index, 4)
        policies = (self.authority_policy_id, self.proposal_policy_id,
                    self.receipt_policy_id, self.intent_policy_id, self.vams_policy_id)
        for item in policies + (self.governor_script_hash, self.timelock_script_hash):
            fixed(item, 28)
        if len(set(policies)) != 5 or len({self.authority_policy_id, self.governor_script_hash, self.timelock_script_hash}) != 3:
            raise ContractError('ambiguous policy/script identity')
        if type(self.vams_asset_name) is not bytes or len(self.vams_asset_name) > 32:
            raise ContractError('invalid VAMS name')
        if type(self.members) is not tuple or len(self.members) != 5 or len(set(self.members)) != 5:
            raise ContractError('five unique members required')
        for member in self.members:
            fixed(member, 28)
        for value in (self.authority_state_lovelace, self.proposal_base_lovelace, self.per_voter_refund_lovelace):
            uint(value, 8)
            if not value:
                raise ContractError('positive state/refund amounts required')
        uint(self.next_proposal_nonce, 8)
        uint(self.next_intent_nonce, 8)
        uint(self.proposal_base_lovelace + MAX_VOTERS * self.per_voter_refund_lovelace, 8)
        if type(self.target_domains) is not tuple or not 1 <= len(self.target_domains) <= 4 or len(set(self.target_domains)) != len(self.target_domains):
            raise ContractError('invalid domain list')
        for item in self.target_domains:
            domain(item)


@dataclass(frozen=True)
class Lock:
    voter: bytes
    amount: int
    support: bool
    weight: int
    receipt: bytes


@dataclass(frozen=True)
class Proposal:
    nonce: int
    proposer: bytes
    description_hash: bytes
    action_hash: bytes
    payload_hash: bytes
    target_domain: bytes
    epoch: int
    quorum: int
    deadline: int
    asset: bytes = bytes(32)
    passed: bool = False
    yes: int = 0
    no: int = 0
    locks: tuple[Lock, ...] = ()


@dataclass(frozen=True)
class Intent:
    proposal_id: bytes
    proposal_asset: bytes
    action_hash: bytes
    payload_hash: bytes
    target_domain: bytes
    epoch: int
    nonce: int
    queue_time: int
    execute_after: int
    lifetime: int
    proposer: bytes


def authority_preimage(c):
    c.validate()
    return (DOMAINS['authority'] + c.authority_policy_id + c.seed_tx_id + uint(c.seed_index, 4) +
            uint(c.network_id, 1) + uint(c.policy_epoch, 4))


def proposal_preimage(c, p):
    c.validate()
    if p.epoch != c.policy_epoch or p.target_domain not in c.target_domains or not 0 < p.quorum <= MAX_VOTERS * math.isqrt(MAX_LOCK):
        raise ContractError('invalid proposal scope')
    return (DOMAINS['proposal'] + c.authority_policy_id + digest(authority_preimage(c)) + c.proposal_policy_id +
            uint(p.epoch, 4) + uint(p.nonce, 8) + fixed(p.proposer, 28) + fixed(p.description_hash, 32) +
            fixed(p.action_hash, 32) + fixed(p.payload_hash, 32) + domain(p.target_domain) +
            uint(p.quorum, 8) + uint(p.deadline, 8))


def receipt_preimage(c, p, lock, index):
    c.validate()
    if type(lock.amount) is not int or not 0 < lock.amount <= MAX_LOCK or type(index) is not int or not 0 <= index < MAX_VOTERS:
        raise ContractError('invalid lock/index')
    return (DOMAINS['receipt'] + c.receipt_policy_id + c.proposal_policy_id + fixed(p.asset, 32) +
            fixed(lock.voter, 28) + uint(lock.amount, 8) + flag(lock.support) + uint(index, 4))


def proposal_state_preimage(p):
    if type(p.locks) is not tuple or len(p.locks) > MAX_VOTERS:
        raise ContractError('too many locks')
    out = (DOMAINS['proposal-state'] + fixed(p.asset, 32) + flag(p.passed) + uint(p.yes, 8) + uint(p.no, 8) + uint(len(p.locks), 1))
    for lock in p.locks:
        out += fixed(lock.voter, 28) + uint(lock.amount, 8) + flag(lock.support) + uint(lock.weight, 8) + fixed(lock.receipt, 32)
    return out


def intent_preimage(c, i):
    c.validate()
    if (i.epoch != c.policy_epoch or i.target_domain not in c.target_domains or
        i.execute_after != i.queue_time + DELAY_MS or i.lifetime != LIFETIME_MS):
        raise ContractError('invalid intent scope/delay')
    uint(i.execute_after + i.lifetime, 8)
    return (DOMAINS['intent'] + c.intent_policy_id + c.proposal_policy_id + fixed(i.proposal_asset, 32) +
            fixed(i.proposal_id, 32) + fixed(i.action_hash, 32) + fixed(i.payload_hash, 32) + domain(i.target_domain) +
            uint(i.epoch, 4) + uint(i.nonce, 8) + uint(i.queue_time, 8) + fixed(i.proposer, 28))


def add_lock(c, p, voter, amount, support):
    if p.passed or len(p.locks) >= MAX_VOTERS or any(lock.voter == voter for lock in p.locks):
        raise ContractError('duplicate/terminal/full proposal')
    if type(amount) is not int or not 0 < amount <= MAX_LOCK:
        raise ContractError('invalid voting amount')
    flag(support)
    added = Lock(fixed(voter, 28), amount, support, math.isqrt(amount), bytes(32))
    added = replace(added, receipt=digest(receipt_preimage(c, p, added, len(p.locks))))
    return replace(p, locks=p.locks + (added,), yes=p.yes + (added.weight if support else 0),
                   no=p.no + (0 if support else added.weight))


def queue_intent(c, p, time):
    if not p.passed or p.yes + p.no < p.quorum or p.yes <= p.no:
        raise ContractError('proposal has not passed')
    uint(time, 8)
    if time < p.deadline:
        raise ContractError('premature queue')
    return Intent(digest(proposal_state_preimage(p)), p.asset, p.action_hash, p.payload_hash,
                  p.target_domain, c.policy_epoch, c.next_intent_nonce, time, time + DELAY_MS,
                  LIFETIME_MS, p.proposer)


@dataclass(frozen=True)
class Value:
    lovelace: int
    tokens: tuple[tuple[bytes, bytes, int], ...] = ()

    def amounts(self):
        uint(self.lovelace, 8)
        result = {(b'', b''): self.lovelace}
        for policy, name, quantity in self.tokens:
            fixed(policy, 28)
            if type(name) is not bytes or len(name) > 32 or type(quantity) is not int or quantity <= 0:
                raise ContractError('invalid held asset')
            key = (policy, name)
            if key in result:
                raise ContractError('duplicate asset')
            result[key] = quantity
        return result


def proposal_value(c, p):
    tokens = [(c.proposal_policy_id, p.asset, 1)]
    total = sum(lock.amount for lock in p.locks)
    if total:
        tokens.append((c.vams_policy_id, c.vams_asset_name, total))
    tokens += [(c.receipt_policy_id, lock.receipt, 1) for lock in p.locks]
    return Value(c.proposal_base_lovelace + len(p.locks) * c.per_voter_refund_lovelace, tuple(tokens))


def refunds(c, p):
    return tuple(Value(c.per_voter_refund_lovelace, ((c.vams_policy_id, c.vams_asset_name, lock.amount),)) for lock in p.locks)


def conserves(inputs, outputs, minted, fee):
    """Arithmetic only, deliberately no claim of authority or ledger validity."""
    uint(fee, 8)
    balance = {}
    for direction, values in ((1, inputs), (-1, outputs)):
        for value in values:
            for key, amount in value.amounts().items():
                balance[key] = balance.get(key, 0) + direction * amount
    for policy, name, amount in minted:
        fixed(policy, 28)
        if type(name) is not bytes or len(name) > 32 or type(amount) is not int or not amount:
            raise ContractError('invalid mint')
        key = (policy, name)
        balance[key] = balance.get(key, 0) + amount
    balance[(b'', b'')] = balance.get((b'', b''), 0) - fee
    return all(amount == 0 for amount in balance.values())


def fixture():
    """Synthetic IDs, not deployed hashes, signers or admission parameters."""
    c = Config(0, 2, b'\x11' * 32, 7, b'\0' * 28, b'\x11' * 28, b'\x22' * 28,
               b'\x33' * 28, b'\x44' * 28, b'\x55' * 28, b'\x66' * 28, b'VAMS',
               tuple(bytes([i]) * 28 for i in range(1, 6)), 5_000_000, 3_000_000,
               1_000_000, 1, 0, (b'preprod/test',))
    p = Proposal(0, c.members[2], b'\x66' * 32, b'\x77' * 32, b'\x88' * 32,
                 c.target_domains[0], 2, 10, 2000)
    return c, replace(p, asset=digest(proposal_preimage(c, p)))
