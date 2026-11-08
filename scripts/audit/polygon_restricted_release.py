"""Restricted EVM package consistency; not runtime/proof/reviewer authentication.

All records remain subject to the full assurance, signature, runtime and live
qualification gates. Hash-bound declarations alone do not prove their contents.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re

PROFILE = 'restricted-testnet-v1'
PREFIX = Path('docs/audit/evidence/polygon-restricted-v1')
ARTIFACT_SOURCES = {
    'VAMSToken': 'contracts/src/token/VAMSToken.sol',
    'VAMSRestrictedStaking': 'contracts/src/staking/VAMSRestrictedStaking.sol',
    'VAMSTimelockController': 'contracts/src/governance/VAMSTimelockController.sol',
    'VAMSSentinel': 'contracts/src/sentinel/VAMSSentinel.sol',
    'ServiceBlockRegistry': 'contracts/src/registry/ServiceBlockRegistry.sol',
    'ProviderBondRegistry': 'contracts/src/economic/ProviderBondRegistry.sol',
    'RestrictedTestnetPolicyV1': 'contracts/src/trust/RestrictedTestnetPolicyV1.sol',
    'ActionDeliveryVerifierV1': 'contracts/src/trust/ActionDeliveryVerifierV1.sol',
    'AutomataSgxActionVerifierV1': 'contracts/src/trust/AutomataSgxActionVerifierV1.sol',
    'EzklActionVerifierV1': 'contracts/src/trust/EzklActionVerifierV1.sol',
    'ComposedSettlement': 'contracts/src/economic/ComposedSettlement.sol',
}
RECORDS = {'build', 'state_readback', 'activation_tests', 'dcap_qualification',
           'ezkl_qualification', 'insurance_custody'}
ACTIVATION = {
    'reward_per_second': 0, 'annual_emission_budget': 0,
    'staking_rewards_enabled': False, 'staking_minter_enabled': False,
    'vesting_enabled': False, 'buyback_enabled': False, 'delegation_enabled': False,
    'ordinary_token_governor_enabled': False, 'deposits_enabled': False,
    'slash_activation_enabled': False, 'execute_intent_enabled': False,
    'real_fiat_enabled': False, 'real_yield_enabled': False,
}
PARAMETERS = {'host_domain', 'budget_unit', 'insurance_recipient',
              'insurance_recipient_code_hash', 'sgx', 'ezkl'}
SGX_FIELDS = {'backend', 'backend_code_hash', 'collateral_router', 'collateral_router_code_hash',
              'enclave_measurement', 'signer_measurement', 'runtime_id', 'minimum_svn', 'tcb_evaluation'}
EZKL_FIELDS = {'backend', 'backend_code_hash', 'model_hash', 'circuit_manifest_hash'}


def _hex(value: object, size: int, prefix: str = '0x') -> bool:
    return (isinstance(value, str)
            and re.fullmatch(re.escape(prefix) + '[0-9a-fA-F]{' + str(size) + '}', value) is not None
            and int(value[len(prefix):], 16) != 0)


def _int(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _same(actual: object, expected: object) -> bool:
    """JSON bool/int/float equality must not erase the public type contract."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(_same(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _reference(value: object, root: Path) -> Path | None:
    if not isinstance(value, dict) or set(value) != {'path', 'sha256'}:
        return None
    raw = value.get('path')
    if not isinstance(raw, str) or '\\' in raw or ':' in raw:
        return None
    relative = PurePosixPath(raw)
    if relative.is_absolute() or '..' in relative.parts or relative.as_posix() != raw:
        return None
    try:
        relative.relative_to(PREFIX.as_posix())
        path = (root / raw).resolve()
        path.relative_to((root / PREFIX).resolve())
        path.relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    if (not path.is_file() or path.stat().st_size == 0
            or not isinstance(value.get('sha256'), str)
            or re.fullmatch('[0-9a-f]{64}', value['sha256']) is None):
        return None
    return path if hashlib.sha256(path.read_bytes()).hexdigest() == value['sha256'] else None


def referenced_paths(manifest: dict, root: Path) -> list[Path]:
    package = manifest.get('restricted_evm')
    if manifest.get('network') != 'polygon-amoy' or not isinstance(package, dict):
        return []
    records = package.get('records')
    if not isinstance(records, dict):
        return []
    return [path for value in records.values() if (path := _reference(value, root)) is not None]


def expected_bindings(artifacts: dict[str, dict], authorities: dict[str, dict], parameters: dict) -> dict:
    """Constructor/configuration observations; labels are not assumed RPC getters."""
    address = lambda name: artifacts.get(name, {}).get('address')
    code = lambda name: artifacts.get(name, {}).get('runtime_code_hash')
    timelock = address('VAMSTimelockController')
    sgx = parameters.get('sgx', {})
    ezkl = parameters.get('ezkl', {})
    return {
        'VAMSRestrictedStaking': {'token': address('VAMSToken'), 'governance': timelock},
        'ServiceBlockRegistry': {'token': address('VAMSToken'), 'admin': timelock},
        'ProviderBondRegistry': {'token': address('VAMSToken'), 'admin': timelock,
                                 'insurance_recipient': parameters.get('insurance_recipient')},
        'ComposedSettlement': {'token': address('VAMSToken'), 'admin': timelock,
            'bond_registry': address('ProviderBondRegistry'),
            'treasury': authorities.get('treasury', {}).get('address'),
            'service_registry': address('ServiceBlockRegistry'),
            'delivery_verifier': address('ActionDeliveryVerifierV1')},
        'RestrictedTestnetPolicyV1': {'governance': timelock,
            'host_domain': parameters.get('host_domain'), 'budget_unit': parameters.get('budget_unit')},
        'ActionDeliveryVerifierV1': {'policy': address('RestrictedTestnetPolicyV1'),
            'policy_code_hash': code('RestrictedTestnetPolicyV1'),
            'sgx': address('AutomataSgxActionVerifierV1'), 'sgx_code_hash': code('AutomataSgxActionVerifierV1'),
            'ezkl': address('EzklActionVerifierV1'), 'ezkl_code_hash': code('EzklActionVerifierV1')},
        'AutomataSgxActionVerifierV1': dict(sgx),
        'EzklActionVerifierV1': dict(ezkl),
    }


def expected_roles(artifacts: dict[str, dict]) -> dict:
    timelock = artifacts.get('VAMSTimelockController', {}).get('address')
    return {
        'VAMSToken': {'DEFAULT_ADMIN_ROLE': [timelock], 'PAUSER_ROLE': [timelock], 'MINTER_ROLE': []},
        'ServiceBlockRegistry': {'DEFAULT_ADMIN_ROLE': [timelock], 'VERIFIER_ROLE': [timelock]},
        'ProviderBondRegistry': {'DEFAULT_ADMIN_ROLE': [timelock], 'ADMIN_ROLE': [timelock],
            'PAUSER_ROLE': [timelock], 'ESCROW_ROLE': [artifacts.get('ComposedSettlement', {}).get('address')],
            'SLASHER_ROLE': [], 'HARDWARE_COMMITMENT_ROLE': [], 'SENTINEL_ROLE': []},
        'ComposedSettlement': {'DEFAULT_ADMIN_ROLE': [timelock], 'ADMIN_ROLE': [timelock],
                               'PAUSER_ROLE': [timelock]},
    }


def validate_package(manifest: dict, root: Path, artifacts: dict, authorities: dict) -> list[str]:
    errors = []
    context = 'polygon-amoy restricted profile'
    if manifest.get('schema_version') != '2.0.0' or manifest.get('release_profile') != PROFILE:
        errors.append(f'{context} requires schema 2.0.0 and {PROFILE}; legacy governance is retired')
    if manifest.get('chain_identifier') != '80002':
        errors.append(f'{context} chain_identifier must equal 80002')
    for name in ARTIFACT_SOURCES:
        if not _hex(artifacts.get(name, {}).get('runtime_code_hash'), 64):
            errors.append(f'{context} {name} runtime identity must be nonzero')
    package = manifest.get('restricted_evm')
    if not isinstance(package, dict):
        return errors + [f'{context} package is missing']
    if set(package) != {'schema', 'parameters', 'bindings', 'role_memberships', 'activation', 'records'}:
        errors.append(f'{context} package fields are invalid')
    if package.get('schema') != 'vams.restricted-evm-release.v1':
        errors.append(f'{context} package schema is invalid')
    parameters = package.get('parameters')
    if not isinstance(parameters, dict) or set(parameters) != PARAMETERS:
        return errors + [f'{context} parameters are missing or invalid']
    for field in ('host_domain', 'budget_unit', 'insurance_recipient_code_hash'):
        if not _hex(parameters.get(field), 64):
            errors.append(f'{context} {field} must be a nonzero bytes32')
    if not _hex(parameters.get('insurance_recipient'), 40):
        errors.append(f'{context} insurance_recipient must be a nonzero address')
    sgx, ezkl = parameters.get('sgx'), parameters.get('ezkl')
    if not isinstance(sgx, dict) or set(sgx) != SGX_FIELDS:
        errors.append(f'{context} SGX parameters are invalid')
    else:
        for field in SGX_FIELDS - {'minimum_svn', 'tcb_evaluation'}:
            if not _hex(sgx[field], 40 if field in {'backend', 'collateral_router'} else 64):
                errors.append(f'{context} SGX {field} is invalid')
        if not _int(sgx['minimum_svn'], 0, 2**16 - 1):
            errors.append(f'{context} minimum_svn is invalid')
        if not _int(sgx['tcb_evaluation'], 1, 2**32 - 1):
            errors.append(f'{context} tcb_evaluation is invalid')
    if not isinstance(ezkl, dict) or set(ezkl) != EZKL_FIELDS:
        errors.append(f'{context} EZKL parameters are invalid')
    else:
        for field in EZKL_FIELDS:
            if not _hex(ezkl[field], 40 if field == 'backend' else 64):
                errors.append(f'{context} EZKL {field} is invalid')
    if not isinstance(sgx, dict) or not isinstance(ezkl, dict):
        return errors
    if not _same(package.get('bindings'), expected_bindings(artifacts, authorities, parameters)):
        errors.append(f'{context} constructor/configuration bindings do not match declared identities')
    if not _same(package.get('role_memberships'), expected_roles(artifacts)):
        errors.append(f'{context} role memberships differ; exact settlement ESCROW_ROLE and disabled minter/slasher required')
    if not _same(package.get('activation'), ACTIVATION):
        errors.append(f'{context} restricted activation must match the disabled economic/action profile')
    records = package.get('records')
    if not isinstance(records, dict) or set(records) != RECORDS:
        errors.append(f'{context} records must cover build/readback/activation/DCAP/EZKL/insurance')
    else:
        paths = []
        for name in sorted(RECORDS):
            path = _reference(records[name], root)
            if path is None:
                errors.append(f'{context} {name} record is missing, unsafe or hash-mismatched')
            else:
                paths.append(path)
        if len(paths) != len(set(paths)):
            errors.append(f'{context} requires distinct scoped evidence records')
    return errors
