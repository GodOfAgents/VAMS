"""Cardano v2 package consistency, never a substitute for native qualification.

No compiler, ledger, signer or provider is invoked. A consistent package still
needs authentic build/ledger/review evidence and the signed full release gates.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath


GOVERNANCE_SOURCE = 'cardano/validators/governance_v2.ak'
PROGRAMS = {
    'governance_authority_v2', 'governor_v2', 'timelock_v2',
    'proposal_policy_v2', 'receipt_policy_v2', 'intent_policy_v2',
}
ARTIFACT_SOURCES = {
    **{name: GOVERNANCE_SOURCE for name in PROGRAMS},
    'insurance_fund.ak': 'cardano/validators/insurance_fund.ak',
    'agent_registry.ak': 'cardano/validators/agent_registry.ak',
}
BUILD_REFERENCES = (
    'build_evidence', 'native_test_evidence', 'ledger_evidence',
    'budget_evidence', 'parameters_evidence', 'review_evidence',
)
PREFIX = 'docs/audit/evidence/cardano-v2/'
SHA256 = re.compile(r'[0-9a-f]{64}')


def enterprise_testnet_address(script_hash: str) -> str:
    """CIP-19 type7/network0 for the v2 stake-less script address profile.

    Testnet0 does not distinguish Pre-Prod from Preview. Genesis/network-magic
    qualification remains an independent ledger/operator requirement.
    """
    if not isinstance(script_hash, str) or re.fullmatch(r'[0-9a-f]{56}', script_hash) is None:
        raise ValueError('canonical script hash required')
    # This fixed29-byte address uses47 padded base32 groups (three zero bits).
    number = int.from_bytes(b'\x70' + bytes.fromhex(script_hash), 'big') << 3
    groups = [(number >> (5 * index)) & 31 for index in range(46, -1, -1)]
    prefix = 'addr_test'
    symbols = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'
    stream = [ord(char) >> 5 for char in prefix] + [0] + [ord(char) & 31 for char in prefix]
    residue = 1
    polynomials = (0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)
    for group in stream + groups + [0] * 6:
        high = residue >> 25
        residue = ((residue & 0x1ffffff) << 5) ^ group
        for index, polynomial in enumerate(polynomials):
            if high & (1 << index):
                residue ^= polynomial
    residue ^= 1
    checksum = [(residue >> (5 * index)) & 31 for index in range(5, -1, -1)]
    return prefix + '1' + ''.join(symbols[group] for group in groups + checksum)


def _hash(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None and value != '0' * 64


def _path(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative.startswith(PREFIX) or '\\' in relative:
        return None
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != relative:
        return None
    candidate = root / relative
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return candidate


def reference_bytes(reference: object, root: Path, context: str) -> tuple[list[str], bytes | None]:
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'}:
        return [f'{context}: exact path/sha256 artifact reference required'], None
    path = _path(root, reference['path'])
    if path is None:
        return [f'{context}: artifact must stay inside {PREFIX}'], None
    if not _hash(reference['sha256']):
        return [f'{context}: invalid artifact hash'], None
    if not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
        return [f'{context}: artifact missing, empty or oversized'], None
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != reference['sha256']:
        return [f'{context}: artifact hash mismatch'], None
    return [], data


def source_inputs(root: Path) -> dict[str, str]:
    paths = [root / 'cardano' / name for name in
             ('aiken.toml', 'aiken.lock', 'aiken-dependency-manifest.json')]
    for directory in ('lib', 'validators'):
        paths.extend((root / 'cardano' / directory).rglob('*.ak'))
    required = set(paths[:3]) | {root / value for value in ARTIFACT_SOURCES.values()}
    required |= {root / f'cardano/lib/vams/{name}.ak' for name in (
        'governance_v2', 'governance_v2_types', 'governance_v2_transitions', 'governance_v2_vectors')}
    if any(not path.is_file() for path in required):
        raise ValueError('required current Cardano source/dependency input is missing')
    inputs = {}
    for path in sorted(set(paths) | required):
        try:
            path.resolve().relative_to(root.resolve())
        except (ValueError, OSError):
            raise ValueError('Cardano source input escapes the release repository') from None
        inputs[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return inputs


def referenced_paths(manifest: dict, root: Path) -> list[Path]:
    """Collect the bounded direct package references for aggregate signing."""
    if manifest.get('network') != 'cardano-preprod':
        return []
    references = []
    build = manifest.get('cardano_build')
    if isinstance(build, dict):
        references.extend(build.get(name) for name in BUILD_REFERENCES)
    artifacts = manifest.get('artifacts')
    if isinstance(artifacts, list):
        references.extend(item.get('compiled_script') for item in artifacts if isinstance(item, dict))
    result = set()
    for reference in references:
        if isinstance(reference, dict):
            path = _path(root, reference.get('path'))
            if path is not None:
                result.add(path)
    return sorted(result)


def validate_package(manifest: dict, root: Path, artifacts: dict[str, dict]) -> list[str]:
    errors = []
    if set(artifacts) != set(ARTIFACT_SOURCES):
        errors.append('cardano-preprod package must contain exactly the eight current artifacts')
    if manifest.get('schema_version') != '2.0.0':
        errors.append('cardano-preprod deployment schema_version must equal 2.0.0; legacy governance is retired')
    build = manifest.get('cardano_build')
    if not isinstance(build, dict):
        return errors + ['cardano-preprod authenticated-governance build package is missing']
    expected_fields = {
        'schema', 'compiler_name', 'compiler_version', 'compiler_binary_sha256',
        'runner_id', 'language', 'source_files', 'governance_version',
        'normal_delay_seconds', 'cancel_threshold', 'execute_intent_enabled',
        *BUILD_REFERENCES,
    }
    if set(build) != expected_fields:
        errors.append('cardano-preprod build package has missing or unexpected fields')
    exact = {
        'schema': 'vams.cardano-governance-build.v2', 'compiler_name': 'aiken',
        'compiler_version': '1.1.21', 'language': 'plutus-v3',
        'governance_version': 2, 'normal_delay_seconds': 172800, 'cancel_threshold': 3,
    }
    for field, expected in exact.items():
        if type(build.get(field)) is not type(expected) or build[field] != expected:
            errors.append(f'cardano-preprod build {field} must equal {expected}')
    if build.get('execute_intent_enabled') is not False:
        errors.append('cardano-preprod build must preserve ExecuteIntent rejection')
    if not _hash(build.get('compiler_binary_sha256')):
        errors.append('cardano-preprod build compiler binary hash is invalid')
    runner = build.get('runner_id')
    if not isinstance(runner, str) or not runner.strip() or runner.strip().lower() in {'unknown', 'pending'}:
        errors.append('cardano-preprod build runner identity is missing; approval remains separate')
    try:
        current = source_inputs(root)
    except (ValueError, OSError) as error:
        errors.append(f'cardano-preprod build source input error: {error}')
        current = None
    if current is None or build.get('source_files') != current:
        errors.append('cardano-preprod build source files must exactly match current Aiken source and dependency inputs')
    for field in BUILD_REFERENCES:
        issues, _ = reference_bytes(build.get(field), root, f'cardano-preprod {field}')
        errors.extend(issues)
    script_hashes = []
    for name, expected_source in sorted(ARTIFACT_SOURCES.items()):
        artifact = artifacts.get(name)
        if not isinstance(artifact, dict):
            errors.append(f'cardano-preprod current artifact missing: {name}')
            continue
        if artifact.get('source') != expected_source:
            errors.append(f'cardano-preprod {name} must bind current source {expected_source}')
        if current is not None and artifact.get('source_sha256') != current.get(expected_source):
            errors.append(f'cardano-preprod {name} source hash differs from current build input')
        issues, data = reference_bytes(artifact.get('compiled_script'), root, f'cardano-preprod {name} compiled script')
        errors.extend(issues)
        if data is None:
            continue
        # Raw bytes are the serialized Plutus script (CIP-57 compiledCode bytes),
        # not a JSON text envelope, hex text or an extra CBOR wrapping layer.
        actual_sha = hashlib.sha256(data).hexdigest()
        actual_hash = hashlib.blake2b(b'\x03' + data, digest_size=28).hexdigest()
        if artifact.get('script_cbor_sha256') != actual_sha or artifact.get('artifact_sha256') != actual_sha:
            errors.append(f'cardano-preprod {name} artifact/CBOR hashes do not bind exact script bytes')
        if artifact.get('script_hash') != actual_hash:
            errors.append(f'cardano-preprod {name} Plutus-v3 script hash does not match script bytes')
        if name in PROGRAMS and artifact.get('address') != enterprise_testnet_address(actual_hash):
            errors.append(f'cardano-preprod {name} address does not match its canonical script identity')
        script_hashes.append(actual_hash)
    if len(script_hashes) != len(set(script_hashes)):
        errors.append('cardano-preprod applied programs must have distinct script identities')
    authorities = manifest.get('authorities')
    authority = authorities.get('governance') if isinstance(authorities, dict) else None
    if not isinstance(authority, dict):
        errors.append('cardano-preprod governance authority is missing')
        authority = {}
    artifact = artifacts.get('governance_authority_v2', {})
    for field, artifact_field in (('script_hash', 'script_hash'), ('script_cbor_sha256', 'script_cbor_sha256'),
                                  ('address', 'address'), ('script_source', 'source'), ('script_source_sha256', 'source_sha256')):
        if authority.get(field) != artifact.get(artifact_field):
            errors.append(f'cardano-preprod governance authority {field} does not match authenticated authority artifact')
    return errors
