#!/usr/bin/env python3
"""Validate fail-closed inputs for the local credential-history rewrite."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INCIDENT_ID = "VAMS-PEM-2026-001"
REPOSITORY = "GodOfAgents/VAMS"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
GENERIC_REVIEWERS = {"automated", "github-actions", "pending", "self", "tbd"}
ROLE_CHECKS = {
    "deployment_signer",
    "funded_account",
    "node",
    "provider",
    "safe",
    "timelock",
    "validator",
}
OCCURRENCE_COUNTS = {"node_identity.pem": 1, "neuron/node_identity.pem": 1}


def _strict(value: Any, fields: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    missing = fields - set(value)
    unexpected = set(value) - fields
    if missing:
        errors.append(f"{label} missing fields: {', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"{label} unexpected fields: {', '.join(sorted(unexpected))}")
    return not missing and not unexpected


def _utc(value: Any, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{label} must be an ISO-8601 UTC timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be an ISO-8601 UTC timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        errors.append(f"{label} must include a UTC offset")
        return None
    return parsed


def _hash(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        errors.append(f"{label} must be a lowercase SHA-256 digest")
        return False
    return True


def _commit(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        errors.append(f"{label} must be a lowercase commit SHA")
        return False
    return True


def _reviewer(report: dict[str, Any], errors: list[str]) -> None:
    reviewer = report.get("reviewer")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or reviewer.strip().lower() in GENERIC_REVIEWERS
    ):
        errors.append("reviewer must identify the Architect owner")
    if report.get("review_mode") != "architect-owner":
        errors.append("review_mode must be architect-owner")
    if report.get("independent_review") is not False:
        errors.append("independent_review must truthfully remain false")
    _utc(report.get("reviewed_at"), "reviewed_at", errors)


def validate_rotation_evidence(report: Any) -> list[str]:
    errors: list[str] = []
    fields = {
        "schema_version",
        "incident_id",
        "reviewer",
        "review_mode",
        "independent_review",
        "reviewed_at",
        "approved_for_local_rewrite",
        "remote_force_push_approved",
        "affected_occurrences",
        "affected_identities",
        "provider_credentials",
    }
    if not _strict(report, fields, "rotation evidence", errors):
        return errors
    assert isinstance(report, dict)
    if report.get("schema_version") != "1.0.0":
        errors.append("rotation evidence schema_version must be 1.0.0")
    if report.get("incident_id") != INCIDENT_ID:
        errors.append("rotation evidence incident_id is invalid")
    _reviewer(report, errors)
    if report.get("approved_for_local_rewrite") is not True:
        errors.append("rotation evidence does not approve the local rewrite")
    if report.get("remote_force_push_approved") is not False:
        errors.append("rotation evidence must not pre-approve a remote force push")

    occurrences = report.get("affected_occurrences")
    occurrence_counts = {path: 0 for path in OCCURRENCE_COUNTS}
    occurrence_fingerprints: set[str] = set()
    if not isinstance(occurrences, list) or len(occurrences) != 2:
        errors.append("affected_occurrences must contain exactly two records")
        occurrences = []
    for index, occurrence in enumerate(occurrences):
        label = f"affected_occurrences[{index}]"
        if not _strict(occurrence, {"path", "commit_sha", "fingerprint_sha256"}, label, errors):
            continue
        path = occurrence.get("path")
        if path not in occurrence_counts:
            errors.append(f"{label}.path is not an approved PEM path")
        else:
            occurrence_counts[path] += 1
        _commit(occurrence.get("commit_sha"), f"{label}.commit_sha", errors)
        fingerprint = occurrence.get("fingerprint_sha256")
        if _hash(fingerprint, f"{label}.fingerprint_sha256", errors):
            occurrence_fingerprints.add(fingerprint)
    if occurrence_counts != OCCURRENCE_COUNTS:
        errors.append("affected_occurrences do not match the required PEM path counts")

    identities = report.get("affected_identities")
    identity_fingerprints: set[str] = set()
    if not isinstance(identities, list) or len(identities) != 2:
        errors.append("affected_identities must contain exactly two records")
        identities = []
    identity_fields = {
        "fingerprint_sha256",
        "key_type",
        "decommissioned_at",
        "decommission_disposition",
        "public_evm_identifier",
        "no_replacement",
        "role_impact_checks",
        "polygon_amoy",
        "cardano_preprod",
        "decommission_evidence_sha256",
    }
    for index, identity in enumerate(identities):
        label = f"affected_identities[{index}]"
        if not _strict(identity, identity_fields, label, errors):
            continue
        fingerprint = identity.get("fingerprint_sha256")
        if _hash(fingerprint, f"{label}.fingerprint_sha256", errors):
            identity_fingerprints.add(fingerprint)
        if identity.get("key_type") != "secp256k1":
            errors.append(f"{label}.key_type must be secp256k1")
        _utc(identity.get("decommissioned_at"), f"{label}.decommissioned_at", errors)
        if identity.get("decommission_disposition") != "permanently-decommissioned-no-replacement":
            errors.append(f"{label}.decommission_disposition is invalid")
        if identity.get("no_replacement") is not True:
            errors.append(f"{label}.no_replacement must be true")
        if not isinstance(identity.get("public_evm_identifier"), str) or EVM_RE.fullmatch(identity["public_evm_identifier"]) is None:
            errors.append(f"{label}.public_evm_identifier is invalid")
        _hash(identity.get("decommission_evidence_sha256"), f"{label}.decommission_evidence_sha256", errors)

        roles = identity.get("role_impact_checks")
        if _strict(roles, ROLE_CHECKS, f"{label}.role_impact_checks", errors):
            for role, result in roles.items():
                role_label = f"{label}.role_impact_checks.{role}"
                if _strict(result, {"clear", "evidence_sha256"}, role_label, errors):
                    if result.get("clear") is not True:
                        errors.append(f"{role_label} is not clear")
                    _hash(result.get("evidence_sha256"), f"{role_label}.evidence_sha256", errors)

        polygon = identity.get("polygon_amoy")
        polygon_fields = {"zero_balance", "observed_at", "block_number", "evidence_sha256"}
        if _strict(polygon, polygon_fields, f"{label}.polygon_amoy", errors):
            if polygon.get("zero_balance") is not True:
                errors.append(f"{label}.polygon_amoy does not prove zero balance")
            _utc(polygon.get("observed_at"), f"{label}.polygon_amoy.observed_at", errors)
            if not isinstance(polygon.get("block_number"), int) or polygon["block_number"] < 0:
                errors.append(f"{label}.polygon_amoy.block_number is invalid")
            _hash(polygon.get("evidence_sha256"), f"{label}.polygon_amoy.evidence_sha256", errors)

        cardano = identity.get("cardano_preprod")
        cardano_fields = {"applicability", "observed_at", "reason", "evidence_sha256"}
        if _strict(cardano, cardano_fields, f"{label}.cardano_preprod", errors):
            if cardano.get("applicability") != "cryptographically-inapplicable":
                errors.append(f"{label}.cardano_preprod.applicability is invalid")
            _utc(cardano.get("observed_at"), f"{label}.cardano_preprod.observed_at", errors)
            if not isinstance(cardano.get("reason"), str) or not cardano["reason"].strip():
                errors.append(f"{label}.cardano_preprod.reason is required")
            _hash(cardano.get("evidence_sha256"), f"{label}.cardano_preprod.evidence_sha256", errors)
    if identity_fingerprints != occurrence_fingerprints or len(identity_fingerprints) != 2:
        errors.append("PEM occurrences must bind exactly the two decommissioned identities")

    providers = report.get("provider_credentials")
    if not isinstance(providers, list) or len(providers) != 1:
        errors.append("provider_credentials must contain exactly one Infura record")
        providers = []
    provider_fields = {
        "provider",
        "fingerprint_sha256",
        "revocation_status",
        "exact_revocation_time_unavailable",
        "revoked_before",
        "observed_at",
        "access_review_clear",
        "billing_review_clear",
        "evidence_sha256",
    }
    for index, provider in enumerate(providers):
        label = f"provider_credentials[{index}]"
        if not _strict(provider, provider_fields, label, errors):
            continue
        if provider.get("provider") != "infura":
            errors.append(f"{label}.provider must be infura")
        _hash(provider.get("fingerprint_sha256"), f"{label}.fingerprint_sha256", errors)
        if provider.get("revocation_status") != "revoked":
            errors.append(f"{label} is not revoked")
        if provider.get("exact_revocation_time_unavailable") is not True:
            errors.append(f"{label} must preserve the unavailable exact revocation time")
        revoked_before = _utc(provider.get("revoked_before"), f"{label}.revoked_before", errors)
        observed_at = _utc(provider.get("observed_at"), f"{label}.observed_at", errors)
        if revoked_before and observed_at and revoked_before > observed_at:
            errors.append(f"{label}.revoked_before postdates observed_at")
        if provider.get("access_review_clear") is not True:
            errors.append(f"{label}.access_review_clear must be true")
        if provider.get("billing_review_clear") is not True:
            errors.append(f"{label}.billing_review_clear must be true")
        _hash(provider.get("evidence_sha256"), f"{label}.evidence_sha256", errors)
    return errors


def validate_maintenance_approval(report: Any, expected_main_sha: str) -> list[str]:
    errors: list[str] = []
    fields = {
        "schema_version",
        "incident_id",
        "repository",
        "frozen_main_sha",
        "frozen_at",
        "branch_ruleset",
        "tag_ruleset",
        "actions_enabled",
        "inventory_counts",
        "authoritative_refs",
        "approved_by",
        "approved_at",
        "local_rewrite_approved",
        "remote_force_push_approved",
    }
    if not _strict(report, fields, "maintenance approval", errors):
        return errors
    assert isinstance(report, dict)
    if report.get("schema_version") != "1.0.0":
        errors.append("maintenance approval schema_version must be 1.0.0")
    if report.get("incident_id") != INCIDENT_ID:
        errors.append("maintenance approval incident_id is invalid")
    if report.get("repository") != REPOSITORY:
        errors.append("maintenance approval repository is invalid")
    if report.get("frozen_main_sha") != expected_main_sha:
        errors.append("maintenance approval does not bind the mirrored main SHA")
    _commit(report.get("frozen_main_sha"), "frozen_main_sha", errors)
    _utc(report.get("frozen_at"), "frozen_at", errors)
    _utc(report.get("approved_at"), "approved_at", errors)
    approved_by = report.get("approved_by")
    if not isinstance(approved_by, str) or not approved_by.strip() or approved_by.lower() in GENERIC_REVIEWERS:
        errors.append("approved_by must identify the maintenance approver")
    if report.get("local_rewrite_approved") is not True:
        errors.append("maintenance record does not approve the local rewrite")
    if report.get("remote_force_push_approved") is not False:
        errors.append("maintenance record must not pre-approve a remote force push")
    if report.get("actions_enabled") is not False:
        errors.append("GitHub Actions must be disabled during the rewrite window")

    ruleset_fields = {"id", "name", "enforcement", "bypass_actor_count", "current_user_can_bypass"}
    for key, expected_target in (("branch_ruleset", "branches"), ("tag_ruleset", "tags")):
        ruleset = report.get(key)
        if _strict(ruleset, ruleset_fields, key, errors):
            if not isinstance(ruleset.get("id"), int) or ruleset["id"] <= 0:
                errors.append(f"{key}.id is invalid")
            if INCIDENT_ID not in str(ruleset.get("name")) or expected_target not in str(ruleset.get("name")):
                errors.append(f"{key}.name is not incident-bound")
            if ruleset.get("enforcement") != "active":
                errors.append(f"{key}.enforcement must be active")
            if ruleset.get("bypass_actor_count") != 0:
                errors.append(f"{key} must have zero bypass actors")
            if ruleset.get("current_user_can_bypass") != "never":
                errors.append(f"{key} must not permit a standing bypass")

    counts = report.get("inventory_counts")
    if _strict(counts, {"branches", "tags", "releases", "deployments", "open_pull_requests"}, "inventory_counts", errors):
        if not isinstance(counts.get("branches"), int) or counts["branches"] < 1:
            errors.append("inventory_counts.branches is invalid")
        for key in ("tags", "releases", "deployments"):
            if counts.get(key) != 0:
                errors.append(f"inventory_counts.{key} must be zero during the freeze")
        if not isinstance(counts.get("open_pull_requests"), int) or counts["open_pull_requests"] < 0:
            errors.append("inventory_counts.open_pull_requests is invalid")

    refs = report.get("authoritative_refs")
    if not isinstance(refs, dict) or not refs:
        errors.append("authoritative_refs must be a nonempty object")
    else:
        for ref, sha in refs.items():
            if not isinstance(ref, str) or not ref.startswith("refs/heads/"):
                errors.append("authoritative_refs contains an invalid ref")
            _commit(sha, f"authoritative_refs.{ref}", errors)
        if refs.get("refs/heads/main") != expected_main_sha:
            errors.append("authoritative_refs.main does not match the mirrored main SHA")
    return errors


def _load(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read {label} as JSON: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rotation-evidence", type=Path, required=True)
    parser.add_argument("--maintenance-approval", type=Path, required=True)
    parser.add_argument("--expected-main-sha", required=True)
    args = parser.parse_args()
    errors: list[str] = []
    if COMMIT_RE.fullmatch(args.expected_main_sha) is None:
        errors.append("--expected-main-sha is invalid")
    try:
        rotation = _load(args.rotation_evidence, "rotation evidence")
        maintenance = _load(args.maintenance_approval, "maintenance approval")
    except ValueError as exc:
        errors.append(str(exc))
    else:
        errors.extend(validate_rotation_evidence(rotation))
        errors.extend(validate_maintenance_approval(maintenance, args.expected_main_sha))
    if errors:
        print("History rewrite input validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("History rewrite inputs are incident-bound and approve only the local rewrite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
