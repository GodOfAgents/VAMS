#!/usr/bin/env python3
"""Validate public, exact-commit evidence closing the historical PEM incident."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_ROLE_CHECKS = {
    "deployment_signer",
    "funded_account",
    "node",
    "provider",
    "safe",
    "timelock",
    "validator",
}
REQUIRED_NETWORKS = {"polygon-amoy", "cardano-preprod"}
REQUIRED_OCCURRENCE_PATH_COUNTS = {
    "node_identity.pem": 2,
    "neuron/node_identity.pem": 1,
}
EXPECTED_FINDING_OCCURRENCES = sum(REQUIRED_OCCURRENCE_PATH_COUNTS.values())
EXPECTED_UNIQUE_IDENTITIES = 2
CREDENTIAL_INCIDENT_SCHEMA_VERSION = "3.0.0"
FUNDING_APPLICABILITIES = {
    "account-derived",
    "cryptographically-inapplicable",
}
GENERIC_REVIEWERS = {"automated", "github-actions", "pending", "self", "tbd"}


def _strict(value: Any, fields: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    missing = fields - set(value)
    unexpected = set(value) - fields
    if missing:
        errors.append(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"{label} has unexpected fields: {', '.join(sorted(unexpected))}")
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


def _artifact(
    reference: Any,
    root: Path,
    label: str,
    errors: list[str],
) -> None:
    if not _strict(reference, {"path", "sha256"}, label, errors):
        return
    relative = reference.get("path")
    digest = reference.get("sha256")
    if not isinstance(relative, str) or not relative or "\\" in relative:
        errors.append(f"{label}.path must be a repository-relative POSIX path")
        return
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        errors.append(f"{label}.path escapes the evidence bundle")
        return
    if not isinstance(digest, str) or HASH_RE.fullmatch(digest) is None:
        errors.append(f"{label}.sha256 is invalid")
        return
    candidate = root.joinpath(*pure.parts)
    boundary = (root / "docs" / "audit" / "evidence").resolve()
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(boundary)
    except (FileNotFoundError, OSError, ValueError):
        errors.append(f"{label} is missing or outside docs/audit/evidence")
        return
    if candidate.is_symlink() or not resolved.is_file() or resolved.stat().st_size == 0:
        errors.append(f"{label} must bind a nonempty regular file")
        return
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != digest:
        errors.append(f"{label} hash does not match {relative}")


def validate_credential_incident_report(
    path: Path,
    commit_sha: str,
    artifact_root: Path | None = None,
) -> list[str]:
    if not path.is_file():
        return [f"credential incident report is missing: {path}"]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [f"credential incident report is not valid JSON: {path}"]

    errors: list[str] = []
    top = {
        "schema_version",
        "commit_sha",
        "incident_id",
        "affected_occurrences",
        "affected_identities",
        "history_rewrite",
        "full_history_scans",
        "reviewer",
        "reviewer_organization",
        "review_mode",
        "independent_review",
        "reviewed_at",
        "blocking_findings_open",
    }
    if not _strict(report, top, "credential incident report", errors):
        if not isinstance(report, dict):
            return errors
    if report.get("schema_version") != CREDENTIAL_INCIDENT_SCHEMA_VERSION:
        errors.append(
            "credential incident schema_version must be "
            + CREDENTIAL_INCIDENT_SCHEMA_VERSION
        )
    if COMMIT_RE.fullmatch(commit_sha) is None or report.get("commit_sha") != commit_sha:
        errors.append("credential incident report does not match the target commit")
    if report.get("incident_id") != "VAMS-PEM-2026-001":
        errors.append("credential incident report has an unexpected incident_id")
    reviewed_at = _utc(report.get("reviewed_at"), "reviewed_at", errors)
    reviewer = str(report.get("reviewer", "")).strip()
    organization = str(report.get("reviewer_organization", "")).strip()
    if not reviewer or reviewer.casefold() in GENERIC_REVIEWERS:
        errors.append("credential incident report requires a named human reviewer")
    if not organization or organization.casefold() in GENERIC_REVIEWERS:
        errors.append("credential incident report requires a reviewer organization")
    if report.get("review_mode") != "architect-owner":
        errors.append("credential incident report review_mode must be architect-owner")
    if report.get("independent_review") is not False:
        errors.append("credential incident report must not claim independent review")
    if report.get("blocking_findings_open") != 0 or isinstance(
        report.get("blocking_findings_open"), bool
    ):
        errors.append("credential incident report has open blocking findings")

    root = artifact_root or ROOT
    occurrences = report.get("affected_occurrences")
    occurrence_fingerprints: set[str] = set()
    occurrence_pairs: set[tuple[str, str]] = set()
    occurrence_path_counts = {
        path: 0 for path in REQUIRED_OCCURRENCE_PATH_COUNTS
    }
    if not isinstance(occurrences, list) or len(occurrences) != EXPECTED_FINDING_OCCURRENCES:
        errors.append(
            "credential incident report must contain exactly "
            f"{EXPECTED_FINDING_OCCURRENCES} historical PEM finding occurrences"
        )
        occurrences = []
    occurrence_fields = {"path", "commit_sha", "fingerprint_sha256"}
    for index, occurrence in enumerate(occurrences):
        label = f"affected_occurrences[{index}]"
        if not _strict(occurrence, occurrence_fields, label, errors):
            continue
        path_value = occurrence.get("path")
        occurrence_commit = occurrence.get("commit_sha")
        fingerprint = occurrence.get("fingerprint_sha256")
        if path_value not in REQUIRED_OCCURRENCE_PATH_COUNTS:
            errors.append(f"{label}.path is not an affected PEM path")
        else:
            occurrence_path_counts[path_value] += 1
        if (
            not isinstance(occurrence_commit, str)
            or COMMIT_RE.fullmatch(occurrence_commit) is None
        ):
            errors.append(f"{label}.commit_sha is invalid")
        if not isinstance(fingerprint, str) or HASH_RE.fullmatch(fingerprint) is None:
            errors.append(f"{label}.fingerprint_sha256 is invalid")
        else:
            occurrence_fingerprints.add(fingerprint)
        if isinstance(path_value, str) and isinstance(occurrence_commit, str):
            pair = (path_value, occurrence_commit)
            if pair in occurrence_pairs:
                errors.append("credential incident report contains a duplicate PEM occurrence")
            occurrence_pairs.add(pair)
    if occurrence_path_counts != REQUIRED_OCCURRENCE_PATH_COUNTS:
        errors.append(
            "credential incident occurrence paths do not match the verified "
            "two root and one neuron findings"
        )

    identities = report.get("affected_identities")
    fingerprints: set[str] = set()
    replacements: set[str] = set()
    if not isinstance(identities, list) or len(identities) != EXPECTED_UNIQUE_IDENTITIES:
        errors.append(
            "credential incident report must contain exactly "
            f"{EXPECTED_UNIQUE_IDENTITIES} unique PEM key identities"
        )
        identities = []
    identity_fields = {
        "fingerprint_sha256",
        "key_type",
        "revoked_at",
        "replacement_fingerprint_sha256",
        "public_identifiers",
        "role_impact_checks",
        "funding_checks",
        "revocation_evidence",
    }
    for index, identity in enumerate(identities):
        label = f"affected_identities[{index}]"
        if not _strict(identity, identity_fields, label, errors):
            continue
        fingerprint = identity.get("fingerprint_sha256")
        if not isinstance(fingerprint, str) or HASH_RE.fullmatch(fingerprint) is None:
            errors.append(f"{label}.fingerprint_sha256 is invalid")
        elif fingerprint in fingerprints:
            errors.append("credential incident report contains duplicate fingerprints")
        else:
            fingerprints.add(fingerprint)
        replacement = identity.get("replacement_fingerprint_sha256")
        if not isinstance(replacement, str) or HASH_RE.fullmatch(replacement) is None:
            errors.append(f"{label}.replacement_fingerprint_sha256 is invalid")
        elif replacement == fingerprint:
            errors.append(f"{label} replacement fingerprint equals the compromised identity")
        elif replacement in replacements:
            errors.append("credential incident report contains duplicate replacement fingerprints")
        else:
            replacements.add(replacement)
        revoked_at = _utc(identity.get("revoked_at"), f"{label}.revoked_at", errors)
        if reviewed_at and revoked_at and revoked_at > reviewed_at:
            errors.append(f"{label} revocation postdates the review")
        identifiers = identity.get("public_identifiers")
        if not isinstance(identifiers, list) or not identifiers or not all(
            isinstance(item, str) and item.strip() for item in identifiers
        ):
            errors.append(f"{label}.public_identifiers must be nonempty public values")
        role_checks = identity.get("role_impact_checks")
        if not _strict(role_checks, REQUIRED_ROLE_CHECKS, f"{label}.role_impact_checks", errors):
            role_checks = {}
        for role, result in role_checks.items():
            role_label = f"{label}.role_impact_checks.{role}"
            if _strict(result, {"clear", "evidence"}, role_label, errors):
                if result.get("clear") is not True:
                    errors.append(f"{role_label} is not clear")
                _artifact(result.get("evidence"), root, f"{role_label}.evidence", errors)
        funding = identity.get("funding_checks")
        seen_networks: set[str] = set()
        if not isinstance(funding, list) or len(funding) != len(REQUIRED_NETWORKS):
            errors.append(
                f"{label}.funding_checks must contain exactly one check per required network"
            )
            funding = []
        for item_index, check in enumerate(funding):
            check_label = f"{label}.funding_checks[{item_index}]"
            if not isinstance(check, dict):
                errors.append(f"{check_label} must be an object")
                continue
            applicability = check.get("applicability")
            if applicability not in FUNDING_APPLICABILITIES:
                errors.append(f"{check_label}.applicability is invalid")
                continue
            if applicability == "account-derived":
                fields = {
                    "network",
                    "applicability",
                    "public_identifier",
                    "observed_at",
                    "zero_balance",
                    "evidence",
                }
            elif applicability == "cryptographically-inapplicable":
                fields = {
                    "network",
                    "applicability",
                    "observed_at",
                    "non_applicability_reason",
                    "evidence",
                }
            if not _strict(check, fields, check_label, errors):
                continue
            network = check.get("network")
            if network not in REQUIRED_NETWORKS:
                errors.append(f"{check_label}.network is invalid")
            elif network in seen_networks:
                errors.append(f"{check_label}.network is duplicated")
            else:
                seen_networks.add(network)
            _utc(check.get("observed_at"), f"{check_label}.observed_at", errors)
            if applicability == "account-derived":
                public_identifier = check.get("public_identifier")
                if not isinstance(public_identifier, str) or not public_identifier.strip():
                    errors.append(f"{check_label}.public_identifier is invalid")
                if check.get("zero_balance") is not True:
                    errors.append(f"{check_label} does not prove zero balance")
            else:
                reason = check.get("non_applicability_reason")
                if not isinstance(reason, str) or not reason.strip():
                    errors.append(f"{check_label}.non_applicability_reason is invalid")
            _artifact(check.get("evidence"), root, f"{check_label}.evidence", errors)
        if seen_networks != REQUIRED_NETWORKS:
            errors.append(f"{label} lacks Polygon Amoy or Cardano Pre-Prod funding proof")
        _artifact(
            identity.get("revocation_evidence"),
            root,
            f"{label}.revocation_evidence",
            errors,
        )

    if fingerprints & replacements:
        errors.append("a replacement fingerprint is also listed as a compromised identity")
    if occurrence_fingerprints != fingerprints:
        errors.append(
            "credential incident occurrence fingerprints do not match the unique identities"
        )

    rewrite = report.get("history_rewrite")
    rewrite_fields = {
        "completed",
        "completed_at",
        "all_refs_rewritten",
        "collaborators_recloned",
        "forks_coordinated",
        "github_cached_refs_purged",
        "changed_refs_evidence",
        "github_support_evidence",
    }
    if _strict(rewrite, rewrite_fields, "history_rewrite", errors):
        for field in (
            "completed",
            "all_refs_rewritten",
            "collaborators_recloned",
            "forks_coordinated",
            "github_cached_refs_purged",
        ):
            if rewrite.get(field) is not True:
                errors.append(f"history_rewrite.{field} must be true")
        _utc(rewrite.get("completed_at"), "history_rewrite.completed_at", errors)
        _artifact(
            rewrite.get("changed_refs_evidence"),
            root,
            "history_rewrite.changed_refs_evidence",
            errors,
        )
        _artifact(
            rewrite.get("github_support_evidence"),
            root,
            "history_rewrite.github_support_evidence",
            errors,
        )

    scans = report.get("full_history_scans")
    if _strict(scans, {"gitleaks", "trufflehog"}, "full_history_scans", errors):
        for scanner, result in scans.items():
            scan_label = f"full_history_scans.{scanner}"
            if _strict(
                result,
                {"full_history", "findings_count", "command", "evidence"},
                scan_label,
                errors,
            ):
                if result.get("full_history") is not True or result.get("findings_count") != 0:
                    errors.append(f"{scan_label} is not a clean complete-history scan")
                command = str(result.get("command", ""))
                if scanner == "gitleaks" and "--all" not in command:
                    errors.append("Gitleaks closure scan must include literal --all")
                if scanner == "trufflehog" and not all(
                    marker in command for marker in ("verified", "unknown", "unverified")
                ):
                    errors.append("TruffleHog closure scan must include every result class")
                _artifact(result.get("evidence"), root, f"{scan_label}.evidence", errors)
    return errors
