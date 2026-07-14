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
from collections import Counter
from datetime import datetime, timezone
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
    "audit-program": "python scripts/audit/audit_program.py validate",
    "public-content": "python scripts/security/public_content_policy_scan.py",
    "default-credentials": "python scripts/security/default_credential_scan.py",
    "mock-mode": "python scripts/security/mock_mode_promotion_scan.py",
    "gitleaks": "gitleaks detect --source .",
    "trufflehog": "trufflehog filesystem .",
    "solidity": "forge build --sizes && forge test -vvv",
    "slither": "slither . --config-file slither.config.json",
    "aiken": "aiken check --deny --seed 20260713 --max-success 250",
    "vir-core": "cargo test --workspace --all-targets --locked",
    "python": "pytest -v --tb=short && bandit && pip-audit",
    "semgrep": "semgrep scan --config auto --error",
    "frontend": "npm ci && npm audit --audit-level=high && npm run build",
    "gateway-config": "caddy validate --config gateway/Caddyfile.testnet.example --adapter caddyfile",
    "sbom": "syft dir:. -o cyclonedx-json",
}
CANARY_EVM_ARTIFACTS = {
    "VAMSToken",
    "VAMSStaking",
    "VAMSVesting",
    "VAMSGovernor",
    "VAMSTimelockController",
    "VAMSSentinel",
}
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
        if profile.get("staking_rewards_enabled") is not False:
            errors.append("testnet staking rewards must remain disabled")
        if governance.get("timelock_seconds", 0) < 172800:
            errors.append("testnet timelock must be at least 48 hours")
        if governance.get("safe_threshold", 0) < 3:
            errors.append("testnet Safe threshold must be at least 3")
        if concentration.get("regional_reward_share_bps", 10001) > 3000:
            errors.append("regional reward stop condition must not exceed 30%")
        if exposure.get("single_operation_insurance_reserve_bps", 10001) > 100:
            errors.append("single-operation canary exposure must not exceed 1%")
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
    if manifest.get("schema_version") != "1.0.0":
        errors.append("evidence manifest schema_version must be 1.0.0")
    if manifest.get("commit_sha") != commit_sha:
        errors.append("evidence manifest commit does not match the current commit")
    if manifest.get("dirty") is not False:
        errors.append("evidence manifest was generated from a dirty tree")
    if manifest.get("environment") != "github-actions":
        errors.append("evidence manifest must be generated by GitHub Actions")
    expected_matrix_hash = hashlib.sha256(MATRIX_PATH.read_bytes()).hexdigest()
    if manifest.get("control_matrix_sha256") != expected_matrix_hash:
        errors.append("evidence manifest control matrix hash does not match")
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
            if result.get("reviewer") != "github-actions":
                errors.append(f"evidence gate reviewer mismatch: {name}")
    return errors


def _validate_manifest_artifact_binding(
    manifest_path: Path, required_paths: list[Path]
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
    for path in required_paths:
        try:
            relative_path = path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            errors.append(f"supporting evidence escapes the repository: {path}")
            continue
        if not path.is_file():
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


def _validate_deployment_artifacts(
    manifest: dict, network: str, stage: str, required_artifacts: set[str]
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
            if stage == "public" and not _is_sha256(artifact.get("transaction_hash")):
                errors.append(f"{context} public transaction_hash is invalid")
    if len(addresses) != len(set(addresses)):
        errors.append(f"{network} deployment artifact addresses must be distinct")
    return errors, artifacts


def _validate_deployment_authorities(
    manifest: dict, network: str
) -> tuple[list[str], dict[str, dict]]:
    errors: list[str] = []
    raw_authorities = manifest.get("authorities")
    if not isinstance(raw_authorities, dict):
        return [f"{network} authorities are missing"], {}
    expected_names = {"governance", "treasury", "emergency"}
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
                _validate_source_binding(
                    authority.get("script_source"),
                    authority.get("script_source_sha256"),
                    f"{network} {name} authority",
                )
            )
            if not _is_sha256(authority.get("identity_check_evidence_sha256")):
                errors.append(f"{network} {name} identity evidence hash is invalid")
    if len(addresses) == 3 and len(set(addresses)) != 3:
        errors.append(f"{network} authority addresses must be distinct")
    if script_hashes and len(script_hashes) != len(set(script_hashes)):
        errors.append(f"{network} authority script hashes must be distinct")
    return errors, authorities


def _validate_timelock_identity(
    manifest: dict, network: str, artifacts: dict[str, dict], authorities: dict[str, dict]
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
            missing = expected_roles - observed_roles
            unexpected = observed_roles - expected_roles
            if missing:
                errors.append(f"{network} timelock required role assignments are missing")
            if unexpected:
                errors.append(f"{network} timelock contains unexpected role assignments")
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
    return errors


def _validate_role_transfers(
    manifest: dict, network: str, stage: str, artifacts: dict[str, dict], authorities: dict[str, dict]
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
            removal_found |= action == "retire-deployer" and source == deployer
            handoff_found |= action in {"parameterize", "handoff"}
    if not removal_found:
        errors.append(f"{network} does not include verified deployer privilege removal")
    if not handoff_found:
        errors.append(f"{network} does not include verified authority handoff")
    return errors


def _validate_deployer_privilege_checks(
    manifest: dict, network: str, required_artifacts: set[str]
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
    missing = required_coverage - covered
    if missing:
        errors.append(
            f"{network} deployer privilege checks missing artifacts: "
            + ", ".join(sorted(missing))
        )
    return errors


def _validate_deployment_manifests(
    paths: list[Path], stage: str, commit_sha: str
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
        if manifest.get("schema_version") != "1.0.0":
            errors.append(f"{network} deployment schema_version must equal 1.0.0")
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

        artifact_errors, artifacts = _validate_deployment_artifacts(
            manifest, network, stage, required_artifacts
        )
        authority_errors, authorities = _validate_deployment_authorities(manifest, network)
        errors.extend(artifact_errors)
        errors.extend(authority_errors)
        errors.extend(_validate_timelock_identity(manifest, network, artifacts, authorities))
        errors.extend(_validate_role_transfers(manifest, network, stage, artifacts, authorities))
        errors.extend(_validate_deployer_privilege_checks(manifest, network, required_artifacts))
    missing = DEPLOYMENT_NETWORKS - seen_networks
    if missing:
        errors.append("deployment manifests missing networks: " + ", ".join(sorted(missing)))
    return errors


def _validate_assurance_index(
    path: Path, stage: str, commit_sha: str, required_track_ids: set[str]
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
            artifact_path = (ROOT / relative_path).resolve()
            try:
                artifact_path.relative_to(ROOT.resolve())
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


def _validate_canary_report(path: Path, commit_sha: str) -> list[str]:
    if not path.is_file():
        return [f"closed-canary report is missing: {path}"]
    report = _load_json(path)
    if not isinstance(report, dict):
        return ["closed-canary report must be an object"]
    errors: list[str] = []
    if report.get("commit_sha") != commit_sha:
        errors.append("closed-canary report commit does not match the current commit")
    if report.get("consecutive_days", 0) < 7:
        errors.append("closed canary must complete at least 7 consecutive days")
    if report.get("stop_conditions_triggered") is not False:
        errors.append("closed canary recorded a stop condition")
    drills = report.get("drills")
    if not isinstance(drills, dict):
        errors.append("closed-canary report must contain drill results")
    else:
        missing = REQUIRED_DRILLS - {
            name for name, passed in drills.items() if passed is True
        }
        if missing:
            errors.append("closed-canary drills not passed: " + ", ".join(sorted(missing)))
    return errors


def _validate_runtime_report(path: Path, commit_sha: str) -> list[str]:
    return validate_runtime_report(path, commit_sha, ROOT)


def _validate_privacy_review(path: Path, commit_sha: str) -> list[str]:
    return validate_privacy_review(path, commit_sha, ROOT)


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
        commit_sha = _git("rev-parse", "HEAD")
        if _git("status", "--porcelain"):
            errors.append("readiness requires a clean working tree, including untracked files")
    except subprocess.CalledProcessError as exc:
        errors.append(f"unable to inspect git state: {exc}")
        return errors

    evidence_manifest = evidence_manifest or EVIDENCE_DIR / "audit-evidence.json"
    evidence_signature = evidence_signature or EVIDENCE_DIR / "audit-evidence.sig"
    evidence_certificate = evidence_certificate or EVIDENCE_DIR / "audit-evidence.pem"
    errors.extend(
        _validate_evidence_manifest(
            evidence_manifest,
            evidence_signature,
            evidence_certificate,
            commit_sha,
        )
    )

    assurance_index = assurance_index or EVIDENCE_DIR / "assurance-index.json"
    errors.extend(
        _validate_assurance_index(
            assurance_index,
            stage,
            commit_sha,
            {track["id"] for track in applicable_tracks},
        )
    )

    if deployment_manifests is None:
        suffix = "rehearsal" if stage == "canary" else "deployment"
        deployment_manifests = [
            EVIDENCE_DIR / f"polygon-amoy-{suffix}.json",
            EVIDENCE_DIR / f"cardano-preprod-{suffix}.json",
        ]
    errors.extend(_validate_deployment_manifests(deployment_manifests, stage, commit_sha))

    runtime_report = runtime_report or EVIDENCE_DIR / "runtime-integration.json"
    privacy_review = privacy_review or EVIDENCE_DIR / "privacy-review.json"
    errors.extend(_validate_runtime_report(runtime_report, commit_sha))
    errors.extend(_validate_privacy_review(privacy_review, commit_sha))

    supporting_artifacts = [
        assurance_index,
        *deployment_manifests,
        runtime_report,
        privacy_review,
    ]
    if stage == "public":
        canary_report = canary_report or EVIDENCE_DIR / "closed-canary-report.json"
        canary_signature = canary_signature or EVIDENCE_DIR / "closed-canary-report.sig"
        canary_certificate = (
            canary_certificate or EVIDENCE_DIR / "closed-canary-report.pem"
        )
        errors.extend(_validate_canary_report(canary_report, commit_sha))
        _require_nonempty_file(
            canary_signature, "closed-canary signature", errors
        )
        _require_nonempty_file(
            canary_certificate, "closed-canary certificate", errors
        )
        supporting_artifacts.append(canary_report)
        independent_reviews = (
            independent_reviews or EVIDENCE_DIR / "independent-reviews.json"
        )
        errors.extend(_validate_independent_reviews(independent_reviews, commit_sha))
        supporting_artifacts.append(independent_reviews)
        register_text = (ROOT / "contracts" / "CONTRACTS.md").read_text(
            encoding="utf-8"
        )
        if re.search(r"\|\s*Pending\s*\|", register_text, flags=re.IGNORECASE):
            errors.append("deployment evidence register still contains Pending fields")
    errors.extend(
        _validate_manifest_artifact_binding(evidence_manifest, supporting_artifacts)
    )
    return errors


def generate_manifest(output: Path, raw_results: list[str]) -> None:
    matrix_bytes = MATRIX_PATH.read_bytes()
    matrix = json.loads(matrix_bytes)
    statuses = Counter(track["status"] for track in matrix["tracks"])
    parsed_statuses: dict[str, str] = {}
    for item in raw_results:
        try:
            name, status = item.split("=", 1)
        except ValueError as exc:
            raise ValueError(f"invalid result {item!r}; expected name=status") from exc
        if status not in {"success", "failure", "skipped", "pending"}:
            raise ValueError(f"invalid status {status!r} for {name!r}")
        if name not in REQUIRED_EVIDENCE_RESULTS:
            raise ValueError(f"unexpected evidence result name: {name!r}")
        if name in parsed_statuses:
            raise ValueError(f"duplicate evidence result name: {name!r}")
        parsed_statuses[name] = status

    missing_results = set(REQUIRED_EVIDENCE_RESULTS) - set(parsed_statuses)
    if missing_results:
        raise ValueError(
            "missing required evidence results: " + ", ".join(sorted(missing_results))
        )

    parsed_results = []
    for name in sorted(REQUIRED_EVIDENCE_RESULTS):
        parsed_results.append(
            {
                "name": name,
                "status": parsed_statuses[name],
                "command": REQUIRED_EVIDENCE_RESULTS[name],
                "artifact_sha256": None,
                "reviewer": "github-actions",
            }
        )

    evidence_artifacts = []
    if EVIDENCE_DIR.is_dir():
        for artifact in sorted(EVIDENCE_DIR.glob("*.json")):
            if artifact.resolve() == output.resolve():
                continue
            evidence_artifacts.append(
                {
                    "path": artifact.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                }
            )

    manifest = {
        "schema_version": "1.0.0",
        "commit_sha": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": "github-actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local",
        "control_matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest(),
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
    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("--output", type=Path, required=True)
    manifest_parser.add_argument("--result", action="append", default=[])
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
        )
        if args.command == "readiness"
        else validate_program()
    )
    if errors:
        print("Audit program validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.command == "manifest":
        try:
            generate_manifest(args.output, args.result)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f"Evidence manifest generation failed: {exc}", file=sys.stderr)
            return 1
        print(f"Evidence manifest written to {args.output}")
    elif args.command == "readiness":
        print(f"Testnet {args.stage} readiness passed.")
    else:
        print("Audit program validation passed: 36 tracks and testnet profile valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
