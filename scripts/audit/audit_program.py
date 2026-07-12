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
REQUIRED_GATEWAY_CHECKS = {
    "tls",
    "mtls",
    "did_auth",
    "replay_rejection",
    "cors",
    "rate_limits",
    "request_limits",
    "loopback_bind",
    "dast",
    "load_test",
}
REQUIRED_EXCLUDED_ROUTES = {
    "avail",
    "eigenda",
    "mock_identity",
    "mock_tee",
    "mock_bridge",
    "coinme",
    "trails",
    "incomplete_interrupt",
    "incomplete_storage",
}
REQUIRED_INDEPENDENT_DOMAINS = {
    "solidity-governance",
    "aiken-bridge",
    "economics-centralization",
    "gateway-agent-sdk",
    "privacy",
    "ai-agent-safety",
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

    for schema_path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = _load_json(schema_path)
        if not isinstance(schema, dict) or "$schema" not in schema or "title" not in schema:
            errors.append(f"{schema_path.relative_to(ROOT)} is not a complete JSON schema")

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
    if manifest.get("commit_sha") != commit_sha:
        errors.append("evidence manifest commit does not match the current commit")
    if manifest.get("dirty") is not False:
        errors.append("evidence manifest was generated from a dirty tree")
    results = manifest.get("results")
    if not isinstance(results, list) or not results:
        errors.append("evidence manifest must contain gate results")
    elif any(result.get("status") != "success" for result in results):
        errors.append("every evidence-manifest gate result must be successful")
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
        elif network in seen_networks:
            errors.append(f"duplicate deployment manifest for {network}")
        else:
            seen_networks.add(network)
        expected_status = "rehearsed" if stage == "canary" else "deployed"
        if manifest.get("deployment_status") != expected_status:
            errors.append(
                f"{network or path} must have deployment_status={expected_status}"
            )
        if manifest.get("commit_sha") != commit_sha:
            errors.append(f"{network or path} commit does not match the current commit")
        if _contains_pending(manifest):
            errors.append(f"{network or path} contains Pending deployment evidence")
        artifacts = manifest.get("artifacts")
        artifact_names = {
            artifact.get("name")
            for artifact in artifacts
            if isinstance(artifact, dict) and isinstance(artifact.get("name"), str)
        } if isinstance(artifacts, list) else set()
        if network == "polygon-amoy":
            required_artifacts = (
                CANARY_EVM_ARTIFACTS if stage == "canary" else PUBLIC_EVM_ARTIFACTS
            )
        elif network == "cardano-preprod":
            required_artifacts = CARDANO_ARTIFACTS
        else:
            required_artifacts = set()
        missing_artifacts = required_artifacts - artifact_names
        if missing_artifacts:
            errors.append(
                f"{network or path} missing deployment artifacts: "
                + ", ".join(sorted(missing_artifacts))
            )
        if manifest.get("deployer_privileges_removed") is not True:
            errors.append(f"{network or path} does not prove deployer privilege removal")
        if manifest.get("mock_routes_disabled") is not True:
            errors.append(f"{network or path} does not prove mock-route exclusion")
        if manifest.get("timelock_seconds", 0) < 172800:
            errors.append(f"{network or path} timelock is below 48 hours")
        authorities = manifest.get("authorities")
        if not isinstance(authorities, dict):
            errors.append(f"{network or path} authorities are missing")
        else:
            addresses: list[str] = []
            authority_specs = {
                "governance": (5, 3),
                "treasury": (5, 3),
                "emergency": (3, 2),
            }
            for name, (owner_count, threshold) in authority_specs.items():
                authority = authorities.get(name)
                if not isinstance(authority, dict):
                    errors.append(f"{network or path} {name} authority is missing")
                    continue
                address = str(authority.get("address", "")).strip()
                owners = authority.get("owners")
                if not address:
                    errors.append(f"{network or path} {name} address is missing")
                else:
                    addresses.append(address.lower())
                if (
                    not isinstance(owners, list)
                    or len(owners) != owner_count
                    or len(set(owners)) != owner_count
                ):
                    errors.append(
                        f"{network or path} {name} must have {owner_count} distinct owners"
                    )
                if authority.get("threshold") != threshold:
                    errors.append(
                        f"{network or path} {name} threshold must equal {threshold}"
                    )
            if len(addresses) == 3 and len(set(addresses)) != 3:
                errors.append(f"{network or path} authority addresses must be distinct")
            emergency = authorities.get("emergency", {})
            if emergency.get("scope") != "pause-only":
                errors.append(f"{network or path} emergency scope must be pause-only")
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
        track_number = int(track_id[1:])
        if stage == "public" and 10 <= track_number <= 34:
            if entry.get("independent_review") is not True:
                errors.append(f"public readiness requires independent review for {track_id}")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"assurance index artifacts are missing for {track_id}")
            continue
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                errors.append(f"{track_id} contains an invalid artifact record")
                continue
            relative_path = artifact.get("path")
            expected_hash = artifact.get("sha256")
            if not isinstance(relative_path, str) or not relative_path:
                errors.append(f"{track_id} artifact path is missing")
                continue
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
    if not path.is_file():
        return [f"runtime integration report is missing: {path}"]
    report = _load_json(path)
    if not isinstance(report, dict):
        return ["runtime integration report must be an object"]
    errors: list[str] = []
    if report.get("commit_sha") != commit_sha:
        errors.append("runtime integration report commit does not match current commit")
    if report.get("environment") != "testnet":
        errors.append("runtime integration report environment must be testnet")
    gateway = report.get("gateway_checks")
    if not isinstance(gateway, dict):
        errors.append("runtime integration report lacks Gateway checks")
    else:
        missing = REQUIRED_GATEWAY_CHECKS - {
            name for name, passed in gateway.items() if passed is True
        }
        if missing:
            errors.append("Gateway runtime checks not passed: " + ", ".join(sorted(missing)))
    receipts = report.get("da_receipts")
    verified_providers: set[str] = set()
    if isinstance(receipts, list):
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            provider = receipt.get("provider")
            if (
                provider in {"celestia", "near"}
                and receipt.get("retrieval_verified") is True
                and str(receipt.get("submission_id", "")).strip()
                and re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("payload_sha256", "")))
            ):
                verified_providers.add(provider)
    missing_providers = {"celestia", "near"} - verified_providers
    if missing_providers:
        errors.append(
            "verified DA receipts missing providers: "
            + ", ".join(sorted(missing_providers))
        )
    excluded = report.get("excluded_live_routes")
    excluded_set = set(excluded) if isinstance(excluded, list) else set()
    missing_routes = REQUIRED_EXCLUDED_ROUTES - excluded_set
    if missing_routes:
        errors.append("live route exclusions missing: " + ", ".join(sorted(missing_routes)))
    return errors


def _validate_privacy_review(path: Path, commit_sha: str) -> list[str]:
    if not path.is_file():
        return [f"privacy review is missing: {path}"]
    review = _load_json(path)
    if not isinstance(review, dict):
        return ["privacy review must be an object"]
    errors: list[str] = []
    if review.get("commit_sha") != commit_sha:
        errors.append("privacy review commit does not match current commit")
    for field in (
        "data_inventory_approved",
        "retention_policy_approved",
        "redaction_tests_passed",
        "public_content_reviewed",
        "publisher_inventory_complete",
    ):
        if review.get(field) is not True:
            errors.append(f"privacy review has not approved {field}")
    if review.get("blocking_findings_open") != 0:
        errors.append("privacy review has open blocking findings")
    if not str(review.get("reviewer", "")).strip():
        errors.append("privacy reviewer is missing")
    return errors


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
    parsed_results = []
    for item in raw_results:
        try:
            name, status = item.split("=", 1)
        except ValueError as exc:
            raise ValueError(f"invalid result {item!r}; expected name=status") from exc
        if status not in {"success", "failure", "skipped", "pending"}:
            raise ValueError(f"invalid status {status!r} for {name!r}")
        parsed_results.append(
            {
                "name": name,
                "status": status,
                "command": "",
                "artifact_sha256": None,
                "reviewer": None,
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
        "environment": os.getenv("GITHUB_ACTIONS", "local"),
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
