"""Concrete, fail-closed network observers for the private VDSO shadow."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

import requests

from neuron.runtime_safety import (
    RuntimeConfigurationError,
    current_environment,
    current_network,
)
from neuron.vdso.keccak import keccak_256
from neuron.vdso.service import CanaryDeploymentConfig


POLYGON_AMOY_CHAIN_ID = 80_002
CARDANO_PREPROD_BLOCKFROST_URL = (
    "https://cardano-preprod.blockfrost.io/api/v0"
)
MAX_UINT64 = (1 << 64) - 1
ZERO_ADDRESS = "0x" + "00" * 20
SAFE_SENTINEL_MODULE = "0x" + "00" * 19 + "01"
SAFE_FALLBACK_HANDLER_STORAGE_SLOT = bytes.fromhex(
    "6c9a6c4a39284e37ed1cf53d337577d14212a4870fb976a4366c693b939918d5"
)
SAFE_GUARD_STORAGE_SLOT = bytes.fromhex(
    "4a204f620c8c5ccdca3fd54d003badd85ba500436a431f0cbda4f558c93c34c8"
)
SAFE_MODULE_GUARD_STORAGE_SLOT = bytes.fromhex(
    "b104e0b93118902c651344349b610029d694cfdec91c589c91ebafbcd0289947"
)
MINIMUM_TIMELOCK_DELAY = 48 * 60 * 60
EMPTY_SENTINEL = keccak_256(b"VDSO_CANARY_EMPTY_SENTINEL")

DEFAULT_ADMIN_ROLE = bytes(32)
PAUSER_ROLE = keccak_256(b"VDSO_PAUSER_ROLE")
AUTHORITY_ADMIN_ROLE = keccak_256(b"VDSO_AUTHORITY_ADMIN_ROLE")
OBJECT_KERNEL_ROLE = keccak_256(b"VDSO_OBJECT_KERNEL_ROLE")
RESERVATION_KERNEL_ROLE = keccak_256(b"VDSO_RESERVATION_KERNEL_ROLE")
RECOVERY_ROLE = keccak_256(b"VDSO_RECOVERY_ROLE")
ADAPTER_REGISTRAR_ROLE = keccak_256(b"VDSO_ADAPTER_REGISTRAR_ROLE")
ADAPTER_GUARDIAN_ROLE = keccak_256(b"VDSO_ADAPTER_GUARDIAN_ROLE")
PROGRAM_REGISTRAR_ROLE = keccak_256(b"VDSO_PROGRAM_REGISTRAR_ROLE")
PROGRAM_GUARDIAN_ROLE = keccak_256(b"VDSO_PROGRAM_GUARDIAN_ROLE")
PROOF_CONFIG_ROLE = keccak_256(b"VDSO_PROOF_CONFIG_ROLE")
PROOF_KERNEL_ROLE = keccak_256(b"VDSO_PROOF_KERNEL_ROLE")
EXECUTOR_ROLE = keccak_256(b"VDSO_EXECUTOR_ROLE")
ROLE_GRANTED_TOPIC = keccak_256(b"RoleGranted(bytes32,address,address)")
ROLE_REVOKED_TOPIC = keccak_256(b"RoleRevoked(bytes32,address,address)")
PAUSED_TOPIC = keccak_256(b"Paused(address)")
EVENT_SCAN_BLOCK_CHUNK = 2_000

_MODULES = (
    ("object_store", "VDSO_OBJECT_STORE", True),
    ("reservation_manager", "VDSO_RESERVATION_MANAGER", True),
    ("adapter_registry", "VDSO_ADAPTER_REGISTRY", True),
    ("program_registry", "VDSO_PROGRAM_REGISTRY", True),
    ("proof_router", "VDSO_PROOF_ROUTER", True),
    ("capability_router", "VDSO_CAPABILITY_ROUTER", True),
    ("execution_kernel", "VDSO_EXECUTION_KERNEL", True),
)
_KERNEL_WIRING = {
    "objectStore()": "object_store",
    "reservationManager()": "reservation_manager",
    "adapterRegistry()": "adapter_registry",
    "programRegistry()": "program_registry",
    "proofRouter()": "proof_router",
    "capabilityRouter()": "capability_router",
}


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeConfigurationError(f"{name} is required for private VDSO shadow")
    return value.strip()


def _validated_https_url(name: str, value: str, *, exact: str | None = None) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.fragment:
        raise RuntimeConfigurationError(f"{name} must not contain credentials or fragments")
    if parsed.scheme != "https" or not parsed.hostname:
        if not (
            current_environment() == "local"
            and parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise RuntimeConfigurationError(
                f"{name} must use HTTPS (HTTP is local-loopback only)"
            )
    normalized = value.rstrip("/")
    if exact is not None and normalized != exact:
        raise RuntimeConfigurationError(
            f"{name} must use the official Cardano Pre-Prod Blockfrost endpoint"
        )
    return normalized


def _address(name: str, value: str) -> str:
    normalized = value.strip().lower()
    if (
        len(normalized) != 42
        or not normalized.startswith("0x")
        or any(character not in "0123456789abcdef" for character in normalized[2:])
        or normalized == ZERO_ADDRESS
    ):
        raise RuntimeConfigurationError(f"{name} must be a nonzero 20-byte address")
    return normalized


def _bytes32(name: str, value: str) -> bytes:
    normalized = value.strip().lower()
    if len(normalized) != 66 or not normalized.startswith("0x"):
        raise RuntimeConfigurationError(f"{name} must be a bytes32 hexadecimal value")
    try:
        raw = bytes.fromhex(normalized[2:])
    except ValueError as exc:
        raise RuntimeConfigurationError(
            f"{name} must be a bytes32 hexadecimal value"
        ) from exc
    if raw == bytes(32):
        raise RuntimeConfigurationError(f"{name} must not be the zero hash")
    return raw


def _quantity(name: str, value) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise RuntimeError(f"{name} returned a non-hex quantity")
    try:
        parsed = int(value, 16)
    except ValueError as exc:
        raise RuntimeError(f"{name} returned an invalid hex quantity") from exc
    if not 0 <= parsed <= MAX_UINT64:
        raise RuntimeError(f"{name} returned a value outside uint64")
    return parsed


def _required_uint64(name: str) -> int:
    raw = _required_environment(name)
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise RuntimeConfigurationError(f"{name} must be a base-10 uint64") from exc
    if not 0 <= value <= MAX_UINT64:
        raise RuntimeConfigurationError(f"{name} must be a base-10 uint64")
    return value


class EVMJsonRpcClient:
    """Minimal HTTPS JSON-RPC reader with no write methods or fallback values."""

    def __init__(self, url: str, *, timeout: int = 10, session=None) -> None:
        self.url = _validated_https_url("VDSO_AMOY_RPC_URL", url)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 60:
            raise RuntimeConfigurationError("VDSO RPC timeout must be between 1 and 60 seconds")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._request_id = 0
        # requests.Session and the monotonically increasing request id are both
        # shared state. Serializing a complete call prevents concurrent reads
        # from comparing a response against another request's id.
        self._request_lock = threading.Lock()

    def call(self, method: str, params: list):
        with self._request_lock:
            self._request_id += 1
            request_id = self._request_id
            response = self._session.post(
                self.url,
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
                raise RuntimeError("VDSO Amoy RPC returned a malformed response")
            if payload.get("id") != request_id or "error" in payload:
                raise RuntimeError("VDSO Amoy RPC rejected or mismatched the request")
            if "result" not in payload:
                raise RuntimeError("VDSO Amoy RPC response omitted result")
            return payload["result"]


class PolygonAmoyHeightProvider:
    def __init__(self, rpc: EVMJsonRpcClient) -> None:
        self._rpc = rpc

    def __call__(self, binding) -> int:
        if binding.host_authority.name != "POLYGON":
            raise RuntimeError("Polygon Amoy height provider rejected a non-Polygon binding")
        chain_id = _quantity("eth_chainId", self._rpc.call("eth_chainId", []))
        if chain_id != POLYGON_AMOY_CHAIN_ID:
            raise RuntimeError("VDSO Amoy RPC returned the wrong chain ID")
        return _quantity("eth_blockNumber", self._rpc.call("eth_blockNumber", []))


class CardanoPreprodHeightProvider:
    def __init__(self, base_url: str, project_id: str, *, timeout: int = 10, session=None):
        self.base_url = _validated_https_url(
            "VDSO_CARDANO_BLOCKFROST_URL",
            base_url,
            exact=CARDANO_PREPROD_BLOCKFROST_URL,
        )
        if not project_id.strip():
            raise RuntimeConfigurationError(
                "VDSO_CARDANO_BLOCKFROST_PROJECT_ID is required"
            )
        self._project_id = project_id.strip()
        self._timeout = timeout
        self._session = session or requests.Session()

    def __call__(self, binding) -> int:
        if binding.host_authority.name != "CARDANO":
            raise RuntimeError("Cardano height provider rejected a non-Cardano binding")
        response = self._session.get(
            f"{self.base_url}/blocks/latest",
            headers={"project_id": self._project_id},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        height = payload.get("height") if isinstance(payload, dict) else None
        if isinstance(height, bool) or not isinstance(height, int) or not 0 <= height <= MAX_UINT64:
            raise RuntimeError("Cardano Pre-Prod height endpoint returned an invalid height")
        return height


@dataclass(frozen=True)
class DeployedModule:
    address: str
    code_hash: bytes
    expected_paused: bool


@dataclass(frozen=True)
class DeploymentAuthorities:
    governance_safe: str
    timelock: str
    pause_council: str
    guardian: str
    recovery_authority: str
    deployer: str

    def privileged_contracts(self) -> tuple[str, ...]:
        return (
            self.governance_safe,
            self.timelock,
            self.pause_council,
            self.guardian,
            self.recovery_authority,
        )

    def all_accounts(self) -> tuple[str, ...]:
        return self.privileged_contracts() + (self.deployer,)


@dataclass(frozen=True)
class ControlPlaneIdentity:
    safe_proxy_code_hash: bytes
    safe_singleton: str
    safe_singleton_code_hash: bytes
    timelock_code_hash: bytes


@dataclass(frozen=True)
class DeploymentProvenance:
    transaction_hash: bytes
    block_number: int
    block_hash: bytes


class PolygonAmoyDeploymentVerifier:
    """Verify the exact empty, fully paused seven-module Amoy deployment."""

    def __init__(
        self,
        rpc: EVMJsonRpcClient,
        modules: Mapping[str, DeployedModule],
        authorities: DeploymentAuthorities,
        control_identity: ControlPlaneIdentity,
        provenance: Mapping[str, DeploymentProvenance],
        timelock_provenance: DeploymentProvenance,
    ):
        self._rpc = rpc
        self._modules = dict(modules)
        self._authorities = authorities
        self._control_identity = control_identity
        self._provenance = dict(provenance)
        self._timelock_provenance = timelock_provenance
        self._verification_lock = threading.Lock()
        self._block_tag: str | None = None
        if set(self._modules) != {item[0] for item in _MODULES}:
            raise RuntimeConfigurationError("all seven VDSO deployment modules are required")
        if len({module.address for module in self._modules.values()}) != len(_MODULES):
            raise RuntimeConfigurationError("VDSO module addresses must be distinct")
        if len(set(authorities.all_accounts())) != len(authorities.all_accounts()):
            raise RuntimeConfigurationError("VDSO control-plane authorities must be distinct")
        if set(self._provenance) != set(self._modules):
            raise RuntimeConfigurationError(
                "per-module VDSO creation provenance is required"
            )
        if any(item.block_number == 0 for item in self._provenance.values()):
            raise RuntimeConfigurationError(
                "every VDSO module deployment block must be greater than zero"
            )
        if timelock_provenance.block_number == 0:
            raise RuntimeConfigurationError("timelock deployment block must be greater than zero")

    def _call_bytes(self, address: str, signature: str, arguments: bytes = b"") -> bytes:
        if self._block_tag is None:
            raise RuntimeError("VDSO verification has no fixed block snapshot")
        selector = keccak_256(signature.encode())[:4]
        result = self._rpc.call(
            "eth_call",
            [
                {"to": address, "data": "0x" + (selector + arguments).hex()},
                self._block_tag,
            ],
        )
        if not isinstance(result, str) or not result.startswith("0x"):
            raise RuntimeError(f"{signature} returned malformed call data")
        try:
            return bytes.fromhex(result[2:])
        except ValueError as exc:
            raise RuntimeError(f"{signature} returned malformed call data") from exc

    def _call_word(self, address: str, signature: str, arguments: bytes = b"") -> bytes:
        result = self._call_bytes(address, signature, arguments)
        if len(result) != 32:
            raise RuntimeError(f"{signature} did not return one ABI word")
        return result

    @staticmethod
    def _address_argument(address: str) -> bytes:
        return bytes(12) + bytes.fromhex(address[2:])

    @staticmethod
    def _word_address(word: bytes, signature: str) -> str:
        if len(word) != 32 or any(word[:12]):
            raise RuntimeError(f"{signature} returned a malformed address")
        return "0x" + word[12:].hex()

    @staticmethod
    def _word_bool(word: bytes, signature: str) -> bool:
        if len(word) != 32 or word not in {bytes(32), bytes(31) + b"\x01"}:
            raise RuntimeError(f"{signature} returned a non-canonical boolean")
        return word[-1] == 1

    def _has_role(self, target: str, role: bytes, account: str) -> bool:
        return self._word_bool(
            self._call_word(
                target,
                "hasRole(bytes32,address)",
                role + self._address_argument(account),
            ),
            "hasRole(bytes32,address)",
        )

    def _require_known_role_holder(
        self,
        target: str,
        role: bytes,
        expected_holder: str,
        denied_accounts: tuple[str, ...],
    ) -> bool:
        if not self._has_role(target, role, expected_holder):
            return False
        return all(
            account == expected_holder or not self._has_role(target, role, account)
            for account in denied_accounts
        )

    def _zero_call(
        self,
        address: str,
        signature: str,
        expected_length: int,
        arguments: bytes = b"",
    ) -> bool:
        result = self._call_bytes(address, signature, arguments)
        return len(result) == expected_length and not any(result)

    def _runtime_code(self, address: str, block_tag: str | None = None) -> bytes:
        tag = block_tag or self._block_tag
        if tag is None:
            raise RuntimeError("VDSO verification has no fixed block snapshot")
        code_hex = self._rpc.call("eth_getCode", [address, tag])
        if not isinstance(code_hex, str) or not code_hex.startswith("0x"):
            raise RuntimeError("eth_getCode returned malformed runtime code")
        try:
            code = bytes.fromhex(code_hex[2:])
        except ValueError as exc:
            raise RuntimeError("eth_getCode returned malformed runtime code") from exc
        if not code:
            raise RuntimeError("privileged contract has no runtime code")
        return code

    @staticmethod
    def _rpc_bytes32(name: str, value) -> bytes:
        if not isinstance(value, str) or len(value) != 66 or not value.startswith("0x"):
            raise RuntimeError(f"{name} returned malformed bytes32 data")
        try:
            return bytes.fromhex(value[2:])
        except ValueError as exc:
            raise RuntimeError(f"{name} returned malformed bytes32 data") from exc

    def _block_identity(self, tag: str) -> tuple[int, bytes]:
        block = self._rpc.call("eth_getBlockByNumber", [tag, False])
        if not isinstance(block, dict):
            raise RuntimeError("eth_getBlockByNumber returned malformed block data")
        return (
            _quantity("block number", block.get("number")),
            self._rpc_bytes32("block hash", block.get("hash")),
        )

    def _verify_creation_provenance(
        self, provenance: DeploymentProvenance, addresses: tuple[str, ...]
    ) -> bool:
        if len(addresses) != 1:
            return False
        block_tag = hex(provenance.block_number)
        block_number, block_hash = self._block_identity(block_tag)
        if block_number != provenance.block_number or block_hash != provenance.block_hash:
            return False

        receipt = self._rpc.call(
            "eth_getTransactionReceipt", ["0x" + provenance.transaction_hash.hex()]
        )
        if not isinstance(receipt, dict):
            return False
        if (
            _quantity("receipt status", receipt.get("status")) != 1
            or _quantity("receipt block number", receipt.get("blockNumber"))
            != provenance.block_number
            or self._rpc_bytes32("receipt block hash", receipt.get("blockHash"))
            != provenance.block_hash
            or self._rpc_bytes32(
                "receipt transaction hash", receipt.get("transactionHash")
            )
            != provenance.transaction_hash
        ):
            return False
        contract_address = receipt.get("contractAddress")
        if (
            not isinstance(contract_address, str)
            or contract_address.lower() != addresses[0]
        ):
            return False
        receipt_logs = receipt.get("logs")
        if not isinstance(receipt_logs, list):
            return False
        receipt_addresses = {
            log.get("address", "").lower()
            for log in receipt_logs
            if isinstance(log, dict) and isinstance(log.get("address"), str)
        }
        if not set(addresses).issubset(receipt_addresses):
            return False

        previous_tag = hex(provenance.block_number - 1)
        for address in addresses:
            previous_code = self._rpc.call("eth_getCode", [address, previous_tag])
            if previous_code != "0x":
                return False
            if not self._runtime_code(address, block_tag):
                return False
        return True

    def _event_logs(
        self, addresses: tuple[str, ...], first_block: int, last_block: int
    ) -> list[dict]:
        logs = []
        for chunk_start in range(first_block, last_block + 1, EVENT_SCAN_BLOCK_CHUNK):
            chunk_end = min(last_block, chunk_start + EVENT_SCAN_BLOCK_CHUNK - 1)
            result = self._rpc.call(
                "eth_getLogs",
                [
                    {
                        "address": list(addresses),
                        "fromBlock": hex(chunk_start),
                        "toBlock": hex(chunk_end),
                    }
                ],
            )
            if not isinstance(result, list) or not all(
                isinstance(log, dict) for log in result
            ):
                raise RuntimeError("eth_getLogs returned malformed log data")
            logs.extend(result)
        return sorted(
            logs,
            key=lambda log: (
                _quantity("log block number", log.get("blockNumber")),
                _quantity("log transaction index", log.get("transactionIndex")),
                _quantity("log index", log.get("logIndex")),
            ),
        )

    def _reconstruct_roles(
        self,
        addresses: tuple[str, ...],
        first_block: int,
        last_block: int,
        *,
        reject_non_control_events: bool,
        allow_zero_account: bool = False,
    ) -> tuple[set[tuple[str, bytes, str]], set[str]] | None:
        memberships: set[tuple[str, bytes, str]] = set()
        paused_addresses: set[str] = set()
        seen_logs: set[tuple[bytes, bytes, int]] = set()
        for log in self._event_logs(addresses, first_block, last_block):
            address = log.get("address", "").lower()
            if address not in addresses or log.get("removed") is not False:
                return None
            block_hash = self._rpc_bytes32("log block hash", log.get("blockHash"))
            transaction_hash = self._rpc_bytes32(
                "log transaction hash", log.get("transactionHash")
            )
            log_index = _quantity("log index", log.get("logIndex"))
            identity = (block_hash, transaction_hash, log_index)
            if identity in seen_logs:
                return None
            seen_logs.add(identity)

            topics = log.get("topics")
            data = log.get("data")
            if not isinstance(topics, list) or not topics:
                return None
            topic0 = self._rpc_bytes32("event topic", topics[0])
            if topic0 in {ROLE_GRANTED_TOPIC, ROLE_REVOKED_TOPIC}:
                if len(topics) != 4 or data != "0x":
                    return None
                role = self._rpc_bytes32("role topic", topics[1])
                account_word = self._rpc_bytes32("account topic", topics[2])
                sender_word = self._rpc_bytes32("sender topic", topics[3])
                account = self._word_address(account_word, "role account")
                sender = self._word_address(sender_word, "role sender")
                if (account == ZERO_ADDRESS and not allow_zero_account) or sender == ZERO_ADDRESS:
                    return None
                membership = (address, role, account)
                if topic0 == ROLE_GRANTED_TOPIC:
                    if membership in memberships:
                        return None
                    memberships.add(membership)
                else:
                    if membership not in memberships:
                        return None
                    memberships.remove(membership)
                continue
            if topic0 == PAUSED_TOPIC and reject_non_control_events:
                if len(topics) != 1 or not isinstance(data, str):
                    return None
                pauser = self._word_address(
                    self._rpc_bytes32("Paused event data", data), "Paused(address)"
                )
                if pauser == ZERO_ADDRESS:
                    return None
                paused_addresses.add(address)
                continue
            if reject_non_control_events:
                return None
        return memberships, paused_addresses

    def _expected_module_roles(self) -> set[tuple[str, bytes, str]]:
        expected = set()
        for module in self._modules.values():
            expected.add(
                (module.address, DEFAULT_ADMIN_ROLE, self._authorities.timelock)
            )
            expected.add((module.address, PAUSER_ROLE, self._authorities.pause_council))
        kernel = self._modules["execution_kernel"].address
        expected.update(
            {
                (
                    self._modules["object_store"].address,
                    AUTHORITY_ADMIN_ROLE,
                    self._authorities.timelock,
                ),
                (self._modules["object_store"].address, OBJECT_KERNEL_ROLE, kernel),
                (
                    self._modules["reservation_manager"].address,
                    RESERVATION_KERNEL_ROLE,
                    kernel,
                ),
                (
                    self._modules["reservation_manager"].address,
                    RECOVERY_ROLE,
                    self._authorities.recovery_authority,
                ),
                (
                    self._modules["adapter_registry"].address,
                    ADAPTER_REGISTRAR_ROLE,
                    self._authorities.timelock,
                ),
                (
                    self._modules["adapter_registry"].address,
                    ADAPTER_GUARDIAN_ROLE,
                    self._authorities.guardian,
                ),
                (
                    self._modules["program_registry"].address,
                    PROGRAM_REGISTRAR_ROLE,
                    self._authorities.timelock,
                ),
                (
                    self._modules["program_registry"].address,
                    PROGRAM_GUARDIAN_ROLE,
                    self._authorities.guardian,
                ),
                (
                    self._modules["proof_router"].address,
                    PROOF_CONFIG_ROLE,
                    self._authorities.timelock,
                ),
                (self._modules["proof_router"].address, PROOF_KERNEL_ROLE, kernel),
                (
                    self._modules["execution_kernel"].address,
                    EXECUTOR_ROLE,
                    self._authorities.timelock,
                ),
            }
        )
        return expected

    def _verify_exhaustive_history(self, snapshot_number: int) -> bool:
        module_addresses = tuple(
            module.address for module in self._modules.values()
        )
        for module_name, module in self._modules.items():
            if not self._verify_creation_provenance(
                self._provenance[module_name], (module.address,)
            ):
                return False
        first_module_block = min(
            item.block_number for item in self._provenance.values()
        )
        module_history = self._reconstruct_roles(
            module_addresses,
            first_module_block,
            snapshot_number,
            reject_non_control_events=True,
        )
        if module_history is None:
            return False
        module_memberships, paused_addresses = module_history
        if (
            module_memberships != self._expected_module_roles()
            or paused_addresses != set(module_addresses)
        ):
            return False

        timelock = self._authorities.timelock
        if not self._verify_creation_provenance(
            self._timelock_provenance, (timelock,)
        ):
            return False
        proposer = self._call_word(timelock, "PROPOSER_ROLE()")
        canceller = self._call_word(timelock, "CANCELLER_ROLE()")
        executor = self._call_word(timelock, "EXECUTOR_ROLE()")
        governance = self._authorities.governance_safe
        governance_executor = self._has_role(timelock, executor, governance)
        open_executor = self._has_role(timelock, executor, ZERO_ADDRESS)
        if governance_executor == open_executor:
            return False
        executor_holder = governance if governance_executor else ZERO_ADDRESS
        expected_timelock_roles = {
            (timelock, DEFAULT_ADMIN_ROLE, timelock),
            (timelock, proposer, governance),
            (timelock, canceller, governance),
            (timelock, executor, executor_holder),
        }
        timelock_history = self._reconstruct_roles(
            (timelock,),
            self._timelock_provenance.block_number,
            snapshot_number,
            reject_non_control_events=False,
            allow_zero_account=True,
        )
        return timelock_history is not None and timelock_history[0] == expected_timelock_roles

    def _verify_safe(self, safe: str, owners: int, threshold: int) -> bool:
        if keccak_256(self._runtime_code(safe)) != self._control_identity.safe_proxy_code_hash:
            return False
        singleton = self._word_address(
            self._call_word(safe, "masterCopy()"), "masterCopy()"
        )
        if singleton != self._control_identity.safe_singleton:
            return False
        threshold_word = self._call_word(safe, "getThreshold()")
        if int.from_bytes(threshold_word, "big") != threshold:
            return False
        if int.from_bytes(self._call_word(safe, "nonce()"), "big") != 0:
            return False

        encoded_owners = self._call_bytes(safe, "getOwners()")
        if len(encoded_owners) < 64 or int.from_bytes(encoded_owners[:32], "big") != 32:
            return False
        owner_count = int.from_bytes(encoded_owners[32:64], "big")
        if owner_count != owners or len(encoded_owners) != 64 + 32 * owner_count:
            return False
        decoded_owners = []
        for index in range(owner_count):
            start = 64 + 32 * index
            owner = self._word_address(
                encoded_owners[start : start + 32], "getOwners()"
            )
            if owner == ZERO_ADDRESS:
                return False
            decoded_owners.append(owner)
        if len(set(decoded_owners)) != owner_count:
            return False

        modules = self._call_bytes(
            safe,
            "getModulesPaginated(address,uint256)",
            self._address_argument(SAFE_SENTINEL_MODULE) + (1).to_bytes(32, "big"),
        )
        if (
            len(modules) != 96
            or int.from_bytes(modules[:32], "big") != 64
            or self._word_address(modules[32:64], "getModulesPaginated next")
            != SAFE_SENTINEL_MODULE
            or int.from_bytes(modules[64:96], "big") != 0
        ):
            return False

        for slot in (
            SAFE_GUARD_STORAGE_SLOT,
            SAFE_MODULE_GUARD_STORAGE_SLOT,
            SAFE_FALLBACK_HANDLER_STORAGE_SLOT,
        ):
            storage = self._rpc.call(
                "eth_getStorageAt",
                [safe, "0x" + slot.hex(), self._block_tag],
            )
            if self._rpc_bytes32("Safe control storage", storage) != bytes(32):
                return False
        return True

    def _verify_authority_identities(self) -> bool:
        if (
            keccak_256(self._runtime_code(self._control_identity.safe_singleton))
            != self._control_identity.safe_singleton_code_hash
        ):
            return False
        return all(
            (
                self._verify_safe(self._authorities.governance_safe, 5, 3),
                self._verify_safe(self._authorities.pause_council, 3, 2),
                self._verify_safe(self._authorities.guardian, 3, 2),
                self._verify_safe(self._authorities.recovery_authority, 3, 2),
            )
        )

    def _verify_timelock(self) -> bool:
        timelock = self._authorities.timelock
        if (
            keccak_256(self._runtime_code(timelock))
            != self._control_identity.timelock_code_hash
        ):
            return False
        min_delay = int.from_bytes(self._call_word(timelock, "getMinDelay()"), "big")
        if min_delay < MINIMUM_TIMELOCK_DELAY:
            return False
        governance = self._authorities.governance_safe
        proposer = self._call_word(timelock, "PROPOSER_ROLE()")
        canceller = self._call_word(timelock, "CANCELLER_ROLE()")
        executor = self._call_word(timelock, "EXECUTOR_ROLE()")
        governance_executor = self._has_role(timelock, executor, governance)
        open_executor = self._has_role(timelock, executor, ZERO_ADDRESS)
        return (
            self._has_role(timelock, DEFAULT_ADMIN_ROLE, timelock)
            and not self._has_role(
                timelock, DEFAULT_ADMIN_ROLE, self._authorities.deployer
            )
            and self._has_role(timelock, proposer, governance)
            and self._has_role(timelock, canceller, governance)
            and governance_executor != open_executor
            and not self._has_role(timelock, executor, self._authorities.deployer)
        )

    def _verify_control_plane(self) -> bool:
        known_accounts = self._authorities.all_accounts()
        denied_accounts = known_accounts + tuple(
            module.address for module in self._modules.values()
        )
        for module in self._modules.values():
            if not self._require_known_role_holder(
                module.address,
                DEFAULT_ADMIN_ROLE,
                self._authorities.timelock,
                denied_accounts,
            ):
                return False
            if not self._require_known_role_holder(
                module.address,
                PAUSER_ROLE,
                self._authorities.pause_council,
                denied_accounts,
            ):
                return False

        kernel = self._modules["execution_kernel"].address
        role_bindings = (
            ("object_store", AUTHORITY_ADMIN_ROLE, self._authorities.timelock),
            ("object_store", OBJECT_KERNEL_ROLE, kernel),
            ("reservation_manager", RESERVATION_KERNEL_ROLE, kernel),
            (
                "reservation_manager",
                RECOVERY_ROLE,
                self._authorities.recovery_authority,
            ),
            ("adapter_registry", ADAPTER_REGISTRAR_ROLE, self._authorities.timelock),
            ("adapter_registry", ADAPTER_GUARDIAN_ROLE, self._authorities.guardian),
            ("program_registry", PROGRAM_REGISTRAR_ROLE, self._authorities.timelock),
            ("program_registry", PROGRAM_GUARDIAN_ROLE, self._authorities.guardian),
            ("proof_router", PROOF_CONFIG_ROLE, self._authorities.timelock),
            ("proof_router", PROOF_KERNEL_ROLE, kernel),
            ("execution_kernel", EXECUTOR_ROLE, self._authorities.timelock),
        )
        return all(
            self._require_known_role_holder(
                self._modules[module_name].address,
                role,
                holder,
                denied_accounts,
            )
            for module_name, role, holder in role_bindings
        )

    def _verify_empty_state(self, binding) -> bool:
        sentinel = EMPTY_SENTINEL
        object_store = self._modules["object_store"].address
        reservation_manager = self._modules["reservation_manager"].address
        adapter_registry = self._modules["adapter_registry"].address
        program_registry = self._modules["program_registry"].address
        proof_router = self._modules["proof_router"].address
        kernel = self._modules["execution_kernel"].address

        return all(
            (
                self._zero_call(
                    object_store,
                    "getDomainAuthority(bytes32)",
                    128,
                    binding.state_domain,
                ),
                self._zero_call(
                    object_store,
                    "getDomainAuthority(bytes32)",
                    128,
                    sentinel,
                ),
                self._zero_call(object_store, "getObject(bytes32)", 160, sentinel),
                self._zero_call(
                    reservation_manager, "recoveryVerifier()", 32
                ),
                self._zero_call(
                    reservation_manager, "getReservation(bytes32)", 576, sentinel
                ),
                self._zero_call(
                    reservation_manager, "activeReservation(bytes32)", 32, sentinel
                ),
                self._zero_call(
                    reservation_manager, "lastFencingToken(bytes32)", 32, sentinel
                ),
                self._zero_call(
                    reservation_manager, "reservationIdUsed(bytes32)", 32, sentinel
                ),
                self._zero_call(
                    adapter_registry, "getAdapter(bytes32)", 416, sentinel
                ),
                self._zero_call(
                    program_registry, "getProgram(bytes32)", 224, sentinel
                ),
                self._zero_call(
                    proof_router, "getVerifier(bytes32)", 192, sentinel
                ),
                self._zero_call(
                    proof_router, "receiptUsed(bytes32)", 32, sentinel
                ),
                self._zero_call(kernel, "executionUsed(bytes32)", 32, sentinel),
                self._zero_call(kernel, "executionAdapter(bytes32)", 32, sentinel),
            )
        )

    def _verify_at_snapshot(
        self, config: CanaryDeploymentConfig, binding, snapshot_number: int
    ) -> bool:
        try:
            if _quantity("eth_chainId", self._rpc.call("eth_chainId", [])) != POLYGON_AMOY_CHAIN_ID:
                return False
            configured = {
                "object_store": config.object_store_address.lower(),
                "adapter_registry": config.adapter_registry_address.lower(),
                "execution_kernel": config.execution_kernel_address.lower(),
            }
            if any(self._modules[name].address != address for name, address in configured.items()):
                return False

            for module in self._modules.values():
                if keccak_256(self._runtime_code(module.address)) != module.code_hash:
                    return False
                paused_word = self._call_word(module.address, "paused()")
                if self._word_bool(paused_word, "paused()") != module.expected_paused:
                    return False

            if (
                not self._verify_authority_identities()
                or not self._verify_timelock()
                or not self._verify_control_plane()
                or not self._verify_exhaustive_history(snapshot_number)
            ):
                return False

            kernel = self._modules["execution_kernel"].address
            for signature, module_name in _KERNEL_WIRING.items():
                word = self._call_word(kernel, signature)
                actual = self._word_address(word, signature)
                if actual != self._modules[module_name].address:
                    return False

            capability_registry = self._call_word(
                self._modules["capability_router"].address, "adapterRegistry()"
            )
            if self._word_address(
                capability_registry, "adapterRegistry()"
            ) != self._modules["adapter_registry"].address:
                return False
            return self._verify_empty_state(binding)
        except (RuntimeError, ValueError, requests.RequestException):
            return False

    def __call__(self, config: CanaryDeploymentConfig, binding) -> bool:
        with self._verification_lock:
            try:
                snapshot_number, snapshot_hash = self._block_identity("latest")
                if snapshot_number < max(
                    *(item.block_number for item in self._provenance.values()),
                    self._timelock_provenance.block_number,
                ):
                    return False
                self._block_tag = hex(snapshot_number)
                if not self._verify_at_snapshot(config, binding, snapshot_number):
                    return False
                final_number, final_hash = self._block_identity(self._block_tag)
                return final_number == snapshot_number and final_hash == snapshot_hash
            except (RuntimeError, ValueError, requests.RequestException):
                return False
            finally:
                self._block_tag = None


def shadow_runtime_from_environment():
    """Build real network observers from explicit, deployment-bound configuration."""

    network = current_network(required=True)
    amoy_rpc = EVMJsonRpcClient(_required_environment("VDSO_AMOY_RPC_URL"))
    modules = {}
    for module_name, environment_prefix, expected_paused in _MODULES:
        modules[module_name] = DeployedModule(
            address=_address(
                f"{environment_prefix}_ADDRESS",
                _required_environment(f"{environment_prefix}_ADDRESS"),
            ),
            code_hash=_bytes32(
                f"{environment_prefix}_CODE_HASH",
                _required_environment(f"{environment_prefix}_CODE_HASH"),
            ),
            expected_paused=expected_paused,
        )
    authorities = DeploymentAuthorities(
        governance_safe=_address(
            "VAMS_VDSO_GOVERNANCE_SAFE",
            _required_environment("VAMS_VDSO_GOVERNANCE_SAFE"),
        ),
        timelock=_address(
            "VAMS_VDSO_TIMELOCK", _required_environment("VAMS_VDSO_TIMELOCK")
        ),
        pause_council=_address(
            "VAMS_VDSO_PAUSE_COUNCIL",
            _required_environment("VAMS_VDSO_PAUSE_COUNCIL"),
        ),
        guardian=_address(
            "VAMS_VDSO_GUARDIAN", _required_environment("VAMS_VDSO_GUARDIAN")
        ),
        recovery_authority=_address(
            "VAMS_VDSO_RECOVERY_AUTHORITY",
            _required_environment("VAMS_VDSO_RECOVERY_AUTHORITY"),
        ),
        deployer=_address(
            "VAMS_VDSO_DEPLOYER", _required_environment("VAMS_VDSO_DEPLOYER")
        ),
    )
    control_identity = ControlPlaneIdentity(
        safe_proxy_code_hash=_bytes32(
            "VAMS_VDSO_SAFE_PROXY_RUNTIME_CODE_HASH",
            _required_environment("VAMS_VDSO_SAFE_PROXY_RUNTIME_CODE_HASH"),
        ),
        safe_singleton=_address(
            "VAMS_VDSO_SAFE_SINGLETON",
            _required_environment("VAMS_VDSO_SAFE_SINGLETON"),
        ),
        safe_singleton_code_hash=_bytes32(
            "VAMS_VDSO_SAFE_SINGLETON_RUNTIME_CODE_HASH",
            _required_environment("VAMS_VDSO_SAFE_SINGLETON_RUNTIME_CODE_HASH"),
        ),
        timelock_code_hash=_bytes32(
            "VAMS_VDSO_TIMELOCK_RUNTIME_CODE_HASH",
            _required_environment("VAMS_VDSO_TIMELOCK_RUNTIME_CODE_HASH"),
        ),
    )
    provenance = {}
    for module_name, environment_prefix, _expected_paused in _MODULES:
        provenance[module_name] = DeploymentProvenance(
            transaction_hash=_bytes32(
                f"{environment_prefix}_DEPLOYMENT_TX_HASH",
                _required_environment(f"{environment_prefix}_DEPLOYMENT_TX_HASH"),
            ),
            block_number=_required_uint64(
                f"{environment_prefix}_DEPLOYMENT_BLOCK_NUMBER"
            ),
            block_hash=_bytes32(
                f"{environment_prefix}_DEPLOYMENT_BLOCK_HASH",
                _required_environment(f"{environment_prefix}_DEPLOYMENT_BLOCK_HASH"),
            ),
        )
    timelock_provenance = DeploymentProvenance(
        transaction_hash=_bytes32(
            "VAMS_VDSO_TIMELOCK_DEPLOYMENT_TX_HASH",
            _required_environment("VAMS_VDSO_TIMELOCK_DEPLOYMENT_TX_HASH"),
        ),
        block_number=_required_uint64(
            "VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_NUMBER"
        ),
        block_hash=_bytes32(
            "VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_HASH",
            _required_environment("VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_HASH"),
        ),
    )
    verifier = PolygonAmoyDeploymentVerifier(
        amoy_rpc,
        modules,
        authorities,
        control_identity,
        provenance,
        timelock_provenance,
    )
    if network == "polygon-amoy":
        height_provider = PolygonAmoyHeightProvider(amoy_rpc)
    else:
        height_provider = CardanoPreprodHeightProvider(
            _required_environment("VDSO_CARDANO_BLOCKFROST_URL"),
            _required_environment("VDSO_CARDANO_BLOCKFROST_PROJECT_ID"),
        )
    return height_provider, verifier
