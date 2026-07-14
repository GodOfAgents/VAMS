import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

os.environ["VAMS_ENV"] = "local"
os.environ["VDSO_MODE"] = "off"
os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "SecureVDSORuntimeTestPassword!")

from gateway import server
from gateway.vdso_runtime import (
    ADAPTER_GUARDIAN_ROLE,
    ADAPTER_REGISTRAR_ROLE,
    AUTHORITY_ADMIN_ROLE,
    CARDANO_PREPROD_BLOCKFROST_URL,
    DEFAULT_ADMIN_ROLE,
    PAUSED_TOPIC,
    ROLE_GRANTED_TOPIC,
    SAFE_FALLBACK_HANDLER_STORAGE_SLOT,
    SAFE_GUARD_STORAGE_SLOT,
    SAFE_MODULE_GUARD_STORAGE_SLOT,
    EXECUTOR_ROLE,
    OBJECT_KERNEL_ROLE,
    PAUSER_ROLE,
    PROGRAM_GUARDIAN_ROLE,
    PROGRAM_REGISTRAR_ROLE,
    PROOF_CONFIG_ROLE,
    PROOF_KERNEL_ROLE,
    RECOVERY_ROLE,
    RESERVATION_KERNEL_ROLE,
    CardanoPreprodHeightProvider,
    ControlPlaneIdentity,
    DeployedModule,
    DeploymentAuthorities,
    DeploymentProvenance,
    EVMJsonRpcClient,
    PolygonAmoyDeploymentVerifier,
    PolygonAmoyHeightProvider,
)
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.vdso.keccak import keccak_256
from neuron.vdso.models import DomainAuthorityBinding, HostAuthority
from neuron.vdso.service import CanaryDeploymentConfig


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _RpcSession:
    def __init__(self, handler):
        self.handler = handler

    def post(self, _url, *, json, timeout):
        assert timeout == 10
        return _Response(
            {
                "jsonrpc": "2.0",
                "id": json["id"],
                "result": self.handler(json["method"], json["params"]),
            }
        )


class _BlockfrostSession:
    def get(self, url, *, headers, timeout):
        assert url == f"{CARDANO_PREPROD_BLOCKFROST_URL}/blocks/latest"
        assert headers == {"project_id": "preprod-project"}
        assert timeout == 10
        return _Response({"height": 12_345})


def _address(index):
    return "0x" + index.to_bytes(20, "big").hex()


def _word_address(value):
    return bytes(12) + bytes.fromhex(value[2:])


def _deployment_fixture():
    names = (
        "object_store",
        "reservation_manager",
        "adapter_registry",
        "program_registry",
        "proof_router",
        "capability_router",
        "execution_kernel",
    )
    modules = {}
    code_by_address = {}
    for index, name in enumerate(names, start=1):
        code = b"\x60" + bytes((index,))
        address = _address(index)
        code_by_address[address] = code
        modules[name] = DeployedModule(
            address=address,
            code_hash=keccak_256(code),
            expected_paused=True,
        )

    authorities = DeploymentAuthorities(
        governance_safe=_address(101),
        timelock=_address(102),
        pause_council=_address(103),
        guardian=_address(104),
        recovery_authority=_address(105),
        deployer=_address(106),
    )
    safe_proxy_code = b"\x60\x20"
    timelock_code = b"\x60\x21"
    safe_singleton = _address(107)
    singleton_code = b"\x60\x22"
    for address in (
        authorities.governance_safe,
        authorities.pause_council,
        authorities.guardian,
        authorities.recovery_authority,
    ):
        code_by_address[address] = safe_proxy_code
    code_by_address[authorities.timelock] = timelock_code
    code_by_address[safe_singleton] = singleton_code
    control_identity = ControlPlaneIdentity(
        safe_proxy_code_hash=keccak_256(safe_proxy_code),
        safe_singleton=safe_singleton,
        safe_singleton_code_hash=keccak_256(singleton_code),
        timelock_code_hash=keccak_256(timelock_code),
    )
    safe_owners = {
        authorities.governance_safe: [_address(index) for index in range(201, 206)],
        authorities.pause_council: [_address(index) for index in range(211, 214)],
        authorities.guardian: [_address(index) for index in range(221, 224)],
        authorities.recovery_authority: [_address(index) for index in range(231, 234)],
    }
    safe_thresholds = {
        authorities.governance_safe: 3,
        authorities.pause_council: 2,
        authorities.guardian: 2,
        authorities.recovery_authority: 2,
    }

    selectors = {
        keccak_256(signature.encode())[:4].hex(): (signature, module_name)
        for signature, module_name in {
            "objectStore()": "object_store",
            "reservationManager()": "reservation_manager",
            "adapterRegistry()": "adapter_registry",
            "programRegistry()": "program_registry",
            "proofRouter()": "proof_router",
            "capabilityRouter()": "capability_router",
        }.items()
    }
    paused_selector = keccak_256(b"paused()")[:4].hex()
    has_role_selector = keccak_256(b"hasRole(bytes32,address)")[:4].hex()
    zero_result_lengths = {
        keccak_256(signature.encode())[:4].hex(): length
        for signature, length in {
            "getDomainAuthority(bytes32)": 128,
            "getObject(bytes32)": 160,
            "recoveryVerifier()": 32,
            "getReservation(bytes32)": 576,
            "activeReservation(bytes32)": 32,
            "lastFencingToken(bytes32)": 32,
            "reservationIdUsed(bytes32)": 32,
            "getAdapter(bytes32)": 416,
            "getProgram(bytes32)": 224,
            "getVerifier(bytes32)": 192,
            "receiptUsed(bytes32)": 32,
            "executionUsed(bytes32)": 32,
            "executionAdapter(bytes32)": 32,
        }.items()
    }
    timelock_roles = {
        "PROPOSER_ROLE()": keccak_256(b"PROPOSER_ROLE"),
        "CANCELLER_ROLE()": keccak_256(b"CANCELLER_ROLE"),
        "EXECUTOR_ROLE()": keccak_256(b"TIMELOCK_EXECUTOR_ROLE"),
    }
    timelock_selectors = {
        keccak_256(signature.encode())[:4].hex(): role
        for signature, role in timelock_roles.items()
    }
    master_copy_selector = keccak_256(b"masterCopy()")[:4].hex()
    owners_selector = keccak_256(b"getOwners()")[:4].hex()
    threshold_selector = keccak_256(b"getThreshold()")[:4].hex()
    modules_selector = keccak_256(b"getModulesPaginated(address,uint256)")[:4].hex()
    nonce_selector = keccak_256(b"nonce()")[:4].hex()
    role_memberships = set()
    for module in modules.values():
        role_memberships.add((module.address, DEFAULT_ADMIN_ROLE, authorities.timelock))
        role_memberships.add((module.address, PAUSER_ROLE, authorities.pause_council))
    kernel = modules["execution_kernel"].address
    role_memberships.update(
        {
            (modules["object_store"].address, AUTHORITY_ADMIN_ROLE, authorities.timelock),
            (modules["object_store"].address, OBJECT_KERNEL_ROLE, kernel),
            (modules["reservation_manager"].address, RESERVATION_KERNEL_ROLE, kernel),
            (modules["reservation_manager"].address, RECOVERY_ROLE, authorities.recovery_authority),
            (modules["adapter_registry"].address, ADAPTER_REGISTRAR_ROLE, authorities.timelock),
            (modules["adapter_registry"].address, ADAPTER_GUARDIAN_ROLE, authorities.guardian),
            (modules["program_registry"].address, PROGRAM_REGISTRAR_ROLE, authorities.timelock),
            (modules["program_registry"].address, PROGRAM_GUARDIAN_ROLE, authorities.guardian),
            (modules["proof_router"].address, PROOF_CONFIG_ROLE, authorities.timelock),
            (modules["proof_router"].address, PROOF_KERNEL_ROLE, kernel),
            (modules["execution_kernel"].address, EXECUTOR_ROLE, authorities.timelock),
            (
                authorities.timelock,
                timelock_roles["PROPOSER_ROLE()"],
                authorities.governance_safe,
            ),
            (
                authorities.timelock,
                timelock_roles["CANCELLER_ROLE()"],
                authorities.governance_safe,
            ),
            (
                authorities.timelock,
                timelock_roles["EXECUTOR_ROLE()"],
                authorities.governance_safe,
            ),
        }
    )
    deployment_provenance_by_module = {
        module_name: DeploymentProvenance(
            transaction_hash=bytes((0x31 + index,)) * 32,
            block_number=500 + index,
            block_hash=bytes((0x41 + index,)) * 32,
        )
        for index, module_name in enumerate(modules)
    }
    module_name_by_address = {
        module.address: module_name for module_name, module in modules.items()
    }
    timelock_provenance = DeploymentProvenance(
        transaction_hash=bytes.fromhex("90" * 32),
        block_number=400,
        block_hash=bytes.fromhex("42" * 32),
    )
    snapshot_number = 600
    snapshot_hash = bytes.fromhex("43" * 32)

    event_logs = []

    def append_log(address, topics, data, block_number, block_hash, transaction_hash):
        event_logs.append(
            {
                "address": address,
                "topics": ["0x" + topic.hex() for topic in topics],
                "data": "0x" + data.hex(),
                "blockNumber": hex(block_number),
                "blockHash": "0x" + block_hash.hex(),
                "transactionHash": "0x" + transaction_hash.hex(),
                "transactionIndex": "0x0",
                "logIndex": hex(len(event_logs)),
                "removed": False,
            }
        )

    module_addresses = {module.address for module in modules.values()}
    for target, role, account in sorted(
        (membership for membership in role_memberships if membership[0] in module_addresses),
        key=lambda membership: (membership[0], membership[1], membership[2]),
    ):
        module_provenance = deployment_provenance_by_module[
            module_name_by_address[target]
        ]
        append_log(
            target,
            (
                ROLE_GRANTED_TOPIC,
                role,
                _word_address(account),
                _word_address(authorities.deployer),
            ),
            b"",
            module_provenance.block_number,
            module_provenance.block_hash,
            module_provenance.transaction_hash,
        )
    for module_name, module in modules.items():
        module_provenance = deployment_provenance_by_module[module_name]
        append_log(
            module.address,
            (PAUSED_TOPIC,),
            _word_address(authorities.deployer),
            module_provenance.block_number,
            module_provenance.block_hash,
            module_provenance.transaction_hash,
        )
    for target, role, account in sorted(
        (membership for membership in role_memberships if membership[0] == authorities.timelock),
        key=lambda membership: (membership[1], membership[2]),
    ):
        append_log(
            target,
            (
                ROLE_GRANTED_TOPIC,
                role,
                _word_address(account),
                _word_address(authorities.deployer),
            ),
            b"",
            timelock_provenance.block_number,
            timelock_provenance.block_hash,
            timelock_provenance.transaction_hash,
        )
    # TimelockController is its own sole DEFAULT_ADMIN_ROLE holder.
    role_memberships.add(
        (authorities.timelock, DEFAULT_ADMIN_ROLE, authorities.timelock)
    )
    append_log(
        authorities.timelock,
        (
            ROLE_GRANTED_TOPIC,
            DEFAULT_ADMIN_ROLE,
            _word_address(authorities.timelock),
            _word_address(authorities.deployer),
        ),
        b"",
        timelock_provenance.block_number,
        timelock_provenance.block_hash,
        timelock_provenance.transaction_hash,
    )

    def rpc_handler(method, params):
        if method == "eth_chainId":
            return hex(80_002)
        if method == "eth_blockNumber":
            return hex(9_999)
        if method == "eth_getCode":
            target, block_tag = params
            if (
                target in module_addresses
                and block_tag
                == hex(
                    deployment_provenance_by_module[
                        module_name_by_address[target]
                    ].block_number
                    - 1
                )
            ) or (
                target == authorities.timelock
                and block_tag == hex(timelock_provenance.block_number - 1)
            ):
                return "0x"
            return "0x" + code_by_address[params[0]].hex()
        if method == "eth_getBlockByNumber":
            tag = params[0]
            if tag == "latest" or tag == hex(snapshot_number):
                return {
                    "number": hex(snapshot_number),
                    "hash": "0x" + snapshot_hash.hex(),
                }
            for provenance in deployment_provenance_by_module.values():
                if tag == hex(provenance.block_number):
                    return {
                        "number": hex(provenance.block_number),
                        "hash": "0x" + provenance.block_hash.hex(),
                    }
            if tag == hex(timelock_provenance.block_number):
                return {
                    "number": hex(timelock_provenance.block_number),
                    "hash": "0x" + timelock_provenance.block_hash.hex(),
                }
            raise AssertionError(f"unexpected block tag: {tag}")
        if method == "eth_getTransactionReceipt":
            transaction_hash = bytes.fromhex(params[0][2:])
            module_name = next(
                (
                    name
                    for name, item in deployment_provenance_by_module.items()
                    if item.transaction_hash == transaction_hash
                ),
                None,
            )
            provenance = (
                deployment_provenance_by_module[module_name]
                if module_name is not None
                else timelock_provenance
            )
            contract_address = (
                modules[module_name].address
                if module_name is not None
                else authorities.timelock
            )
            return {
                "status": "0x1",
                "blockNumber": hex(provenance.block_number),
                "blockHash": "0x" + provenance.block_hash.hex(),
                "transactionHash": "0x" + provenance.transaction_hash.hex(),
                "contractAddress": contract_address,
                "logs": [
                    log
                    for log in event_logs
                    if log["transactionHash"]
                    == "0x" + provenance.transaction_hash.hex()
                ],
            }
        if method == "eth_getLogs":
            query = params[0]
            addresses = set(query["address"])
            first = int(query["fromBlock"], 16)
            last = int(query["toBlock"], 16)
            return [
                log
                for log in event_logs
                if log["address"] in addresses
                and first <= int(log["blockNumber"], 16) <= last
            ]
        if method == "eth_getStorageAt":
            target, slot, block_tag = params
            assert target in safe_owners
            assert slot in {
                "0x" + SAFE_GUARD_STORAGE_SLOT.hex(),
                "0x" + SAFE_MODULE_GUARD_STORAGE_SLOT.hex(),
                "0x" + SAFE_FALLBACK_HANDLER_STORAGE_SLOT.hex(),
            }
            assert block_tag == hex(snapshot_number)
            return "0x" + bytes(32).hex()
        if method == "eth_call":
            assert params[1] == hex(snapshot_number)
            target = params[0]["to"]
            call_data = bytes.fromhex(params[0]["data"][2:])
            selector = call_data[:4].hex()
            arguments = call_data[4:]
            if selector == paused_selector:
                return "0x" + (bytes(31) + b"\x01").hex()
            if selector == has_role_selector:
                role = arguments[:32]
                account = "0x" + arguments[44:64].hex()
                present = (target, role, account) in role_memberships
                return "0x" + int(present).to_bytes(32, "big").hex()
            if target in safe_owners:
                if selector == master_copy_selector:
                    return "0x" + _word_address(safe_singleton).hex()
                if selector == threshold_selector:
                    return "0x" + safe_thresholds[target].to_bytes(32, "big").hex()
                if selector == nonce_selector:
                    return "0x" + bytes(32).hex()
                if selector == owners_selector:
                    owners = safe_owners[target]
                    encoded = (
                        (32).to_bytes(32, "big")
                        + len(owners).to_bytes(32, "big")
                        + b"".join(_word_address(owner) for owner in owners)
                    )
                    return "0x" + encoded.hex()
                if selector == modules_selector:
                    encoded = (
                        (64).to_bytes(32, "big")
                        + _word_address(_address(1))
                        + (0).to_bytes(32, "big")
                    )
                    return "0x" + encoded.hex()
            if target == authorities.timelock:
                if selector == keccak_256(b"getMinDelay()")[:4].hex():
                    return "0x" + (48 * 60 * 60).to_bytes(32, "big").hex()
                if selector in timelock_selectors:
                    return "0x" + timelock_selectors[selector].hex()
            if selector in zero_result_lengths:
                return "0x" + bytes(zero_result_lengths[selector]).hex()
            if target == modules["capability_router"].address and selector in selectors:
                return "0x" + _word_address(modules["adapter_registry"].address).hex()
            _signature, module_name = selectors[selector]
            return "0x" + _word_address(modules[module_name].address).hex()
        raise AssertionError(f"unexpected method: {method}")

    config = CanaryDeploymentConfig(
        environment="local",
        object_store_address=modules["object_store"].address,
        execution_kernel_address=modules["execution_kernel"].address,
        adapter_registry_address=modules["adapter_registry"].address,
    )
    binding = DomainAuthorityBinding(bytes.fromhex("ab" * 32), HostAuthority.POLYGON, 0)
    return (
        modules,
        authorities,
        control_identity,
        deployment_provenance_by_module,
        timelock_provenance,
        code_by_address,
        role_memberships,
        rpc_handler,
        config,
        binding,
    )


def test_polygon_height_provider_verifies_amoy_chain_id():
    rpc = EVMJsonRpcClient(
        "https://amoy-rpc.example",
        session=_RpcSession(
            lambda method, _params: hex(80_002) if method == "eth_chainId" else hex(123)
        ),
    )
    provider = PolygonAmoyHeightProvider(rpc)
    binding = DomainAuthorityBinding(bytes.fromhex("01" * 32), HostAuthority.POLYGON, 0)
    assert provider(binding) == 123


def test_cardano_height_provider_is_pinned_to_official_preprod_endpoint():
    provider = CardanoPreprodHeightProvider(
        CARDANO_PREPROD_BLOCKFROST_URL,
        "preprod-project",
        session=_BlockfrostSession(),
    )
    binding = DomainAuthorityBinding(bytes.fromhex("01" * 32), HostAuthority.CARDANO, 0)
    assert provider(binding) == 12_345

    with pytest.raises(RuntimeConfigurationError, match="official Cardano Pre-Prod"):
        CardanoPreprodHeightProvider(
            "https://cardano-mainnet.blockfrost.io/api/v0",
            "mainnet-project",
        )


def test_deployment_verifier_checks_all_codehashes_pause_wiring_and_empty_domain():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient(
            "https://amoy-rpc.example", session=_RpcSession(handler)
        ),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is True


def test_deployment_verifier_rejects_runtime_codehash_mismatch():
    modules, authorities, identity, provenance, timelock_provenance, codes, _roles, handler, config, binding = _deployment_fixture()
    codes[modules["object_store"].address] = b"\x60\xff"
    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient(
            "https://amoy-rpc.example", session=_RpcSession(handler)
        ),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_creation_receipt_address_mismatch():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    object_transaction = provenance["object_store"].transaction_hash

    def mismatched_receipt(method, params):
        result = handler(method, params)
        if (
            method == "eth_getTransactionReceipt"
            and bytes.fromhex(params[0][2:]) == object_transaction
        ):
            return {**result, "contractAddress": _address(999)}
        return result

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient(
            "https://amoy-rpc.example", session=_RpcSession(mismatched_receipt)
        ),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_deployer_privilege():
    modules, authorities, identity, provenance, timelock_provenance, _codes, roles, handler, config, binding = _deployment_fixture()
    roles.add((modules["execution_kernel"].address, EXECUTOR_ROLE, authorities.deployer))
    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(handler)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_unknown_role_from_complete_event_history():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    module_provenance = provenance["execution_kernel"]
    hidden_role_log = {
        "address": modules["execution_kernel"].address,
        "topics": [
            "0x" + ROLE_GRANTED_TOPIC.hex(),
            "0x" + keccak_256(b"HIDDEN_ROLE").hex(),
            "0x" + _word_address(_address(999)).hex(),
            "0x" + _word_address(authorities.deployer).hex(),
        ],
        "data": "0x",
        "blockNumber": hex(module_provenance.block_number),
        "blockHash": "0x" + module_provenance.block_hash.hex(),
        "transactionHash": "0x" + module_provenance.transaction_hash.hex(),
        "transactionIndex": "0x0",
        "logIndex": "0xffff",
        "removed": False,
    }

    def hidden_history(method, params):
        result = handler(method, params)
        if method == "eth_getLogs" and modules["execution_kernel"].address in params[0]["address"]:
            return [*result, hidden_role_log]
        return result

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(hidden_history)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_nonempty_or_malformed_registry_record():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    adapter_selector = keccak_256(b"getAdapter(bytes32)")[:4].hex()

    def malformed_adapter(method, params):
        if method == "eth_call" and params[0]["data"][2:10] == adapter_selector:
            # The final AdapterStatus ABI word is outside the NONE state.
            return "0x" + (bytes(384) + (2).to_bytes(32, "big")).hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient(
            "https://amoy-rpc.example", session=_RpcSession(malformed_adapter)
        ),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_safe_singleton_codehash_mismatch():
    modules, authorities, identity, provenance, timelock_provenance, codes, _roles, handler, config, binding = _deployment_fixture()
    codes[identity.safe_singleton] = b"\x60\xff"
    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(handler)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_enabled_safe_module():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    modules_selector = keccak_256(b"getModulesPaginated(address,uint256)")[:4].hex()

    def enabled_module(method, params):
        if (
            method == "eth_call"
            and params[0]["to"] == authorities.pause_council
            and params[0]["data"][2:10] == modules_selector
        ):
            encoded = (
                (64).to_bytes(32, "big")
                + _word_address(_address(1))
                + (1).to_bytes(32, "big")
                + _word_address(_address(777))
            )
            return "0x" + encoded.hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(enabled_module)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_safe_with_executed_transaction():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    nonce_selector = keccak_256(b"nonce()")[:4].hex()

    def used_safe(method, params):
        if (
            method == "eth_call"
            and params[0]["to"] == authorities.governance_safe
            and params[0]["data"][2:10] == nonce_selector
        ):
            return "0x" + (1).to_bytes(32, "big").hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(used_safe)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_safe_guard_or_fallback_storage():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()

    def guarded_safe(method, params):
        if method == "eth_getStorageAt" and params[0] == authorities.guardian:
            return "0x" + _word_address(_address(778)).hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(guarded_safe)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


@pytest.mark.parametrize(
    "signature",
    (
        "masterCopy()",
        "getThreshold()",
        "nonce()",
        "getOwners()",
        "getModulesPaginated(address,uint256)",
    ),
)
def test_deployment_verifier_rejects_reverting_safe_queries(signature):
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    selector = keccak_256(signature.encode())[:4].hex()

    def reverting_query(method, params):
        if (
            method == "eth_call"
            and params[0]["to"] == authorities.governance_safe
            and params[0]["data"][2:10] == selector
        ):
            raise RuntimeError("simulated Safe query revert")
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(reverting_query)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_malformed_safe_module_pagination():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()
    selector = keccak_256(b"getModulesPaginated(address,uint256)")[:4].hex()

    def malformed_page(method, params):
        if (
            method == "eth_call"
            and params[0]["to"] == authorities.governance_safe
            and params[0]["data"][2:10] == selector
        ):
            return "0x" + ((64).to_bytes(32, "big") + _word_address(_address(2)) + bytes(32)).hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(malformed_page)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_malformed_safe_storage_return():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()

    def malformed_storage(method, params):
        if method == "eth_getStorageAt" and params[0] == authorities.governance_safe:
            return "0x" + bytes(31).hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(malformed_storage)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_deployment_verifier_rejects_safe_module_guard_storage():
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, handler, config, binding = _deployment_fixture()

    def module_guard(method, params):
        if (
            method == "eth_getStorageAt"
            and params[0] == authorities.recovery_authority
            and params[1] == "0x" + SAFE_MODULE_GUARD_STORAGE_SLOT.hex()
        ):
            return "0x" + _word_address(_address(779)).hex()
        return handler(method, params)

    verifier = PolygonAmoyDeploymentVerifier(
        EVMJsonRpcClient("https://amoy-rpc.example", session=_RpcSession(module_guard)),
        modules,
        authorities,
        identity,
        provenance,
        timelock_provenance,
    )
    assert verifier(config, binding) is False


def test_private_shadow_import_factory_builds_real_provider_composition(monkeypatch):
    modules, authorities, identity, provenance, timelock_provenance, _codes, _roles, _handler, _config, _binding = _deployment_fixture()
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("VAMS_NETWORK", "polygon-amoy")
    monkeypatch.setenv("VDSO_MODE", "shadow")
    monkeypatch.setenv("VDSO_POSTGRES_DSN", "postgresql://shadow-test")
    monkeypatch.setenv("VDSO_AMOY_RPC_URL", "https://amoy-rpc.example")
    for module_name, environment_prefix in (
        ("object_store", "VDSO_OBJECT_STORE"),
        ("reservation_manager", "VDSO_RESERVATION_MANAGER"),
        ("adapter_registry", "VDSO_ADAPTER_REGISTRY"),
        ("program_registry", "VDSO_PROGRAM_REGISTRY"),
        ("proof_router", "VDSO_PROOF_ROUTER"),
        ("capability_router", "VDSO_CAPABILITY_ROUTER"),
        ("execution_kernel", "VDSO_EXECUTION_KERNEL"),
    ):
        monkeypatch.setenv(f"{environment_prefix}_ADDRESS", modules[module_name].address)
        monkeypatch.setenv(
            f"{environment_prefix}_CODE_HASH",
            "0x" + modules[module_name].code_hash.hex(),
        )
        module_provenance = provenance[module_name]
        monkeypatch.setenv(
            f"{environment_prefix}_DEPLOYMENT_TX_HASH",
            "0x" + module_provenance.transaction_hash.hex(),
        )
        monkeypatch.setenv(
            f"{environment_prefix}_DEPLOYMENT_BLOCK_NUMBER",
            str(module_provenance.block_number),
        )
        monkeypatch.setenv(
            f"{environment_prefix}_DEPLOYMENT_BLOCK_HASH",
            "0x" + module_provenance.block_hash.hex(),
        )
    for name, value in {
        "VAMS_VDSO_GOVERNANCE_SAFE": authorities.governance_safe,
        "VAMS_VDSO_TIMELOCK": authorities.timelock,
        "VAMS_VDSO_PAUSE_COUNCIL": authorities.pause_council,
        "VAMS_VDSO_GUARDIAN": authorities.guardian,
        "VAMS_VDSO_RECOVERY_AUTHORITY": authorities.recovery_authority,
        "VAMS_VDSO_DEPLOYER": authorities.deployer,
        "VAMS_VDSO_SAFE_PROXY_RUNTIME_CODE_HASH": "0x"
        + identity.safe_proxy_code_hash.hex(),
        "VAMS_VDSO_SAFE_SINGLETON": identity.safe_singleton,
        "VAMS_VDSO_SAFE_SINGLETON_RUNTIME_CODE_HASH": "0x"
        + identity.safe_singleton_code_hash.hex(),
        "VAMS_VDSO_TIMELOCK_RUNTIME_CODE_HASH": "0x"
        + identity.timelock_code_hash.hex(),
        "VAMS_VDSO_TIMELOCK_DEPLOYMENT_TX_HASH": "0x"
        + timelock_provenance.transaction_hash.hex(),
        "VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_NUMBER": str(
            timelock_provenance.block_number
        ),
        "VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_HASH": "0x"
        + timelock_provenance.block_hash.hex(),
    }.items():
        monkeypatch.setenv(name, value)

    app = server.create_shadow_app()
    assert app.state.vdso_mode == "shadow"
    assert any(path.startswith("/v1/vdso") for path in app.openapi()["paths"])


def test_private_shadow_factory_rejects_missing_real_provider_config(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("VAMS_NETWORK", "polygon-amoy")
    monkeypatch.setenv("VDSO_MODE", "shadow")
    monkeypatch.delenv("VDSO_AMOY_RPC_URL", raising=False)
    with pytest.raises(RuntimeConfigurationError, match="VDSO_AMOY_RPC_URL"):
        server.create_shadow_app()


class _SerializingSession:
    def __init__(self):
        self._guard = threading.Lock()
        self.active = 0
        self.max_active = 0

    def post(self, _url, *, json, timeout):
        with self._guard:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.005)
        with self._guard:
            self.active -= 1
        return _Response({"jsonrpc": "2.0", "id": json["id"], "result": "0x1"})


def test_rpc_client_serializes_shared_session_and_request_ids():
    session = _SerializingSession()
    rpc = EVMJsonRpcClient("https://amoy-rpc.example", session=session)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: rpc.call("eth_chainId", []), range(32)))
    assert results == ["0x1"] * 32
    assert session.max_active == 1
