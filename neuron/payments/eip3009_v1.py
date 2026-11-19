"""Pure local EOA ERC-3009 codec; no signing, submission or payment authority.

Standard authorization binds token transfer fields, not VAMS job/policy or an
allocation credit. Verification neither reserves funds nor proves token support,
nonce consumption, chain finality, exclusive facilitator or escrow funding.
"""
from dataclasses import dataclass

from eth_abi import encode
from eth_keys import keys
from eth_keys.constants import SECPK1_N
from web3 import Web3

from neuron.payments.intent_v1 import PaymentIntentV1, UINT256_MAX

DOMAIN_TYPE = 'EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)'
TRANSFER_TYPE = 'TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)'
RECEIVE_TYPE = 'ReceiveWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)'
DOMAIN_TYPEHASH = bytes(Web3.keccak(text=DOMAIN_TYPE))
TRANSFER_TYPEHASH = bytes(Web3.keccak(text=TRANSFER_TYPE))
RECEIVE_TYPEHASH = bytes(Web3.keccak(text=RECEIVE_TYPE))


class EIP3009Error(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise EIP3009Error(message)


def _uint(value, *, positive=False):
    _require(type(value) is int and int(positive) <= value <= UINT256_MAX, 'invalid uint256')
    return value


def _address(value):
    _require(type(value) is bytes and len(value) == 32 and value[:12] == bytes(12)
             and value[12:] != bytes(20), 'nonzero canonical padded EVM address required')
    return value


def _text(value):
    _require(type(value) is str and value.isprintable(), 'explicit printable domain text required')
    try:
        raw = value.encode('utf8')
    except UnicodeError:
        raise EIP3009Error('invalid domain UTF8') from None
    _require(1 <= len(raw) <= 128, 'domain text exceeds bound')
    return value


def _signature(value):
    _require(type(value) is bytes and len(value) == 65, '65-byte r/s/v signature required')
    r, s, v = int.from_bytes(value[:32], 'big'), int.from_bytes(value[32:64], 'big'), value[64]
    _require(1 <= r < SECPK1_N and 1 <= s <= SECPK1_N // 2 and v in (27, 28),
             'canonical low-S EOA signature with v27/28 required')
    return r, s, v


@dataclass(frozen=True)
class EIP3009DomainV1:
    name: str
    version: str
    chain_id: int
    token: bytes

    def __post_init__(self):
        _text(self.name); _text(self.version); _uint(self.chain_id, positive=True); _address(self.token)

    @property
    def separator(self):
        return bytes(Web3.keccak(encode(
            ['bytes32', 'bytes32', 'bytes32', 'uint256', 'address'],
            [DOMAIN_TYPEHASH, Web3.keccak(text=self.name), Web3.keccak(text=self.version),
             self.chain_id, self.token[12:]])))

    def typed_domain(self):
        return {'name': self.name, 'version': self.version, 'chainId': self.chain_id,
                'verifyingContract': '0x' + self.token[12:].hex()}


@dataclass(frozen=True)
class EIP3009AuthorizationV1:
    payer: bytes
    payee: bytes
    value: int
    valid_after: int
    valid_before: int
    nonce: bytes
    method: str

    def __post_init__(self):
        _address(self.payer); _address(self.payee); _uint(self.value)
        _uint(self.valid_after); _uint(self.valid_before)
        _require(self.valid_after < self.valid_before, 'empty authorization window')
        _require(type(self.nonce) is bytes and len(self.nonce) == 32, 'bytes32 nonce required')
        _require(type(self.method) is str and self.method in ('transfer', 'receive'),
                 'explicit transfer or receive method required')

    @property
    def typehash(self):
        return TRANSFER_TYPEHASH if self.method == 'transfer' else RECEIVE_TYPEHASH

    @property
    def struct_hash(self):
        return bytes(Web3.keccak(encode(
            ['bytes32', 'address', 'address', 'uint256', 'uint256', 'uint256', 'bytes32'],
            [self.typehash, self.payer[12:], self.payee[12:], self.value,
             self.valid_after, self.valid_before, self.nonce])))

    def digest(self, domain):
        _require(type(domain) is EIP3009DomainV1, 'exact EIP3009 domain required')
        return bytes(Web3.keccak(b'\x19\x01' + domain.separator + self.struct_hash))

    def typed_data(self, domain):
        _require(type(domain) is EIP3009DomainV1, 'exact EIP3009 domain required')
        primary = 'TransferWithAuthorization' if self.method == 'transfer' else 'ReceiveWithAuthorization'
        return {'types': {
            'EIP712Domain': [{'name': 'name', 'type': 'string'}, {'name': 'version', 'type': 'string'},
                            {'name': 'chainId', 'type': 'uint256'}, {'name': 'verifyingContract', 'type': 'address'}],
            primary: [{'name': 'from', 'type': 'address'}, {'name': 'to', 'type': 'address'},
                      {'name': 'value', 'type': 'uint256'}, {'name': 'validAfter', 'type': 'uint256'},
                      {'name': 'validBefore', 'type': 'uint256'}, {'name': 'nonce', 'type': 'bytes32'}]},
            'primaryType': primary, 'domain': domain.typed_domain(),
            'message': {'from': '0x' + self.payer[12:].hex(), 'to': '0x' + self.payee[12:].hex(),
                        'value': self.value, 'validAfter': self.valid_after,
                        'validBefore': self.valid_before, 'nonce': '0x' + self.nonce.hex()}}

    def validate_time(self, now):
        _uint(now)
        _require(self.valid_after < now < self.valid_before, 'authorization is not strictly current')

    def verify_eoa(self, domain, signature65, now, *, payer_kind='eoa'):
        """Verify only the configured token transfer digest; no replay-state oracle."""
        _require(type(payer_kind) is str and payer_kind == 'eoa', 'only EOA payer signatures supported')
        self.validate_time(now)
        r, s, v = _signature(signature65)
        digest = self.digest(domain)
        try:
            recovered = keys.Signature(vrs=(v - 27, r, s)).recover_public_key_from_msg_hash(digest)
        except Exception:
            raise EIP3009Error('invalid EOA signature') from None
        _require(recovered.to_canonical_address() == self.payer[12:], 'EOA signature does not match payer')

    def calldata(self, signature65, *, caller=None):
        """Construct ABI bytes only; this method never verifies policy or submits.

        Receive additionally requires its token-level caller==payee precondition.
        Transfer is bearer authorization; its relay caller is not in the digest.
        """
        r, s, v = _signature(signature65)
        if caller is not None:
            _address(caller)
        if self.method == 'receive':
            _require(caller == self.payee, 'receive authorization requires payee caller')
        function = self.method + 'WithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)'
        return bytes(Web3.keccak(text=function)[:4]) + encode(
            ['address', 'address', 'uint256', 'uint256', 'uint256', 'bytes32', 'uint8', 'bytes32', 'bytes32'],
            [self.payer[12:], self.payee[12:], self.value, self.valid_after, self.valid_before,
             self.nonce, v, r.to_bytes(32, 'big'), s.to_bytes(32, 'big')])

    @classmethod
    def from_intent(cls, domain, intent, *, method):
        """Project approved metadata, without granting policy/signing authority."""
        _require(cls is EIP3009AuthorizationV1 and type(intent) is PaymentIntentV1,
                 'exact canonical payment intent required')
        intent.validate()
        result = cls(intent.payer, intent.payee, intent.amount, intent.valid_after,
                     intent.valid_before, intent.nonce, method)
        result.validate_for_intent(domain, intent)
        return result

    def validate_for_intent(self, domain, intent):
        _require(type(domain) is EIP3009DomainV1 and type(intent) is PaymentIntentV1,
                 'exact domain and payment intent required')
        intent.validate()
        _require(self.method == 'transfer', 'V1 intent supports transfer only; receive requires another profile')
        _require(domain.chain_id == intent.chain_id and domain.token == intent.asset
                 and domain.separator == intent.token_domain, 'intent token domain differs')
        _require((self.payer, self.payee, self.value, self.nonce, self.valid_after, self.valid_before) ==
                 (intent.payer, intent.payee, intent.amount, intent.nonce, intent.valid_after, intent.valid_before),
                 'authorization differs from exact payment intent')
