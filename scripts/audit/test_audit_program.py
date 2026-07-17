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


def _write_bytes(root: Path, relative_path: str, content: bytes) -> str:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return audit_program.hashlib.sha256(path.read_bytes()).hexdigest()


def _attach_observation(
    root: Path,
    record: dict,
    *,
    relative_path: str,
    kind: str,
    commit: str,
    network: str,
    fields: tuple[str, ...],
    path_field: str = "evidence_path",
    hash_field: str = "evidence_sha256",
) -> None:
    observation = audit_program._observation_record(
        kind,
        commit,
        network,
        {field: record.get(field) for field in fields if field in record},
    )
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(observation, sort_keys=True), encoding="utf-8")
    record[path_field] = relative_path
    record[hash_field] = audit_program.hashlib.sha256(path.read_bytes()).hexdigest()


def _deployment_manifest(root: Path, network: str, commit: str) -> dict:
    required = (
        audit_program.CANARY_EVM_ARTIFACTS
        if network == "polygon-amoy"
        else audit_program.CARDANO_ARTIFACTS
    )
    artifacts: list[dict] = []
    for index, name in enumerate(sorted(required), start=1):
        source = audit_program.DEPLOYMENT_ARTIFACT_SOURCES[name]
        safe_name = name.replace(".", "-")
        artifact_path = f"evidence/{network}/artifacts/{safe_name}.bin"
        artifact = {
            "name": name,
            "source": source,
            "source_sha256": _write_source(root, source),
            "artifact_path": artifact_path,
            "artifact_sha256": _write_bytes(
                root, artifact_path, f"artifact:{network}:{name}".encode("utf-8")
            ),
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
            script_cbor_path = f"evidence/{network}/cbor/{safe_name}.cbor"
            artifact.update(
                {
                    "address": f"addr_test1script{index}",
                    "script_hash": _hex(3000 + index, 56),
                    "script_cbor_path": script_cbor_path,
                    "script_cbor_sha256": _write_bytes(
                        root,
                        script_cbor_path,
                        f"cbor:{network}:{name}".encode("utf-8"),
                    ),
                }
            )
        _attach_observation(
            root,
            artifact,
            relative_path=f"evidence/{network}/observations/artifact-{safe_name}.json",
            kind="deployment-artifact-observation",
            commit=commit,
            network=network,
            fields=(
                "name",
                "source",
                "source_sha256",
                "artifact_path",
                "artifact_sha256",
                "verification",
                "address",
                "transaction_hash",
                "runtime_code_hash",
                "script_hash",
                "script_cbor_path",
                "script_cbor_sha256",
            ),
            path_field="observation_evidence_path",
            hash_field="observation_evidence_sha256",
        )
        artifacts.append(artifact)
    by_name = {artifact["name"]: artifact for artifact in artifacts}
    auxiliary_policy_templates: list[dict] = []

    if network == "polygon-amoy":
        deployer = _evm_address(1)
        authorities = {}
        for offset, (name, owner_count, threshold) in enumerate(
            (
                ("governance", 5, 3),
                ("treasury", 5, 3),
                ("emergency", 3, 2),
                ("vdso_guardian", 3, 2),
                ("vdso_recovery", 3, 2),
            ),
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
                "recovery_policy": f"{name} recovery runbook",
            }
            if name == "emergency":
                authority["scope"] = "pause-only"
            elif name == "vdso_guardian":
                authority["scope"] = "vdso-quarantine"
            elif name == "vdso_recovery":
                authority["scope"] = "vdso-recovery"
            _attach_observation(
                root,
                authority,
                relative_path=f"evidence/{network}/authorities/{name}.json",
                kind="deployment-authority-identity",
                commit=commit,
                network=network,
                fields=(
                    "authority_type",
                    "address",
                    "owners",
                    "threshold",
                    "scope",
                    "proxy_runtime_code_hash",
                    "singleton_address",
                    "singleton_runtime_code_hash",
                    "script_hash",
                    "script_cbor_sha256",
                    "script_source",
                    "script_source_sha256",
                    "recovery_policy",
                ),
                path_field="identity_check_evidence_path",
                hash_field="identity_check_evidence_sha256",
            )
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
        role_records = []
        for index, (role, account, granted) in enumerate(roles):
            role_record = {
                "role": role,
                "account": account,
                "granted": granted,
                "observed_at_block": 1,
            }
            _attach_observation(
                root,
                role_record,
                relative_path=f"evidence/{network}/timelock/role-{index}.json",
                kind="timelock-role-observation",
                commit=commit,
                network=network,
                fields=("role", "account", "granted", "observed_at_block"),
            )
            role_records.append(role_record)
        timelock_identity = {
            "identity_type": "evm-runtime",
            "address": timelock_address,
            "source": timelock_source,
            "source_sha256": _write_source(root, timelock_source),
            "actual_runtime_code_hash": timelock_artifact["runtime_code_hash"],
            "expected_runtime_code_hash": timelock_artifact["runtime_code_hash"],
            "minimum_delay_seconds": 172800,
            "roles": role_records,
        }
        _attach_observation(
            root,
            timelock_identity,
            relative_path=f"evidence/{network}/timelock/runtime-identity.json",
            kind="timelock-runtime-identity",
            commit=commit,
            network=network,
            fields=(
                "identity_type",
                "address",
                "source",
                "source_sha256",
                "actual_runtime_code_hash",
                "expected_runtime_code_hash",
                "minimum_delay_seconds",
            ),
            path_field="identity_check_evidence_path",
            hash_field="identity_check_evidence_sha256",
        )
        role_transfers = [
            {
                "target": timelock_address,
                "role": "DEFAULT_ADMIN_ROLE",
                "action": "grant",
                "account": timelock_address,
                "verified": True,
                "observed_at_block": 1,
            },
            {
                "target": timelock_address,
                "role": "DEFAULT_ADMIN_ROLE",
                "action": "renounce",
                "account": deployer,
                "verified": True,
                "observed_at_block": 1,
            },
        ]
        for index, transfer in enumerate(role_transfers):
            _attach_observation(
                root,
                transfer,
                relative_path=f"evidence/{network}/transfers/role-{index}.json",
                kind="role-transfer-observation",
                commit=commit,
                network=network,
                fields=(
                    "target",
                    "role",
                    "action",
                    "account",
                    "verified",
                    "observed_at_block",
                    "transaction_hash",
                ),
            )
        privilege_checks = []
        for index, name in enumerate(sorted(required)):
            check = {
                "artifact": name,
                "account": deployer,
                "privilege": "ANY_PRIVILEGED_ROLE",
                "granted": False,
                "observed_at_block": 1,
            }
            _attach_observation(
                root,
                check,
                relative_path=f"evidence/{network}/privileges/{index}-{name}.json",
                kind="deployer-privilege-observation",
                commit=commit,
                network=network,
                fields=(
                    "artifact",
                    "account",
                    "credential",
                    "privilege",
                    "granted",
                    "can_authorize",
                    "observed_at_block",
                    "observed_at_slot",
                ),
            )
            privilege_checks.append(check)
        modules = []
        for index, name in enumerate(
            sorted(audit_program.VDSO_EVM_ARTIFACTS), start=1
        ):
            module = {
                "name": name,
                "address": by_name[name]["address"],
                "empty": True,
                "paused": True,
                "active_entries": 0,
            }
            _attach_observation(
                root,
                module,
                relative_path=f"evidence/{network}/vdso/{index}-{name}.json",
                kind="vdso-module-state",
                commit=commit,
                network=network,
                fields=("name", "address", "empty", "paused", "active_entries"),
                path_field="state_evidence_path",
                hash_field="state_evidence_sha256",
            )
            modules.append(module)
        vdso = {
            "schema_version": "1.0.0",
            "mode": "off",
            "authoritative_enabled": False,
            "value_bearing_domains_enabled": False,
            "kernel_paused": True,
            "recovery_verifier_configured": False,
            "execution_routes_enabled": False,
            "active_domains": 0,
            "active_adapters": 0,
            "active_programs": 0,
            "active_verifiers": 0,
            "active_routes": 0,
            "modules": modules,
        }
    else:
        deployer = _hex(1, 56)
        authorities = {}
        for offset, (name, owner_count, threshold) in enumerate(
            (("governance", 5, 3), ("treasury", 5, 3), ("emergency", 3, 2)),
            start=1,
        ):
            source = f"cardano/authorities/{name}.ak"
            script_cbor_path = f"evidence/{network}/authorities/{name}.cbor"
            authority = {
                "authority_type": "cardano-script",
                "address": f"addr_test1authority{offset}",
                "owners": [_hex(offset * 20 + i, 56) for i in range(owner_count)],
                "threshold": threshold,
                "script_hash": _hex(11000 + offset, 56),
                "script_cbor_path": script_cbor_path,
                "script_cbor_sha256": _write_bytes(
                    root,
                    script_cbor_path,
                    f"authority-cbor:{name}".encode("utf-8"),
                ),
                "script_source": source,
                "script_source_sha256": _write_source(root, source),
                "recovery_policy": f"{name} recovery runbook",
            }
            if name == "emergency":
                authority["scope"] = "pause-only"
            _attach_observation(
                root,
                authority,
                relative_path=f"evidence/{network}/authorities/{name}.json",
                kind="deployment-authority-identity",
                commit=commit,
                network=network,
                fields=(
                    "authority_type",
                    "address",
                    "owners",
                    "threshold",
                    "scope",
                    "proxy_runtime_code_hash",
                    "singleton_address",
                    "singleton_runtime_code_hash",
                    "script_hash",
                    "script_cbor_path",
                    "script_cbor_sha256",
                    "script_source",
                    "script_source_sha256",
                    "recovery_policy",
                ),
                path_field="identity_check_evidence_path",
                hash_field="identity_check_evidence_sha256",
            )
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
        }
        _attach_observation(
            root,
            timelock_identity,
            relative_path=f"evidence/{network}/timelock/control.json",
            kind="timelock-cardano-control",
            commit=commit,
            network=network,
            fields=(
                "identity_type",
                "script_address",
                "script_hash",
                "source",
                "source_sha256",
                "actual_script_cbor_sha256",
                "expected_script_cbor_sha256",
                "governor_script_hash",
                "minimum_delay_seconds",
                "cancel_threshold",
                "observed_at_slot",
            ),
            path_field="control_evidence_path",
            hash_field="control_evidence_sha256",
        )
        role_transfers = [
            {
                "control": "governor-binding",
                "action": "handoff",
                "from_credential": deployer,
                "to_script_hash": governor_artifact["script_hash"],
                "verified": True,
                "observed_at_slot": 1,
            },
            {
                "control": "deployer-retirement",
                "action": "retire-deployer",
                "from_credential": deployer,
                "to_script_hash": timelock_artifact["script_hash"],
                "verified": True,
                "observed_at_slot": 1,
            },
        ]
        for index, transfer in enumerate(role_transfers):
            _attach_observation(
                root,
                transfer,
                relative_path=f"evidence/{network}/transfers/control-{index}.json",
                kind="control-transfer-observation",
                commit=commit,
                network=network,
                fields=(
                    "control",
                    "action",
                    "from_credential",
                    "to_script_hash",
                    "verified",
                    "observed_at_slot",
                    "transaction_hash",
                ),
            )
        privilege_checks = []
        for index, name in enumerate(sorted(required)):
            check = {
                "artifact": name,
                "credential": deployer,
                "can_authorize": False,
                "observed_at_slot": 1,
            }
            _attach_observation(
                root,
                check,
                relative_path=f"evidence/{network}/privileges/{index}-{name}.json",
                kind="deployer-privilege-observation",
                commit=commit,
                network=network,
                fields=(
                    "artifact",
                    "account",
                    "credential",
                    "privilege",
                    "granted",
                    "can_authorize",
                    "observed_at_block",
                    "observed_at_slot",
                ),
            )
            privilege_checks.append(check)
        vdso_source = "cardano/lib/vams/vdso.ak"
        vdso = {
            "schema_version": "1.0.0",
            "mode": "conformance-only",
            "authoritative_enabled": False,
            "value_bearing_domains_enabled": False,
            "deployable": False,
            "source": vdso_source,
            "source_sha256": _write_source(root, vdso_source),
        }
        _attach_observation(
            root,
            vdso,
            relative_path=f"evidence/{network}/vdso/conformance.json",
            kind="vdso-cardano-conformance",
            commit=commit,
            network=network,
            fields=(
                "schema_version",
                "mode",
                "authoritative_enabled",
                "value_bearing_domains_enabled",
                "deployable",
                "source",
                "source_sha256",
            ),
            path_field="conformance_evidence_path",
            hash_field="conformance_evidence_sha256",
        )

        for index, (name, (title, source)) in enumerate(
            sorted(audit_program.CARDANO_AUXILIARY_POLICIES.items()), start=1
        ):
            safe_name = name.replace(".ak", "")
            template_path = f"evidence/{network}/auxiliary/{safe_name}.template.json"
            template = {
                "name": name,
                "title": title,
                "source": source,
                "source_sha256": _write_source(root, source),
                "parameter_count": index + 1,
                "template_script_hash": _hex(12000 + index, 56),
                "template_artifact_path": template_path,
                "template_artifact_sha256": _write_bytes(
                    root,
                    template_path,
                    f"template:{title}".encode("utf-8"),
                ),
                "instances": [],
            }
            if name == "fund_nft.ak":
                parameter_path = f"evidence/{network}/parameters/fund-bootstrap.json"
                cbor_path = f"evidence/{network}/auxiliary/fund-bootstrap.plutus"
                instance = {
                    "name": name,
                    "title": title,
                    "instance_id": "fund-bootstrap",
                    "script_hash": _hex(13000, 56),
                    "script_cbor_path": cbor_path,
                    "script_cbor_sha256": _write_bytes(
                        root, cbor_path, b"applied-fund-bootstrap"
                    ),
                    "parameter_manifest_path": parameter_path,
                    "parameter_manifest_sha256": _write_bytes(
                        root, parameter_path, b"public-fund-parameters"
                    ),
                    "verification": "simulation-passed",
                }
                _attach_observation(
                    root,
                    instance,
                    relative_path=f"evidence/{network}/auxiliary/fund-bootstrap-observation.json",
                    kind="cardano-auxiliary-policy-instance",
                    commit=commit,
                    network=network,
                    fields=(
                        "name",
                        "title",
                        "instance_id",
                        "script_hash",
                        "script_cbor_path",
                        "script_cbor_sha256",
                        "parameter_manifest_path",
                        "parameter_manifest_sha256",
                        "verification",
                        "transaction_hash",
                    ),
                    path_field="observation_evidence_path",
                    hash_field="observation_evidence_sha256",
                )
                instance.pop("name")
                instance.pop("title")
                template["instances"] = [instance]
            auxiliary_policy_templates.append(template)

    manifest = {
        "schema_version": audit_program.DEPLOYMENT_MANIFEST_SCHEMA_VERSION,
        "network": network,
        "deployment_status": "rehearsed",
        "commit_sha": commit,
        "deployment_source_sha": commit,
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
        "vdso": vdso,
    }
    if network == "cardano-preprod":
        manifest["auxiliary_policy_templates"] = auxiliary_policy_templates
    return manifest


def _gate_bundle(root: Path, commit: str, run_id: int = 1234) -> Path:
    bundle = root / "stage-evidence"
    raw_gates = bundle / "raw-gates"
    raw_gates.mkdir(parents=True)
    for name, command in audit_program.REQUIRED_EVIDENCE_RESULTS.items():
        gate_dir = raw_gates / f"raw-gate-{name}"
        gate_dir.mkdir()
        (gate_dir / "transcript.log").write_text(
            f"$ {command}\nraw command output\n", encoding="utf-8"
        )
        if name == "gitleaks":
            (gate_dir / "gitleaks-report.json").write_text("[]\n", encoding="utf-8")
        elif name == "trufflehog":
            (gate_dir / "trufflehog-sanitized.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "scanner": "trufflehog",
                        "command": command,
                        "exit_status": 0,
                        "commit_sha": commit,
                        "stage_evidence_run_id": run_id,
                        "findings_count": 0,
                        "verified_findings_count": 0,
                        "unverified_findings_count": 0,
                        "findings": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        (gate_dir / "gate.json").write_text(
            json.dumps(
                {
                    "schema_version": audit_program.GATE_ARTIFACT_SCHEMA_VERSION,
                    "name": name,
                    "status": "success",
                    "exit_status": 0,
                    "command": command,
                    "commit_sha": commit,
                    "stage_evidence_run_id": run_id,
                    "seed": audit_program.AUDIT_SEED,
                    "generated_at": "2026-07-13T00:00:00Z",
                    "environment": "github-actions",
                    "raw_outputs": audit_program._raw_output_bindings(gate_dir),
                }
            ),
            encoding="utf-8",
        )
    return bundle


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
        governance = profile["governance"]
        self.assertEqual(governance["governance_mode"], "team-controlled-bootstrap")
        self.assertIs(governance["decentralized_governance_claimed"], False)
        self.assertEqual(governance["human_signers"], 4)
        self.assertEqual(
            set(governance["stable_signer_roles"]),
            audit_program.REQUIRED_TEAM_SIGNER_ROLES,
        )

    def test_testnet_profile_rejects_weakened_capital_authority_and_soak_controls(self) -> None:
        profile = audit_program._load_json(audit_program.PROFILE_PATH)
        assert isinstance(profile, dict)
        profile["asset_policy"] = "unrestricted"
        profile["real_fiat_enabled"] = True
        profile["real_yield_capital_enabled"] = True
        profile["exposure_limits"]["daily_aggregate_insurance_reserve_bps"] = 1001
        profile["governance"]["safe_threshold"] = 2
        profile["governance"]["emergency_scope"] = "unrestricted"
        profile["governance"]["governance_mode"] = "decentralized"
        profile["governance"]["decentralized_governance_claimed"] = True
        profile["governance"]["human_signers"] = 1
        profile["governance"]["offline_recovery_custody"] = "single-person"
        profile["soak_periods"]["closed_canary_days"] = 6
        profile["soak_periods"]["public_testnet_days"] = 13
        profile["vdso"]["mode"] = "shadow"
        profile["vdso"]["authoritative_enabled"] = True
        profile["vdso"]["value_bearing_domains_enabled"] = True
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "testnet-profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            with mock.patch.object(audit_program, "PROFILE_PATH", path):
                errors = "\n".join(audit_program.validate_program())
        for expected in (
            "asset policy must remain faucet-only",
            "real-fiat capital must remain disabled",
            "real-yield capital must remain disabled",
            "daily aggregate canary exposure must not exceed 10%",
            "Safes must remain exact 3-of-5",
            "emergency authority must remain a distinct pause-only 2-of-3",
            "governance must remain team-controlled-bootstrap",
            "must not claim decentralized governance",
            "must use exactly four human signers",
            "offline recovery seats must use 2-of-3 split custody",
            "closed-canary soak must remain at least 7 days",
            "public-testnet soak must remain at least 14 days",
            "keep VDSO mode off",
            "block authoritative VDSO",
            "block value-bearing VDSO domains",
        ):
            self.assertIn(expected, errors)

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

    def test_canary_excludes_g6_track_but_deployed_stages_include_it(self) -> None:
        canary = "\n".join(audit_program.validate_readiness(stage="canary"))
        bootstrap = "\n".join(
            audit_program.validate_readiness(stage="bootstrap-public")
        )
        public = "\n".join(audit_program.validate_readiness(stage="public"))
        self.assertNotIn("T36=partial", canary)
        self.assertIn("T36=partial", bootstrap)
        self.assertIn("T36=partial", public)

    def test_evidence_manifest_is_commit_bound_clean_and_signed(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = _gate_bundle(root, commit)
            manifest = root / "evidence.json"
            signature = root / "evidence.sig"
            certificate = root / "evidence.pem"
            with mock.patch.dict(audit_program.os.environ, {"GITHUB_ACTIONS": "true"}), mock.patch.object(
                audit_program,
                "_git",
                side_effect=lambda *args: commit if args[:2] == ("rev-parse", "HEAD") else "",
            ):
                audit_program.generate_manifest(manifest, bundle, commit, 1234, 5678)
            signature.write_text("signature", encoding="utf-8")
            certificate.write_text("certificate", encoding="utf-8")

            self.assertEqual(
                audit_program._validate_evidence_manifest(
                    manifest,
                    signature,
                    certificate,
                    commit,
                    bundle_dir=bundle,
                    stage_evidence_run_id=1234,
                ),
                [],
            )

            errors = audit_program._validate_evidence_manifest(
                manifest,
                signature,
                certificate,
                "b" * 40,
                bundle_dir=bundle,
                stage_evidence_run_id=1234,
            )
            self.assertIn("commit does not match", errors[0])

    def test_evidence_manifest_rejects_missing_duplicate_and_unexpected_gates(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = _gate_bundle(root, commit)
            manifest = root / "evidence.json"
            signature = root / "evidence.sig"
            certificate = root / "evidence.pem"
            with mock.patch.dict(audit_program.os.environ, {"GITHUB_ACTIONS": "true"}), mock.patch.object(
                audit_program,
                "_git",
                side_effect=lambda *args: commit if args[:2] == ("rev-parse", "HEAD") else "",
            ):
                audit_program.generate_manifest(manifest, bundle, commit, 1234, 5678)
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            results = manifest_data["results"]
            results.pop()
            results.extend(
                [
                    dict(results[0]),
                    {
                        "name": "invented-gate",
                        "status": "success",
                        "command": "true",
                        "artifact_path": results[0]["artifact_path"],
                        "artifact_sha256": results[0]["artifact_sha256"],
                        "reviewer": "github-actions",
                    },
                ]
            )
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            signature.write_text("signature", encoding="utf-8")
            certificate.write_text("certificate", encoding="utf-8")

            errors = audit_program._validate_evidence_manifest(
                manifest,
                signature,
                certificate,
                commit,
                bundle_dir=bundle,
                stage_evidence_run_id=1234,
            )
            joined = "\n".join(errors)
            self.assertIn("duplicate gate results", joined)
            self.assertIn("missing gates", joined)
            self.assertIn("unexpected gates", joined)

    def test_manifest_generation_requires_the_complete_gate_set(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "audit-evidence.json"
            bundle = _gate_bundle(root, commit)
            missing = bundle / "raw-gates" / "raw-gate-slither" / "gate.json"
            missing.unlink()
            git = mock.patch.object(
                audit_program,
                "_git",
                side_effect=lambda *args: commit if args[:2] == ("rev-parse", "HEAD") else "",
            )
            with mock.patch.dict(audit_program.os.environ, {"GITHUB_ACTIONS": "true"}), git:
                with self.assertRaisesRegex(ValueError, "raw gate artifact is missing"):
                    audit_program.generate_manifest(output, bundle, commit, 1234, 5678)

            bundle = _gate_bundle(root / "complete", commit)
            with mock.patch.dict(audit_program.os.environ, {"GITHUB_ACTIONS": "true"}), mock.patch.object(
                audit_program,
                "_git",
                side_effect=lambda *args: commit if args[:2] == ("rev-parse", "HEAD") else "",
            ):
                audit_program.generate_manifest(output, bundle, commit, 1234, 5678)
            generated = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(generated["environment"], "github-actions")
            self.assertEqual(generated["stage_evidence_run_id"], 1234)
            self.assertTrue(generated["bundle_sha256"])
            self.assertTrue(
                all(result["artifact_sha256"] for result in generated["results"])
            )
            self.assertEqual(
                {result["name"] for result in generated["results"]},
                set(audit_program.REQUIRED_EVIDENCE_RESULTS),
            )
            self.assertTrue(
                all(result["raw_outputs"] for result in generated["results"])
            )
            with mock.patch.dict(audit_program.os.environ, {"GITHUB_ACTIONS": "true"}), mock.patch.object(
                audit_program,
                "_git",
                side_effect=lambda *args: commit if args[:2] == ("rev-parse", "HEAD") else "",
            ):
                with self.assertRaisesRegex(ValueError, "outside the bound bundle"):
                    audit_program.generate_manifest(
                        bundle / "audit-evidence.json", bundle, commit, 1234, 5678
                    )

    def test_raw_gate_results_bind_exact_commands_outputs_and_secret_redaction(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = _gate_bundle(Path(temp_dir), commit)
            gate_dir = bundle / "raw-gates" / "raw-gate-public-content"
            transcript = gate_dir / "transcript.log"
            transcript.write_text("$ substituted-command\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output hash mismatch"):
                audit_program._load_gate_results(bundle, commit, 1234)

        trufflehog_report = {
            "schema_version": "1.0.0",
            "scanner": "trufflehog",
            "command": audit_program.REQUIRED_EVIDENCE_RESULTS["trufflehog"],
            "exit_status": 1,
            "commit_sha": commit,
            "stage_evidence_run_id": 1234,
            "findings_count": 1,
            "verified_findings_count": 0,
            "unverified_findings_count": 1,
            "findings": [
                {
                    "detector_name": "test",
                    "detector_type": 1,
                    "verified": False,
                    "commit": commit,
                    "path": "example.txt",
                    "line": 1,
                    "Raw": "must-never-be-uploaded",
                }
            ],
        }
        trufflehog_errors = "\n".join(
            audit_program._validate_sanitized_trufflehog(
                trufflehog_report, commit, 1234
            )
        )
        self.assertIn("secret-bearing fields", trufflehog_errors)
        self.assertIn("finding fields do not match", trufflehog_errors)
        self.assertIn(
            "not fully redacted",
            "\n".join(
                audit_program._validate_gitleaks_report(
                    [{"Secret": "credential-value", "Match": "credential-value"}]
                )
            ),
        )

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

    def test_deployment_source_binding_rejects_rehearsal_mismatch(self) -> None:
        commit = "a" * 40
        manifest = {"deployment_source_sha": "b" * 40}
        errors = audit_program._validate_deployment_source_binding(
            manifest, "canary", commit
        )
        self.assertEqual(
            errors,
            ["canary rehearsal deployment_source_sha must equal the evidence commit"],
        )

    def test_public_deployment_source_binding_rejects_protected_drift(self) -> None:
        commit = "a" * 40
        source = "b" * 40
        manifest = {"deployment_source_sha": source}
        with mock.patch.object(
            audit_program, "_git_returncode", side_effect=[0, 0, 1]
        ) as git_returncode:
            errors = audit_program._validate_deployment_source_binding(
                manifest, "public", commit
            )
        self.assertEqual(
            errors,
            [
                "deployment source and evidence commits differ in protected "
                "executable or configuration paths"
            ],
        )
        diff_call = git_returncode.call_args_list[-1].args
        self.assertEqual(diff_call[:5], ("diff", "--quiet", source, commit, "--"))
        self.assertTrue(
            set(audit_program.DEPLOYMENT_PROTECTED_PATHS) <= set(diff_call)
        )

    def test_public_deployment_source_binding_accepts_metadata_only_commit(self) -> None:
        commit = "a" * 40
        manifest = {"deployment_source_sha": "b" * 40}
        with mock.patch.object(
            audit_program, "_git_returncode", side_effect=[0, 0, 0]
        ):
            self.assertEqual(
                audit_program._validate_deployment_source_binding(
                    manifest, "public", commit
                ),
                [],
            )

    def test_public_deployment_source_binding_rejects_nonancestor(self) -> None:
        commit = "a" * 40
        manifest = {"deployment_source_sha": "b" * 40}
        with mock.patch.object(
            audit_program, "_git_returncode", side_effect=[0, 1]
        ):
            errors = audit_program._validate_deployment_source_binding(
                manifest, "public", commit
            )
        self.assertEqual(
            errors,
            ["deployment_source_sha must be an ancestor of the evidence commit"],
        )

    def test_deployment_manifest_rejects_substituted_authority_and_timelock_code(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for network in sorted(audit_program.DEPLOYMENT_NETWORKS):
                manifest = _deployment_manifest(root, network, commit)
                if network == "polygon-amoy":
                    manifest["authorities"]["governance"]["proxy_runtime_code_hash"] = "0x0"
                    manifest["authorities"]["vdso_guardian"]["address"] = manifest[
                        "authorities"
                    ]["governance"]["address"]
                    manifest["authorities"]["vdso_recovery"]["authority_type"] = "eoa"
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
            self.assertIn("authority addresses must be distinct", joined)
            self.assertIn("vdso_recovery authority_type must equal safe", joined)
            self.assertIn("actual and expected runtime code hashes differ", joined)
            self.assertIn("required role assignments are missing", joined)
            self.assertIn("actual and expected script CBOR hashes differ", joined)
            self.assertIn("governance script_hash is invalid", joined)

    def test_cardano_manifest_requires_auxiliary_templates_and_fund_bootstrap(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = _deployment_manifest(root, "cardano-preprod", commit)
            manifest["auxiliary_policy_templates"] = [
                item
                for item in manifest["auxiliary_policy_templates"]
                if item["name"] != "proposal_nft.ak"
            ]
            fund = next(
                item
                for item in manifest["auxiliary_policy_templates"]
                if item["name"] == "fund_nft.ak"
            )
            fund["instances"] = []
            errors = audit_program._validate_cardano_auxiliary_policies(
                manifest, "canary", root, commit
            )
        joined = "\n".join(errors)
        self.assertIn("missing auxiliary policy templates", joined)
        self.assertIn("exactly one fund bootstrap", joined)

    def test_deployment_manifests_require_fail_closed_vdso_state(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            polygon = _deployment_manifest(root, "polygon-amoy", commit)
            polygon["vdso"]["authoritative_enabled"] = True
            polygon["vdso"]["kernel_paused"] = False
            polygon["vdso"]["recovery_verifier_configured"] = True
            polygon["vdso"]["execution_routes_enabled"] = True
            polygon["vdso"]["active_domains"] = 1
            polygon["vdso"]["modules"][0]["paused"] = False
            polygon["vdso"]["modules"].pop()
            polygon_path = root / "polygon.json"
            polygon_path.write_text(json.dumps(polygon), encoding="utf-8")

            cardano = _deployment_manifest(root, "cardano-preprod", commit)
            cardano["vdso"]["deployable"] = True
            cardano_path = root / "cardano.json"
            cardano_path.write_text(json.dumps(cardano), encoding="utf-8")

            with mock.patch.object(audit_program, "ROOT", root):
                errors = audit_program._validate_deployment_manifests(
                    [polygon_path, cardano_path], "canary", commit
                )
            joined = "\n".join(errors)
            self.assertIn("VDSO must remain non-authoritative", joined)
            self.assertIn("execution kernel must remain paused", joined)
            self.assertIn("recovery verifier must remain unconfigured", joined)
            self.assertIn("execution routes must remain disabled", joined)
            self.assertIn("active domains must equal zero", joined)
            self.assertIn("must prove paused=true", joined)
            self.assertIn("missing VDSO module state", joined)
            self.assertIn("must not be marked deployable", joined)
            self.assertNotIn("vdso.ak missing deployment artifact", joined)

    def test_deployment_nested_evidence_requires_safe_paths_hashes_and_content(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            polygon = _deployment_manifest(root, "polygon-amoy", commit)
            polygon["artifacts"][0]["artifact_sha256"] = "f" * 64
            polygon["authorities"]["vdso_guardian"][
                "identity_check_evidence_path"
            ] = "../outside.json"
            polygon["vdso"]["modules"][0]["state_evidence_sha256"] = "e" * 64
            role_evidence = root / polygon["timelock_identity"]["roles"][0][
                "evidence_path"
            ]
            role_evidence.write_text('{"substituted":true}', encoding="utf-8")
            path = root / "polygon.json"
            path.write_text(json.dumps(polygon), encoding="utf-8")

            with mock.patch.object(audit_program, "ROOT", root):
                errors = audit_program._validate_deployment_manifests(
                    [path], "canary", commit, bundle_root=root
                )
            joined = "\n".join(errors)
            self.assertIn("canonical artifact evidence hash mismatch", joined)
            self.assertIn("authority identity evidence path is unsafe", joined)
            self.assertIn("state evidence hash mismatch", joined)
            self.assertIn("timelock role", joined)
            self.assertIn("evidence content does not bind", joined)

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
                        "schema_version": "2.0.0",
                        "commit_sha": commit,
                        "tracks": [
                            {
                                "id": "T10",
                                "status": "verified",
                                "reviewer": "reviewer",
                                "review_mode": "independent",
                                "assurance_level": "independent",
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

    def test_bootstrap_assurance_rejects_independence_overclaim(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "report.txt"
            artifact.write_text("Architect-bootstrap evidence", encoding="utf-8")
            digest = audit_program.hashlib.sha256(artifact.read_bytes()).hexdigest()
            entry = {
                "id": "T10",
                "status": "verified",
                "reviewer": "Architect",
                "review_mode": "architect-bootstrap",
                "assurance_level": "architect-bootstrap",
                "independent_review": False,
                "blocking_findings_open": 0,
                "approved_at": "2026-07-13T00:00:00Z",
                "artifacts": [{"path": "report.txt", "sha256": digest}],
            }
            index = root / "assurance.json"
            index.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0.0",
                        "commit_sha": commit,
                        "tracks": [entry],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                audit_program._validate_assurance_index(
                    index, "bootstrap-public", commit, {"T10"}, root
                ),
                [],
            )
            entry["independent_review"] = True
            index.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0.0",
                        "commit_sha": commit,
                        "tracks": [entry],
                    }
                ),
                encoding="utf-8",
            )
            errors = "\n".join(
                audit_program._validate_assurance_index(
                    index, "bootstrap-public", commit, {"T10"}, root
                )
            )
            self.assertIn("independence claim is inconsistent", errors)

    def test_public_canary_report_requires_duration_and_all_drills(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "canary.json"
            drills = {}
            for drill in audit_program.REQUIRED_DRILLS:
                evidence_path = f"drills/{drill}.log"
                evidence_hash = _write_bytes(
                    root, evidence_path, f"raw drill output:{drill}".encode("utf-8")
                )
                drills[drill] = {
                    "passed": True,
                    "evidence_path": evidence_path,
                    "evidence_sha256": evidence_hash,
                }
            metric_path = "metrics/canary-duration.jsonl"
            metric_hash = _write_bytes(
                root, metric_path, b'{"elapsed_seconds":604800}\n'
            )
            daily_evidence = []
            for offset in range(7):
                day = f"2026-07-{offset + 1:02d}"
                evidence_path = f"days/{day}.jsonl"
                evidence_hash = _write_bytes(
                    root,
                    evidence_path,
                    f'{{"date":"{day}","continuous":true}}\n'.encode("utf-8"),
                )
                daily_evidence.append(
                    {
                        "date": day,
                        "started_at": f"{day}T00:00:00Z",
                        "ended_at": f"2026-07-{offset + 2:02d}T00:00:00Z",
                        "evidence_path": evidence_path,
                        "evidence_sha256": evidence_hash,
                    }
                )
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "commit_sha": commit,
                        "started_at": "2026-07-01T00:00:00Z",
                        "ended_at": "2026-07-08T00:00:00Z",
                        "consecutive_days": 7,
                        "stop_conditions_triggered": False,
                        "daily_evidence": daily_evidence,
                        "drills": drills,
                        "metric_artifacts": [
                            {
                                "name": "elapsed_seconds",
                                "value": 604800,
                                "unit": "seconds",
                                "evidence_path": metric_path,
                                "evidence_sha256": metric_hash,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(audit_program._validate_canary_report(path, commit), [])

            report = json.loads(path.read_text(encoding="utf-8"))
            report["drills"]["rollback"]["passed"] = False
            report["ended_at"] = "2026-07-01T00:00:01Z"
            report["metric_artifacts"][0]["evidence_sha256"] = "f" * 64
            report["daily_evidence"].pop(3)
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = "\n".join(audit_program._validate_canary_report(path, commit))
            self.assertIn("drill not passed: rollback", errors)
            self.assertIn("measured duration is below 7 days", errors)
            self.assertIn("metric elapsed_seconds evidence hash mismatch", errors)
            self.assertIn("requires at least 7 daily evidence records", errors)

            report["ended_at"] = "2099-07-08T00:00:00Z"
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = "\n".join(audit_program._validate_canary_report(path, commit))
            self.assertIn("ended_at must not be in the future", errors)

    def test_public_vdso_shadow_report_is_fail_closed_and_evidence_bound(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            implementation_roots = {}
            implementation_artifacts = []
            with mock.patch.object(audit_program, "ROOT", root):
                for implementation, source_paths in (
                    audit_program.VDSO_IMPLEMENTATION_SOURCE_PATHS.items()
                ):
                    for source_path in source_paths:
                        path = root / source_path
                        if path.suffix:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(
                                f"{implementation} implementation", encoding="utf-8"
                            )
                        else:
                            path.mkdir(parents=True, exist_ok=True)
                            suffix = ".py" if implementation == "python" else ".rs"
                            (path / f"implementation{suffix}").write_text(
                                f"{implementation} implementation", encoding="utf-8"
                            )
                    source_root = audit_program._compute_source_root(source_paths)
                    artifact = root / audit_program.VDSO_IMPLEMENTATION_ARTIFACT_PATHS[
                        implementation
                    ]
                    artifact.write_bytes(
                        f"{implementation}-evaluator-artifact".encode("utf-8")
                    )
                    artifact_hash = audit_program.hashlib.sha256(
                        artifact.read_bytes()
                    ).hexdigest()
                    implementation_roots[implementation] = {
                        "source_paths": source_paths,
                        "source_root_sha256": source_root,
                        "artifact_path": artifact.name,
                        "artifact_sha256": artifact_hash,
                    }
                    implementation_artifacts.append(
                        {"path": artifact.name, "sha256": artifact_hash}
                    )
            input_artifact = root / audit_program.VDSO_SHADOW_INPUT_PATH
            source_boundaries = []
            previous_source_hash = "0" * 64
            current_source_boundary = None
            with input_artifact.open("w", encoding="utf-8", newline="") as handle:
                for source_sequence in range(1, 100001):
                    encoded_sequence = source_sequence.to_bytes(8, "big")
                    source_cursor = audit_program.hashlib.sha256(
                        b"cursor" + encoded_sequence
                    ).hexdigest()
                    input_commitment = audit_program.hashlib.sha256(
                        b"commitment" + encoded_sequence
                    ).hexdigest()
                    source_record = {
                        "schema_version": audit_program.VDSO_SHADOW_AUDIT_SCHEMA_VERSION,
                        "source_sequence": source_sequence,
                        "source_cursor_hash": source_cursor,
                        "input_commitment": input_commitment,
                        "previous_source_record_sha256": previous_source_hash,
                    }
                    source_hash = audit_program.hashlib.sha256(
                        audit_program._canonical_shadow_record(source_record).encode(
                            "utf-8"
                        )
                    ).hexdigest()
                    source_record["source_record_sha256"] = source_hash
                    handle.write(
                        audit_program._canonical_shadow_record(source_record) + "\n"
                    )
                    if (source_sequence - 1) % 1000 == 0:
                        current_source_boundary = {
                            "start_cursor_hash": source_cursor,
                        }
                    if source_sequence % 1000 == 0:
                        current_source_boundary.update(
                            {
                                "end_cursor_hash": source_cursor,
                                "source_chain_root_sha256": source_hash,
                            }
                        )
                        source_boundaries.append(current_source_boundary)
                    previous_source_hash = source_hash
            source_final_cursor = source_cursor
            source_chain_root = previous_source_hash
            input_hash = audit_program.hashlib.sha256(
                input_artifact.read_bytes()
            ).hexdigest()
            audit = root / audit_program.VDSO_SHADOW_AUDIT_PATH
            records = []
            previous_record_hash = "0" * 64

            def append_record(record: dict) -> str:
                nonlocal previous_record_hash
                record["previous_record_sha256"] = previous_record_hash
                unhashed = audit_program._canonical_shadow_record(record)
                record_hash = audit_program.hashlib.sha256(
                    unhashed.encode("utf-8")
                ).hexdigest()
                record["record_sha256"] = record_hash
                records.append(record)
                previous_record_hash = record_hash
                return record_hash

            started = audit_program.datetime(2026, 7, 1, tzinfo=audit_program.timezone.utc)
            initial_root = audit_program.hashlib.sha256(b"initial-root").hexdigest()
            append_record(
                {
                    "record_type": "run",
                    "schema_version": audit_program.VDSO_SHADOW_AUDIT_SCHEMA_VERSION,
                    "run_id": audit_program.hashlib.sha256(b"shadow-run").hexdigest(),
                    "commit_sha": commit,
                    "seed": audit_program.AUDIT_SEED,
                    "started_at": "2026-07-01T00:00:00Z",
                    "chunk_size": audit_program.VDSO_SHADOW_CHUNK_SIZE,
                    "configured_max_gap_seconds": 7000,
                    "initial_root": initial_root,
                    "implementation_roots": implementation_roots,
                    "input_source_schema": audit_program.VDSO_SHADOW_INPUT_SCHEMA,
                    "input_jsonl_path": audit_program.VDSO_SHADOW_INPUT_PATH,
                }
            )
            current_root = initial_root
            last_transcript_roots = None
            run_id = records[0]["run_id"]
            for chunk_index in range(100):
                chunk_started = started + audit_program.timedelta(
                    seconds=chunk_index * 6048
                )
                chunk_completed = (
                    started + audit_program.timedelta(days=7)
                    if chunk_index == 99
                    else chunk_started + audit_program.timedelta(seconds=1)
                )
                ending_root = audit_program.hashlib.sha256(
                    f"ending-root-{chunk_index}".encode("utf-8")
                ).hexdigest()
                transcript_root = audit_program.hashlib.sha256(
                    f"transcript-{chunk_index}".encode("utf-8")
                ).hexdigest()
                last_transcript_roots = {
                    backend: transcript_root
                    for backend in audit_program.VDSO_SHADOW_BACKENDS
                }
                append_record(
                    {
                        "record_type": "chunk",
                        "schema_version": audit_program.VDSO_SHADOW_AUDIT_SCHEMA_VERSION,
                        "run_id": run_id,
                        "chunk_index": chunk_index,
                        "start_sequence": chunk_index * 1000 + 1,
                        "end_sequence": (chunk_index + 1) * 1000,
                        "transition_count": 1000,
                        "started_at": chunk_started.isoformat().replace("+00:00", "Z"),
                        "completed_at": chunk_completed.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "max_gap_seconds": 6048 if chunk_index == 99 else 1,
                        "starting_root": current_root,
                        "ending_root": ending_root,
                        "backend_eval_count": {
                            backend: 1000
                            for backend in audit_program.VDSO_SHADOW_BACKENDS
                        },
                        "transcript_roots": last_transcript_roots,
                        "source_start_cursor_hash": source_boundaries[chunk_index][
                            "start_cursor_hash"
                        ],
                        "source_end_cursor_hash": source_boundaries[chunk_index][
                            "end_cursor_hash"
                        ],
                        "source_chain_root_sha256": source_boundaries[chunk_index][
                            "source_chain_root_sha256"
                        ],
                    }
                )
                current_root = ending_root
            audit_chain_root = append_record(
                {
                    "record_type": "summary",
                    "schema_version": audit_program.VDSO_SHADOW_AUDIT_SCHEMA_VERSION,
                    "run_id": run_id,
                    "completed_at": "2026-07-08T00:00:00Z",
                    "observed_seconds": 604800,
                    "transition_count": 100000,
                    "chunk_count": 100,
                    "max_transition_gap_seconds": 6048.0,
                    "configured_max_gap_seconds": 7000,
                    "restart_count": 1,
                    "replay_verification_count": 1,
                    "backend_eval_count": {
                        backend: 100000
                        for backend in audit_program.VDSO_SHADOW_BACKENDS
                    },
                    "source_record_count": 100000,
                    "source_final_cursor_hash": source_final_cursor,
                    "source_chain_root_sha256": source_chain_root,
                    "final_root": current_root,
                    "final_transcript_roots": last_transcript_roots,
                    "divergence_count": 0,
                    "external_write_count": 0,
                    "plaintext_payload_count": 0,
                    "privacy_result": "pass",
                    "stop_conditions_triggered": False,
                }
            )
            audit.write_text(
                "\n".join(
                    audit_program._canonical_shadow_record(record)
                    for record in records
                )
                + "\n",
                encoding="utf-8",
                newline="",
            )
            audit_hash = audit_program.hashlib.sha256(audit.read_bytes()).hexdigest()
            report = root / "vdso-shadow-report.json"
            report.write_text(
                json.dumps(
                    {
                        "schema_version": audit_program.VDSO_SHADOW_REPORT_SCHEMA_VERSION,
                        "commit_sha": commit,
                        "seed": audit_program.AUDIT_SEED,
                        "started_at": "2026-07-01T00:00:00Z",
                        "completed_at": "2026-07-08T00:00:00Z",
                        "consecutive_days": 7,
                        "observed_seconds": 604800,
                        "transition_count": 100000,
                        "chunk_count": 100,
                        "configured_max_gap_seconds": 7000,
                        "max_transition_gap_seconds": 6048.0,
                        "continuity_passed": True,
                        "restart_count": 1,
                        "replay_verification_count": 1,
                        "backend_eval_count": {
                            backend: 100000
                            for backend in audit_program.VDSO_SHADOW_BACKENDS
                        },
                        "audit_chain_root_sha256": audit_chain_root,
                        "source_record_count": 100000,
                        "source_final_cursor_hash": source_final_cursor,
                        "source_chain_root_sha256": source_chain_root,
                        "input_jsonl_path": audit_program.VDSO_SHADOW_INPUT_PATH,
                        "input_jsonl_sha256": input_hash,
                        "audit_jsonl_path": audit_program.VDSO_SHADOW_AUDIT_PATH,
                        "audit_jsonl_sha256": audit_hash,
                        "public_vdso_mode": "off",
                        "worker_mode": "shadow",
                        "authoritative_enabled": False,
                        "read_only": True,
                        "value_bearing_domains_enabled": False,
                        "divergence_count": 0,
                        "external_write_count": 0,
                        "plaintext_payload_count": 0,
                        "restart_recovery_passed": True,
                        "replay_determinism_passed": True,
                        "privacy_result": "pass",
                        "stop_conditions_triggered": False,
                        "stop_conditions": {
                            condition: False
                            for condition in audit_program.REQUIRED_VDSO_STOP_CONDITIONS
                        },
                        "implementation_roots": implementation_roots,
                        "evidence_artifacts": [
                            {
                                "path": audit.name,
                                "sha256": audit_hash,
                            },
                            {
                                "path": input_artifact.name,
                                "sha256": input_hash,
                            },
                            *implementation_artifacts,
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(audit_program, "ROOT", root):
                self.assertEqual(
                    audit_program._validate_vdso_shadow_report(report, commit), []
                )

            data = json.loads(report.read_text(encoding="utf-8"))
            data["transition_count"] = 99999
            data["observed_seconds"] = 1
            data["chunk_count"] = 1
            data["continuity_passed"] = False
            data["restart_count"] = 0
            data["backend_eval_count"]["rust"] = 99998
            data["external_write_count"] = 1
            data["plaintext_payload_count"] = 1
            data["restart_recovery_passed"] = False
            data["public_vdso_mode"] = "shadow"
            data["worker_mode"] = "off"
            data["privacy_result"] = "failure"
            data["stop_conditions_triggered"] = True
            data["stop_conditions"]["external_write"] = True
            data["stop_conditions"].pop("replay_mismatch")
            data["implementation_roots"]["python"]["source_root_sha256"] = "f" * 64
            data["implementation_roots"].pop("aiken")
            tampered_records = [
                json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()
            ]
            tampered_records[1]["start_sequence"] = 2
            audit.write_text(
                "\n".join(
                    audit_program._canonical_shadow_record(record)
                    for record in tampered_records
                )
                + "\n",
                encoding="utf-8",
                newline="",
            )
            tampered_audit_hash = audit_program.hashlib.sha256(
                audit.read_bytes()
            ).hexdigest()
            data["audit_jsonl_sha256"] = tampered_audit_hash
            data["evidence_artifacts"][0]["sha256"] = tampered_audit_hash
            with input_artifact.open("r+b") as handle:
                first_line = handle.readline()
                first_source_record = json.loads(first_line.decode("utf-8"))
                first_source_record["source_sequence"] = 2
                tampered_first_line = (
                    audit_program._canonical_shadow_record(first_source_record) + "\n"
                ).encode("utf-8")
                self.assertEqual(len(tampered_first_line), len(first_line))
                handle.seek(0)
                handle.write(tampered_first_line)
            tampered_input_hash = audit_program.hashlib.sha256(
                input_artifact.read_bytes()
            ).hexdigest()
            data["input_jsonl_sha256"] = tampered_input_hash
            data["evidence_artifacts"][1]["sha256"] = tampered_input_hash
            data["evidence_artifacts"].append(
                {
                    "path": report.name,
                    "sha256": audit_program.hashlib.sha256(
                        report.read_bytes()
                    ).hexdigest(),
                }
            )
            report.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch.object(audit_program, "ROOT", root):
                joined = "\n".join(
                    audit_program._validate_vdso_shadow_report(report, commit)
                )
            self.assertIn("at least 100000 transitions", joined)
            self.assertIn("at least 604800 observed seconds", joined)
            self.assertIn("at least 100 audit chunks", joined)
            self.assertIn("continuity proof must pass", joined)
            self.assertIn("restart_count must be at least one", joined)
            self.assertIn("backend_eval_count must equal 99999", joined)
            self.assertIn("zero external writes", joined)
            self.assertIn("zero plaintext payloads", joined)
            self.assertIn("restart recovery must pass", joined)
            self.assertIn("public_vdso_mode=off", joined)
            self.assertIn("worker_mode=shadow", joined)
            self.assertIn("privacy result must pass", joined)
            self.assertIn("recorded a stop condition", joined)
            self.assertIn("stop conditions are missing: replay_mismatch", joined)
            self.assertIn("stop conditions must all be false: external_write", joined)
            self.assertIn("does not match declared source files", joined)
            self.assertIn("implementation roots are missing: aiken", joined)
            self.assertIn("must not self-reference", joined)
            self.assertIn("audit record 2 hash is invalid", joined)
            self.assertIn("sequence range must contain exactly 1000 transitions", joined)
            self.assertIn("input record 1 hash is invalid", joined)
            self.assertIn("input record 2 sequence is duplicated, reordered, or gapped", joined)

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
            root = Path(temp_dir)
            reviews = []
            for domain in audit_program.REQUIRED_INDEPENDENT_DOMAINS:
                report_path = f"reviews/{domain}.md"
                report_hash = _write_bytes(
                    root, report_path, f"independent report:{domain}".encode("utf-8")
                )
                reviews.append(
                    {
                        "domain": domain,
                        "reviewer": f"reviewer-{domain}",
                        "organization": "independent-org",
                        "review_mode": "independent",
                        "assurance_level": "independent",
                        "independent": True,
                        "approved": True,
                        "blocking_findings_open": 0,
                        "report_path": report_path,
                        "report_sha256": report_hash,
                        "approved_at": "2026-07-13T00:00:00Z",
                    }
                )
            path = root / "reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0.0",
                        "commit_sha": commit,
                        "reviews": reviews,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                audit_program._validate_independent_reviews(path, commit, root), []
            )

            data = json.loads(path.read_text(encoding="utf-8"))
            data["reviews"][0]["independent"] = False
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = "\n".join(
                audit_program._validate_independent_reviews(path, commit, root)
            )
            self.assertIn("independent must equal True", errors)

    def test_bootstrap_public_requires_content_bound_architect_reviews(self) -> None:
        commit = "a" * 40
        declaration = (
            "This assessment is Architect-reviewed and is not an independent or "
            "third-party audit."
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reviews = []
            for domain in audit_program.REQUIRED_ARCHITECT_REVIEW_DOMAINS:
                report_path = f"architect/{domain}.md"
                report_hash = _write_bytes(
                    root, report_path, f"Architect report:{domain}".encode("utf-8")
                )
                evidence_path = f"architect/{domain}.log"
                evidence_hash = _write_bytes(
                    root, evidence_path, f"command output:{domain}".encode("utf-8")
                )
                reviews.append(
                    {
                        "domain": domain,
                        "reviewer": "Aseem",
                        "review_mode": "architect-bootstrap",
                        "assurance_level": "architect-bootstrap",
                        "independent": False,
                        "approved": True,
                        "blocking_findings_open": 0,
                        "approved_at": "2026-07-13T00:00:00Z",
                        "declaration": declaration,
                        "invariants_reviewed": ["INV-1"],
                        "commands": ["verify exact commit"],
                        "limitations": ["not independently audited"],
                        "stop_conditions": ["any failed executable gate"],
                        "report_path": report_path,
                        "report_sha256": report_hash,
                        "evidence_artifacts": [
                            {"path": evidence_path, "sha256": evidence_hash}
                        ],
                    }
                )
            path = root / "architect-reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "commit_sha": commit,
                        "assurance_level": "architect-bootstrap",
                        "reviewer_role": "Architect",
                        "reviews": reviews,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                audit_program._validate_architect_reviews(path, commit, root), []
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            data["reviews"][0]["independent"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = "\n".join(
                audit_program._validate_architect_reviews(path, commit, root)
            )
            self.assertIn("must not claim independent review", errors)

    def test_team_signer_governance_requires_exact_councils_and_evidence(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roles = ["ARCHITECT", "SIGNER_A", "SIGNER_B", "SIGNER_C"]
            signers = [
                {
                    "role": role,
                    "address": f"0x{index:040x}",
                    "historical_pem_relationship": False,
                    "independent_key_custody": True,
                }
                for index, role in enumerate(roles, start=1)
            ]
            consent_records = []
            for role in roles:
                evidence_path = f"consent/{role}.json"
                evidence_hash = _write_bytes(root, evidence_path, role.encode("utf-8"))
                consent_records.append(
                    {
                        "role": role,
                        "consented": True,
                        "understands_authority": True,
                        "independent_key_custody_confirmed": True,
                        "emergency_channel_recorded": True,
                        "compromise_reporting_accepted": True,
                        "amoy_rehearsal_completed": True,
                        "evidence_path": evidence_path,
                        "evidence_sha256": evidence_hash,
                    }
                )
            rehearsals = []
            for scenario in audit_program.REQUIRED_SIGNER_REHEARSALS:
                evidence_path = f"rehearsals/{scenario}.json"
                evidence_hash = _write_bytes(
                    root, evidence_path, scenario.encode("utf-8")
                )
                rehearsals.append(
                    {
                        "scenario": scenario,
                        "passed": True,
                        "evidence_path": evidence_path,
                        "evidence_sha256": evidence_hash,
                    }
                )
            authorities = [
                {
                    "id": authority_id,
                    "members": sorted(expected["members"]),
                    "threshold": expected["threshold"],
                    "scope": expected["scope"],
                }
                for authority_id, expected in audit_program.REQUIRED_TEAM_AUTHORITY_MEMBERS.items()
            ]
            report = {
                "schema_version": "1.0.0",
                "commit_sha": commit,
                "network": "polygon-amoy",
                "governance_mode": "team-controlled-bootstrap",
                "decentralized_governance_claimed": False,
                "externally_audited_claimed": False,
                "signers": signers,
                "offline_recovery_seats": [
                    {
                        "role": "GOVERNANCE_RECOVERY",
                        "address": f"0x{5:040x}",
                        "custody_mode": "2-of-3-split-custody",
                        "custodians": ["SIGNER_A", "SIGNER_B", "SIGNER_C"],
                        "custody_threshold": 2,
                        "routine_use": False,
                        "rotate_after_use": True,
                    },
                    {
                        "role": "TREASURY_RECOVERY",
                        "address": f"0x{6:040x}",
                        "custody_mode": "2-of-3-split-custody",
                        "custodians": ["SIGNER_A", "SIGNER_B", "SIGNER_C"],
                        "custody_threshold": 2,
                        "routine_use": False,
                        "rotate_after_use": True,
                    },
                ],
                "authorities": authorities,
                "consent_records": consent_records,
                "rehearsals": rehearsals,
                "emergency_response_target_seconds": 1800,
                "limitations": ["team-controlled bootstrap governance"],
                "blocking_findings_open": 0,
            }
            path = root / "team-signer-governance.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(
                audit_program._validate_team_signer_governance(path, commit, root), []
            )
            report["authorities"][0]["threshold"] = 2
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = "\n".join(
                audit_program._validate_team_signer_governance(path, commit, root)
            )
            self.assertIn("governance authority threshold is invalid", errors)


if __name__ == "__main__":
    unittest.main()
