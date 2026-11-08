from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("audit_program.py")
SPEC = importlib.util.spec_from_file_location("audit_program", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
audit_program = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_program)


def _evm_address(value: int) -> str:
    return f"0x{value:040x}"


def _hex(value: int, length: int) -> str:
    return f"{value:0{length}x}"[-length:]


def _write_source(root: Path, relative_path: str) -> str:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"source:{relative_path}", encoding="utf-8")
    return audit_program.hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_deployment_manifest(root: Path, network: str, commit: str) -> dict:
    required = (
        {"VAMSToken", "VAMSStaking", "VAMSVesting", "VAMSGovernor", "VAMSTimelockController", "VAMSSentinel"}
        if network == "polygon-amoy"
        else {"governor.ak", "timelock.ak", "insurance_fund.ak", "agent_registry.ak"}
    )
    artifacts: list[dict] = []
    for index, name in enumerate(sorted(required), start=1):
        source = audit_program.DEPLOYMENT_ARTIFACT_SOURCES[name]
        artifact = {
            "name": name,
            "source": source,
            "source_sha256": _write_source(root, source),
            "artifact_sha256": _hex(1000 + index, 64),
            "verification": "simulation-passed",
        }
        if network == "polygon-amoy":
            artifact.update(
                {
                    "address": _evm_address(1000 + index),
                    "runtime_code_hash": "0x" + _hex(2000 + index, 64),
                }
            )
        else:
            artifact.update(
                {
                    "address": f"addr_test1script{index}",
                    "script_hash": _hex(3000 + index, 56),
                    "script_cbor_sha256": _hex(4000 + index, 64),
                }
            )
        artifacts.append(artifact)
    by_name = {artifact["name"]: artifact for artifact in artifacts}

    if network == "polygon-amoy":
        deployer = _evm_address(1)
        authorities = {}
        for offset, (name, owner_count, threshold) in enumerate(
            (("governance", 5, 3), ("treasury", 5, 3), ("emergency", 3, 2)),
            start=1,
        ):
            authority = {
                "authority_type": "safe",
                "address": _evm_address(100 + offset),
                "owners": [_evm_address(offset * 20 + i) for i in range(owner_count)],
                "threshold": threshold,
                "proxy_runtime_code_hash": "0x" + _hex(5000 + offset, 64),
                "singleton_address": _evm_address(200 + offset),
                "singleton_runtime_code_hash": "0x" + _hex(6000 + offset, 64),
                "identity_check_evidence_sha256": _hex(7000 + offset, 64),
                "recovery_policy": f"{name} recovery runbook",
            }
            if name == "emergency":
                authority["scope"] = "pause-only"
            authorities[name] = authority
        timelock_artifact = by_name["VAMSTimelockController"]
        governor_artifact = by_name["VAMSGovernor"]
        timelock_source = audit_program.DEPLOYMENT_ARTIFACT_SOURCES[
            "VAMSTimelockController"
        ]
        timelock_address = timelock_artifact["address"]
        roles = [
            ("DEFAULT_ADMIN_ROLE", timelock_address, True),
            ("PROPOSER_ROLE", authorities["governance"]["address"], True),
            ("PROPOSER_ROLE", governor_artifact["address"], True),
            ("CANCELLER_ROLE", authorities["governance"]["address"], True),
            ("EXECUTOR_ROLE", audit_program.EVM_ZERO_ADDRESS, True),
            ("DEFAULT_ADMIN_ROLE", deployer, False),
        ]
        timelock_identity = {
            "identity_type": "evm-runtime",
            "address": timelock_address,
            "source": timelock_source,
            "source_sha256": _write_source(root, timelock_source),
            "actual_runtime_code_hash": timelock_artifact["runtime_code_hash"],
            "expected_runtime_code_hash": timelock_artifact["runtime_code_hash"],
            "minimum_delay_seconds": 172800,
            "roles": [
                {
                    "role": role,
                    "account": account,
                    "granted": granted,
                    "observed_at_block": 1,
                    "evidence_sha256": _hex(8000 + index, 64),
                }
                for index, (role, account, granted) in enumerate(roles)
            ],
        }
        role_transfers = [
            {
                "target": timelock_address,
                "role": "DEFAULT_ADMIN_ROLE",
                "action": "grant",
                "account": timelock_address,
                "verified": True,
                "observed_at_block": 1,
                "evidence_sha256": _hex(9001, 64),
            },
            {
                "target": timelock_address,
                "role": "DEFAULT_ADMIN_ROLE",
                "action": "renounce",
                "account": deployer,
                "verified": True,
                "observed_at_block": 1,
                "evidence_sha256": _hex(9002, 64),
            },
        ]
        privilege_checks = [
            {
                "artifact": name,
                "account": deployer,
                "privilege": "ANY_PRIVILEGED_ROLE",
                "granted": False,
                "observed_at_block": 1,
                "evidence_sha256": _hex(10000 + index, 64),
            }
            for index, name in enumerate(sorted(required))
        ]
    else:
        deployer = _hex(1, 56)
        authorities = {}
        for offset, (name, owner_count, threshold) in enumerate(
            (("governance", 5, 3), ("treasury", 5, 3), ("emergency", 3, 2)),
            start=1,
        ):
            source = f"cardano/authorities/{name}.ak"
            authority = {
                "authority_type": "cardano-script",
                "address": f"addr_test1authority{offset}",
                "owners": [_hex(offset * 20 + i, 56) for i in range(owner_count)],
                "threshold": threshold,
                "script_hash": _hex(11000 + offset, 56),
                "script_cbor_sha256": _hex(12000 + offset, 64),
                "script_source": source,
                "script_source_sha256": _write_source(root, source),
                "identity_check_evidence_sha256": _hex(13000 + offset, 64),
                "recovery_policy": f"{name} recovery runbook",
            }
            if name == "emergency":
                authority["scope"] = "pause-only"
            authorities[name] = authority
        timelock_artifact = by_name["timelock.ak"]
        governor_artifact = by_name["governor.ak"]
        timelock_source = audit_program.DEPLOYMENT_ARTIFACT_SOURCES["timelock.ak"]
        timelock_identity = {
            "identity_type": "plutus-script",
            "script_address": timelock_artifact["address"],
            "script_hash": timelock_artifact["script_hash"],
            "source": timelock_source,
            "source_sha256": _write_source(root, timelock_source),
            "actual_script_cbor_sha256": timelock_artifact["script_cbor_sha256"],
            "expected_script_cbor_sha256": timelock_artifact["script_cbor_sha256"],
            "governor_script_hash": governor_artifact["script_hash"],
            "minimum_delay_seconds": 172800,
            "cancel_threshold": 2,
            "observed_at_slot": 1,
            "control_evidence_sha256": _hex(14000, 64),
        }
        role_transfers = [
            {
                "control": "governor-binding",
                "action": "handoff",
                "from_credential": deployer,
                "to_script_hash": governor_artifact["script_hash"],
                "verified": True,
                "observed_at_slot": 1,
                "evidence_sha256": _hex(15001, 64),
            },
            {
                "control": "deployer-retirement",
                "action": "retire-deployer",
                "from_credential": deployer,
                "to_script_hash": timelock_artifact["script_hash"],
                "verified": True,
                "observed_at_slot": 1,
                "evidence_sha256": _hex(15002, 64),
            },
        ]
        privilege_checks = [
            {
                "artifact": name,
                "credential": deployer,
                "can_authorize": False,
                "observed_at_slot": 1,
                "evidence_sha256": _hex(16000 + index, 64),
            }
            for index, name in enumerate(sorted(required))
        ]

    return {
        "schema_version": "1.0.0",
        "network": network,
        "deployment_status": "rehearsed",
        "commit_sha": commit,
        "chain_identifier": f"test:{network}",
        "deployer": deployer,
        "deployer_privileges_removed": True,
        "deployer_privilege_checks": privilege_checks,
        "mock_routes_disabled": True,
        "timelock_seconds": 172800,
        "timelock_identity": timelock_identity,
        "authorities": authorities,
        "artifacts": artifacts,
        "role_transfers": role_transfers,
        "rollback_plan": f"rollback {network} using the signed runbook",
    }


def _restricted_polygon_manifest(root: Path, manifest: dict) -> dict:
    """Opaque synthetic metadata only; no deployment, readback or genuine proof."""
    from scripts.audit import polygon_restricted_release as package
    artifacts = []
    for index, (name, source) in enumerate(sorted(package.ARTIFACT_SOURCES.items()), 1):
        artifacts.append({'name': name, 'source': source, 'source_sha256': _write_source(root, source),
            'artifact_sha256': _hex(1000 + index, 64), 'verification': 'simulation-passed',
            'address': _evm_address(1000 + index), 'runtime_code_hash': '0x' + _hex(2000 + index, 64)})
    by_name = {item['name']: item for item in artifacts}
    address = lambda name: by_name[name]['address']
    code = lambda name: by_name[name]['runtime_code_hash']
    timelock = address('VAMSTimelockController')
    parameters = {'host_domain': '0x' + '1' * 64, 'budget_unit': '0x' + '2' * 64,
        'insurance_recipient': _evm_address(3001), 'insurance_recipient_code_hash': '0x' + '3' * 64,
        'sgx': {'backend': _evm_address(3002), 'backend_code_hash': '0x' + '4' * 64,
            'collateral_router': _evm_address(3003), 'collateral_router_code_hash': '0x' + '5' * 64,
            'enclave_measurement': '0x' + '6' * 64, 'signer_measurement': '0x' + '7' * 64,
            'runtime_id': '0x' + '8' * 64, 'minimum_svn': 1, 'tcb_evaluation': 1},
        'ezkl': {'backend': _evm_address(3004), 'backend_code_hash': '0x' + '9' * 64,
            'model_hash': '0x' + 'a' * 64, 'circuit_manifest_hash': '0x' + 'b' * 64}}
    bindings = {
        'VAMSRestrictedStaking': {'token': address('VAMSToken'), 'governance': timelock},
        'ServiceBlockRegistry': {'token': address('VAMSToken'), 'admin': timelock},
        'ProviderBondRegistry': {'token': address('VAMSToken'), 'admin': timelock,
                                 'insurance_recipient': parameters['insurance_recipient']},
        'ComposedSettlement': {'token': address('VAMSToken'), 'admin': timelock,
            'bond_registry': address('ProviderBondRegistry'),
            'treasury': manifest['authorities']['treasury']['address'],
            'service_registry': address('ServiceBlockRegistry'), 'delivery_verifier': address('ActionDeliveryVerifierV1')},
        'RestrictedTestnetPolicyV1': {'governance': timelock,
            'host_domain': parameters['host_domain'], 'budget_unit': parameters['budget_unit']},
        'ActionDeliveryVerifierV1': {'policy': address('RestrictedTestnetPolicyV1'),
            'policy_code_hash': code('RestrictedTestnetPolicyV1'), 'sgx': address('AutomataSgxActionVerifierV1'),
            'sgx_code_hash': code('AutomataSgxActionVerifierV1'), 'ezkl': address('EzklActionVerifierV1'),
            'ezkl_code_hash': code('EzklActionVerifierV1')},
        'AutomataSgxActionVerifierV1': dict(parameters['sgx']), 'EzklActionVerifierV1': dict(parameters['ezkl'])}
    roles = {
        'VAMSToken': {'DEFAULT_ADMIN_ROLE': [timelock], 'PAUSER_ROLE': [timelock], 'MINTER_ROLE': []},
        'ServiceBlockRegistry': {'DEFAULT_ADMIN_ROLE': [timelock], 'VERIFIER_ROLE': [timelock]},
        'ProviderBondRegistry': {'DEFAULT_ADMIN_ROLE': [timelock], 'ADMIN_ROLE': [timelock],
            'PAUSER_ROLE': [timelock], 'ESCROW_ROLE': [address('ComposedSettlement')],
            'SLASHER_ROLE': [], 'HARDWARE_COMMITMENT_ROLE': [], 'SENTINEL_ROLE': []},
        'ComposedSettlement': {'DEFAULT_ADMIN_ROLE': [timelock], 'ADMIN_ROLE': [timelock], 'PAUSER_ROLE': [timelock]}}
    activation = {'reward_per_second': 0, 'annual_emission_budget': 0, 'staking_rewards_enabled': False,
        'staking_minter_enabled': False, 'vesting_enabled': False, 'buyback_enabled': False,
        'delegation_enabled': False, 'ordinary_token_governor_enabled': False, 'deposits_enabled': False,
        'slash_activation_enabled': False, 'execute_intent_enabled': False, 'real_fiat_enabled': False,
        'real_yield_enabled': False}
    records = {}
    for name in ('build', 'state_readback', 'activation_tests', 'dcap_qualification', 'ezkl_qualification', 'insurance_custody'):
        path = root / package.PREFIX / (name + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'scope': 'SYNTHETIC_METADATA_FIXTURE_NOT_QUALIFICATION', 'purpose': name}), encoding='utf-8')
        records[name] = {'path': path.relative_to(root).as_posix(),
                         'sha256': audit_program.hashlib.sha256(path.read_bytes()).hexdigest()}
    identity = manifest['timelock_identity']
    identity.update(address=timelock, actual_runtime_code_hash=code('VAMSTimelockController'),
                    expected_runtime_code_hash=code('VAMSTimelockController'))
    identity['roles'] = [item for item in identity['roles'] if not (item['role'] == 'PROPOSER_ROLE'
                         and item['account'] != manifest['authorities']['governance']['address'])]
    for item in identity['roles']:
        if item['role'] == 'DEFAULT_ADMIN_ROLE' and item['granted']:
            item['account'] = timelock
    for item in manifest['role_transfers']:
        item['target'] = timelock
        if item['action'] == 'grant':
            item['account'] = timelock
    template = manifest['deployer_privilege_checks'][0]
    manifest.update(schema_version='2.0.0', chain_identifier='80002', release_profile='restricted-testnet-v1', artifacts=artifacts,
        deployer_privilege_checks=[dict(template, artifact=name) for name in sorted(by_name)],
        restricted_evm={'schema': 'vams.restricted-evm-release.v1', 'parameters': parameters,
                        'bindings': bindings, 'role_memberships': roles, 'activation': activation, 'records': records})
    return manifest


def _deployment_manifest(root: Path, network: str, commit: str) -> dict:
    """Synthetic package fixture; none of these bytes are compiled validators."""
    manifest = _legacy_deployment_manifest(root, network, commit)
    if network == 'polygon-amoy':
        return _restricted_polygon_manifest(root, manifest)
    from scripts.audit import cardano_governance_release as package
    artifacts = []
    for index, name in enumerate(sorted(package.ARTIFACT_SOURCES), 1):
        source = package.ARTIFACT_SOURCES[name]
        path = root / package.PREFIX / f'{name}.cbor'
        path.parent.mkdir(parents=True, exist_ok=True)
        data = b'SYNTHETIC-METADATA-FIXTURE-NOT-UPLC:' + name.encode()
        path.write_bytes(data)
        digest = audit_program.hashlib.sha256(data).hexdigest()
        artifacts.append({
            'name': name, 'source': source, 'source_sha256': _write_source(root, source),
            'artifact_sha256': digest, 'verification': 'simulation-passed',
            'address': package.enterprise_testnet_address(
                audit_program.hashlib.blake2b(b'\x03' + data, digest_size=28).hexdigest()),
            'script_hash': audit_program.hashlib.blake2b(b'\x03' + data, digest_size=28).hexdigest(),
            'script_cbor_sha256': digest,
            'compiled_script': {'path': path.relative_to(root).as_posix(), 'sha256': digest},
        })
    for name in ('aiken.toml', 'aiken.lock', 'aiken-dependency-manifest.json'):
        _write_source(root, f'cardano/{name}')
    for name in ('governance_v2', 'governance_v2_types', 'governance_v2_transitions', 'governance_v2_vectors'):
        _write_source(root, f'cardano/lib/vams/{name}.ak')
    build = {
        'schema': 'vams.cardano-governance-build.v2', 'compiler_name': 'aiken',
        'compiler_version': '1.1.21', 'compiler_binary_sha256': 'b' * 64,
        'runner_id': 'synthetic-fixture-not-approved-runner', 'language': 'plutus-v3',
        'source_files': package.source_inputs(root), 'governance_version': 2,
        'normal_delay_seconds': 172800, 'cancel_threshold': 3, 'execute_intent_enabled': False,
    }
    for field in package.BUILD_REFERENCES:
        path = root / package.PREFIX / f'{field}.json'
        path.write_text('{"scope":"SYNTHETIC_METADATA_FIXTURE_NO_QUALIFICATION"}', encoding='utf-8')
        build[field] = {'path': path.relative_to(root).as_posix(),
                        'sha256': audit_program.hashlib.sha256(path.read_bytes()).hexdigest()}
    by_name = {item['name']: item for item in artifacts}
    authority = by_name['governance_authority_v2']
    manifest['authorities']['governance'].update({
        'address': authority['address'], 'script_hash': authority['script_hash'],
        'script_cbor_sha256': authority['script_cbor_sha256'],
        'script_source': authority['source'], 'script_source_sha256': authority['source_sha256'],
    })
    timelock = by_name['timelock_v2']
    governor = by_name['governor_v2']
    manifest['timelock_identity'].update({
        'script_address': timelock['address'], 'script_hash': timelock['script_hash'],
        'source': timelock['source'], 'source_sha256': timelock['source_sha256'],
        'actual_script_cbor_sha256': timelock['script_cbor_sha256'],
        'expected_script_cbor_sha256': timelock['script_cbor_sha256'],
        'governor_script_hash': governor['script_hash'], 'cancel_threshold': 3,
    })
    manifest['role_transfers'][0]['to_script_hash'] = governor['script_hash']
    manifest['role_transfers'][1]['to_script_hash'] = timelock['script_hash']
    template = manifest['deployer_privilege_checks'][0]
    manifest['deployer_privilege_checks'] = [dict(template, artifact=name) for name in sorted(by_name)]
    manifest.update(schema_version='2.0.0', artifacts=artifacts, cardano_build=build)
    return manifest

class AuditProgramTests(unittest.TestCase):
    def test_audit_program_has_all_36_tracks(self) -> None:
        matrix = audit_program._load_json(audit_program.MATRIX_PATH)
        self.assertEqual(
            [track["id"] for track in matrix["tracks"]],
            [f"T{i:02d}" for i in range(1, 37)],
        )

    def test_audit_program_validation_passes(self) -> None:
        self.assertEqual(audit_program.validate_program(), [])

    def test_public_testnet_profile_keeps_vdso_fail_closed(self) -> None:
        profile = audit_program._load_json(audit_program.PROFILE_PATH)
        self.assertEqual(profile["vdso"]["mode"], "off")
        self.assertIs(profile["vdso"]["authoritative_enabled"], False)
        self.assertIs(profile["vdso"]["value_bearing_domains_enabled"], False)

    def test_release_claim_scan_covers_readme_and_audit(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('"audit.md"', source)
        self.assertIn('"README.md"', source)

    def test_all_invariants_have_a_control(self) -> None:
        matrix = audit_program._load_json(audit_program.MATRIX_PATH)
        covered = {
            invariant for track in matrix["tracks"] for invariant in track["invariants"]
        }
        self.assertEqual(covered, {f"INV-{i}" for i in range(1, 11)})

    def test_blocked_tracks_cannot_be_mistaken_for_verified(self) -> None:
        matrix = audit_program._load_json(audit_program.MATRIX_PATH)
        statuses = {track["id"]: track["status"] for track in matrix["tracks"]}
        self.assertEqual(statuses["T16"], "blocked")
        self.assertEqual(statuses["T21"], "blocked")
        self.assertEqual(statuses["T30"], "blocked")
        self.assertEqual(statuses["T33"], "blocked")

    def test_current_program_is_not_testnet_ready(self) -> None:
        errors = audit_program.validate_readiness(stage="public")
        joined = "\n".join(errors)
        self.assertIn("T16=blocked", joined)
        self.assertIn("T30=blocked", joined)
        # "clean working tree" is only emitted when the tree is dirty;
        # do not assert it since CI starts from a clean checkout.
        self.assertIn("evidence manifest", joined)

    def test_canary_excludes_g6_track_but_public_includes_it(self) -> None:
        canary = "\n".join(audit_program.validate_readiness(stage="canary"))
        public = "\n".join(audit_program.validate_readiness(stage="public"))
        self.assertNotIn("T36=partial", canary)
        self.assertIn("T36=partial", public)

    def test_evidence_manifest_is_commit_bound_clean_and_signed(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "evidence.json"
            signature_bundle = root / "evidence.sigstore.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "commit_sha": commit,
                        "dirty": False,
                        "environment": "github-actions",
                        "control_matrix_sha256": audit_program.hashlib.sha256(
                            audit_program.MATRIX_PATH.read_bytes()
                        ).hexdigest(),
                        "results": [
                            {
                                "name": name,
                                "status": "success",
                                "command": command,
                                "artifact_sha256": None,
                                "reviewer": "github-actions",
                            }
                            for name, command in sorted(
                                audit_program.REQUIRED_EVIDENCE_RESULTS.items()
                            )
                        ],
                    }
                ),
                encoding="utf-8",
            )
            signature_bundle.write_text(
                '{"mediaType":"application/vnd.dev.sigstore.bundle.v0.3+json"}',
                encoding="utf-8",
            )

            self.assertEqual(
                audit_program._validate_evidence_manifest(
                    manifest, signature_bundle, commit
                ),
                [],
            )

            with mock.patch.object(audit_program, "_git", return_value=""):
                errors = audit_program._validate_evidence_manifest(
                    manifest, signature_bundle, "b" * 40
                )
            self.assertIn("commit does not match", errors[0])

    def test_evidence_manifest_rejects_missing_duplicate_and_unexpected_gates(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "evidence.json"
            signature_bundle = root / "evidence.sigstore.json"
            results = [
                {
                    "name": name,
                    "status": "success",
                    "command": command,
                    "artifact_sha256": None,
                    "reviewer": "github-actions",
                }
                for name, command in sorted(audit_program.REQUIRED_EVIDENCE_RESULTS.items())
            ]
            results.pop()
            results.extend(
                [
                    dict(results[0]),
                    {
                        "name": "invented-gate",
                        "status": "success",
                        "command": "true",
                        "artifact_sha256": None,
                        "reviewer": "github-actions",
                    },
                ]
            )
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "commit_sha": commit,
                        "dirty": False,
                        "environment": "github-actions",
                        "control_matrix_sha256": audit_program.hashlib.sha256(
                            audit_program.MATRIX_PATH.read_bytes()
                        ).hexdigest(),
                        "results": results,
                    }
                ),
                encoding="utf-8",
            )
            signature_bundle.write_text(
                '{"mediaType":"application/vnd.dev.sigstore.bundle.v0.3+json"}',
                encoding="utf-8",
            )

            errors = audit_program._validate_evidence_manifest(
                manifest, signature_bundle, commit
            )
            joined = "\n".join(errors)
            self.assertIn("duplicate gate results", joined)
            self.assertIn("missing gates", joined)
            self.assertIn("unexpected gates", joined)

    def test_manifest_generation_requires_the_complete_gate_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "audit-evidence.json"
            with self.assertRaisesRegex(ValueError, "missing required evidence results"):
                audit_program.generate_manifest(output, ["audit-program=success"])

            complete = [
                f"{name}=success" for name in sorted(audit_program.REQUIRED_EVIDENCE_RESULTS)
            ]
            with mock.patch.dict(audit_program.os.environ, {"GITHUB_ACTIONS": "true"}):
                audit_program.generate_manifest(output, complete)
            generated = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(generated["environment"], "github-actions")
            self.assertEqual(
                {result["name"] for result in generated["results"]},
                set(audit_program.REQUIRED_EVIDENCE_RESULTS),
            )

    def test_evidence_command_catalog_describes_current_blocking_gates(self) -> None:
        commands = audit_program.REQUIRED_EVIDENCE_RESULTS
        self.assertIn("--seed 20260711", commands["aiken"])
        self.assertIn("--fail-high", commands["slither"])
        self.assertIn("--config .semgrep/vams-security.yml --error", commands["semgrep"])
        self.assertIn("--config auto", commands["semgrep"])
        self.assertIn("trufflehog_gate.py", commands["trufflehog"])
        self.assertIn("npm audit --omit=dev", commands["frontend"])
        self.assertIn("npm run lint", commands["frontend"])
        self.assertIn("cargo +1.92.0 audit --deny warnings", commands["vir-core"])
        self.assertIn("cosign sign-blob --bundle", commands["sbom"])

    def test_deployment_manifests_require_both_networks_and_stage(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for network in sorted(audit_program.DEPLOYMENT_NETWORKS):
                path = root / f"{network}.json"
                path.write_text(
                    json.dumps(_deployment_manifest(root, network, commit)),
                    encoding="utf-8",
                )
                paths.append(path)

            with mock.patch.object(audit_program, "ROOT", root):
                self.assertEqual(
                    audit_program._validate_deployment_manifests(
                        paths, "canary", commit
                    ),
                    [],
                )
                public_errors = audit_program._validate_deployment_manifests(
                    paths, "public", commit
                )
            self.assertEqual(
                sum("deployment_status=deployed" in item for item in public_errors),
                2,
            )
            self.assertTrue(any("missing deployment artifacts" in item for item in public_errors))

    def test_deployment_manifest_rejects_substituted_authority_and_timelock_code(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for network in sorted(audit_program.DEPLOYMENT_NETWORKS):
                manifest = _deployment_manifest(root, network, commit)
                if network == "polygon-amoy":
                    manifest["authorities"]["governance"]["proxy_runtime_code_hash"] = "0x0"
                    manifest["timelock_identity"]["expected_runtime_code_hash"] = "0x" + "f" * 64
                    manifest["timelock_identity"]["roles"].pop()
                else:
                    manifest["timelock_identity"]["expected_script_cbor_sha256"] = "f" * 64
                    manifest["authorities"]["governance"]["script_hash"] = "f" * 55
                path = root / f"{network}.json"
                path.write_text(json.dumps(manifest), encoding="utf-8")
                paths.append(path)
            with mock.patch.object(audit_program, "ROOT", root):
                errors = audit_program._validate_deployment_manifests(
                    paths, "canary", commit
                )
            joined = "\n".join(errors)
            self.assertIn("proxy_runtime_code_hash is invalid", joined)
            self.assertIn("actual and expected runtime code hashes differ", joined)
            self.assertIn("required role assignments are missing", joined)
            self.assertIn("actual and expected script CBOR hashes differ", joined)
            self.assertIn("governance script_hash is invalid", joined)

    def test_assurance_index_binds_track_artifacts(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "report.txt"
            artifact.write_text("verified evidence", encoding="utf-8")
            artifact_hash = audit_program.hashlib.sha256(artifact.read_bytes()).hexdigest()
            index = root / "assurance.json"
            index.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "commit_sha": commit,
                        "tracks": [
                            {
                                "id": "T10",
                                "status": "verified",
                                "reviewer": "reviewer",
                                "independent_review": True,
                                "blocking_findings_open": 0,
                                "approved_at": "2026-07-13T00:00:00Z",
                                "artifacts": [
                                    {
                                        "path": "report.txt",
                                        "sha256": artifact_hash,
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(audit_program, "ROOT", root):
                self.assertEqual(
                    audit_program._validate_assurance_index(
                        index, "public", commit, {"T10"}
                    ),
                    [],
                )

            index_data = json.loads(index.read_text(encoding="utf-8"))
            index_data["tracks"].append(
                {
                    **index_data["tracks"][0],
                    "id": "T11",
                    "approved_at": "not-a-timestamp",
                }
            )
            index.write_text(json.dumps(index_data), encoding="utf-8")
            with mock.patch.object(audit_program, "ROOT", root):
                errors = audit_program._validate_assurance_index(
                    index, "public", commit, {"T10"}
                )
            self.assertTrue(any("unexpected tracks: T11" in error for error in errors))

    def test_public_canary_report_requires_duration_and_all_drills(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "canary.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "schema_version": "1.0.0",
                        "started_at": "2020-01-01T00:00:00Z",
                        "ended_at": "2020-01-08T00:00:00Z",
                        "consecutive_days": 7,
                        "stop_conditions_triggered": False,
                        "drills": {
                            drill: True for drill in audit_program.REQUIRED_DRILLS
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(audit_program._validate_canary_report(path, commit), [])

            report = json.loads(path.read_text(encoding="utf-8"))
            report["drills"]["rollback"] = False
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = audit_program._validate_canary_report(path, commit)
            self.assertIn("rollback", errors[0])

    def test_signed_manifest_binds_supporting_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "assurance-index.json"
            artifact.write_text("{}", encoding="utf-8")
            digest = audit_program.hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = root / "audit-evidence.json"
            manifest.write_text(
                json.dumps(
                    {
                        "evidence_artifacts": [
                            {"path": "assurance-index.json", "sha256": digest}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(audit_program, "ROOT", root):
                self.assertEqual(
                    audit_program._validate_manifest_artifact_binding(
                        manifest, [artifact]
                    ),
                    [],
                )
                artifact.write_text('{"changed":true}', encoding="utf-8")
                errors = audit_program._validate_manifest_artifact_binding(
                    manifest, [artifact]
                )
            self.assertIn("does not bind artifact", errors[0])

    def test_runtime_report_rejects_unbound_boolean_results(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtime.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "environment": "testnet",
                        "gateway_checks": {
                            name: True for name in audit_program.REQUIRED_GATEWAY_CHECKS
                        },
                        "da_receipts": [
                            {
                                "provider": provider,
                                "submission_id": f"{provider}-receipt",
                                "payload_sha256": "b" * 64,
                                "retrieval_verified": True,
                            }
                            for provider in ("celestia", "near")
                        ],
                        "excluded_live_routes": sorted(
                            audit_program.REQUIRED_EXCLUDED_ROUTES
                        ),
                    }
                ),
                encoding="utf-8",
            )
            errors = audit_program._validate_runtime_report(path, commit)
            self.assertTrue(any("schema_version" in error for error in errors))
            self.assertTrue(any("must be an object" in error for error in errors))

    def test_privacy_review_rejects_unbound_boolean_approvals(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "privacy.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "reviewer": "privacy-reviewer",
                        "data_inventory_approved": True,
                        "retention_policy_approved": True,
                        "redaction_tests_passed": True,
                        "public_content_reviewed": True,
                        "publisher_inventory_complete": True,
                        "blocking_findings_open": 0,
                    }
                ),
                encoding="utf-8",
            )
            errors = audit_program._validate_privacy_review(path, commit)
            self.assertTrue(any("schema_version" in error for error in errors))
            self.assertTrue(any("evidence_artifacts" in error for error in errors))

    def test_public_requires_all_independent_review_domains(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "reviews": [
                            {
                                "domain": domain,
                                "reviewer": f"reviewer-{domain}",
                                "organization": "independent-org",
                                "approved": True,
                                "blocking_findings_open": 0,
                                "report_sha256": "c" * 64,
                            }
                            for domain in audit_program.REQUIRED_INDEPENDENT_DOMAINS
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                audit_program._validate_independent_reviews(path, commit), []
            )


class LegacyGovernanceRetirementRegressionTests(unittest.TestCase):
    # These use the preserved v1 fixture, never an invented deployment record.
    def legacy_errors(self):
        commit = 'a' * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for network in sorted(audit_program.DEPLOYMENT_NETWORKS):
                manifest = _legacy_deployment_manifest(root, network, commit)
                path = root / f'{network}.json'
                path.write_text(json.dumps(manifest), encoding='utf-8')
                paths.append(path)
            with mock.patch.object(audit_program, 'ROOT', root):
                return audit_program._validate_deployment_manifests(paths, 'canary', commit)

    def test_legacy_cardano_governance_cannot_be_admitted(self):
        self.assertTrue(any('legacy governance is retired' in error for error in self.legacy_errors()))

    def test_two_signatures_cannot_satisfy_governance_cancellation(self):
        self.assertTrue(any('cancel threshold must equal 3' in error for error in self.legacy_errors()))


class CardanoPackageConsistencyTests(unittest.TestCase):
    """Opaque byte fixtures test binding only, never compilation or ledger validity."""
    def setUp(self):
        from scripts.audit import cardano_governance_release
        self.package = cardano_governance_release
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.manifest = _deployment_manifest(self.root, 'cardano-preprod', 'a' * 40)
        self.artifacts = {item['name']: item for item in self.manifest['artifacts']}

    def errors(self):
        return self.package.validate_package(self.manifest, self.root, self.artifacts)

    def test_consistent_synthetic_package_checks_bytes_only(self):
        self.assertEqual(self.errors(), [])

    def test_published_cip19_enterprise_script_address_vector(self):
        self.assertEqual(self.package.enterprise_testnet_address(
            'c37b1b5dc0669f1d3c61a6fddb2e8fde96be87b881c60bce8e8d542f'),
            'addr_test1wrphkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtcl6szpr')

    def test_wrong_governance_script_address_rejects(self):
        self.artifacts['governor_v2']['address'] = self.artifacts['timelock_v2']['address']
        self.assertTrue(any('address does not match its canonical script identity' in item for item in self.errors()))

    def test_wrong_address_checksum_rejects(self):
        artifact = self.artifacts['governor_v2']
        final = artifact['address'][-1]
        artifact['address'] = artifact['address'][:-1] + ('q' if final != 'q' else 'p')
        self.assertTrue(any('address does not match its canonical script identity' in item for item in self.errors()))

    def test_mainnet_governance_address_rejects(self):
        self.artifacts['governor_v2']['address'] = 'addr1w8phkx6acpnf78fuvxn0mkew3l0fd058hzquvz7w36x4gtcyjy7wx'
        self.assertTrue(any('address does not match its canonical script identity' in item for item in self.errors()))

    def test_missing_build_package_rejects(self):
        del self.manifest['cardano_build']
        self.assertTrue(any('build package is missing' in item for item in self.errors()))

    def test_source_edit_invalidates_package(self):
        path = self.root / 'cardano/lib/vams/governance_v2_transitions.ak'
        path.write_text('changed source', encoding='utf-8')
        self.assertTrue(any('source files must exactly match' in item for item in self.errors()))

    def test_omitted_source_input_rejects(self):
        self.manifest['cardano_build']['source_files'].pop('cardano/aiken.lock')
        self.assertTrue(any('source files must exactly match' in item for item in self.errors()))

    def test_new_native_source_requires_new_build_evidence(self):
        (self.root / 'cardano/validators/extra.test.ak').write_text('new test', encoding='utf-8')
        self.assertTrue(any('source files must exactly match' in item for item in self.errors()))

    def test_missing_required_native_source_rejects(self):
        (self.root / 'cardano/lib/vams/governance_v2_types.ak').unlink()
        self.assertTrue(any('source input error' in item for item in self.errors()))

    def test_legacy_source_label_cannot_replace_governor_v2(self):
        self.artifacts['governor_v2']['source'] = 'cardano/validators/governor.ak'
        self.assertTrue(any('must bind current source' in item for item in self.errors()))

    def test_compiled_script_mutation_rejects(self):
        artifact = self.artifacts['governor_v2']
        (self.root / artifact['compiled_script']['path']).write_bytes(b'changed opaque bytes')
        self.assertTrue(any('artifact hash mismatch' in item for item in self.errors()))

    def test_rehashed_script_substitution_cannot_keep_old_script_identity(self):
        artifact = self.artifacts['governor_v2']
        data = b'different opaque metadata fixture'
        (self.root / artifact['compiled_script']['path']).write_bytes(data)
        digest = audit_program.hashlib.sha256(data).hexdigest()
        artifact['compiled_script']['sha256'] = digest
        artifact['artifact_sha256'] = artifact['script_cbor_sha256'] = digest
        self.assertTrue(any('Plutus-v3 script hash does not match' in item for item in self.errors()))

    def test_wrong_language_hash_domain_rejects(self):
        artifact = self.artifacts['governor_v2']
        data = (self.root / artifact['compiled_script']['path']).read_bytes()
        artifact['script_hash'] = audit_program.hashlib.blake2b(b'\x02' + data, digest_size=28).hexdigest()
        self.assertTrue(any('Plutus-v3 script hash does not match' in item for item in self.errors()))

    def test_historical_blueprint_is_not_an_applied_script_reference(self):
        artifact = self.artifacts['governor_v2']
        artifact['compiled_script']['path'] = 'cardano/plutus.json'
        self.assertTrue(any('artifact must stay inside' in item for item in self.errors()))

    def test_symlink_escape_rejects_without_reading_external_bytes(self):
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / 'outside.cbor'
            outside.write_bytes(b'unrelated fixture')
            artifact = self.artifacts['governor_v2']
            link = self.root / self.package.PREFIX / 'escape.cbor'
            link.symlink_to(outside)
            artifact['compiled_script']['path'] = link.relative_to(self.root).as_posix()
            self.assertTrue(any('artifact must stay inside' in item for item in self.errors()))

    def test_unknown_runner_cannot_complete_identity_field(self):
        self.manifest['cardano_build']['runner_id'] = 'UNKNOWN'
        self.assertTrue(any('runner identity is missing' in item for item in self.errors()))

    def test_24_hour_build_configuration_rejects(self):
        self.manifest['cardano_build']['normal_delay_seconds'] = 86400
        self.assertTrue(any('normal_delay_seconds must equal 172800' in item for item in self.errors()))

    def test_execute_intent_activation_rejects(self):
        self.manifest['cardano_build']['execute_intent_enabled'] = True
        self.assertTrue(any('preserve ExecuteIntent rejection' in item for item in self.errors()))

    def test_governance_authority_cannot_be_substituted(self):
        self.manifest['authorities']['governance']['script_hash'] = 'f' * 56
        self.assertTrue(any('governance authority script_hash does not match' in item for item in self.errors()))

    def test_missing_native_record_rejects(self):
        del self.manifest['cardano_build']['native_test_evidence']
        self.assertTrue(any('native_test_evidence: exact path/sha256' in item for item in self.errors()))

    def test_malformed_authority_is_a_rejection_not_an_exception(self):
        self.manifest['authorities'] = []
        self.assertTrue(any('governance authority is missing' in item for item in self.errors()))

    def test_aggregate_includes_all_direct_build_and_script_references(self):
        directory = self.root / 'docs/audit/evidence'
        deployment = directory / 'cardano-preprod-rehearsal.json'
        deployment.write_text(json.dumps(self.manifest), encoding='utf-8')
        output = directory / 'audit-evidence.json'
        with mock.patch.object(audit_program, 'ROOT', self.root), \
                mock.patch.object(audit_program, 'EVIDENCE_DIR', directory), \
                mock.patch.object(audit_program, '_git', side_effect=lambda *args: 'a' * 40 if args[0] == 'rev-parse' else ''):
            audit_program.generate_manifest(output, [f'{name}=success' for name in audit_program.REQUIRED_EVIDENCE_RESULTS])
            references = self.package.referenced_paths(self.manifest, self.root)
            self.assertEqual(len(references), 14)
            self.assertEqual(audit_program._validate_manifest_artifact_binding(output, references), [])
            aggregate = json.loads(output.read_text(encoding='utf-8'))
            omitted = references[0].relative_to(self.root).as_posix()
            aggregate['evidence_artifacts'] = [item for item in aggregate['evidence_artifacts'] if item['path'] != omitted]
            output.write_text(json.dumps(aggregate), encoding='utf-8')
            self.assertTrue(any('does not bind artifact' in item
                                for item in audit_program._validate_manifest_artifact_binding(output, references)))


if __name__ == "__main__":
    unittest.main()
