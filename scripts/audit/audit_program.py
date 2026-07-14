#!/usr/bin/env python3
"""Validate the VAMS audit program and emit commit-bound evidence manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts.audit.runtime_privacy_evidence import (
        PUBLISHER_INVENTORY_PATH,
        REQUIRED_EXCLUDED_ROUTES as RUNTIME_REQUIRED_EXCLUDED_ROUTES,
        REQUIRED_GATEWAY_CHECKS as RUNTIME_REQUIRED_GATEWAY_CHECKS,
        validate_privacy_review,
        validate_publisher_inventory,
        validate_runtime_report,
    )
except ModuleNotFoundError:
    from runtime_privacy_evidence import (  # type: ignore[no-redef]
        PUBLISHER_INVENTORY_PATH,
        REQUIRED_EXCLUDED_ROUTES as RUNTIME_REQUIRED_EXCLUDED_ROUTES,
        REQUIRED_GATEWAY_CHECKS as RUNTIME_REQUIRED_GATEWAY_CHECKS,
        validate_privacy_review,
        validate_publisher_inventory,
        validate_runtime_report,
    )


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs" / "audit" / "control-matrix.json"
PROFILE_PATH = ROOT / "docs" / "audit" / "testnet-profile.json"
SCHEMA_DIR = ROOT / "docs" / "audit" / "schemas"
EVIDENCE_DIR = ROOT / "docs" / "audit" / "evidence"
ALLOWED_STATUSES = {"planned", "partial", "implemented", "verified", "blocked"}
ALLOWED_GATES = {f"G{i}" for i in range(7)}
EXPECTED_TRACK_IDS = [f"T{i:02d}" for i in range(1, 37)]
EXPECTED_INVARIANTS = {f"INV-{i}" for i in range(1, 11)}
REQUIRED_TRACK_FIELDS = {
    "id",
    "phase",
    "title",
    "owner_role",
    "status",
    "economic_effect",
    "invariants",
    "components",
    "evidence",
    "gate",
}
STAGE_GATES = {
    "canary": {"G0", "G1", "G2", "G3", "G4"},
    "public": ALLOWED_GATES,
}
AUDIT_SEED = 20260713
EVIDENCE_MANIFEST_SCHEMA_VERSION = "2.0.0"
DEPLOYMENT_MANIFEST_SCHEMA_VERSION = "2.0.0"
GATE_ARTIFACT_SCHEMA_VERSION = "2.0.0"
VDSO_SHADOW_REPORT_SCHEMA_VERSION = "1.0.0"
DEPLOYMENT_NETWORKS = {"polygon-amoy", "cardano-preprod"}
REQUIRED_DRILLS = {
    "pause",
    "key_loss",
    "da_outage",
    "identity_outage",
    "bridge_replay",
    "backup_restore",
    "rollback",
}
REQUIRED_GATEWAY_CHECKS = set(RUNTIME_REQUIRED_GATEWAY_CHECKS)
REQUIRED_EXCLUDED_ROUTES = set(RUNTIME_REQUIRED_EXCLUDED_ROUTES)
REQUIRED_INDEPENDENT_DOMAINS = {
    "solidity-governance",
    "aiken-bridge",
    "economics-centralization",
    "gateway-agent-sdk",
    "privacy",
    "ai-agent-safety",
}
REQUIRED_EVIDENCE_RESULTS = {
    "audit-program": " && ".join(
        (
            "python scripts/audit/audit_program.py validate",
            "python scripts/audit/test_audit_program.py",
            "python scripts/audit/deployment_readiness.py",
            "python scripts/audit/test_deployment_readiness.py",
            "python scripts/audit/validate_traceability.py",
            "python scripts/audit/test_traceability.py",
            "python scripts/docs/validate_docs.py",
            "python -m unittest scripts/docs/test_validate_docs.py",
            "python scripts/docs/validate_vdso_evidence.py",
            "python -m unittest discover -s scripts/docs/tests -p test_validate_vdso_evidence.py",
            "python scripts/audit/validate_workflow_security.py",
            "python scripts/audit/test_workflow_security.py",
            "python scripts/audit/test_economic_concentration.py",
            "python scripts/audit/test_economic_adversarial.py",
            "python scripts/audit/run_economic_adversarial.py --epochs 100000 --seed 20260713 --output economic-adversarial-report.json",
            "python scripts/audit/validate_agent_red_team.py",
        )
    ),
    "public-content": "python scripts/security/public_content_policy_scan.py",
    "default-credentials": "python scripts/security/default_credential_scan.py",
    "mock-mode": "python scripts/security/mock_mode_promotion_scan.py",
    "gitleaks": "gitleaks git . --redact=100 --report-format json --report-path raw-gate/gitleaks-report.json --log-opts=--all --exit-code 1",
    "trufflehog": 'trufflehog git "file://$PWD" --json --fail --no-update --results=verified,unknown,unverified',
    "solidity": "cd contracts && forge build --sizes && forge test -vvv",
    "slither": "cd contracts && slither . --exclude-dependencies --exclude-informational --exclude-low --fail-high",
    "aiken": "cd cardano && aiken check --deny --seed 20260713 --max-success 250",
    "vir-core": " && ".join(
        (
            "cd vams-vm",
            "cargo +1.92.0 fmt --all -- --check",
            "cargo +1.92.0 check --workspace --all-targets --locked",
            "cargo +1.92.0 clippy --workspace --all-targets --locked -- -D warnings",
            "cargo +1.92.0 test --workspace --all-targets --locked",
        )
    ),
    "python": " && ".join(
        (
            "pip-audit -r gateway/requirements.txt",
            "pip-audit -r neuron/requirements.txt",
            "bandit -r neuron/ gateway/ -ll -ii",
            "pytest -v --tb=short --ignore=neuron/tests/test_vdso_postgres_integration.py",
            "pytest -v --tb=short neuron/tests/test_vdso_postgres_integration.py::test_postgres_atomicity_restart_and_six_figure_state",
        )
    ),
    "semgrep": "semgrep scan --config auto --error --exclude contracts/lib --exclude node_modules --exclude frontend-vite/node_modules --exclude .foundry --exclude frontend-vite/.vite --exclude contracts/out --exclude .git",
    "frontend": "cd frontend-vite && npm ci && npm audit --audit-level=high && npm run build",
    "gateway-config": 'docker run --rm -e VAMS_ROOT_CA_CERT=/etc/ssl/certs/ca-certificates.crt -v "$PWD/gateway/Caddyfile.testnet.example:/etc/caddy/Caddyfile:ro" caddy:2@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && docker run --rm -e VAMS_ROOT_CA_CERT=/etc/ssl/certs/ca-certificates.crt -v "$PWD/gateway/Caddyfile.testnet.example:/etc/caddy/Caddyfile:ro" caddy:2@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile --pretty',
    "sbom": "syft dir:. -o cyclonedx-json=sbom.json",
}
REQUIRED_VDSO_STOP_CONDITIONS = {
    "transition_divergence",
    "external_write",
    "plaintext_payload",
    "restart_failure",
    "replay_mismatch",
    "privacy_failure",
    "public_mode_enabled",
    "authoritative_enabled",
    "value_bearing_enabled",
    "continuity_gap",
    "backend_unavailable",
    "source_chain_mismatch",
}
VDSO_SHADOW_AUDIT_PATH = "vdso-shadow-audit.jsonl"
VDSO_SHADOW_INPUT_PATH = "vdso-shadow-input.jsonl"
VDSO_SHADOW_INPUT_SCHEMA = "vdso-shadow-input-v1"
VDSO_SHADOW_AUDIT_SCHEMA_VERSION = "1.0.0"
VDSO_SHADOW_CHUNK_SIZE = 1000
VDSO_SHADOW_MIN_CHUNKS = 100
VDSO_SHADOW_BACKENDS = {"python", "rust", "aiken"}
VDSO_IMPLEMENTATION_SOURCE_PATHS = {
    "python": ["neuron/vdso"],
    "rust": ["vams-vm/crates"],
    "aiken": ["cardano/lib/vams/vdso.ak"],
}
VDSO_IMPLEMENTATION_ARTIFACT_PATHS = {
    "python": "vdso-shadow-python-evaluator.py",
    "rust": "vdso-shadow-rust-evaluator.bin",
    "aiken": "vdso-shadow-aiken-evaluator.cbor",
}
CANARY_EVM_ARTIFACTS = {
    "VAMSToken",
    "VAMSStaking",
    "VAMSVesting",
    "VAMSGovernor",
    "VAMSTimelockController",
    "VAMSSentinel",
}
VDSO_EVM_ARTIFACTS = {
    "VAMSObjectStore",
    "VAMSProgramRegistry",
    "VAMSAdapterRegistry",
    "VAMSProofRouter",
    "VAMSReservationManager",
    "VAMSExecutionKernel",
    "VAMSCapabilityRouter",
}
CANARY_EVM_ARTIFACTS |= VDSO_EVM_ARTIFACTS
PUBLIC_EVM_ARTIFACTS = CANARY_EVM_ARTIFACTS | {
    "GovernorExecutor",
    "ComposedSettlement",
    "RegionAwareDEC",
    "RegionalIncentives",
    "RewardDistributor",
    "VAMSInsuranceFund",
    "VAMSFeeCollector",
    "TransactionCompensation",
    "BatchSettlement",
    "SLAEnforcer",
    "SlashingParameters",
    "VAMSRouter",
    "VAMSAgentRegistry",
    "VAMSHardwareRegistry",
    "VAMSTrustAggregator",
    "VAMSUpgradeableBase",
    "VAMSEmergencyPausable",
    "InsuranceFundProxy",
}
CARDANO_ARTIFACTS = {"governor.ak", "timelock.ak", "insurance_fund.ak", "agent_registry.ak"}
DEPLOYMENT_ARTIFACT_SOURCES = {
    "VAMSToken": "contracts/src/token/VAMSToken.sol",
    "VAMSStaking": "contracts/src/staking/VAMSStaking.sol",
    "VAMSVesting": "contracts/src/vesting/VAMSVesting.sol",
    "VAMSGovernor": "contracts/src/governance/VAMSGovernor.sol",
    "VAMSTimelockController": "contracts/src/governance/VAMSTimelockController.sol",
    "VAMSSentinel": "contracts/src/sentinel/VAMSSentinel.sol",
    "VAMSObjectStore": "contracts/src/vdso/VAMSObjectStore.sol",
    "VAMSProgramRegistry": "contracts/src/vdso/VAMSProgramRegistry.sol",
    "VAMSAdapterRegistry": "contracts/src/vdso/VAMSAdapterRegistry.sol",
    "VAMSProofRouter": "contracts/src/vdso/VAMSProofRouter.sol",
    "VAMSReservationManager": "contracts/src/vdso/VAMSReservationManager.sol",
    "VAMSExecutionKernel": "contracts/src/vdso/VAMSExecutionKernel.sol",
    "VAMSCapabilityRouter": "contracts/src/vdso/VAMSCapabilityRouter.sol",
    "GovernorExecutor": "contracts/src/governance/GovernorExecutor.sol",
    "ComposedSettlement": "contracts/src/economic/ComposedSettlement.sol",
    "RegionAwareDEC": "contracts/src/economic/RegionAwareDEC.sol",
    "RegionalIncentives": "contracts/src/economic/RegionalIncentives.sol",
    "RewardDistributor": "contracts/src/economic/RewardDistributor.sol",
    "VAMSInsuranceFund": "contracts/src/economic/VAMSInsuranceFund.sol",
    "VAMSFeeCollector": "contracts/src/economic/VAMSFeeCollector.sol",
    "TransactionCompensation": "contracts/src/economic/TransactionCompensation.sol",
    "BatchSettlement": "contracts/src/economic/BatchSettlement.sol",
    "SLAEnforcer": "contracts/src/sentinel/SLAEnforcer.sol",
    "SlashingParameters": "contracts/src/slashing/SlashingParameters.sol",
    "VAMSRouter": "contracts/src/routing/VAMSRouter.sol",
    "VAMSAgentRegistry": "contracts/src/registry/VAMSAgentRegistry.sol",
    "VAMSHardwareRegistry": "contracts/src/registry/VAMSHardwareRegistry.sol",
    "VAMSTrustAggregator": "contracts/src/trust/VAMSTrustAggregator.sol",
    "VAMSUpgradeableBase": "contracts/src/base/VAMSUpgradeableBase.sol",
    "VAMSEmergencyPausable": "contracts/src/base/VAMSEmergencyPausable.sol",
    "InsuranceFundProxy": "contracts/src/economic/InsuranceFundProxy.sol",
    "governor.ak": "cardano/validators/governor.ak",
    "timelock.ak": "cardano/validators/timelock.ak",
    "insurance_fund.ak": "cardano/validators/insurance_fund.ak",
    "agent_registry.ak": "cardano/validators/agent_registry.ak",
}
NON_DEPLOYABLE_EVM_ARTIFACTS = {"VAMSUpgradeableBase", "VAMSEmergencyPausable"}
EVM_ZERO_ADDRESS = "0x" + "0" * 40
EVM_ADDRESS_PATTERN = re.compile(r"0x[0-9a-fA-F]{40}")
EVM_HASH_PATTERN = re.compile(r"0x[0-9a-fA-F]{64}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CARDANO_HASH_PATTERN = re.compile(r"[0-9a-f]{56}")


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def validate_program() -> list[str]:
    errors: list[str] = []
    matrix = _load_json(MATRIX_PATH)
    if not isinstance(matrix, dict) or not isinstance(matrix.get("tracks"), list):
        return ["control-matrix.json must contain a tracks array"]

    tracks = matrix["tracks"]
    ids = [track.get("id") for track in tracks if isinstance(track, dict)]
    if ids != EXPECTED_TRACK_IDS:
        errors.append("track IDs must be exactly T01 through T36 in order")

    for index, track in enumerate(tracks, start=1):
        if not isinstance(track, dict):
            errors.append(f"track {index} must be an object")
            continue
        missing = REQUIRED_TRACK_FIELDS - set(track)
        if missing:
            errors.append(f"{track.get('id', index)} missing fields: {sorted(missing)}")
        if track.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{track.get('id', index)} has invalid status")
        if track.get("gate") not in ALLOWED_GATES:
            errors.append(f"{track.get('id', index)} has invalid gate")
        if track.get("phase") not in range(0, 6):
            errors.append(f"{track.get('id', index)} phase must be 0 through 5")
        invariants = set(track.get("invariants", []))
        if not invariants <= EXPECTED_INVARIANTS:
            errors.append(f"{track.get('id', index)} references an unknown invariant")
        for field in ("title", "owner_role", "economic_effect"):
            if not isinstance(track.get(field), str) or not track[field].strip():
                errors.append(f"{track.get('id', index)} {field} must be non-empty")
        for field in ("components", "evidence"):
            if not isinstance(track.get(field), list) or not track[field]:
                errors.append(f"{track.get('id', index)} {field} must be non-empty")

    profile = _load_json(PROFILE_PATH)
    if not isinstance(profile, dict):
        errors.append("testnet-profile.json must be an object")
    else:
        governance = profile.get("governance", {})
        concentration = profile.get("concentration_stop_conditions", {})
        exposure = profile.get("exposure_limits", {})
        vdso = profile.get("vdso", {})
        soak_periods = profile.get("soak_periods", {})
        if profile.get("asset_policy") != "faucet-only":
            errors.append("testnet asset policy must remain faucet-only")
        if profile.get("real_fiat_enabled") is not False:
            errors.append("testnet real-fiat capital must remain disabled")
        if profile.get("real_yield_capital_enabled") is not False:
            errors.append("testnet real-yield capital must remain disabled")
        if profile.get("staking_rewards_enabled") is not False:
            errors.append("testnet staking rewards must remain disabled")
        if governance.get("timelock_seconds", 0) < 172800:
            errors.append("testnet timelock must be at least 48 hours")
        if governance.get("safe_threshold") != 3 or governance.get("safe_owners") != 5:
            errors.append(
                "testnet governance and treasury Safes must remain exact 3-of-5"
            )
        if (
            governance.get("emergency_threshold") != 2
            or governance.get("emergency_owners") != 3
            or governance.get("emergency_scope") != "pause-only"
        ):
            errors.append(
                "testnet emergency authority must remain a distinct pause-only 2-of-3"
            )
        if concentration.get("regional_reward_share_bps", 10001) > 3000:
            errors.append("regional reward stop condition must not exceed 30%")
        if exposure.get("single_operation_insurance_reserve_bps", 10001) > 100:
            errors.append("single-operation canary exposure must not exceed 1%")
        daily_exposure = exposure.get("daily_aggregate_insurance_reserve_bps")
        if (
            not isinstance(daily_exposure, int)
            or isinstance(daily_exposure, bool)
            or daily_exposure > 1000
        ):
            errors.append("daily aggregate canary exposure must not exceed 10%")
        closed_days = soak_periods.get("closed_canary_days")
        if (
            not isinstance(closed_days, int)
            or isinstance(closed_days, bool)
            or closed_days < 7
        ):
            errors.append("closed-canary soak must remain at least 7 days")
        public_days = soak_periods.get("public_testnet_days")
        if (
            not isinstance(public_days, int)
            or isinstance(public_days, bool)
            or public_days < 14
        ):
            errors.append("public-testnet soak must remain at least 14 days")
        if vdso.get("mode") != "off":
            errors.append("the public-testnet profile must keep VDSO mode off")
        if vdso.get("authoritative_enabled") is not False:
            errors.append("the public-testnet profile must block authoritative VDSO")
        if vdso.get("value_bearing_domains_enabled") is not False:
            errors.append("the public-testnet profile must block value-bearing VDSO domains")

    for schema_path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = _load_json(schema_path)
        if not isinstance(schema, dict) or "$schema" not in schema or "title" not in schema:
            errors.append(f"{schema_path.relative_to(ROOT)} is not a complete JSON schema")
    errors.extend(validate_publisher_inventory(PUBLISHER_INVENTORY_PATH, ROOT))

    claim_checks = {
        "audit.md": {
            "stale total verdict": r"Tests:\s+1,083 PASSING",
            "CI checks called non-blocking": r"not deployment blockers[^\n]*testnet",
            "v0.6.0 described as current architecture": r"fully modular OMS-integrated platform \(v0\.6\.0\)",
        },
        "README.md": {
            "stale fixed test-count badge": r"Tests-1,083(?:%20|\s)Passing",
        },
    }
    for rel_path, forbidden_current_claims in claim_checks.items():
        text = (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
        for label, pattern in forbidden_current_claims.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                errors.append(f"{rel_path} contains {label}")

    return errors


def _contains_pending(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == "pending"
    if isinstance(value, dict):
        return any(_contains_pending(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_pending(item) for item in value)
    return False


def _require_nonempty_file(path: Path, label: str, errors: list[str]) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        errors.append(f"{label} is missing or empty: {path}")


def _validate_evidence_manifest(
    path: Path,
    signature: Path,
    certificate: Path,
    commit_sha: str,
    *,
    bundle_dir: Path | None = None,
    stage_evidence_run_id: int | None = None,
    operational_evidence_run_id: int | None = None,
) -> list[str]:
    errors: list[str] = []
    _require_nonempty_file(path, "evidence manifest", errors)
    _require_nonempty_file(signature, "evidence signature", errors)
    _require_nonempty_file(certificate, "evidence certificate", errors)
    if errors:
        return errors

    manifest = _load_json(path)
    if not isinstance(manifest, dict):
        return ["evidence manifest must be an object"]
    if manifest.get("schema_version") != EVIDENCE_MANIFEST_SCHEMA_VERSION:
        errors.append(
            "evidence manifest schema_version must be "
            + EVIDENCE_MANIFEST_SCHEMA_VERSION
        )
    if manifest.get("commit_sha") != commit_sha:
        errors.append("evidence manifest commit does not match the target commit")
    run_id = manifest.get("stage_evidence_run_id")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        errors.append("evidence manifest stage_evidence_run_id is invalid")
    elif stage_evidence_run_id is not None and run_id != stage_evidence_run_id:
        errors.append("evidence manifest stage-evidence run ID does not match")
    operational_run_id = manifest.get("operational_evidence_run_id")
    if (
        not isinstance(operational_run_id, int)
        or isinstance(operational_run_id, bool)
        or operational_run_id < 1
    ):
        errors.append("evidence manifest operational_evidence_run_id is invalid")
    elif (
        operational_evidence_run_id is not None
        and operational_run_id != operational_evidence_run_id
    ):
        errors.append("evidence manifest operational-evidence run ID does not match")
    if operational_run_id == run_id:
        errors.append("operational and stage evidence must come from distinct runs")
    if manifest.get("seed") != AUDIT_SEED:
        errors.append(f"evidence manifest seed must equal {AUDIT_SEED}")
    if manifest.get("dirty") is not False:
        errors.append("evidence manifest was generated from a dirty tree")
    if manifest.get("environment") != "github-actions":
        errors.append("evidence manifest must be generated by GitHub Actions")
    expected_matrix_hash = hashlib.sha256(MATRIX_PATH.read_bytes()).hexdigest()
    if manifest.get("control_matrix_sha256") != expected_matrix_hash:
        errors.append("evidence manifest control matrix hash does not match")
    records = manifest.get("evidence_artifacts")
    bound: dict[str, str] = {}
    if not isinstance(records, list) or not records:
        errors.append("evidence manifest must bind the complete stage-evidence bundle")
    else:
        for record in records:
            if not isinstance(record, dict):
                errors.append("evidence manifest contains an invalid artifact record")
                continue
            relative_path = record.get("path")
            digest = record.get("sha256")
            if not isinstance(relative_path, str) or not relative_path:
                errors.append("evidence manifest artifact path is missing")
                continue
            if relative_path in bound:
                errors.append(
                    f"evidence manifest contains duplicate artifact: {relative_path}"
                )
                continue
            if Path(relative_path).name.lower() in {
                "audit-evidence.json",
                "audit-evidence.sig",
                "audit-evidence.pem",
            }:
                errors.append(
                    f"evidence manifest must not self-reference: {relative_path}"
                )
            if not _is_sha256(digest):
                errors.append(
                    f"evidence manifest artifact hash is invalid: {relative_path}"
                )
                continue
            bound[relative_path] = str(digest)
        expected_bundle_hash = _canonical_bundle_hash(
            [
                {"path": relative_path, "sha256": digest}
                for relative_path, digest in sorted(bound.items())
            ]
        )
        if manifest.get("bundle_sha256") != expected_bundle_hash:
            errors.append("evidence manifest bundle_sha256 does not match its records")

    results = manifest.get("results")
    if not isinstance(results, list) or not results:
        errors.append("evidence manifest must contain gate results")
    else:
        names = [result.get("name") for result in results if isinstance(result, dict)]
        if len(names) != len(results):
            errors.append("evidence manifest gate results must be objects")
        if len(names) != len(set(names)):
            errors.append("evidence manifest contains duplicate gate results")
        missing = set(REQUIRED_EVIDENCE_RESULTS) - set(names)
        unexpected = set(names) - set(REQUIRED_EVIDENCE_RESULTS)
        if missing:
            errors.append("evidence manifest missing gates: " + ", ".join(sorted(missing)))
        if unexpected:
            errors.append("evidence manifest contains unexpected gates: " + ", ".join(sorted(unexpected)))
        for result in results:
            if not isinstance(result, dict):
                continue
            name = result.get("name")
            if result.get("status") != "success":
                errors.append(f"evidence gate did not pass: {name}")
            expected_command = REQUIRED_EVIDENCE_RESULTS.get(name)
            if expected_command is not None and result.get("command") != expected_command:
                errors.append(f"evidence gate command mismatch: {name}")
            artifact_path = result.get("artifact_path")
            artifact_hash = result.get("artifact_sha256")
            if not isinstance(artifact_path, str) or not artifact_path:
                errors.append(f"evidence gate artifact path is missing: {name}")
            elif bound.get(artifact_path) != artifact_hash:
                errors.append(f"evidence gate artifact binding mismatch: {name}")
            if not _is_sha256(artifact_hash):
                errors.append(f"evidence gate artifact hash is invalid: {name}")
            raw_outputs = result.get("raw_outputs")
            if not isinstance(raw_outputs, list) or not raw_outputs:
                errors.append(f"evidence gate raw output bindings are missing: {name}")
            else:
                seen_outputs: set[str] = set()
                for raw_output in raw_outputs:
                    if not isinstance(raw_output, dict):
                        errors.append(f"evidence gate raw output is invalid: {name}")
                        continue
                    raw_path = raw_output.get("path")
                    raw_hash = raw_output.get("sha256")
                    if not isinstance(raw_path, str) or not raw_path:
                        errors.append(f"evidence gate raw output path is missing: {name}")
                    elif raw_path in seen_outputs:
                        errors.append(f"evidence gate raw output is duplicated: {name}")
                    elif bound.get(raw_path) != raw_hash:
                        errors.append(f"evidence gate raw output binding mismatch: {name}")
                    else:
                        seen_outputs.add(raw_path)
                    if not _is_sha256(raw_hash):
                        errors.append(f"evidence gate raw output hash is invalid: {name}")
            if result.get("reviewer") != "github-actions":
                errors.append(f"evidence gate reviewer mismatch: {name}")
    if bundle_dir is not None:
        if isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0:
            try:
                expected_results = _load_gate_results(bundle_dir, commit_sha, run_id)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
            else:
                if results != expected_results:
                    errors.append(
                        "evidence manifest results do not match raw gate artifacts"
                    )
        errors.extend(_validate_complete_bundle(path, manifest, bundle_dir))
    return errors


def _canonical_bundle_hash(records: list[dict[str, str]]) -> str:
    encoded = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _collect_bundle_records(bundle_dir: Path) -> list[dict[str, str]]:
    bundle_root = bundle_dir.resolve()
    if not bundle_root.is_dir():
        raise ValueError(f"stage-evidence bundle is missing: {bundle_dir}")
    records: list[dict[str, str]] = []
    for artifact in sorted(
        bundle_root.rglob("*"),
        key=lambda path: path.relative_to(bundle_root).as_posix(),
    ):
        if artifact.is_symlink():
            raise ValueError(f"stage-evidence bundle contains a symlink: {artifact}")
        if not artifact.is_file():
            continue
        if artifact.stat().st_size == 0:
            raise ValueError(f"stage-evidence artifact is empty: {artifact}")
        relative_path = artifact.relative_to(bundle_root).as_posix()
        if artifact.name.lower() in {
            "audit-evidence.json",
            "audit-evidence.sig",
            "audit-evidence.pem",
        }:
            raise ValueError(
                f"stage-evidence bundle contains aggregate self-reference: {relative_path}"
            )
        records.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        )
    if not records:
        raise ValueError("stage-evidence bundle contains no artifacts")
    return records


def _validate_complete_bundle(
    manifest_path: Path, manifest: dict, bundle_dir: Path
) -> list[str]:
    errors: list[str] = []
    bundle_root = bundle_dir.resolve()
    try:
        manifest_path.resolve().relative_to(bundle_root)
    except ValueError:
        pass
    else:
        errors.append("aggregate evidence manifest must be outside the bound bundle")
    try:
        actual_records = _collect_bundle_records(bundle_dir)
    except (OSError, ValueError) as exc:
        return errors + [str(exc)]
    declared_records = manifest.get("evidence_artifacts")
    if not isinstance(declared_records, list):
        return errors + ["evidence manifest does not bind supporting artifacts"]
    if declared_records != actual_records:
        errors.append("evidence manifest does not bind the complete immutable bundle")
    actual_bundle_hash = _canonical_bundle_hash(actual_records)
    if manifest.get("bundle_sha256") != actual_bundle_hash:
        errors.append("evidence manifest bundle hash does not match downloaded bundle")
    return errors


def _validate_manifest_artifact_binding(
    manifest_path: Path,
    required_paths: list[Path],
    *,
    bundle_dir: Path | None = None,
) -> list[str]:
    if not manifest_path.is_file():
        return []
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        return []
    records = manifest.get("evidence_artifacts")
    if not isinstance(records, list):
        return ["evidence manifest does not bind supporting artifacts"]
    bound = {
        record.get("path"): record.get("sha256")
        for record in records
        if isinstance(record, dict)
    }
    errors: list[str] = []
    binding_root = (bundle_dir or ROOT).resolve()
    for path in required_paths:
        try:
            relative_path = path.resolve().relative_to(binding_root).as_posix()
        except ValueError:
            errors.append(f"supporting evidence escapes the bound evidence root: {path}")
            continue
        if not path.is_file():
            errors.append(f"supporting evidence is missing: {path}")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if bound.get(relative_path) != actual_hash:
            errors.append(f"signed evidence does not bind artifact: {relative_path}")
    return errors


def _is_evm_address(value: object) -> bool:
    return isinstance(value, str) and EVM_ADDRESS_PATTERN.fullmatch(value) is not None


def _is_evm_hash(value: object) -> bool:
    return isinstance(value, str) and EVM_HASH_PATTERN.fullmatch(value) is not None


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_cardano_hash(value: object) -> bool:
    return isinstance(value, str) and CARDANO_HASH_PATTERN.fullmatch(value) is not None


def _validate_source_binding(
    source: object, expected_hash: object, context: str, *, expected_source: str | None = None
) -> list[str]:
    errors: list[str] = []
    if not isinstance(source, str) or not source:
        return [f"{context} source is missing"]
    if expected_source is not None and source != expected_source:
        errors.append(f"{context} source must equal {expected_source}")
    source_path = (ROOT / source).resolve()
    try:
        source_path.relative_to(ROOT.resolve())
    except ValueError:
        return errors + [f"{context} source escapes the repository: {source}"]
    if not source_path.is_file():
        return errors + [f"{context} source is missing: {source}"]
    actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if expected_hash != actual_hash:
        errors.append(f"{context} source hash mismatch: {source}")
    return errors


def _validate_bundle_evidence(
    evidence_path: object,
    evidence_sha256: object,
    bundle_root: Path,
    context: str,
    *,
    expected_record: dict[str, object] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence_path, str) or not evidence_path:
        return [f"{context} evidence path is missing"]
    if Path(evidence_path).is_absolute() or ".." in Path(evidence_path).parts:
        return [f"{context} evidence path is unsafe: {evidence_path}"]
    root = bundle_root.resolve()
    artifact = (root / evidence_path).resolve()
    try:
        artifact.relative_to(root)
    except ValueError:
        return [f"{context} evidence escapes the immutable bundle: {evidence_path}"]
    if artifact.is_symlink():
        return [f"{context} evidence must not be a symlink: {evidence_path}"]
    if not artifact.is_file() or artifact.stat().st_size == 0:
        return [f"{context} evidence is missing or empty: {evidence_path}"]
    actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if evidence_sha256 != actual_hash:
        errors.append(f"{context} evidence hash mismatch: {evidence_path}")
    if expected_record is not None:
        try:
            actual_record = _load_json(artifact)
        except (OSError, ValueError, json.JSONDecodeError):
            actual_record = None
        if actual_record != expected_record:
            errors.append(
                f"{context} evidence content does not bind the declared observation"
            )
    return errors


def _observation_record(
    kind: str,
    commit_sha: str,
    network: str,
    fields: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "kind": kind,
        "commit_sha": commit_sha,
        "network": network,
        **fields,
    }


def _validate_deployment_artifacts(
    manifest: dict,
    network: str,
    stage: str,
    required_artifacts: set[str],
    bundle_root: Path,
    commit_sha: str,
) -> tuple[list[str], dict[str, dict]]:
    errors: list[str] = []
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return [f"{network} deployment artifacts must be an array"], {}
    artifacts: dict[str, dict] = {}
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict) or not isinstance(raw_artifact.get("name"), str):
            errors.append(f"{network} contains an invalid deployment artifact")
            continue
        name = raw_artifact["name"]
        if name in artifacts:
            errors.append(f"{network} contains duplicate deployment artifact {name}")
            continue
        artifacts[name] = raw_artifact

    missing = required_artifacts - set(artifacts)
    unexpected = set(artifacts) - required_artifacts
    if missing:
        errors.append(
            f"{network} missing deployment artifacts: " + ", ".join(sorted(missing))
        )
    if unexpected:
        errors.append(
            f"{network} contains unexpected deployment artifacts: "
            + ", ".join(sorted(unexpected))
        )

    expected_verification = (
        "simulation-passed"
        if stage == "canary"
        else "explorer-verified" if network == "polygon-amoy" else "script-hash-verified"
    )
    addresses: list[str] = []
    for name, artifact in artifacts.items():
        context = f"{network} artifact {name}"
        expected_source = DEPLOYMENT_ARTIFACT_SOURCES.get(name)
        errors.extend(
            _validate_source_binding(
                artifact.get("source"),
                artifact.get("source_sha256"),
                context,
                expected_source=expected_source,
            )
        )
        if not _is_sha256(artifact.get("artifact_sha256")):
            errors.append(f"{context} artifact_sha256 is invalid")
        errors.extend(
            _validate_bundle_evidence(
                artifact.get("artifact_path"),
                artifact.get("artifact_sha256"),
                bundle_root,
                f"{context} canonical artifact",
            )
        )
        if artifact.get("verification") != expected_verification:
            errors.append(f"{context} verification must equal {expected_verification}")
        address = artifact.get("address")
        if network == "polygon-amoy":
            if not _is_evm_hash(artifact.get("runtime_code_hash")):
                errors.append(f"{context} runtime_code_hash is invalid")
            if name not in NON_DEPLOYABLE_EVM_ARTIFACTS:
                if not _is_evm_address(address) or str(address).lower() == EVM_ZERO_ADDRESS:
                    errors.append(f"{context} deployed or rehearsed address is invalid")
                else:
                    addresses.append(str(address).lower())
                if stage == "public" and not _is_evm_hash(artifact.get("transaction_hash")):
                    errors.append(f"{context} public transaction_hash is invalid")
        else:
            if not isinstance(address, str) or not address.startswith("addr_test1"):
                errors.append(f"{context} script address is invalid")
            else:
                addresses.append(address)
            if not _is_cardano_hash(artifact.get("script_hash")):
                errors.append(f"{context} script_hash is invalid")
            if not _is_sha256(artifact.get("script_cbor_sha256")):
                errors.append(f"{context} script_cbor_sha256 is invalid")
            errors.extend(
                _validate_bundle_evidence(
                    artifact.get("script_cbor_path"),
                    artifact.get("script_cbor_sha256"),
                    bundle_root,
                    f"{context} script CBOR",
                )
            )
            if stage == "public" and not _is_sha256(artifact.get("transaction_hash")):
                errors.append(f"{context} public transaction_hash is invalid")
        observation_fields = {
            field: artifact.get(field)
            for field in (
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
            )
            if field in artifact
        }
        errors.extend(
            _validate_bundle_evidence(
                artifact.get("observation_evidence_path"),
                artifact.get("observation_evidence_sha256"),
                bundle_root,
                f"{context} chain observation",
                expected_record=_observation_record(
                    "deployment-artifact-observation",
                    commit_sha,
                    network,
                    observation_fields,
                ),
            )
        )
    if len(addresses) != len(set(addresses)):
        errors.append(f"{network} deployment artifact addresses must be distinct")
    return errors, artifacts


def _validate_vdso_deployment_state(
    manifest: dict,
    network: str,
    artifacts: dict[str, dict],
    bundle_root: Path,
    commit_sha: str,
) -> list[str]:
    vdso = manifest.get("vdso")
    if not isinstance(vdso, dict):
        return [f"{network} VDSO state evidence is missing"]
    errors: list[str] = []
    if vdso.get("schema_version") != "1.0.0":
        errors.append(f"{network} VDSO state schema_version must equal 1.0.0")
    if vdso.get("authoritative_enabled") is not False:
        errors.append(f"{network} VDSO must remain non-authoritative")
    if vdso.get("value_bearing_domains_enabled") is not False:
        errors.append(f"{network} VDSO must remain value-free")

    if network == "polygon-amoy":
        if vdso.get("mode") != "off":
            errors.append("polygon-amoy VDSO mode must remain off")
        if vdso.get("kernel_paused") is not True:
            errors.append("polygon-amoy VDSO execution kernel must remain paused")
        if vdso.get("recovery_verifier_configured") is not False:
            errors.append(
                "polygon-amoy VDSO recovery verifier must remain unconfigured"
            )
        if vdso.get("execution_routes_enabled") is not False:
            errors.append("polygon-amoy VDSO execution routes must remain disabled")
        for field, label in (
            ("active_domains", "domains"),
            ("active_adapters", "adapters"),
            ("active_programs", "programs"),
            ("active_verifiers", "verifiers"),
            ("active_routes", "routes"),
        ):
            value = vdso.get(field)
            if value != 0 or isinstance(value, bool):
                errors.append(f"polygon-amoy VDSO active {label} must equal zero")
        raw_modules = vdso.get("modules")
        if not isinstance(raw_modules, list):
            return errors + ["polygon-amoy VDSO modules must be an array"]
        modules: dict[str, dict] = {}
        for item in raw_modules:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                errors.append("polygon-amoy contains an invalid VDSO module state")
                continue
            name = item["name"]
            if name in modules:
                errors.append(f"polygon-amoy contains duplicate VDSO module {name}")
                continue
            modules[name] = item
        missing = VDSO_EVM_ARTIFACTS - set(modules)
        unexpected = set(modules) - VDSO_EVM_ARTIFACTS
        if missing:
            errors.append(
                "polygon-amoy missing VDSO module state: "
                + ", ".join(sorted(missing))
            )
        if unexpected:
            errors.append(
                "polygon-amoy contains unexpected VDSO module state: "
                + ", ".join(sorted(unexpected))
            )
        for name, module in modules.items():
            context = f"polygon-amoy VDSO module {name}"
            artifact = artifacts.get(name)
            if artifact is None:
                continue
            address = module.get("address")
            if not _is_evm_address(address) or str(address).lower() != str(
                artifact.get("address", "")
            ).lower():
                errors.append(f"{context} address does not match deployment artifact")
            if module.get("empty") is not True:
                errors.append(f"{context} must prove empty state")
            if module.get("paused") is not True:
                errors.append(f"{context} must prove paused=true")
            if module.get("active_entries") != 0 or isinstance(
                module.get("active_entries"), bool
            ):
                errors.append(f"{context} active_entries must equal zero")
            if not _is_sha256(module.get("state_evidence_sha256")):
                errors.append(f"{context} state evidence hash is invalid")
            errors.extend(
                _validate_bundle_evidence(
                    module.get("state_evidence_path"),
                    module.get("state_evidence_sha256"),
                    bundle_root,
                    f"{context} state",
                    expected_record=_observation_record(
                        "vdso-module-state",
                        commit_sha,
                        network,
                        {
                            field: module.get(field)
                            for field in (
                                "name",
                                "address",
                                "empty",
                                "paused",
                                "active_entries",
                            )
                        },
                    ),
                )
            )
    else:
        if vdso.get("mode") != "conformance-only":
            errors.append("cardano-preprod VDSO must remain conformance-only")
        if vdso.get("deployable") is not False:
            errors.append("cardano-preprod VDSO must not be marked deployable")
        errors.extend(
            _validate_source_binding(
                vdso.get("source"),
                vdso.get("source_sha256"),
                "cardano-preprod VDSO conformance library",
                expected_source="cardano/lib/vams/vdso.ak",
            )
        )
        if not _is_sha256(vdso.get("conformance_evidence_sha256")):
            errors.append("cardano-preprod VDSO conformance evidence hash is invalid")
        errors.extend(
            _validate_bundle_evidence(
                vdso.get("conformance_evidence_path"),
                vdso.get("conformance_evidence_sha256"),
                bundle_root,
                "cardano-preprod VDSO conformance",
                expected_record=_observation_record(
                    "vdso-cardano-conformance",
                    commit_sha,
                    network,
                    {
                        field: vdso.get(field)
                        for field in (
                            "schema_version",
                            "mode",
                            "authoritative_enabled",
                            "value_bearing_domains_enabled",
                            "deployable",
                            "source",
                            "source_sha256",
                        )
                    },
                ),
            )
        )
    return errors


def _validate_deployment_authorities(
    manifest: dict, network: str, bundle_root: Path, commit_sha: str
) -> tuple[list[str], dict[str, dict]]:
    errors: list[str] = []
    raw_authorities = manifest.get("authorities")
    if not isinstance(raw_authorities, dict):
        return [f"{network} authorities are missing"], {}
    expected_names = {"governance", "treasury", "emergency"}
    if network == "polygon-amoy":
        expected_names |= {"vdso_guardian", "vdso_recovery"}
    unexpected = set(raw_authorities) - expected_names
    if unexpected:
        errors.append(
            f"{network} contains unexpected authorities: " + ", ".join(sorted(unexpected))
        )
    authorities: dict[str, dict] = {}
    addresses: list[str] = []
    script_hashes: list[str] = []
    authority_specs = {
        "governance": (5, 3),
        "treasury": (5, 3),
        "emergency": (3, 2),
    }
    if network == "polygon-amoy":
        authority_specs.update(
            {
                "vdso_guardian": (3, 2),
                "vdso_recovery": (3, 2),
            }
        )
    for name, (owner_count, threshold) in authority_specs.items():
        authority = raw_authorities.get(name)
        if not isinstance(authority, dict):
            errors.append(f"{network} {name} authority is missing")
            continue
        authorities[name] = authority
        address = authority.get("address")
        owners = authority.get("owners")
        if (
            not isinstance(owners, list)
            or len(owners) != owner_count
            or len(set(owners)) != owner_count
        ):
            errors.append(f"{network} {name} must have {owner_count} distinct owners")
        elif network == "polygon-amoy" and any(not _is_evm_address(owner) for owner in owners):
            errors.append(f"{network} {name} owner addresses are invalid")
        elif network == "cardano-preprod" and any(not _is_cardano_hash(owner) for owner in owners):
            errors.append(f"{network} {name} owner credential hashes are invalid")
        if authority.get("threshold") != threshold:
            errors.append(f"{network} {name} threshold must equal {threshold}")
        if not str(authority.get("recovery_policy", "")).strip():
            errors.append(f"{network} {name} recovery policy is missing")
        if name == "emergency" and authority.get("scope") != "pause-only":
            errors.append(f"{network} emergency scope must be pause-only")
        if name == "vdso_guardian" and authority.get("scope") != "vdso-quarantine":
            errors.append(
                f"{network} vdso_guardian scope must be vdso-quarantine"
            )
        if name == "vdso_recovery" and authority.get("scope") != "vdso-recovery":
            errors.append(f"{network} vdso_recovery scope must be vdso-recovery")

        if network == "polygon-amoy":
            if authority.get("authority_type") != "safe":
                errors.append(f"{network} {name} authority_type must equal safe")
            if not _is_evm_address(address) or str(address).lower() == EVM_ZERO_ADDRESS:
                errors.append(f"{network} {name} Safe proxy address is invalid")
            else:
                addresses.append(str(address).lower())
            for field in ("proxy_runtime_code_hash", "singleton_runtime_code_hash"):
                value = authority.get(field)
                if not _is_evm_hash(value) or value == "0x" + "0" * 64:
                    errors.append(f"{network} {name} {field} is invalid")
            singleton = authority.get("singleton_address")
            if not _is_evm_address(singleton) or str(singleton).lower() == EVM_ZERO_ADDRESS:
                errors.append(f"{network} {name} singleton_address is invalid")
            if not _is_sha256(authority.get("identity_check_evidence_sha256")):
                errors.append(f"{network} {name} identity evidence hash is invalid")
        else:
            if authority.get("authority_type") != "cardano-script":
                errors.append(f"{network} {name} authority_type must equal cardano-script")
            if not isinstance(address, str) or not address.startswith("addr_test1"):
                errors.append(f"{network} {name} script address is invalid")
            else:
                addresses.append(address)
            script_hash = authority.get("script_hash")
            if not _is_cardano_hash(script_hash):
                errors.append(f"{network} {name} script_hash is invalid")
            else:
                script_hashes.append(str(script_hash))
            if not _is_sha256(authority.get("script_cbor_sha256")):
                errors.append(f"{network} {name} script_cbor_sha256 is invalid")
            errors.extend(
                _validate_bundle_evidence(
                    authority.get("script_cbor_path"),
                    authority.get("script_cbor_sha256"),
                    bundle_root,
                    f"{network} {name} authority script CBOR",
                )
            )
            errors.extend(
                _validate_source_binding(
                    authority.get("script_source"),
                    authority.get("script_source_sha256"),
                    f"{network} {name} authority",
                )
            )
            if not _is_sha256(authority.get("identity_check_evidence_sha256")):
                errors.append(f"{network} {name} identity evidence hash is invalid")
        identity_fields = {
            field: authority.get(field)
            for field in (
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
            )
            if field in authority
        }
        errors.extend(
            _validate_bundle_evidence(
                authority.get("identity_check_evidence_path"),
                authority.get("identity_check_evidence_sha256"),
                bundle_root,
                f"{network} {name} authority identity",
                expected_record=_observation_record(
                    "deployment-authority-identity",
                    commit_sha,
                    network,
                    identity_fields,
                ),
            )
        )
    if len(addresses) == len(authority_specs) and len(set(addresses)) != len(
        authority_specs
    ):
        errors.append(f"{network} authority addresses must be distinct")
    if script_hashes and len(script_hashes) != len(set(script_hashes)):
        errors.append(f"{network} authority script hashes must be distinct")
    return errors, authorities


def _validate_timelock_identity(
    manifest: dict,
    network: str,
    artifacts: dict[str, dict],
    authorities: dict[str, dict],
    bundle_root: Path,
    commit_sha: str,
) -> list[str]:
    errors: list[str] = []
    identity = manifest.get("timelock_identity")
    if not isinstance(identity, dict):
        return [f"{network} timelock identity is missing"]
    delay = identity.get("minimum_delay_seconds")
    if delay != manifest.get("timelock_seconds") or not isinstance(delay, int) or delay < 172800:
        errors.append(f"{network} timelock identity does not prove the configured 48-hour delay")

    if network == "polygon-amoy":
        if identity.get("identity_type") != "evm-runtime":
            errors.append(f"{network} timelock identity_type must equal evm-runtime")
        address = identity.get("address")
        actual_hash = identity.get("actual_runtime_code_hash")
        expected_hash = identity.get("expected_runtime_code_hash")
        if not _is_evm_address(address) or str(address).lower() == EVM_ZERO_ADDRESS:
            errors.append(f"{network} timelock address is invalid")
        if not _is_evm_hash(actual_hash) or actual_hash == "0x" + "0" * 64:
            errors.append(f"{network} timelock actual runtime code hash is invalid")
        if not _is_evm_hash(expected_hash) or expected_hash == "0x" + "0" * 64:
            errors.append(f"{network} timelock expected runtime code hash is invalid")
        if actual_hash != expected_hash:
            errors.append(f"{network} timelock actual and expected runtime code hashes differ")
        errors.extend(
            _validate_source_binding(
                identity.get("source"),
                identity.get("source_sha256"),
                f"{network} timelock identity",
                expected_source=DEPLOYMENT_ARTIFACT_SOURCES["VAMSTimelockController"],
            )
        )
        timelock_artifact = artifacts.get("VAMSTimelockController", {})
        if timelock_artifact.get("address") != address:
            errors.append(f"{network} timelock identity address does not match its artifact")
        if timelock_artifact.get("runtime_code_hash") != actual_hash:
            errors.append(f"{network} timelock runtime code hash does not match its artifact")

        governance_address = authorities.get("governance", {}).get("address")
        governor_address = artifacts.get("VAMSGovernor", {}).get("address")
        deployer = manifest.get("deployer")
        expected_roles = {
            ("DEFAULT_ADMIN_ROLE", str(address).lower(), True),
            ("PROPOSER_ROLE", str(governance_address).lower(), True),
            ("PROPOSER_ROLE", str(governor_address).lower(), True),
            ("CANCELLER_ROLE", str(governance_address).lower(), True),
            ("EXECUTOR_ROLE", EVM_ZERO_ADDRESS, True),
            ("DEFAULT_ADMIN_ROLE", str(deployer).lower(), False),
        }
        observed_roles: set[tuple[str, str, bool]] = set()
        roles = identity.get("roles")
        if not isinstance(roles, list):
            errors.append(f"{network} timelock role evidence is missing")
        else:
            for role in roles:
                if not isinstance(role, dict):
                    errors.append(f"{network} timelock contains an invalid role record")
                    continue
                role_name = role.get("role")
                account = role.get("account")
                granted = role.get("granted")
                if not isinstance(role_name, str) or not _is_evm_address(account) or not isinstance(granted, bool):
                    errors.append(f"{network} timelock contains an invalid role assignment")
                    continue
                key = (role_name, str(account).lower(), granted)
                if key in observed_roles:
                    errors.append(f"{network} timelock contains duplicate role evidence")
                observed_roles.add(key)
                if not _is_sha256(role.get("evidence_sha256")):
                    errors.append(f"{network} timelock role evidence hash is invalid")
                if not isinstance(role.get("observed_at_block"), int) or role["observed_at_block"] < 0:
                    errors.append(f"{network} timelock role observation block is invalid")
                errors.extend(
                    _validate_bundle_evidence(
                        role.get("evidence_path"),
                        role.get("evidence_sha256"),
                        bundle_root,
                        f"{network} timelock role {role_name}",
                        expected_record=_observation_record(
                            "timelock-role-observation",
                            commit_sha,
                            network,
                            {
                                field: role.get(field)
                                for field in (
                                    "role",
                                    "account",
                                    "granted",
                                    "observed_at_block",
                                )
                            },
                        ),
                    )
                )
            missing = expected_roles - observed_roles
            unexpected = observed_roles - expected_roles
            if missing:
                errors.append(f"{network} timelock required role assignments are missing")
            if unexpected:
                errors.append(f"{network} timelock contains unexpected role assignments")
        errors.extend(
            _validate_bundle_evidence(
                identity.get("identity_check_evidence_path"),
                identity.get("identity_check_evidence_sha256"),
                bundle_root,
                f"{network} timelock runtime identity",
                expected_record=_observation_record(
                    "timelock-runtime-identity",
                    commit_sha,
                    network,
                    {
                        field: identity.get(field)
                        for field in (
                            "identity_type",
                            "address",
                            "source",
                            "source_sha256",
                            "actual_runtime_code_hash",
                            "expected_runtime_code_hash",
                            "minimum_delay_seconds",
                        )
                    },
                ),
            )
        )
    else:
        if identity.get("identity_type") != "plutus-script":
            errors.append(f"{network} timelock identity_type must equal plutus-script")
        if not isinstance(identity.get("script_address"), str) or not identity["script_address"].startswith("addr_test1"):
            errors.append(f"{network} timelock script address is invalid")
        if not _is_cardano_hash(identity.get("script_hash")):
            errors.append(f"{network} timelock script_hash is invalid")
        actual_hash = identity.get("actual_script_cbor_sha256")
        expected_hash = identity.get("expected_script_cbor_sha256")
        if not _is_sha256(actual_hash) or not _is_sha256(expected_hash):
            errors.append(f"{network} timelock actual or expected script CBOR hash is invalid")
        elif actual_hash != expected_hash:
            errors.append(f"{network} timelock actual and expected script CBOR hashes differ")
        if not _is_cardano_hash(identity.get("governor_script_hash")):
            errors.append(f"{network} timelock governor script binding is invalid")
        if identity.get("cancel_threshold") != 2:
            errors.append(f"{network} timelock cancel threshold must equal 2")
        if not isinstance(identity.get("observed_at_slot"), int) or identity["observed_at_slot"] < 0:
            errors.append(f"{network} timelock observation slot is invalid")
        if not _is_sha256(identity.get("control_evidence_sha256")):
            errors.append(f"{network} timelock control evidence hash is invalid")
        errors.extend(
            _validate_source_binding(
                identity.get("source"),
                identity.get("source_sha256"),
                f"{network} timelock identity",
                expected_source=DEPLOYMENT_ARTIFACT_SOURCES["timelock.ak"],
            )
        )
        timelock_artifact = artifacts.get("timelock.ak", {})
        governor_artifact = artifacts.get("governor.ak", {})
        if timelock_artifact.get("address") != identity.get("script_address"):
            errors.append(f"{network} timelock identity address does not match its artifact")
        if timelock_artifact.get("script_hash") != identity.get("script_hash"):
            errors.append(f"{network} timelock script hash does not match its artifact")
        if timelock_artifact.get("script_cbor_sha256") != actual_hash:
            errors.append(f"{network} timelock script CBOR hash does not match its artifact")
        if governor_artifact.get("script_hash") != identity.get("governor_script_hash"):
            errors.append(f"{network} governor script binding does not match its artifact")
        errors.extend(
            _validate_bundle_evidence(
                identity.get("control_evidence_path"),
                identity.get("control_evidence_sha256"),
                bundle_root,
                f"{network} timelock control",
                expected_record=_observation_record(
                    "timelock-cardano-control",
                    commit_sha,
                    network,
                    {
                        field: identity.get(field)
                        for field in (
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
                        )
                    },
                ),
            )
        )
    return errors


def _validate_role_transfers(
    manifest: dict,
    network: str,
    stage: str,
    artifacts: dict[str, dict],
    authorities: dict[str, dict],
    bundle_root: Path,
    commit_sha: str,
) -> list[str]:
    errors: list[str] = []
    transfers = manifest.get("role_transfers")
    if not isinstance(transfers, list) or not transfers:
        return [f"{network} role or control transfer evidence is missing"]
    deployer = manifest.get("deployer")
    removal_found = False
    handoff_found = False
    seen: set[tuple[object, ...]] = set()
    if network == "polygon-amoy":
        permitted_handoff_accounts = {
            str(manifest.get("timelock_identity", {}).get("address", "")).lower(),
            *(
                str(authority.get("address", "")).lower()
                for authority in authorities.values()
            ),
        }
        for transfer in transfers:
            if not isinstance(transfer, dict):
                errors.append(f"{network} contains an invalid role transfer")
                continue
            target = transfer.get("target")
            account = transfer.get("account")
            action = transfer.get("action")
            role = transfer.get("role")
            key = (target, role, action, account)
            if key in seen:
                errors.append(f"{network} contains duplicate role transfer evidence")
            seen.add(key)
            if not _is_evm_address(target) or not _is_evm_address(account):
                errors.append(f"{network} role transfer address is invalid")
            if not isinstance(role, str) or not role:
                errors.append(f"{network} role transfer role is missing")
            if action not in {"grant", "revoke", "renounce"}:
                errors.append(f"{network} role transfer action is invalid")
            if transfer.get("verified") is not True:
                errors.append(f"{network} role transfer is not verified")
            if not _is_sha256(transfer.get("evidence_sha256")):
                errors.append(f"{network} role transfer evidence hash is invalid")
            if not isinstance(transfer.get("observed_at_block"), int) or transfer["observed_at_block"] < 0:
                errors.append(f"{network} role transfer observation block is invalid")
            if stage == "public" and not _is_evm_hash(transfer.get("transaction_hash")):
                errors.append(f"{network} public role transfer transaction_hash is invalid")
            errors.extend(
                _validate_bundle_evidence(
                    transfer.get("evidence_path"),
                    transfer.get("evidence_sha256"),
                    bundle_root,
                    f"{network} role transfer {role}:{action}",
                    expected_record=_observation_record(
                        "role-transfer-observation",
                        commit_sha,
                        network,
                        {
                            field: transfer.get(field)
                            for field in (
                                "target",
                                "role",
                                "action",
                                "account",
                                "verified",
                                "observed_at_block",
                                "transaction_hash",
                            )
                            if field in transfer
                        },
                    ),
                )
            )
            account_text = str(account).lower()
            removal_found |= action in {"revoke", "renounce"} and account_text == str(deployer).lower()
            handoff_found |= action == "grant" and account_text in permitted_handoff_accounts
    else:
        valid_script_hashes = {
            str(artifact.get("script_hash")) for artifact in artifacts.values()
        } | {str(authority.get("script_hash")) for authority in authorities.values()}
        for transfer in transfers:
            if not isinstance(transfer, dict):
                errors.append(f"{network} contains an invalid control transfer")
                continue
            action = transfer.get("action")
            source = transfer.get("from_credential")
            target = transfer.get("to_script_hash")
            control = transfer.get("control")
            key = (control, action, source, target)
            if key in seen:
                errors.append(f"{network} contains duplicate control transfer evidence")
            seen.add(key)
            if not isinstance(control, str) or not control:
                errors.append(f"{network} control transfer name is missing")
            if action not in {"parameterize", "handoff", "retire-deployer"}:
                errors.append(f"{network} control transfer action is invalid")
            if not _is_cardano_hash(source) or not _is_cardano_hash(target):
                errors.append(f"{network} control transfer credential or script hash is invalid")
            elif target not in valid_script_hashes:
                errors.append(f"{network} control transfer target is not a declared script")
            if transfer.get("verified") is not True:
                errors.append(f"{network} control transfer is not verified")
            if not _is_sha256(transfer.get("evidence_sha256")):
                errors.append(f"{network} control transfer evidence hash is invalid")
            if not isinstance(transfer.get("observed_at_slot"), int) or transfer["observed_at_slot"] < 0:
                errors.append(f"{network} control transfer observation slot is invalid")
            if stage == "public" and not _is_sha256(transfer.get("transaction_hash")):
                errors.append(f"{network} public control transfer transaction_hash is invalid")
            errors.extend(
                _validate_bundle_evidence(
                    transfer.get("evidence_path"),
                    transfer.get("evidence_sha256"),
                    bundle_root,
                    f"{network} control transfer {control}:{action}",
                    expected_record=_observation_record(
                        "control-transfer-observation",
                        commit_sha,
                        network,
                        {
                            field: transfer.get(field)
                            for field in (
                                "control",
                                "action",
                                "from_credential",
                                "to_script_hash",
                                "verified",
                                "observed_at_slot",
                                "transaction_hash",
                            )
                            if field in transfer
                        },
                    ),
                )
            )
            removal_found |= action == "retire-deployer" and source == deployer
            handoff_found |= action in {"parameterize", "handoff"}
    if not removal_found:
        errors.append(f"{network} does not include verified deployer privilege removal")
    if not handoff_found:
        errors.append(f"{network} does not include verified authority handoff")
    return errors


def _validate_deployer_privilege_checks(
    manifest: dict,
    network: str,
    required_artifacts: set[str],
    bundle_root: Path,
    commit_sha: str,
) -> list[str]:
    errors: list[str] = []
    checks = manifest.get("deployer_privilege_checks")
    if not isinstance(checks, list):
        return [f"{network} deployer privilege checks are missing"]
    required_coverage = (
        required_artifacts - NON_DEPLOYABLE_EVM_ARTIFACTS
        if network == "polygon-amoy"
        else required_artifacts
    )
    covered: set[str] = set()
    deployer = manifest.get("deployer")
    for check in checks:
        if not isinstance(check, dict):
            errors.append(f"{network} contains an invalid deployer privilege check")
            continue
        artifact = check.get("artifact")
        if not isinstance(artifact, str) or artifact not in required_coverage:
            errors.append(f"{network} deployer privilege check references an invalid artifact")
            continue
        if artifact in covered:
            errors.append(f"{network} contains duplicate deployer privilege check for {artifact}")
        covered.add(artifact)
        if not _is_sha256(check.get("evidence_sha256")):
            errors.append(f"{network} {artifact} deployer privilege evidence hash is invalid")
        if network == "polygon-amoy":
            if check.get("account") != deployer:
                errors.append(f"{network} {artifact} privilege check does not query the deployer")
            if not str(check.get("privilege", "")).strip():
                errors.append(f"{network} {artifact} privilege name is missing")
            if check.get("granted") is not False:
                errors.append(f"{network} {artifact} still grants a deployer privilege")
            if not isinstance(check.get("observed_at_block"), int) or check["observed_at_block"] < 0:
                errors.append(f"{network} {artifact} privilege observation block is invalid")
        else:
            if check.get("credential") != deployer:
                errors.append(f"{network} {artifact} control check does not query the deployer")
            if check.get("can_authorize") is not False:
                errors.append(f"{network} {artifact} still permits deployer authorization")
            if not isinstance(check.get("observed_at_slot"), int) or check["observed_at_slot"] < 0:
                errors.append(f"{network} {artifact} control observation slot is invalid")
        errors.extend(
            _validate_bundle_evidence(
                check.get("evidence_path"),
                check.get("evidence_sha256"),
                bundle_root,
                f"{network} {artifact} deployer privilege check",
                expected_record=_observation_record(
                    "deployer-privilege-observation",
                    commit_sha,
                    network,
                    {
                        field: check.get(field)
                        for field in (
                            "artifact",
                            "account",
                            "credential",
                            "privilege",
                            "granted",
                            "can_authorize",
                            "observed_at_block",
                            "observed_at_slot",
                        )
                        if field in check
                    },
                ),
            )
        )
    missing = required_coverage - covered
    if missing:
        errors.append(
            f"{network} deployer privilege checks missing artifacts: "
            + ", ".join(sorted(missing))
        )
    return errors


def _validate_deployment_manifests(
    paths: list[Path], stage: str, commit_sha: str, bundle_root: Path | None = None
) -> list[str]:
    errors: list[str] = []
    seen_networks: set[str] = set()
    for path in paths:
        if not path.is_file():
            errors.append(f"deployment manifest is missing: {path}")
            continue
        manifest = _load_json(path)
        if not isinstance(manifest, dict):
            errors.append(f"deployment manifest must be an object: {path}")
            continue
        network = manifest.get("network")
        if network not in DEPLOYMENT_NETWORKS:
            errors.append(f"deployment manifest has invalid network: {path}")
            continue
        if network in seen_networks:
            errors.append(f"duplicate deployment manifest for {network}")
        else:
            seen_networks.add(network)
        expected_status = "rehearsed" if stage == "canary" else "deployed"
        if manifest.get("schema_version") != DEPLOYMENT_MANIFEST_SCHEMA_VERSION:
            errors.append(
                f"{network} deployment schema_version must equal "
                + DEPLOYMENT_MANIFEST_SCHEMA_VERSION
            )
        if manifest.get("deployment_status") != expected_status:
            errors.append(f"{network} must have deployment_status={expected_status}")
        if manifest.get("commit_sha") != commit_sha:
            errors.append(f"{network} commit does not match the current commit")
        if _contains_pending(manifest):
            errors.append(f"{network} contains Pending deployment evidence")
        if not str(manifest.get("chain_identifier", "")).strip():
            errors.append(f"{network} chain identifier is missing")
        if network == "polygon-amoy":
            if not _is_evm_address(manifest.get("deployer")):
                errors.append(f"{network} deployer address is invalid")
            required_artifacts = CANARY_EVM_ARTIFACTS if stage == "canary" else PUBLIC_EVM_ARTIFACTS
        else:
            if not _is_cardano_hash(manifest.get("deployer")):
                errors.append(f"{network} deployer credential hash is invalid")
            required_artifacts = CARDANO_ARTIFACTS
        if manifest.get("deployer_privileges_removed") is not True:
            errors.append(f"{network} does not prove deployer privilege removal")
        if manifest.get("mock_routes_disabled") is not True:
            errors.append(f"{network} does not prove mock-route exclusion")
        if not isinstance(manifest.get("timelock_seconds"), int) or manifest["timelock_seconds"] < 172800:
            errors.append(f"{network} timelock is below 48 hours")
        if not str(manifest.get("rollback_plan", "")).strip():
            errors.append(f"{network} rollback plan is missing")
        evidence_root = (bundle_root or path.parent).resolve()

        artifact_errors, artifacts = _validate_deployment_artifacts(
            manifest,
            network,
            stage,
            required_artifacts,
            evidence_root,
            commit_sha,
        )
        authority_errors, authorities = _validate_deployment_authorities(
            manifest, network, evidence_root, commit_sha
        )
        errors.extend(artifact_errors)
        errors.extend(authority_errors)
        errors.extend(
            _validate_vdso_deployment_state(
                manifest, network, artifacts, evidence_root, commit_sha
            )
        )
        errors.extend(
            _validate_timelock_identity(
                manifest,
                network,
                artifacts,
                authorities,
                evidence_root,
                commit_sha,
            )
        )
        errors.extend(
            _validate_role_transfers(
                manifest,
                network,
                stage,
                artifacts,
                authorities,
                evidence_root,
                commit_sha,
            )
        )
        errors.extend(
            _validate_deployer_privilege_checks(
                manifest, network, required_artifacts, evidence_root, commit_sha
            )
        )
    missing = DEPLOYMENT_NETWORKS - seen_networks
    if missing:
        errors.append("deployment manifests missing networks: " + ", ".join(sorted(missing)))
    return errors


def _validate_assurance_index(
    path: Path,
    stage: str,
    commit_sha: str,
    required_track_ids: set[str],
    bundle_root: Path | None = None,
) -> list[str]:
    if not path.is_file():
        return [f"assurance index is missing: {path}"]
    index = _load_json(path)
    if not isinstance(index, dict) or not isinstance(index.get("tracks"), list):
        return ["assurance index must contain a tracks array"]
    errors: list[str] = []
    if index.get("schema_version") != "1.0.0":
        errors.append("assurance index schema_version must equal 1.0.0")
    if index.get("commit_sha") != commit_sha:
        errors.append("assurance index commit does not match the current commit")
    entries: dict[str, dict] = {}
    for entry in index["tracks"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            errors.append("assurance index contains an invalid track entry")
            continue
        track_id = entry["id"]
        if track_id in entries:
            errors.append(f"assurance index contains duplicate track {track_id}")
        entries[track_id] = entry

    unexpected = set(entries) - required_track_ids
    if unexpected:
        errors.append(
            "assurance index contains unexpected tracks: " + ", ".join(sorted(unexpected))
        )

    for track_id in sorted(required_track_ids):
        entry = entries.get(track_id)
        if entry is None:
            errors.append(f"assurance index is missing {track_id}")
            continue
        if entry.get("status") != "verified":
            errors.append(f"assurance index does not verify {track_id}")
        if entry.get("blocking_findings_open") != 0:
            errors.append(f"assurance index records open blocking findings for {track_id}")
        if not str(entry.get("reviewer", "")).strip():
            errors.append(f"assurance index reviewer is missing for {track_id}")
        approved_at = entry.get("approved_at")
        if not isinstance(approved_at, str):
            errors.append(f"assurance index approval timestamp is missing for {track_id}")
        else:
            try:
                parsed_approval = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
            except ValueError:
                parsed_approval = None
            if parsed_approval is None or parsed_approval.tzinfo is None:
                errors.append(f"assurance index approval timestamp is invalid for {track_id}")
        track_number = int(track_id[1:])
        if stage == "public" and 10 <= track_number <= 34:
            if entry.get("independent_review") is not True:
                errors.append(f"public readiness requires independent review for {track_id}")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"assurance index artifacts are missing for {track_id}")
            continue
        artifact_paths: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                errors.append(f"{track_id} contains an invalid artifact record")
                continue
            relative_path = artifact.get("path")
            expected_hash = artifact.get("sha256")
            if not isinstance(relative_path, str) or not relative_path:
                errors.append(f"{track_id} artifact path is missing")
                continue
            if relative_path in artifact_paths:
                errors.append(f"{track_id} contains duplicate artifact path: {relative_path}")
                continue
            artifact_paths.add(relative_path)
            artifact_root = bundle_root or ROOT
            artifact_path = (artifact_root / relative_path).resolve()
            try:
                artifact_path.relative_to(artifact_root.resolve())
            except ValueError:
                errors.append(f"{track_id} artifact escapes the repository: {relative_path}")
                continue
            if not artifact_path.is_file():
                errors.append(f"{track_id} artifact is missing: {relative_path}")
                continue
            actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if expected_hash != actual_hash:
                errors.append(f"{track_id} artifact hash mismatch: {relative_path}")
    return errors


def _validate_canary_report(
    path: Path, commit_sha: str, bundle_root: Path | None = None
) -> list[str]:
    if not path.is_file():
        return [f"closed-canary report is missing: {path}"]
    report = _load_json(path)
    if not isinstance(report, dict):
        return ["closed-canary report must be an object"]
    errors: list[str] = []
    schema = _load_json(SCHEMA_DIR / "closed-canary-report.schema.json")
    if not isinstance(schema, dict):
        return ["closed-canary report schema must be an object"]
    required_fields = set(schema.get("required", []))
    allowed_fields = set(schema.get("properties", {}))
    missing_fields = required_fields - set(report)
    unexpected_fields = set(report) - allowed_fields
    if missing_fields:
        errors.append(
            "closed-canary report schema fields are missing: "
            + ", ".join(sorted(missing_fields))
        )
    if unexpected_fields:
        errors.append(
            "closed-canary report contains unexpected schema fields: "
            + ", ".join(sorted(unexpected_fields))
        )
    if report.get("schema_version") != "1.0.0":
        errors.append("closed-canary report schema_version must equal 1.0.0")
    if report.get("commit_sha") != commit_sha:
        errors.append("closed-canary report commit does not match the current commit")
    consecutive_days = report.get("consecutive_days")
    if (
        not isinstance(consecutive_days, int)
        or isinstance(consecutive_days, bool)
        or consecutive_days < 7
    ):
        errors.append("closed canary must complete at least 7 consecutive days")
    timestamps: dict[str, datetime] = {}
    for field in ("started_at", "ended_at"):
        raw_value = report.get(field)
        if not isinstance(raw_value, str):
            errors.append(f"closed-canary report {field} is missing")
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is None or parsed.tzinfo is None:
            errors.append(f"closed-canary report {field} must be timezone-aware")
        else:
            timestamps[field] = parsed
    if set(timestamps) == {"started_at", "ended_at"}:
        elapsed = timestamps["ended_at"] - timestamps["started_at"]
        if elapsed < timedelta(days=7):
            errors.append("closed-canary measured duration is below 7 days")
        if isinstance(consecutive_days, int) and not isinstance(consecutive_days, bool):
            if elapsed < timedelta(days=consecutive_days):
                errors.append(
                    "closed-canary consecutive_days exceeds measured duration"
                )
        if timestamps["ended_at"] > datetime.now(timezone.utc):
            errors.append("closed-canary ended_at must not be in the future")
    if report.get("stop_conditions_triggered") is not False:
        errors.append("closed canary recorded a stop condition")
    evidence_root = (bundle_root or path.parent).resolve()
    used_paths: set[str] = set()

    def validate_binding(record: dict, context: str) -> None:
        evidence_path = record.get("evidence_path")
        if isinstance(evidence_path, str):
            if evidence_path in used_paths:
                errors.append(f"closed-canary evidence path is reused: {evidence_path}")
            used_paths.add(evidence_path)
            if (evidence_root / evidence_path).resolve() == path.resolve():
                errors.append("closed-canary report must not self-reference")
                return
        errors.extend(
            _validate_bundle_evidence(
                evidence_path,
                record.get("evidence_sha256"),
                evidence_root,
                context,
            )
        )

    daily_evidence = report.get("daily_evidence")
    parsed_days: list[tuple[datetime, datetime]] = []
    seen_dates: set[str] = set()
    if not isinstance(daily_evidence, list) or len(daily_evidence) < 7:
        errors.append("closed-canary report requires at least 7 daily evidence records")
    else:
        for day in daily_evidence:
            if not isinstance(day, dict) or set(day) != {
                "date",
                "started_at",
                "ended_at",
                "evidence_path",
                "evidence_sha256",
            }:
                errors.append("closed-canary daily evidence record is invalid")
                continue
            date_text = day.get("date")
            if not isinstance(date_text, str) or date_text in seen_dates:
                errors.append("closed-canary daily evidence date is invalid or duplicated")
                continue
            seen_dates.add(date_text)
            try:
                calendar_day = datetime.strptime(date_text, "%Y-%m-%d").date()
                day_started = datetime.fromisoformat(
                    str(day.get("started_at", "")).replace("Z", "+00:00")
                )
                day_ended = datetime.fromisoformat(
                    str(day.get("ended_at", "")).replace("Z", "+00:00")
                )
            except ValueError:
                errors.append(f"closed-canary daily evidence timestamps are invalid: {date_text}")
                continue
            expected_start = datetime(
                calendar_day.year,
                calendar_day.month,
                calendar_day.day,
                tzinfo=timezone.utc,
            )
            if (
                day_started.tzinfo is None
                or day_ended.tzinfo is None
                or day_started.utcoffset() != timedelta(0)
                or day_ended.utcoffset() != timedelta(0)
                or day_started != expected_start
                or day_ended != expected_start + timedelta(days=1)
            ):
                errors.append(
                    f"closed-canary daily evidence must cover one exact UTC day: {date_text}"
                )
            else:
                parsed_days.append((day_started, day_ended))
            validate_binding(day, f"closed-canary UTC day {date_text}")
        parsed_days.sort()
        required_day_count = (
            consecutive_days
            if isinstance(consecutive_days, int) and not isinstance(consecutive_days, bool)
            else 7
        )
        if len(parsed_days) < max(7, required_day_count):
            errors.append(
                "closed-canary daily evidence does not cover every asserted consecutive day"
            )
        for previous, current in zip(parsed_days, parsed_days[1:]):
            if previous[1] != current[0]:
                errors.append("closed-canary daily evidence contains a gap or overlap")
                break
        if parsed_days and set(timestamps) == {"started_at", "ended_at"}:
            if (
                parsed_days[0][0] < timestamps["started_at"]
                or parsed_days[-1][1] > timestamps["ended_at"]
            ):
                errors.append(
                    "closed-canary daily evidence falls outside the reported interval"
                )

    drills = report.get("drills")
    if not isinstance(drills, dict):
        errors.append("closed-canary report must contain drill results")
    else:
        missing = REQUIRED_DRILLS - set(drills)
        unexpected = set(drills) - REQUIRED_DRILLS
        if missing:
            errors.append("closed-canary drills are missing: " + ", ".join(sorted(missing)))
        if unexpected:
            errors.append(
                "closed-canary drills are unexpected: " + ", ".join(sorted(unexpected))
            )
        for name in sorted(REQUIRED_DRILLS & set(drills)):
            drill = drills.get(name)
            if not isinstance(drill, dict) or set(drill) != {
                "passed",
                "evidence_path",
                "evidence_sha256",
            }:
                errors.append(f"closed-canary drill {name} evidence is invalid")
                continue
            if drill.get("passed") is not True:
                errors.append(f"closed-canary drill not passed: {name}")
            validate_binding(drill, f"closed-canary drill {name}")
    metrics = report.get("metric_artifacts")
    if not isinstance(metrics, list) or not metrics:
        errors.append("closed-canary report must bind metric artifacts")
    else:
        metric_names: set[str] = set()
        for metric in metrics:
            if not isinstance(metric, dict) or set(metric) != {
                "name",
                "value",
                "unit",
                "evidence_path",
                "evidence_sha256",
            }:
                errors.append("closed-canary metric evidence is invalid")
                continue
            name = metric.get("name")
            value = metric.get("value")
            if not isinstance(name, str) or not name.strip() or name in metric_names:
                errors.append("closed-canary metric name is invalid or duplicated")
            else:
                metric_names.add(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"closed-canary metric value is invalid: {name}")
            if not str(metric.get("unit", "")).strip():
                errors.append(f"closed-canary metric unit is missing: {name}")
            validate_binding(metric, f"closed-canary metric {name}")
    return errors


def _compute_source_root(source_paths: list[str]) -> str:
    repository_root = ROOT.resolve()
    files: list[tuple[str, Path]] = []
    for declared_path in source_paths:
        source_path = (repository_root / declared_path).resolve()
        try:
            source_path.relative_to(repository_root)
        except ValueError as exc:
            raise ValueError(
                f"implementation source escapes the repository: {declared_path}"
            ) from exc
        if not source_path.exists():
            raise ValueError(f"implementation source is missing: {declared_path}")
        candidates = (
            [source_path] if source_path.is_file() else sorted(source_path.rglob("*"))
        )
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError(f"implementation source contains a symlink: {candidate}")
            if not candidate.is_file():
                continue
            if candidate.suffix in {".pyc", ".pyo"} or "__pycache__" in candidate.parts:
                continue
            relative_path = candidate.relative_to(repository_root).as_posix()
            files.append((relative_path, candidate))
    if not files:
        raise ValueError("implementation source set contains no files")
    digest = hashlib.sha256()
    for relative_path, candidate in sorted(files):
        encoded_path = relative_path.encode("utf-8")
        content = candidate.read_bytes()
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _canonical_shadow_record(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _parse_shadow_timestamp(value: object, context: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        errors.append(f"{context} must be an RFC3339 UTC timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        errors.append(f"{context} must be an RFC3339 UTC timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        errors.append(f"{context} must be an RFC3339 UTC timestamp")
        return None
    return parsed


def _validate_backend_counts(
    value: object, expected: int, context: str, errors: list[str]
) -> None:
    if not isinstance(value, dict) or set(value) != VDSO_SHADOW_BACKENDS:
        errors.append(f"{context} must contain exactly python, rust, and aiken")
        return
    invalid = sorted(
        backend
        for backend in VDSO_SHADOW_BACKENDS
        if value.get(backend) != expected or isinstance(value.get(backend), bool)
    )
    if invalid:
        errors.append(
            f"{context} must equal {expected} for every backend: "
            + ", ".join(invalid)
        )


def _validate_vdso_shadow_input(input_path: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    source_fields = {
        "schema_version",
        "source_sequence",
        "source_cursor_hash",
        "input_commitment",
        "previous_source_record_sha256",
        "source_record_sha256",
    }
    expected_previous_hash = "0" * 64
    previous_sequence: int | None = None
    seen_cursors: set[str] = set()
    record_count = 0
    current_chunk: dict | None = None
    chunk_boundaries: list[dict] = []
    final_cursor: object = None
    try:
        handle = input_path.open("rb")
    except OSError as exc:
        return [f"VDSO shadow input JSONL cannot be read: {exc}"], {}
    with handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.endswith(b"\n") or b"\r" in raw_line:
                errors.append(
                    f"VDSO shadow input record {line_number} is not LF-terminated"
                )
            line_bytes = raw_line[:-1] if raw_line.endswith(b"\n") else raw_line
            try:
                line = line_bytes.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(
                    f"VDSO shadow input record {line_number} is not strict UTF-8"
                )
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                errors.append(
                    f"VDSO shadow input record {line_number} is not valid JSON"
                )
                continue
            if not isinstance(record, dict):
                errors.append(f"VDSO shadow input record {line_number} must be an object")
                continue
            if set(record) != source_fields:
                errors.append(
                    f"VDSO shadow input record {line_number} fields do not match the commitment-only contract"
                )
            if line != _canonical_shadow_record(record):
                errors.append(
                    f"VDSO shadow input record {line_number} is not canonical JSON"
                )
            if record.get("schema_version") != VDSO_SHADOW_AUDIT_SCHEMA_VERSION:
                errors.append(
                    f"VDSO shadow input record {line_number} is not schema v1"
                )
            sequence = record.get("source_sequence")
            if (
                not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or sequence < 0
                or sequence > 18446744073709551615
            ):
                errors.append(
                    f"VDSO shadow input record {line_number} source_sequence is not uint64"
                )
            elif previous_sequence is not None and sequence != previous_sequence + 1:
                errors.append(
                    f"VDSO shadow input record {line_number} sequence is duplicated, reordered, or gapped"
                )
            if isinstance(sequence, int) and not isinstance(sequence, bool):
                previous_sequence = sequence
            cursor = record.get("source_cursor_hash")
            if not _is_sha256(cursor) or cursor == "0" * 64:
                errors.append(
                    f"VDSO shadow input record {line_number} cursor is malformed or zero"
                )
            elif cursor in seen_cursors:
                errors.append(
                    f"VDSO shadow input record {line_number} cursor is duplicated"
                )
            else:
                seen_cursors.add(cursor)
            commitment = record.get("input_commitment")
            if not _is_sha256(commitment) or commitment == "0" * 64:
                errors.append(
                    f"VDSO shadow input record {line_number} commitment is malformed or zero"
                )
            if record.get("previous_source_record_sha256") != expected_previous_hash:
                errors.append(
                    f"VDSO shadow input record {line_number} breaks the source hash chain"
                )
            unhashed = dict(record)
            unhashed.pop("source_record_sha256", None)
            computed_hash = hashlib.sha256(
                _canonical_shadow_record(unhashed).encode("utf-8")
            ).hexdigest()
            declared_hash = record.get("source_record_sha256")
            if declared_hash != computed_hash:
                errors.append(
                    f"VDSO shadow input record {line_number} hash is invalid"
                )
            expected_previous_hash = (
                declared_hash if _is_sha256(declared_hash) else computed_hash
            )

            if record_count % VDSO_SHADOW_CHUNK_SIZE == 0:
                current_chunk = {
                    "start_sequence": sequence,
                    "start_cursor_hash": cursor,
                }
            record_count += 1
            final_cursor = cursor
            if record_count % VDSO_SHADOW_CHUNK_SIZE == 0 and current_chunk is not None:
                current_chunk.update(
                    {
                        "end_sequence": sequence,
                        "end_cursor_hash": cursor,
                        "source_chain_root_sha256": expected_previous_hash,
                    }
                )
                chunk_boundaries.append(current_chunk)
                current_chunk = None
    if record_count == 0:
        errors.append("VDSO shadow input JSONL is empty")
    if current_chunk is not None:
        errors.append("VDSO shadow input JSONL ends with a partial 1000-record chunk")
    return errors, {
        "record_count": record_count,
        "final_cursor_hash": final_cursor,
        "source_chain_root_sha256": expected_previous_hash,
        "chunk_boundaries": chunk_boundaries,
    }


def _validate_vdso_shadow_audit(
    audit_path: Path, input_path: Path, report: dict, commit_sha: str
) -> list[str]:
    errors: list[str] = []
    input_errors, source_info = _validate_vdso_shadow_input(input_path)
    errors.extend(input_errors)
    try:
        raw_bytes = audit_path.read_bytes()
    except OSError as exc:
        return [f"VDSO shadow audit JSONL cannot be read: {exc}"]
    if not raw_bytes or not raw_bytes.endswith(b"\n") or b"\r" in raw_bytes:
        errors.append("VDSO shadow audit JSONL must use canonical LF-terminated records")
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return errors + ["VDSO shadow audit JSONL must be strict UTF-8"]
    lines = raw_text.splitlines()
    if len(lines) < 3:
        return errors + ["VDSO shadow audit JSONL requires run, chunk, and summary records"]

    records: list[dict] = []
    expected_previous_hash = "0" * 64
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"VDSO shadow audit record {line_number} is not valid JSON")
            continue
        if not isinstance(record, dict):
            errors.append(f"VDSO shadow audit record {line_number} must be an object")
            continue
        if line != _canonical_shadow_record(record):
            errors.append(f"VDSO shadow audit record {line_number} is not canonical JSON")
        record_hash = record.get("record_sha256")
        previous_hash = record.get("previous_record_sha256")
        if previous_hash != expected_previous_hash:
            errors.append(f"VDSO shadow audit record {line_number} breaks the hash chain")
        unhashed = dict(record)
        unhashed.pop("record_sha256", None)
        computed_hash = hashlib.sha256(
            _canonical_shadow_record(unhashed).encode("utf-8")
        ).hexdigest()
        if record_hash != computed_hash:
            errors.append(f"VDSO shadow audit record {line_number} hash is invalid")
        if _is_sha256(record_hash):
            expected_previous_hash = record_hash
        else:
            errors.append(f"VDSO shadow audit record {line_number} hash is malformed")
            expected_previous_hash = computed_hash
        records.append(record)

    if len(records) != len(lines):
        return errors
    header = records[0]
    summary = records[-1]
    chunks = records[1:-1]
    header_fields = {
        "record_type",
        "schema_version",
        "run_id",
        "commit_sha",
        "seed",
        "started_at",
        "chunk_size",
        "configured_max_gap_seconds",
        "initial_root",
        "implementation_roots",
        "input_source_schema",
        "input_jsonl_path",
        "previous_record_sha256",
        "record_sha256",
    }
    chunk_fields = {
        "record_type",
        "schema_version",
        "run_id",
        "chunk_index",
        "start_sequence",
        "end_sequence",
        "transition_count",
        "started_at",
        "completed_at",
        "max_gap_seconds",
        "starting_root",
        "ending_root",
        "backend_eval_count",
        "transcript_roots",
        "source_start_cursor_hash",
        "source_end_cursor_hash",
        "source_chain_root_sha256",
        "previous_record_sha256",
        "record_sha256",
    }
    summary_fields = {
        "record_type",
        "schema_version",
        "run_id",
        "completed_at",
        "observed_seconds",
        "transition_count",
        "chunk_count",
        "max_transition_gap_seconds",
        "configured_max_gap_seconds",
        "restart_count",
        "replay_verification_count",
        "backend_eval_count",
        "source_record_count",
        "source_final_cursor_hash",
        "source_chain_root_sha256",
        "final_root",
        "final_transcript_roots",
        "divergence_count",
        "external_write_count",
        "plaintext_payload_count",
        "privacy_result",
        "stop_conditions_triggered",
        "previous_record_sha256",
        "record_sha256",
    }
    if set(header) != header_fields:
        errors.append("VDSO shadow audit run fields do not match the v1 contract")
    if set(summary) != summary_fields:
        errors.append("VDSO shadow audit summary fields do not match the v1 contract")
    if header.get("record_type") != "run" or header.get("schema_version") != VDSO_SHADOW_AUDIT_SCHEMA_VERSION:
        errors.append("VDSO shadow audit must begin with a v1 run record")
    if summary.get("record_type") != "summary" or summary.get("schema_version") != VDSO_SHADOW_AUDIT_SCHEMA_VERSION:
        errors.append("VDSO shadow audit must end with a v1 summary record")
    run_id = header.get("run_id")
    if not _is_sha256(run_id):
        errors.append("VDSO shadow audit run_id must be a 64-character lowercase digest")
    if header.get("commit_sha") != commit_sha or header.get("seed") != AUDIT_SEED:
        errors.append("VDSO shadow audit run binding does not match commit and seed")
    if header.get("chunk_size") != VDSO_SHADOW_CHUNK_SIZE:
        errors.append("VDSO shadow audit chunk_size must equal 1000")
    if (
        header.get("input_source_schema") != VDSO_SHADOW_INPUT_SCHEMA
        or header.get("input_jsonl_path") != VDSO_SHADOW_INPUT_PATH
    ):
        errors.append("VDSO shadow audit input source binding is invalid")
    configured_gap = header.get("configured_max_gap_seconds")
    if (
        not isinstance(configured_gap, (int, float))
        or isinstance(configured_gap, bool)
        or configured_gap <= 0
    ):
        errors.append("VDSO shadow audit configured gap must be positive")
        configured_gap = None
    initial_root = header.get("initial_root")
    if not _is_sha256(initial_root):
        errors.append("VDSO shadow audit initial_root is malformed")

    report_roots = report.get("implementation_roots")
    if (
        not isinstance(report_roots, dict)
        or header.get("implementation_roots") != report_roots
    ):
        errors.append("VDSO shadow audit implementation roots do not bind the report sources")

    if len(chunks) < VDSO_SHADOW_MIN_CHUNKS:
        errors.append("VDSO shadow audit requires at least 100 chunk records")
    header_started = _parse_shadow_timestamp(
        header.get("started_at"), "VDSO shadow audit run started_at", errors
    )
    previous_end_sequence: int | None = None
    previous_ending_root = initial_root
    previous_completed: datetime | None = None
    total_transitions = 0
    observed_max_gap = 0.0
    last_transcript_roots: dict | None = None
    source_boundaries = source_info.get("chunk_boundaries", [])
    first_chunk_started: datetime | None = None
    last_chunk_completed: datetime | None = None
    for expected_index, chunk in enumerate(chunks):
        context = f"VDSO shadow audit chunk {expected_index}"
        if set(chunk) != chunk_fields:
            errors.append(f"{context} fields do not match the v1 contract")
        if chunk.get("record_type") != "chunk" or chunk.get("schema_version") != VDSO_SHADOW_AUDIT_SCHEMA_VERSION:
            errors.append(f"{context} is not a v1 chunk record")
        if chunk.get("run_id") != run_id or chunk.get("chunk_index") != expected_index:
            errors.append(f"{context} run or index binding is invalid")
        transition_count = chunk.get("transition_count")
        if transition_count != VDSO_SHADOW_CHUNK_SIZE or isinstance(transition_count, bool):
            errors.append(f"{context} transition_count must equal 1000")
            transition_count = 0
        start_sequence = chunk.get("start_sequence")
        end_sequence = chunk.get("end_sequence")
        if (
            not isinstance(start_sequence, int)
            or isinstance(start_sequence, bool)
            or not isinstance(end_sequence, int)
            or isinstance(end_sequence, bool)
            or start_sequence < 0
            or end_sequence - start_sequence + 1 != VDSO_SHADOW_CHUNK_SIZE
        ):
            errors.append(f"{context} sequence range must contain exactly 1000 transitions")
        elif previous_end_sequence is not None and start_sequence != previous_end_sequence + 1:
            errors.append(f"{context} sequence range is not contiguous")
        if isinstance(end_sequence, int) and not isinstance(end_sequence, bool):
            previous_end_sequence = end_sequence
        if chunk.get("starting_root") != previous_ending_root:
            errors.append(f"{context} starting_root breaks root continuity")
        ending_root = chunk.get("ending_root")
        if not _is_sha256(ending_root):
            errors.append(f"{context} ending_root is malformed")
        else:
            previous_ending_root = ending_root
        _validate_backend_counts(
            chunk.get("backend_eval_count"), VDSO_SHADOW_CHUNK_SIZE, f"{context} backend_eval_count", errors
        )
        transcript_roots = chunk.get("transcript_roots")
        if not isinstance(transcript_roots, dict) or set(transcript_roots) != VDSO_SHADOW_BACKENDS:
            errors.append(f"{context} transcript_roots must contain exactly three backends")
        elif (
            not all(_is_sha256(value) for value in transcript_roots.values())
            or len(set(transcript_roots.values())) != 1
        ):
            errors.append(f"{context} transcript roots must be valid and equal")
        else:
            last_transcript_roots = transcript_roots
        if expected_index >= len(source_boundaries):
            errors.append(f"{context} has no corresponding durable input checkpoint")
        else:
            source_boundary = source_boundaries[expected_index]
            expected_source_binding = {
                "source_start_cursor_hash": source_boundary.get("start_cursor_hash"),
                "source_end_cursor_hash": source_boundary.get("end_cursor_hash"),
                "source_chain_root_sha256": source_boundary.get(
                    "source_chain_root_sha256"
                ),
            }
            source_mismatches = sorted(
                field
                for field, expected in expected_source_binding.items()
                if chunk.get(field) != expected
            )
            if source_mismatches:
                errors.append(
                    f"{context} does not bind the durable input checkpoint: "
                    + ", ".join(source_mismatches)
                )
            if (
                chunk.get("start_sequence") != source_boundary.get("start_sequence")
                or chunk.get("end_sequence") != source_boundary.get("end_sequence")
            ):
                errors.append(f"{context} sequence range does not bind the input source")
        chunk_started = _parse_shadow_timestamp(chunk.get("started_at"), f"{context} started_at", errors)
        chunk_completed = _parse_shadow_timestamp(chunk.get("completed_at"), f"{context} completed_at", errors)
        max_gap = chunk.get("max_gap_seconds")
        if not isinstance(max_gap, (int, float)) or isinstance(max_gap, bool) or max_gap < 0:
            errors.append(f"{context} max_gap_seconds is invalid")
        else:
            observed_max_gap = max(observed_max_gap, float(max_gap))
            if configured_gap is not None and max_gap > configured_gap:
                errors.append(f"{context} exceeds the configured continuity gap")
        if chunk_started is not None and chunk_completed is not None:
            if chunk_completed < chunk_started:
                errors.append(f"{context} completed_at precedes started_at")
            if expected_index == 0:
                first_chunk_started = chunk_started
            if previous_completed is not None:
                cross_gap = (chunk_started - previous_completed).total_seconds()
                if cross_gap < 0:
                    errors.append(f"{context} overlaps the preceding chunk")
                else:
                    observed_max_gap = max(observed_max_gap, cross_gap)
                    if configured_gap is not None and cross_gap > configured_gap:
                        errors.append(f"{context} creates a continuity gap")
            previous_completed = chunk_completed
            last_chunk_completed = chunk_completed
        total_transitions += transition_count

    summary_completed = _parse_shadow_timestamp(
        summary.get("completed_at"), "VDSO shadow audit summary completed_at", errors
    )
    if summary.get("run_id") != run_id:
        errors.append("VDSO shadow audit summary run_id does not match the run")
    if header_started is not None and first_chunk_started != header_started:
        errors.append("VDSO shadow audit first chunk does not start with the run")
    if summary_completed is not None and last_chunk_completed != summary_completed:
        errors.append("VDSO shadow audit final chunk does not complete with the summary")
    if summary.get("transition_count") != total_transitions:
        errors.append("VDSO shadow audit summary transition_count does not equal chunks")
    if summary.get("chunk_count") != len(chunks):
        errors.append("VDSO shadow audit summary chunk_count does not equal chunks")
    if summary.get("configured_max_gap_seconds") != header.get("configured_max_gap_seconds"):
        errors.append("VDSO shadow audit configured gap changes during the run")
    if summary.get("max_transition_gap_seconds") != observed_max_gap:
        errors.append("VDSO shadow audit maximum gap does not equal chunk evidence")
    if configured_gap is not None and (
        not isinstance(summary.get("max_transition_gap_seconds"), (int, float))
        or isinstance(summary.get("max_transition_gap_seconds"), bool)
        or summary.get("max_transition_gap_seconds") > configured_gap
    ):
        errors.append("VDSO shadow audit summary exceeds the configured continuity gap")
    observed_seconds = summary.get("observed_seconds")
    if (
        not isinstance(observed_seconds, int)
        or isinstance(observed_seconds, bool)
        or observed_seconds < 604800
    ):
        errors.append("VDSO shadow audit requires at least 604800 observed seconds")
    elif header_started is not None and summary_completed is not None:
        elapsed_seconds = int((summary_completed - header_started).total_seconds())
        if observed_seconds != elapsed_seconds:
            errors.append("VDSO shadow audit observed_seconds does not equal timestamps")
    for field in ("restart_count", "replay_verification_count"):
        if not isinstance(summary.get(field), int) or isinstance(summary.get(field), bool) or summary.get(field) < 1:
            errors.append(f"VDSO shadow audit summary {field} must be at least one")
    _validate_backend_counts(
        summary.get("backend_eval_count"), total_transitions, "VDSO shadow audit summary backend_eval_count", errors
    )
    if summary.get("final_root") != previous_ending_root:
        errors.append("VDSO shadow audit final_root does not equal the final chunk root")
    if summary.get("final_transcript_roots") != last_transcript_roots:
        errors.append("VDSO shadow audit final transcript roots do not equal the final chunk")
    if summary.get("source_record_count") != source_info.get("record_count"):
        errors.append("VDSO shadow audit source_record_count does not equal the input artifact")
    if summary.get("source_record_count") != total_transitions:
        errors.append("VDSO shadow audit source_record_count does not equal transitions")
    if summary.get("source_final_cursor_hash") != source_info.get("final_cursor_hash"):
        errors.append("VDSO shadow audit final source cursor does not equal the input artifact")
    if summary.get("source_chain_root_sha256") != source_info.get(
        "source_chain_root_sha256"
    ):
        errors.append("VDSO shadow audit source chain root does not equal the input artifact")
    for field in ("divergence_count", "external_write_count", "plaintext_payload_count"):
        if summary.get(field) != 0 or isinstance(summary.get(field), bool):
            errors.append(f"VDSO shadow audit summary {field} must equal zero")
    if summary.get("privacy_result") != "pass" or summary.get("stop_conditions_triggered") is not False:
        errors.append("VDSO shadow audit summary privacy or stop-condition result failed")

    report_matches = {
        "started_at": header.get("started_at"),
        "completed_at": summary.get("completed_at"),
        "observed_seconds": summary.get("observed_seconds"),
        "transition_count": summary.get("transition_count"),
        "chunk_count": summary.get("chunk_count"),
        "configured_max_gap_seconds": summary.get("configured_max_gap_seconds"),
        "max_transition_gap_seconds": summary.get("max_transition_gap_seconds"),
        "restart_count": summary.get("restart_count"),
        "replay_verification_count": summary.get("replay_verification_count"),
        "backend_eval_count": summary.get("backend_eval_count"),
        "source_record_count": summary.get("source_record_count"),
        "source_final_cursor_hash": summary.get("source_final_cursor_hash"),
        "source_chain_root_sha256": summary.get("source_chain_root_sha256"),
        "divergence_count": summary.get("divergence_count"),
        "external_write_count": summary.get("external_write_count"),
        "plaintext_payload_count": summary.get("plaintext_payload_count"),
        "privacy_result": summary.get("privacy_result"),
        "stop_conditions_triggered": summary.get("stop_conditions_triggered"),
        "audit_chain_root_sha256": summary.get("record_sha256"),
    }
    mismatches = sorted(
        field for field, expected in report_matches.items() if report.get(field) != expected
    )
    if mismatches:
        errors.append(
            "VDSO shadow report does not match the audit JSONL: "
            + ", ".join(mismatches)
        )
    return errors


def _validate_vdso_shadow_report(path: Path, commit_sha: str) -> list[str]:
    if not path.is_file():
        return [f"VDSO shadow report is missing: {path}"]
    report = _load_json(path)
    if not isinstance(report, dict):
        return ["VDSO shadow report must be an object"]
    errors: list[str] = []
    if report.get("schema_version") != VDSO_SHADOW_REPORT_SCHEMA_VERSION:
        errors.append(
            "VDSO shadow report schema_version must equal "
            + VDSO_SHADOW_REPORT_SCHEMA_VERSION
        )
    if report.get("commit_sha") != commit_sha:
        errors.append("VDSO shadow report commit does not match the target commit")
    if report.get("seed") != AUDIT_SEED:
        errors.append(f"VDSO shadow report seed must equal {AUDIT_SEED}")
    if report.get("public_vdso_mode") != "off":
        errors.append("VDSO shadow report must prove public_vdso_mode=off")
    if report.get("worker_mode") != "shadow":
        errors.append("VDSO shadow report must prove worker_mode=shadow")
    if report.get("authoritative_enabled") is not False:
        errors.append("VDSO shadow report must prove authoritative mode disabled")
    if report.get("read_only") is not True:
        errors.append("VDSO shadow report must prove read-only execution")
    if report.get("value_bearing_domains_enabled") is not False:
        errors.append("VDSO shadow report must prove value-bearing domains disabled")

    transition_count = report.get("transition_count")
    if (
        not isinstance(transition_count, int)
        or isinstance(transition_count, bool)
        or transition_count < 100000
    ):
        errors.append("VDSO shadow report requires at least 100000 transitions")
    observed_seconds = report.get("observed_seconds")
    if (
        not isinstance(observed_seconds, int)
        or isinstance(observed_seconds, bool)
        or observed_seconds < 604800
    ):
        errors.append("VDSO shadow report requires at least 604800 observed seconds")
    chunk_count = report.get("chunk_count")
    if (
        not isinstance(chunk_count, int)
        or isinstance(chunk_count, bool)
        or chunk_count < VDSO_SHADOW_MIN_CHUNKS
    ):
        errors.append("VDSO shadow report requires at least 100 audit chunks")
    configured_gap = report.get("configured_max_gap_seconds")
    maximum_gap = report.get("max_transition_gap_seconds")
    if (
        not isinstance(configured_gap, (int, float))
        or isinstance(configured_gap, bool)
        or configured_gap <= 0
    ):
        errors.append("VDSO shadow report configured continuity gap must be positive")
    if (
        not isinstance(maximum_gap, (int, float))
        or isinstance(maximum_gap, bool)
        or maximum_gap < 0
        or (
            isinstance(configured_gap, (int, float))
            and not isinstance(configured_gap, bool)
            and maximum_gap > configured_gap
        )
    ):
        errors.append("VDSO shadow report maximum gap exceeds the continuity limit")
    if report.get("continuity_passed") is not True:
        errors.append("VDSO shadow report continuity proof must pass")
    for field in ("restart_count", "replay_verification_count"):
        if (
            not isinstance(report.get(field), int)
            or isinstance(report.get(field), bool)
            or report.get(field) < 1
        ):
            errors.append(f"VDSO shadow report {field} must be at least one")
    if isinstance(transition_count, int) and not isinstance(transition_count, bool):
        _validate_backend_counts(
            report.get("backend_eval_count"),
            transition_count,
            "VDSO shadow report backend_eval_count",
            errors,
        )
    if not _is_sha256(report.get("audit_chain_root_sha256")):
        errors.append("VDSO shadow report audit chain root is malformed")
    source_record_count = report.get("source_record_count")
    if (
        not isinstance(source_record_count, int)
        or isinstance(source_record_count, bool)
        or source_record_count != transition_count
    ):
        errors.append("VDSO shadow report source_record_count must equal transitions")
    for field in (
        "source_final_cursor_hash",
        "source_chain_root_sha256",
        "input_jsonl_sha256",
        "audit_jsonl_sha256",
    ):
        if not _is_sha256(report.get(field)) or report.get(field) == "0" * 64:
            errors.append(f"VDSO shadow report {field} is malformed or zero")
    if report.get("input_jsonl_path") != VDSO_SHADOW_INPUT_PATH:
        errors.append(
            "VDSO shadow report input_jsonl_path must equal "
            + VDSO_SHADOW_INPUT_PATH
        )
    if report.get("audit_jsonl_path") != VDSO_SHADOW_AUDIT_PATH:
        errors.append(
            "VDSO shadow report audit_jsonl_path must equal "
            + VDSO_SHADOW_AUDIT_PATH
        )
    consecutive_days = report.get("consecutive_days")
    if (
        not isinstance(consecutive_days, int)
        or isinstance(consecutive_days, bool)
        or consecutive_days < 7
    ):
        errors.append("VDSO shadow report requires at least 7 consecutive days")

    timestamps: dict[str, datetime] = {}
    for field in ("started_at", "completed_at"):
        raw_value = report.get(field)
        if not isinstance(raw_value, str):
            errors.append(f"VDSO shadow report {field} is missing")
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is None or parsed.tzinfo is None:
            errors.append(f"VDSO shadow report {field} is invalid")
        else:
            timestamps[field] = parsed
    if set(timestamps) == {"started_at", "completed_at"}:
        elapsed = timestamps["completed_at"] - timestamps["started_at"]
        if elapsed < timedelta(days=7):
            errors.append("VDSO shadow report measured duration is below 7 days")
        if isinstance(consecutive_days, int) and not isinstance(consecutive_days, bool):
            if elapsed < timedelta(days=consecutive_days):
                errors.append(
                    "VDSO shadow report consecutive_days exceeds measured duration"
                )
        if isinstance(observed_seconds, int) and not isinstance(observed_seconds, bool):
            if observed_seconds != int(elapsed.total_seconds()):
                errors.append(
                    "VDSO shadow report observed_seconds does not equal measured duration"
                )

    for field, label in (
        ("divergence_count", "divergence"),
        ("external_write_count", "external writes"),
        ("plaintext_payload_count", "plaintext payloads"),
    ):
        if report.get(field) != 0 or isinstance(report.get(field), bool):
            errors.append(f"VDSO shadow report must record zero {label}")
    if report.get("restart_recovery_passed") is not True:
        errors.append("VDSO shadow restart recovery must pass")
    if report.get("replay_determinism_passed") is not True:
        errors.append("VDSO shadow replay determinism must pass")
    if report.get("privacy_result") != "pass":
        errors.append("VDSO shadow privacy result must pass")
    if report.get("stop_conditions_triggered") is not False:
        errors.append("VDSO shadow report recorded a stop condition")
    stop_conditions = report.get("stop_conditions")
    if not isinstance(stop_conditions, dict):
        errors.append("VDSO shadow stop_conditions must be an object")
    else:
        missing_conditions = REQUIRED_VDSO_STOP_CONDITIONS - set(stop_conditions)
        unexpected_conditions = set(stop_conditions) - REQUIRED_VDSO_STOP_CONDITIONS
        if missing_conditions:
            errors.append(
                "VDSO shadow stop conditions are missing: "
                + ", ".join(sorted(missing_conditions))
            )
        if unexpected_conditions:
            errors.append(
                "VDSO shadow stop conditions are unexpected: "
                + ", ".join(sorted(unexpected_conditions))
            )
        triggered = sorted(
            name
            for name in REQUIRED_VDSO_STOP_CONDITIONS & set(stop_conditions)
            if stop_conditions.get(name) is not False
        )
        if triggered:
            errors.append(
                "VDSO shadow stop conditions must all be false: "
                + ", ".join(triggered)
            )

    implementation_roots = report.get("implementation_roots")
    required_roots = set(VDSO_IMPLEMENTATION_SOURCE_PATHS)
    implementation_artifact_bindings: dict[str, str] = {}
    if not isinstance(implementation_roots, dict):
        errors.append("VDSO shadow implementation_roots must be an object")
    else:
        missing_roots = required_roots - set(implementation_roots)
        unexpected_roots = set(implementation_roots) - required_roots
        if missing_roots:
            errors.append(
                "VDSO shadow implementation roots are missing: "
                + ", ".join(sorted(missing_roots))
            )
        if unexpected_roots:
            errors.append(
                "VDSO shadow implementation roots are unexpected: "
                + ", ".join(sorted(unexpected_roots))
            )
        for name in sorted(required_roots & set(implementation_roots)):
            root_record = implementation_roots.get(name)
            context = f"VDSO shadow {name} implementation root"
            if not isinstance(root_record, dict):
                errors.append(f"{context} must be an object")
                continue
            expected_fields = {
                "source_paths",
                "source_root_sha256",
                "artifact_path",
                "artifact_sha256",
            }
            if set(root_record) != expected_fields:
                errors.append(f"{context} fields do not match the evidence contract")
            source_paths = root_record.get("source_paths")
            expected_paths = VDSO_IMPLEMENTATION_SOURCE_PATHS[name]
            if source_paths != expected_paths:
                errors.append(
                    f"{context} source_paths must equal " + ", ".join(expected_paths)
                )
                continue
            try:
                actual_source_root = _compute_source_root(source_paths)
            except (OSError, ValueError) as exc:
                errors.append(f"{context} is invalid: {exc}")
                continue
            if root_record.get("source_root_sha256") != actual_source_root:
                errors.append(f"{context} does not match declared source files")

            artifact_relative = root_record.get("artifact_path")
            artifact_hash = root_record.get("artifact_sha256")
            if artifact_relative != VDSO_IMPLEMENTATION_ARTIFACT_PATHS[name]:
                errors.append(
                    f"{context} artifact_path must equal "
                    + VDSO_IMPLEMENTATION_ARTIFACT_PATHS[name]
                )
                continue
            report_root = path.parent.resolve()
            artifact_candidate = report_root / artifact_relative
            if artifact_candidate.is_symlink():
                errors.append(f"{context} artifact must not be a symlink")
                continue
            artifact_path = artifact_candidate.resolve()
            try:
                artifact_path.relative_to(report_root)
            except ValueError:
                errors.append(f"{context} artifact escapes the report directory")
                continue
            if artifact_path == path.resolve():
                errors.append(f"{context} artifact must not self-reference")
                continue
            if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
                errors.append(f"{context} artifact is missing or empty")
                continue
            actual_artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if artifact_hash != actual_artifact_hash:
                errors.append(f"{context} artifact hash mismatch")
                continue
            implementation_artifact_bindings[artifact_relative] = actual_artifact_hash

    evidence_artifacts = report.get("evidence_artifacts")
    bound_artifacts: dict[str, str] = {}
    if not isinstance(evidence_artifacts, list) or not evidence_artifacts:
        errors.append("VDSO shadow report must bind supporting evidence artifacts")
    else:
        report_root = path.parent.resolve()
        seen: set[str] = set()
        for record in evidence_artifacts:
            if not isinstance(record, dict):
                errors.append("VDSO shadow report contains an invalid artifact record")
                continue
            relative_path = record.get("path")
            if not isinstance(relative_path, str) or not relative_path:
                errors.append("VDSO shadow evidence artifact path is missing")
                continue
            if relative_path in seen:
                errors.append(
                    f"VDSO shadow report contains duplicate artifact: {relative_path}"
                )
                continue
            seen.add(relative_path)
            artifact_candidate = report_root / relative_path
            if artifact_candidate.is_symlink():
                errors.append(
                    f"VDSO shadow evidence must not be a symlink: {relative_path}"
                )
                continue
            artifact_path = artifact_candidate.resolve()
            try:
                artifact_path.relative_to(report_root)
            except ValueError:
                errors.append(
                    f"VDSO shadow evidence escapes the report directory: {relative_path}"
                )
                continue
            if artifact_path == path.resolve():
                errors.append("VDSO shadow report must not self-reference")
                continue
            if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
                errors.append(
                    f"VDSO shadow evidence is missing or empty: {relative_path}"
                )
                continue
            actual_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if record.get("sha256") != actual_hash:
                errors.append(
                    f"VDSO shadow evidence hash mismatch: {relative_path}"
                )
            else:
                bound_artifacts[relative_path] = actual_hash
        for relative_path, expected_hash in implementation_artifact_bindings.items():
            if bound_artifacts.get(relative_path) != expected_hash:
                errors.append(
                    "VDSO shadow implementation artifact is not evidence-bound: "
                    + relative_path
                )
    audit_digest = bound_artifacts.get(VDSO_SHADOW_AUDIT_PATH)
    input_digest = bound_artifacts.get(VDSO_SHADOW_INPUT_PATH)
    if audit_digest is None:
        errors.append(
            "VDSO shadow report must bind the canonical audit artifact: "
            + VDSO_SHADOW_AUDIT_PATH
        )
    elif report.get("audit_jsonl_sha256") != audit_digest:
        errors.append("VDSO shadow report audit_jsonl_sha256 does not match evidence")
    if input_digest is None:
        errors.append(
            "VDSO shadow report must bind the canonical input artifact: "
            + VDSO_SHADOW_INPUT_PATH
        )
    elif report.get("input_jsonl_sha256") != input_digest:
        errors.append("VDSO shadow report input_jsonl_sha256 does not match evidence")
    if audit_digest is not None and input_digest is not None:
        audit_path = path.parent / VDSO_SHADOW_AUDIT_PATH
        input_path = path.parent / VDSO_SHADOW_INPUT_PATH
        errors.extend(
            _validate_vdso_shadow_audit(audit_path, input_path, report, commit_sha)
        )
    return errors


def _validate_runtime_report(
    path: Path, commit_sha: str, artifact_root: Path | None = None
) -> list[str]:
    return validate_runtime_report(path, commit_sha, ROOT, artifact_root)


def _validate_privacy_review(
    path: Path, commit_sha: str, artifact_root: Path | None = None
) -> list[str]:
    return validate_privacy_review(path, commit_sha, ROOT, artifact_root)


def _validate_independent_reviews(path: Path, commit_sha: str) -> list[str]:
    if not path.is_file():
        return [f"independent review index is missing: {path}"]
    index = _load_json(path)
    if not isinstance(index, dict) or not isinstance(index.get("reviews"), list):
        return ["independent review index must contain a reviews array"]
    errors: list[str] = []
    if index.get("commit_sha") != commit_sha:
        errors.append("independent reviews do not match current commit")
    approved: set[str] = set()
    for review in index["reviews"]:
        if not isinstance(review, dict):
            continue
        domain = review.get("domain")
        if (
            domain in REQUIRED_INDEPENDENT_DOMAINS
            and review.get("approved") is True
            and review.get("blocking_findings_open") == 0
            and str(review.get("reviewer", "")).strip()
            and str(review.get("organization", "")).strip()
            and re.fullmatch(r"[0-9a-f]{64}", str(review.get("report_sha256", "")))
        ):
            approved.add(domain)
    missing = REQUIRED_INDEPENDENT_DOMAINS - approved
    if missing:
        errors.append("independent reviews missing domains: " + ", ".join(sorted(missing)))
    return errors


def validate_readiness(
    stage: str = "public",
    evidence_manifest: Path | None = None,
    evidence_signature: Path | None = None,
    evidence_certificate: Path | None = None,
    deployment_manifests: list[Path] | None = None,
    canary_report: Path | None = None,
    assurance_index: Path | None = None,
    canary_signature: Path | None = None,
    canary_certificate: Path | None = None,
    runtime_report: Path | None = None,
    privacy_review: Path | None = None,
    independent_reviews: Path | None = None,
    vdso_shadow_report: Path | None = None,
    bundle_dir: Path | None = None,
    target_sha: str | None = None,
    stage_evidence_run_id: int | None = None,
    operational_evidence_run_id: int | None = None,
) -> list[str]:
    errors = validate_program()
    if errors:
        return errors

    if stage not in STAGE_GATES:
        return [f"unknown readiness stage: {stage}"]

    matrix = _load_json(MATRIX_PATH)
    applicable_tracks = [
        track for track in matrix["tracks"] if track["gate"] in STAGE_GATES[stage]
    ]
    not_verified = [
        f"{track['id']}={track['status']}"
        for track in applicable_tracks
        if track["status"] != "verified"
    ]
    if not_verified:
        errors.append(
            f"{stage} readiness requires all applicable tracks verified; unresolved: "
            + ", ".join(not_verified)
        )

    try:
        head_sha = _git("rev-parse", "HEAD")
        commit_sha = target_sha or head_sha
        if re.fullmatch(r"[0-9a-f]{40}", commit_sha) is None:
            errors.append(
                "readiness target SHA must be a full lowercase 40-character hex commit"
            )
            return errors
        if head_sha != commit_sha:
            errors.append("readiness checkout does not match the explicit target SHA")
        if _git("status", "--porcelain", "--untracked-files=no"):
            errors.append("readiness requires a clean tracked working tree")
    except subprocess.CalledProcessError as exc:
        errors.append(f"unable to inspect git state: {exc}")
        return errors

    evidence_manifest = evidence_manifest or EVIDENCE_DIR / "audit-evidence.json"
    evidence_signature = evidence_signature or EVIDENCE_DIR / "audit-evidence.sig"
    evidence_certificate = evidence_certificate or EVIDENCE_DIR / "audit-evidence.pem"
    bundle_dir = bundle_dir or EVIDENCE_DIR / "stage-evidence"
    bundle_evidence_dir = bundle_dir / "docs" / "audit" / "evidence"
    errors.extend(
        _validate_evidence_manifest(
            evidence_manifest,
            evidence_signature,
            evidence_certificate,
            commit_sha,
            bundle_dir=bundle_dir,
            stage_evidence_run_id=stage_evidence_run_id,
            operational_evidence_run_id=operational_evidence_run_id,
        )
    )

    assurance_index = assurance_index or bundle_evidence_dir / "assurance-index.json"
    errors.extend(
        _validate_assurance_index(
            assurance_index,
            stage,
            commit_sha,
            {track["id"] for track in applicable_tracks},
            bundle_root=bundle_dir,
        )
    )

    if deployment_manifests is None:
        suffix = "rehearsal" if stage == "canary" else "deployment"
        deployment_manifests = [
            bundle_evidence_dir / f"polygon-amoy-{suffix}.json",
            bundle_evidence_dir / f"cardano-preprod-{suffix}.json",
        ]
    errors.extend(
        _validate_deployment_manifests(
            deployment_manifests, stage, commit_sha, bundle_root=bundle_dir
        )
    )

    runtime_report = runtime_report or bundle_evidence_dir / "runtime-integration.json"
    privacy_review = privacy_review or bundle_evidence_dir / "privacy-review.json"
    errors.extend(_validate_runtime_report(runtime_report, commit_sha, bundle_dir))
    errors.extend(_validate_privacy_review(privacy_review, commit_sha, bundle_dir))

    supporting_artifacts = [
        assurance_index,
        *deployment_manifests,
        runtime_report,
        privacy_review,
    ]
    if stage == "public":
        canary_report = canary_report or bundle_evidence_dir / "closed-canary-report.json"
        canary_signature = canary_signature or bundle_evidence_dir / "closed-canary-report.sig"
        canary_certificate = (
            canary_certificate or bundle_evidence_dir / "closed-canary-report.pem"
        )
        errors.extend(
            _validate_canary_report(canary_report, commit_sha, bundle_root=bundle_dir)
        )
        _require_nonempty_file(
            canary_signature, "closed-canary signature", errors
        )
        _require_nonempty_file(
            canary_certificate, "closed-canary certificate", errors
        )
        supporting_artifacts.append(canary_report)
        independent_reviews = (
            independent_reviews or bundle_evidence_dir / "independent-reviews.json"
        )
        errors.extend(_validate_independent_reviews(independent_reviews, commit_sha))
        supporting_artifacts.append(independent_reviews)
        vdso_shadow_report = (
            vdso_shadow_report or bundle_evidence_dir / "vdso-shadow-report.json"
        )
        errors.extend(_validate_vdso_shadow_report(vdso_shadow_report, commit_sha))
        supporting_artifacts.append(vdso_shadow_report)
        register_text = (ROOT / "contracts" / "CONTRACTS.md").read_text(
            encoding="utf-8"
        )
        if re.search(r"\|\s*Pending\s*\|", register_text, flags=re.IGNORECASE):
            errors.append("deployment evidence register still contains Pending fields")
    errors.extend(
        _validate_manifest_artifact_binding(
            evidence_manifest, supporting_artifacts, bundle_dir=bundle_dir
        )
    )
    return errors


def validate_operational_bundle(
    stage: str, bundle_dir: Path, target_sha: str
) -> list[str]:
    """Validate post-freeze operational evidence before immutable upload.

    This deliberately excludes the aggregate manifest and its signature. Those are
    produced only after the stage and operational bundles have been downloaded and
    merged by the promotion run.
    """

    errors = validate_program()
    if errors:
        return errors
    if stage not in STAGE_GATES:
        return [f"unknown operational-evidence stage: {stage}"]
    if re.fullmatch(r"[0-9a-f]{40}", target_sha) is None:
        return ["operational evidence target SHA must be a full lowercase commit"]
    try:
        if _git("rev-parse", "HEAD") != target_sha:
            errors.append("operational evidence checkout does not match target SHA")
        if _git("status", "--porcelain", "--untracked-files=no"):
            errors.append("operational evidence requires a clean tracked working tree")
    except subprocess.CalledProcessError as exc:
        return [f"unable to inspect operational evidence git state: {exc}"]

    evidence_dir = bundle_dir / "docs" / "audit" / "evidence"
    matrix = _load_json(MATRIX_PATH)
    applicable_tracks = [
        track for track in matrix["tracks"] if track["gate"] in STAGE_GATES[stage]
    ]
    assurance_index = evidence_dir / "assurance-index.json"
    errors.extend(
        _validate_assurance_index(
            assurance_index,
            stage,
            target_sha,
            {track["id"] for track in applicable_tracks},
            bundle_root=bundle_dir,
        )
    )
    suffix = "rehearsal" if stage == "canary" else "deployment"
    deployment_manifests = [
        evidence_dir / f"polygon-amoy-{suffix}.json",
        evidence_dir / f"cardano-preprod-{suffix}.json",
    ]
    errors.extend(
        _validate_deployment_manifests(
            deployment_manifests, stage, target_sha, bundle_root=bundle_dir
        )
    )
    errors.extend(
        _validate_runtime_report(
            evidence_dir / "runtime-integration.json", target_sha, bundle_dir
        )
    )
    errors.extend(
        _validate_privacy_review(
            evidence_dir / "privacy-review.json", target_sha, bundle_dir
        )
    )

    if stage == "public":
        canary_report = evidence_dir / "closed-canary-report.json"
        errors.extend(
            _validate_canary_report(
                canary_report, target_sha, bundle_root=bundle_dir
            )
        )
        _require_nonempty_file(
            evidence_dir / "closed-canary-report.sig",
            "closed-canary signature",
            errors,
        )
        _require_nonempty_file(
            evidence_dir / "closed-canary-report.pem",
            "closed-canary certificate",
            errors,
        )
        errors.extend(
            _validate_independent_reviews(
                evidence_dir / "independent-reviews.json", target_sha
            )
        )
        errors.extend(
            _validate_vdso_shadow_report(
                evidence_dir / "vdso-shadow-report.json", target_sha
            )
        )
    return errors


def _require_target_binding(target_sha: str, stage_evidence_run_id: int) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", target_sha) is None:
        raise ValueError("target SHA must be a full lowercase 40-character hex commit")
    if (
        not isinstance(stage_evidence_run_id, int)
        or isinstance(stage_evidence_run_id, bool)
        or stage_evidence_run_id < 1
    ):
        raise ValueError("stage-evidence run ID must be a positive integer")
    if _git("rev-parse", "HEAD") != target_sha:
        raise ValueError("checked-out commit does not match target SHA")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("target commit has tracked working-tree changes")


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


TRUFFLEHOG_FORBIDDEN_KEYS = {
    "raw",
    "rawv2",
    "secret",
    "credential",
    "credentials",
    "password",
    "privatekey",
    "apikey",
    "token",
    "match",
    "redacted",
    "extradata",
}


def _secret_bearing_field_paths(value: object, prefix: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if _normalized_key(key) in TRUFFLEHOG_FORBIDDEN_KEYS:
                errors.append(child_path)
            errors.extend(_secret_bearing_field_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_secret_bearing_field_paths(child, f"{prefix}[{index}]"))
    return errors


def _validate_sanitized_trufflehog(
    report: object,
    target_sha: str,
    stage_evidence_run_id: int,
) -> list[str]:
    if not isinstance(report, dict):
        return ["TruffleHog sanitized report must be an object"]
    errors: list[str] = []
    expected_fields = {
        "schema_version",
        "scanner",
        "command",
        "exit_status",
        "commit_sha",
        "stage_evidence_run_id",
        "findings_count",
        "verified_findings_count",
        "unverified_findings_count",
        "findings",
    }
    if set(report) != expected_fields:
        errors.append("TruffleHog sanitized report fields do not match the contract")
    expected = {
        "schema_version": "1.0.0",
        "scanner": "trufflehog",
        "command": REQUIRED_EVIDENCE_RESULTS["trufflehog"],
        "commit_sha": target_sha,
        "stage_evidence_run_id": stage_evidence_run_id,
    }
    for field, expected_value in expected.items():
        if report.get(field) != expected_value:
            errors.append(f"TruffleHog sanitized report {field} is not evidence-bound")
    exit_status = report.get("exit_status")
    if not isinstance(exit_status, int) or isinstance(exit_status, bool) or exit_status < 0:
        errors.append("TruffleHog sanitized report exit_status is invalid")
    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append("TruffleHog sanitized report findings must be an array")
        findings = []
    expected_finding_fields = {
        "detector_name",
        "detector_type",
        "verified",
        "commit",
        "path",
        "line",
    }
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != expected_finding_fields:
            errors.append("TruffleHog sanitized finding fields do not match the contract")
            continue
        if not isinstance(finding.get("verified"), bool):
            errors.append("TruffleHog sanitized finding verified status is invalid")
    findings_count = report.get("findings_count")
    verified_count = report.get("verified_findings_count")
    unverified_count = report.get("unverified_findings_count")
    if findings_count != len(findings) or isinstance(findings_count, bool):
        errors.append("TruffleHog sanitized findings_count is invalid")
    if verified_count != sum(
        finding.get("verified") is True for finding in findings if isinstance(finding, dict)
    ):
        errors.append("TruffleHog sanitized verified finding count is invalid")
    if unverified_count != sum(
        finding.get("verified") is False for finding in findings if isinstance(finding, dict)
    ):
        errors.append("TruffleHog sanitized unverified finding count is invalid")
    secret_paths = _secret_bearing_field_paths(report)
    if secret_paths:
        errors.append(
            "TruffleHog sanitized report contains secret-bearing fields: "
            + ", ".join(secret_paths)
        )
    return errors


def _sanitize_trufflehog_output(
    raw_path: Path,
    output: Path,
    exit_status: int,
    target_sha: str,
    stage_evidence_run_id: int,
) -> int:
    findings: list[dict[str, object]] = []
    with raw_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                raw_finding = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"TruffleHog JSON output is malformed at record {line_number}"
                ) from exc
            if not isinstance(raw_finding, dict):
                raise ValueError(
                    f"TruffleHog JSON output record {line_number} is not an object"
                )
            git_metadata = (
                raw_finding.get("SourceMetadata", {})
                .get("Data", {})
                .get("Git", {})
            )
            if not isinstance(git_metadata, dict):
                git_metadata = {}
            verified = raw_finding.get("Verified") is True
            findings.append(
                {
                    "detector_name": str(raw_finding.get("DetectorName", "")),
                    "detector_type": raw_finding.get("DetectorType"),
                    "verified": verified,
                    "commit": git_metadata.get("commit"),
                    "path": git_metadata.get("file"),
                    "line": git_metadata.get("line"),
                }
            )
    report = {
        "schema_version": "1.0.0",
        "scanner": "trufflehog",
        "command": REQUIRED_EVIDENCE_RESULTS["trufflehog"],
        "exit_status": exit_status,
        "commit_sha": target_sha,
        "stage_evidence_run_id": stage_evidence_run_id,
        "findings_count": len(findings),
        "verified_findings_count": sum(item["verified"] is True for item in findings),
        "unverified_findings_count": sum(item["verified"] is False for item in findings),
        "findings": findings,
    }
    validation_errors = _validate_sanitized_trufflehog(
        report, target_sha, stage_evidence_run_id
    )
    if validation_errors:
        raise ValueError("; ".join(validation_errors))
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return len(findings)


def _sanitize_gitleaks_report(report_path: Path, transcript_path: Path) -> int:
    if not report_path.is_file():
        raise ValueError("Gitleaks did not produce its redacted JSON report")
    report = _load_json(report_path)
    if not isinstance(report, list):
        raise ValueError("Gitleaks JSON report must be an array")
    sensitive_values: set[str] = set()

    def redact(value: object) -> object:
        if isinstance(value, dict):
            sanitized: dict[str, object] = {}
            for key, child in value.items():
                if _normalized_key(key) in {"secret", "match"}:
                    if isinstance(child, str) and child:
                        sensitive_values.add(child)
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = redact(child)
            return sanitized
        if isinstance(value, list):
            return [redact(child) for child in value]
        return value

    sanitized_report = redact(report)
    report_path.write_text(
        json.dumps(sanitized_report, indent=2) + "\n", encoding="utf-8"
    )
    transcript = transcript_path.read_text(encoding="utf-8")
    for sensitive_value in sorted(sensitive_values, key=len, reverse=True):
        if len(sensitive_value) >= 4:
            transcript = transcript.replace(sensitive_value, "[REDACTED]")
    transcript = re.sub(
        r"-----BEGIN [^-\r\n]*PRIVATE KEY-----[\s\S]*?-----END [^-\r\n]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]",
        transcript,
        flags=re.IGNORECASE,
    )
    transcript_path.write_text(transcript, encoding="utf-8")
    return len(report)


def _validate_gitleaks_report(report: object) -> list[str]:
    if not isinstance(report, list):
        return ["Gitleaks report must be an array"]
    errors: list[str] = []

    def visit(value: object, prefix: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{prefix}.{key}"
                if _normalized_key(key) in {"secret", "match"} and child != "[REDACTED]":
                    errors.append(f"Gitleaks report field is not fully redacted: {path}")
                visit(child, path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{prefix}[{index}]")

    visit(report)
    return errors


def _stream_gate_command(command: str, transcript_path: Path) -> int:
    with transcript_path.open("w", encoding="utf-8", newline="") as transcript:
        transcript.write(f"$ {command}\n")
        transcript.flush()
        process = subprocess.Popen(
            ["bash", "-o", "pipefail", "-c", command],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace")
            transcript.write(line)
            transcript.flush()
            print(line, end="")
        return process.wait()


def _run_trufflehog_gate(
    command: str,
    output_dir: Path,
    transcript_path: Path,
    target_sha: str,
    stage_evidence_run_id: int,
) -> int:
    temp_root = Path(os.getenv("RUNNER_TEMP", str(output_dir.parent)))
    temp_root.mkdir(parents=True, exist_ok=True)
    raw_handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=temp_root, delete=False
    )
    raw_path = Path(raw_handle.name)
    try:
        with raw_handle, transcript_path.open(
            "w", encoding="utf-8", newline=""
        ) as transcript:
            transcript.write(f"$ {command}\n")
            transcript.write(
                "TruffleHog stdout is withheld and transformed into a sanitized report.\n"
            )
            transcript.flush()
            process = subprocess.Popen(
                ["bash", "-o", "pipefail", "-c", command],
                cwd=ROOT,
                stdout=raw_handle,
                stderr=subprocess.PIPE,
            )
            assert process.stderr is not None
            for raw_line in process.stderr:
                line = raw_line.decode("utf-8", errors="replace")
                transcript.write(line)
                transcript.flush()
                print(line, end="")
            exit_status = process.wait()
        findings_count = _sanitize_trufflehog_output(
            raw_path,
            output_dir / "trufflehog-sanitized.json",
            exit_status,
            target_sha,
            stage_evidence_run_id,
        )
        return 1 if findings_count else exit_status
    finally:
        raw_path.unlink(missing_ok=True)


def _raw_output_bindings(output_dir: Path) -> list[dict[str, str]]:
    bindings: list[dict[str, str]] = []
    for artifact in sorted(
        output_dir.rglob("*"), key=lambda item: item.relative_to(output_dir).as_posix()
    ):
        if artifact.is_symlink():
            raise ValueError(f"raw gate output contains a symlink: {artifact}")
        if not artifact.is_file() or artifact.name == "gate.json":
            continue
        if artifact.stat().st_size == 0:
            raise ValueError(f"raw gate output is empty: {artifact}")
        bindings.append(
            {
                "path": artifact.relative_to(output_dir).as_posix(),
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        )
    if not bindings:
        raise ValueError("raw gate execution produced no output artifacts")
    return bindings


def run_gate(
    output_dir: Path,
    name: str,
    target_sha: str,
    stage_evidence_run_id: int,
) -> int:
    if name not in REQUIRED_EVIDENCE_RESULTS:
        raise ValueError(f"unexpected evidence result name: {name!r}")
    _require_target_binding(target_sha, stage_evidence_run_id)
    if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("AUDIT_SEED") != str(
        AUDIT_SEED
    ):
        raise ValueError(f"GitHub Actions AUDIT_SEED must equal {AUDIT_SEED}")
    if output_dir.name != "raw-gate":
        raise ValueError("raw gate output directory must be named raw-gate")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("raw gate output directory must start empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = REQUIRED_EVIDENCE_RESULTS[name]
    transcript_path = output_dir / "transcript.log"
    execution_error: str | None = None
    try:
        if name == "trufflehog":
            exit_status = _run_trufflehog_gate(
                command,
                output_dir,
                transcript_path,
                target_sha,
                stage_evidence_run_id,
            )
        else:
            exit_status = _stream_gate_command(command, transcript_path)
            if name == "gitleaks":
                findings_count = _sanitize_gitleaks_report(
                    output_dir / "gitleaks-report.json", transcript_path
                )
                if findings_count:
                    exit_status = 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        execution_error = type(exc).__name__
        exit_status = 1
        with transcript_path.open("a", encoding="utf-8") as transcript:
            transcript.write(
                f"Gate runner failed closed during evidence processing: {execution_error}\n"
            )

    raw_outputs = _raw_output_bindings(output_dir)
    record = {
        "schema_version": GATE_ARTIFACT_SCHEMA_VERSION,
        "name": name,
        "status": "success" if exit_status == 0 else "failure",
        "exit_status": exit_status,
        "command": command,
        "commit_sha": target_sha,
        "stage_evidence_run_id": stage_evidence_run_id,
        "seed": AUDIT_SEED,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": (
            "github-actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local"
        ),
        "raw_outputs": raw_outputs,
    }
    if execution_error is not None:
        record["processing_error"] = execution_error
    (output_dir / "gate.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return exit_status


def _load_gate_results(
    bundle_dir: Path, target_sha: str, stage_evidence_run_id: int
) -> list[dict[str, object]]:
    bundle_root = bundle_dir.resolve()
    results: list[dict[str, object]] = []
    for name in sorted(REQUIRED_EVIDENCE_RESULTS):
        gate_dir = bundle_root / "raw-gates" / f"raw-gate-{name}"
        artifact = gate_dir / "gate.json"
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise ValueError(f"raw gate artifact is missing or empty: {name}")
        record = _load_json(artifact)
        if not isinstance(record, dict):
            raise ValueError(f"raw gate artifact must be an object: {name}")
        expected = {
            "schema_version": GATE_ARTIFACT_SCHEMA_VERSION,
            "name": name,
            "status": "success",
            "exit_status": 0,
            "command": REQUIRED_EVIDENCE_RESULTS[name],
            "commit_sha": target_sha,
            "stage_evidence_run_id": stage_evidence_run_id,
            "seed": AUDIT_SEED,
            "environment": "github-actions",
        }
        for field, expected_value in expected.items():
            if record.get(field) != expected_value:
                raise ValueError(
                    f"raw gate artifact {name} {field} does not match bound evidence"
                )
        generated_at = record.get("generated_at")
        if not isinstance(generated_at, str):
            raise ValueError(f"raw gate artifact {name} generated_at is missing")
        try:
            generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"raw gate artifact {name} generated_at is invalid"
            ) from exc
        if generated.tzinfo is None:
            raise ValueError(f"raw gate artifact {name} generated_at is invalid")
        if "processing_error" in record:
            raise ValueError(f"raw gate artifact {name} recorded a processing error")
        raw_outputs = record.get("raw_outputs")
        if not isinstance(raw_outputs, list) or not raw_outputs:
            raise ValueError(f"raw gate artifact {name} has no raw output bindings")
        declared_files: set[str] = set()
        manifest_raw_outputs: list[dict[str, str]] = []
        for binding in raw_outputs:
            if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
                raise ValueError(f"raw gate artifact {name} has an invalid output binding")
            relative_output = binding.get("path")
            expected_hash = binding.get("sha256")
            if not isinstance(relative_output, str) or not relative_output:
                raise ValueError(f"raw gate artifact {name} output path is invalid")
            output_path = (gate_dir / relative_output).resolve()
            try:
                output_path.relative_to(gate_dir.resolve())
            except ValueError as exc:
                raise ValueError(
                    f"raw gate artifact {name} output escapes its artifact directory"
                ) from exc
            if output_path == artifact.resolve() or output_path.is_symlink():
                raise ValueError(f"raw gate artifact {name} output binding is unsafe")
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise ValueError(
                    f"raw gate artifact {name} output is missing or empty: {relative_output}"
                )
            actual_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
            if expected_hash != actual_hash:
                raise ValueError(
                    f"raw gate artifact {name} output hash mismatch: {relative_output}"
                )
            if relative_output in declared_files:
                raise ValueError(
                    f"raw gate artifact {name} contains a duplicate output binding"
                )
            declared_files.add(relative_output)
            manifest_raw_outputs.append(
                {
                    "path": output_path.relative_to(bundle_root).as_posix(),
                    "sha256": actual_hash,
                }
            )
        actual_files = {
            item.relative_to(gate_dir).as_posix()
            for item in gate_dir.rglob("*")
            if item.is_file() and item != artifact
        }
        if actual_files != declared_files:
            raise ValueError(f"raw gate artifact {name} does not bind its exact file set")
        transcript = gate_dir / "transcript.log"
        if not transcript.is_file() or not transcript.read_text(
            encoding="utf-8"
        ).startswith(f"$ {REQUIRED_EVIDENCE_RESULTS[name]}\n"):
            raise ValueError(f"raw gate artifact {name} transcript command mismatch")
        if name == "gitleaks":
            gitleaks_errors = _validate_gitleaks_report(
                _load_json(gate_dir / "gitleaks-report.json")
            )
            if gitleaks_errors:
                raise ValueError("; ".join(gitleaks_errors))
        if name == "trufflehog":
            trufflehog_errors = _validate_sanitized_trufflehog(
                _load_json(gate_dir / "trufflehog-sanitized.json"),
                target_sha,
                stage_evidence_run_id,
            )
            if trufflehog_errors:
                raise ValueError("; ".join(trufflehog_errors))
        relative_path = artifact.relative_to(bundle_root).as_posix()
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        results.append(
            {
                "name": name,
                "status": "success",
                "command": REQUIRED_EVIDENCE_RESULTS[name],
                "artifact_path": relative_path,
                "artifact_sha256": digest,
                "raw_outputs": manifest_raw_outputs,
                "reviewer": "github-actions",
            }
        )
    return results


def generate_manifest(
    output: Path,
    bundle_dir: Path,
    target_sha: str,
    stage_evidence_run_id: int,
    operational_evidence_run_id: int,
) -> None:
    _require_target_binding(target_sha, stage_evidence_run_id)
    if (
        not isinstance(operational_evidence_run_id, int)
        or isinstance(operational_evidence_run_id, bool)
        or operational_evidence_run_id < 1
    ):
        raise ValueError("operational-evidence run ID must be a positive integer")
    if operational_evidence_run_id == stage_evidence_run_id:
        raise ValueError("operational and stage evidence must come from distinct runs")
    if os.getenv("GITHUB_ACTIONS") != "true":
        raise ValueError("aggregate evidence manifests may only be generated by GitHub Actions")
    bundle_root = bundle_dir.resolve()
    try:
        output.resolve().relative_to(bundle_root)
    except ValueError:
        pass
    else:
        raise ValueError("aggregate evidence manifest must be outside the bound bundle")

    matrix_bytes = MATRIX_PATH.read_bytes()
    matrix = json.loads(matrix_bytes)
    statuses = Counter(track["status"] for track in matrix["tracks"])
    evidence_artifacts = _collect_bundle_records(bundle_dir)
    parsed_results = _load_gate_results(
        bundle_dir, target_sha, stage_evidence_run_id
    )
    bound = {record["path"]: record["sha256"] for record in evidence_artifacts}
    for result in parsed_results:
        if bound.get(result["artifact_path"]) != result["artifact_sha256"]:
            raise ValueError(f"raw gate artifact was not bound: {result['name']}")
        for raw_output in result["raw_outputs"]:
            if bound.get(raw_output["path"]) != raw_output["sha256"]:
                raise ValueError(
                    f"raw gate output was not bound: {result['name']}:{raw_output['path']}"
                )

    manifest = {
        "schema_version": EVIDENCE_MANIFEST_SCHEMA_VERSION,
        "commit_sha": target_sha,
        "stage_evidence_run_id": stage_evidence_run_id,
        "operational_evidence_run_id": operational_evidence_run_id,
        "seed": AUDIT_SEED,
        "dirty": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": "github-actions",
        "control_matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest(),
        "bundle_sha256": _canonical_bundle_hash(evidence_artifacts),
        "track_summary": {
            "total": len(matrix["tracks"]),
            **{status: statuses[status] for status in sorted(ALLOWED_STATUSES)},
        },
        "evidence_artifacts": evidence_artifacts,
        "results": parsed_results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    readiness_parser = subparsers.add_parser("readiness")
    readiness_parser.add_argument("--stage", choices=sorted(STAGE_GATES), default="public")
    readiness_parser.add_argument("--evidence-manifest", type=Path)
    readiness_parser.add_argument("--evidence-signature", type=Path)
    readiness_parser.add_argument("--evidence-certificate", type=Path)
    readiness_parser.add_argument("--deployment-manifest", type=Path, action="append")
    readiness_parser.add_argument("--canary-report", type=Path)
    readiness_parser.add_argument("--assurance-index", type=Path)
    readiness_parser.add_argument("--canary-signature", type=Path)
    readiness_parser.add_argument("--canary-certificate", type=Path)
    readiness_parser.add_argument("--runtime-report", type=Path)
    readiness_parser.add_argument("--privacy-review", type=Path)
    readiness_parser.add_argument("--independent-reviews", type=Path)
    readiness_parser.add_argument("--vdso-shadow-report", type=Path)
    readiness_parser.add_argument("--bundle-dir", type=Path, required=True)
    readiness_parser.add_argument("--target-sha", required=True)
    readiness_parser.add_argument(
        "--stage-evidence-run-id", type=int, required=True
    )
    readiness_parser.add_argument(
        "--operational-evidence-run-id", type=int, required=True
    )
    operational_parser = subparsers.add_parser("operational")
    operational_parser.add_argument(
        "--stage", choices=sorted(STAGE_GATES), required=True
    )
    operational_parser.add_argument("--bundle-dir", type=Path, required=True)
    operational_parser.add_argument("--target-sha", required=True)
    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("--output", type=Path, required=True)
    manifest_parser.add_argument("--bundle-dir", type=Path, required=True)
    manifest_parser.add_argument("--target-sha", required=True)
    manifest_parser.add_argument("--stage-evidence-run-id", type=int, required=True)
    manifest_parser.add_argument("--operational-evidence-run-id", type=int, required=True)
    gate_parser = subparsers.add_parser("run-gate")
    gate_parser.add_argument("--output-dir", type=Path, required=True)
    gate_parser.add_argument("--name", choices=sorted(REQUIRED_EVIDENCE_RESULTS), required=True)
    gate_parser.add_argument("--target-sha", required=True)
    gate_parser.add_argument("--stage-evidence-run-id", type=int, required=True)
    args = parser.parse_args()

    errors = (
        validate_readiness(
            stage=args.stage,
            evidence_manifest=args.evidence_manifest,
            evidence_signature=args.evidence_signature,
            evidence_certificate=args.evidence_certificate,
            deployment_manifests=args.deployment_manifest,
            canary_report=args.canary_report,
            assurance_index=args.assurance_index,
            canary_signature=args.canary_signature,
            canary_certificate=args.canary_certificate,
            runtime_report=args.runtime_report,
            privacy_review=args.privacy_review,
            independent_reviews=args.independent_reviews,
            vdso_shadow_report=args.vdso_shadow_report,
            bundle_dir=args.bundle_dir,
            target_sha=args.target_sha,
            stage_evidence_run_id=args.stage_evidence_run_id,
            operational_evidence_run_id=args.operational_evidence_run_id,
        )
        if args.command == "readiness"
        else validate_operational_bundle(
            args.stage, args.bundle_dir, args.target_sha
        )
        if args.command == "operational"
        else [] if args.command == "run-gate" else validate_program()
    )
    if errors:
        print("Audit program validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.command == "manifest":
        try:
            generate_manifest(
                args.output,
                args.bundle_dir,
                args.target_sha,
                args.stage_evidence_run_id,
                args.operational_evidence_run_id,
            )
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"Evidence manifest generation failed: {exc}", file=sys.stderr)
            return 1
        print(f"Evidence manifest written to {args.output}")
    elif args.command == "run-gate":
        try:
            exit_status = run_gate(
                args.output_dir,
                args.name,
                args.target_sha,
                args.stage_evidence_run_id,
            )
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"Gate execution failed before evidence capture: {exc}", file=sys.stderr)
            return 1
        print(f"Gate evidence written to {args.output_dir / 'gate.json'}")
        if exit_status != 0:
            return exit_status
    elif args.command == "readiness":
        print(f"Testnet {args.stage} readiness passed.")
    elif args.command == "operational":
        print(f"Testnet {args.stage} operational-evidence bundle passed.")
    else:
        print("Audit program validation passed: 36 tracks and testnet profile valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
