"""Bound escrow request construction. Quotes never become token amounts implicitly.

Reads are pinned to one observed block. The contract independently compares
current terms at creation, so a change after observation rejects atomically.
This module does not sign, submit, qualify a provider, or certify an RPC.
"""
from dataclasses import dataclass
import hashlib
import re

ZERO32 = b"\0" * 32
UINT256_MAX = (1 << 256) - 1

class SettlementBuildError(ValueError):
    pass

def _uint(value, name, minimum=0, maximum=UINT256_MAX):
    if type(value) is not int or not minimum <= value <= maximum:
        raise SettlementBuildError(f"invalid {name}")
    return value

def _address(value):
    if type(value) is not str or not re.fullmatch(r"0x[0-9a-fA-F]{40}", value) or int(value[2:], 16) == 0:
        raise SettlementBuildError("invalid address")
    return value.lower()

def _hash(value):
    if type(value) is bytes and len(value) == 32:
        return value
    if type(value) is str and re.fullmatch(r"0x[0-9a-fA-F]{64}", value):
        return bytes.fromhex(value[2:])
    raise SettlementBuildError("invalid bytes32")

@dataclass(frozen=True)
class SettlementDeployment:
    chain_id: int
    settlement: str
    registry: str
    settlement_runtime_sha256: bytes
    registry_runtime_sha256: bytes

    def validate(self):
        _uint(self.chain_id, "chain", 1)
        _address(self.settlement); _address(self.registry)
        for digest in (self.settlement_runtime_sha256, self.registry_runtime_sha256):
            if _hash(digest) == ZERO32:
                raise SettlementBuildError("missing reviewed runtime identity")

@dataclass(frozen=True)
class BoundEscrowRequest:
    providers: tuple[str, ...]
    amounts: tuple[int, ...]
    valid_for_seconds: int
    blueprint_hash: bytes
    service_block_id: bytes
    expected_terms_hash: bytes
    workload_hashes: tuple[bytes, ...]
    chain_id: int
    settlement: str
    observed_block: int
    observed_block_hash: bytes

    def as_abi_tuple(self):
        return (list(self.providers), list(self.amounts), self.valid_for_seconds,
                self.blueprint_hash, self.service_block_id, self.expected_terms_hash, list(self.workload_hashes))

class SettlementTransactionBuilder:
    """Web3 contract reads against identities supplied by reviewed deployment evidence."""
    def __init__(self, web3, registry_contract, settlement_contract, deployment: SettlementDeployment):
        if type(deployment) is not SettlementDeployment:
            raise SettlementBuildError("typed deployment required")
        deployment.validate()
        if (_address(registry_contract.address) != _address(deployment.registry) or
            _address(settlement_contract.address) != _address(deployment.settlement)):
            raise SettlementBuildError("contract address mismatch")
        self.web3, self.registry, self.settlement, self.deployment = web3, registry_contract, settlement_contract, deployment

    def build(self, *, providers, amounts, workload_hashes, valid_for_seconds, blueprint_hash, service_block_id=ZERO32):
        if type(providers) not in (tuple, list) or type(amounts) not in (tuple, list):
            raise SettlementBuildError("explicit provider and integer amount sequences required")
        if not 1 <= len(providers) <= 20 or len(providers) != len(amounts):
            raise SettlementBuildError("invalid provider count")
        providers = tuple(_address(p) for p in providers)
        amounts = tuple(_uint(a, "token base units", 1) for a in amounts)
        if type(workload_hashes) not in (tuple,list) or len(workload_hashes)!=len(providers):
            raise SettlementBuildError("one workload commitment per provider required")
        workload_hashes=tuple(_hash(h) for h in workload_hashes)
        if ZERO32 in workload_hashes:raise SettlementBuildError("missing workload commitment")
        _uint(sum(amounts), "total token base units", 1)
        _uint(valid_for_seconds, "validity", 300, 172800)
        blueprint_hash, service_block_id = _hash(blueprint_hash), _hash(service_block_id)
        try:
            d = self.deployment
            if _uint(self.web3.eth.chain_id, "chain", 1) != d.chain_id:
                raise SettlementBuildError("chain mismatch")
            observed = self.web3.eth.get_block("latest")
            number, block_hash = _uint(observed["number"], "block"), _hash(bytes(observed["hash"]))
            for address, expected in ((d.registry, d.registry_runtime_sha256), (d.settlement, d.settlement_runtime_sha256)):
                code = bytes(self.web3.eth.get_code(address, block_identifier=number))
                if not code or hashlib.sha256(code).digest() != expected:
                    raise SettlementBuildError("runtime identity mismatch")
            actual_registry = self.settlement.functions.serviceBlockRegistry().call(block_identifier=number)
            if _address(actual_registry) != _address(d.registry):
                raise SettlementBuildError("settlement registry mismatch")
            terms = ZERO32
            if service_block_id != ZERO32:
                block = self.registry.functions.getServiceBlock(service_block_id).call(block_identifier=number)
                if type(block) not in (tuple, list) or len(block) != 21:
                    raise SettlementBuildError("unsupported registry ABI")
                if (_hash(bytes(block[0])) != service_block_id or block[10] is not True or
                    block[11] is not True or block[19] is not False):
                    raise SettlementBuildError("unqualified service block")
                _address(block[1]); _uint(block[7], "builder bps", 0, 5000)
                _uint(block[18], "manifest version", 1)
                if _hash(bytes(block[14])) == ZERO32 or _address(block[17]) != _address(block[1]):
                    raise SettlementBuildError("invalid manifest identity")
                terms = _hash(bytes(self.settlement.functions.getServiceTermsHash(service_block_id).call(block_identifier=number)))
                if terms == ZERO32:
                    raise SettlementBuildError("missing bound terms")
            final = self.web3.eth.get_block(number)
            if _hash(bytes(final["hash"])) != block_hash or self.web3.eth.chain_id != d.chain_id:
                raise SettlementBuildError("chain observation changed")
        except SettlementBuildError:
            raise
        except Exception:
            raise SettlementBuildError("authenticated chain reads unavailable") from None
        return BoundEscrowRequest(providers, amounts, valid_for_seconds, blueprint_hash,
            service_block_id, terms, workload_hashes, d.chain_id, _address(d.settlement), number, block_hash)
