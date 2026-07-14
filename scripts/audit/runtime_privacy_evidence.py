#!/usr/bin/env python3
"""Fail-closed validation for runtime, live-DA, and privacy evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PUBLISHER_INVENTORY_PATH = ROOT / "docs" / "audit" / "privacy-publisher-inventory.json"
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
    "vdso-current-celestia",
    "vdso-current-near",
}
PRIVACY_ARTIFACTS = {
    "data_inventory",
    "retention_policy",
    "redaction_tests",
    "public_content_review",
    "publisher_inventory",
}
PROVIDER_NETWORK = {
    "celestia": "celestia-mocha",
    "near": "near-testnet",
}
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
COMMITMENT_RE = re.compile(r"^0x[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
GENERIC_REVIEWERS = {
    "automated",
    "github-actions",
    "pending",
    "self",
    "tbd",
    "unknown",
}
SIMULATION_MARKERS = (
    b"[mock]",
    b"[stub]",
    b"simulated receipt",
    b"placeholder receipt",
    b"localhost",
    b"127.0.0.1",
    b".invalid",
)
MAX_EVIDENCE_ARTIFACT_BYTES = 64 * 1024 * 1024
PUBLISH_METHODS = {
    "publish",
    "publish_report",
    "publish_sentinel_report",
    "submit_blob",
}
PUBLISHER_SCOPE = ("neuron/da", "neuron/sentinel", "neuron/vdso")
INVENTORY_FIELDS = {
    "id",
    "path",
    "symbol",
    "channel",
    "payload_policy",
    "operational_live_capable",
    "release_evidence_eligible",
    "block_reason",
    "control_refs",
    "tests",
}
OPERATIONAL_LIVE_PUBLISHERS = {
    ("neuron/da/adapters/celestia_adapter.py", "CelestiaDAAdapter.submit_blob"),
    ("neuron/da/performance_audit.py", "PerformanceAuditLog.publish_sentinel_report"),
}
# No current publisher may independently qualify a release receipt. Removing an
# entry requires source and test changes, not an inventory-only status flip.
RELEASE_INELIGIBLE_PUBLISHERS = {
    ("neuron/da/adapters/avail_adapter.py", "AvailDAAdapter.submit_blob"),
    ("neuron/da/adapters/celestia_adapter.py", "CelestiaDAAdapter.submit_blob"),
    ("neuron/da/adapters/eigenda_adapter.py", "EigenDAAdapter.submit_blob"),
    ("neuron/da/adapters/near_adapter.py", "NearDAAdapter.submit_blob"),
    ("neuron/da/performance_audit.py", "PerformanceAuditLog.publish_sentinel_report"),
    ("neuron/sentinel/da_publisher.py", "DAPublisher.publish_report"),
    ("neuron/vdso/da.py", "EncryptedSidecarPublisher.publish"),
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _strict_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    actual = set(value)
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        errors.append(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"{label} has unexpected fields: {', '.join(sorted(unexpected))}")
    return not missing and not unexpected


def _parse_utc(value: Any, label: str, errors: list[str]) -> datetime | None:
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


def _artifact_file(
    reference: Any,
    *,
    root: Path,
    allowed_root: str,
    label: str,
    errors: list[str],
    reject_simulation_markers: bool = False,
) -> Path | None:
    if not _strict_keys(reference, {"path", "sha256"}, label, errors):
        return None
    relative = reference.get("path")
    digest = reference.get("sha256")
    if not isinstance(relative, str) or not relative or "\\" in relative:
        errors.append(f"{label} path must be a repository-relative POSIX path")
        return None
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
        errors.append(f"{label} path escapes the repository")
        return None
    if not isinstance(digest, str) or HASH_RE.fullmatch(digest) is None:
        errors.append(f"{label} sha256 must be 64 lowercase hexadecimal characters")
        return None

    candidate = root.joinpath(*pure.parts)
    boundary = (root / allowed_root).resolve()
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(boundary)
    except (FileNotFoundError, OSError, ValueError):
        errors.append(f"{label} artifact is missing or outside {allowed_root}: {relative}")
        return None
    if candidate.is_symlink() or not resolved.is_file():
        errors.append(f"{label} artifact must be a regular non-symlink file")
        return None
    if resolved.stat().st_size > MAX_EVIDENCE_ARTIFACT_BYTES:
        errors.append(f"{label} artifact exceeds the 64 MiB validation limit")
        return None
    content = resolved.read_bytes()
    if not content:
        errors.append(f"{label} artifact is empty")
        return None
    actual = hashlib.sha256(content).hexdigest()
    if actual != digest:
        errors.append(f"{label} artifact hash does not match {relative}")
        return None
    if reject_simulation_markers:
        lowered = content.lower()
        marker = next((item for item in SIMULATION_MARKERS if item in lowered), None)
        if marker is not None:
            errors.append(
                f"{label} artifact contains a non-live marker: {marker.decode('ascii')}"
            )
            return None
    return resolved


def validate_runtime_report(path: Path, commit_sha: str, root: Path = ROOT) -> list[str]:
    """Validate artifact-bound testnet Gateway and live-DA evidence."""

    if not path.is_file():
        return [f"runtime integration report is missing: {path}"]
    report = _load_json(path)
    expected_top = {
        "schema_version",
        "commit_sha",
        "environment",
        "generated_at",
        "gateway_checks",
        "da_receipts",
        "excluded_live_routes",
    }
    errors: list[str] = []
    if not _strict_keys(report, expected_top, "runtime integration report", errors):
        if not isinstance(report, dict):
            return errors
    if report.get("schema_version") != "2.0.0":
        errors.append("runtime integration report schema_version must be 2.0.0")
    if report.get("commit_sha") != commit_sha:
        errors.append("runtime integration report commit does not match current commit")
    if report.get("environment") != "testnet":
        errors.append("runtime integration report environment must be testnet")
    generated_at = _parse_utc(report.get("generated_at"), "generated_at", errors)

    gateway = report.get("gateway_checks")
    if _strict_keys(gateway, REQUIRED_GATEWAY_CHECKS, "gateway_checks", errors):
        for name in sorted(REQUIRED_GATEWAY_CHECKS):
            check = gateway[name]
            label = f"gateway_checks.{name}"
            if not _strict_keys(check, {"passed", "artifact"}, label, errors):
                continue
            if check.get("passed") is not True:
                errors.append(f"{label} did not pass")
            _artifact_file(
                check.get("artifact"),
                root=root,
                allowed_root="docs/audit/evidence",
                label=f"{label}.artifact",
                errors=errors,
            )

    receipts = report.get("da_receipts")
    seen_providers: set[str] = set()
    da_artifact_paths: set[str] = set()
    if not isinstance(receipts, list) or len(receipts) != 2:
        errors.append("runtime integration report must contain exactly two DA receipts")
        receipts = []
    receipt_fields = {
        "provider",
        "network",
        "submission_id",
        "inclusion_reference",
        "commitment",
        "payload_sha256",
        "retrieved_payload_sha256",
        "submitted_at",
        "retrieved_at",
        "retrieval_verified",
        "mock_mode",
        "submitter_identity",
        "retrieval_observer_identity",
        "submission_artifact",
        "retrieval_artifact",
    }
    for index, receipt in enumerate(receipts):
        label = f"da_receipts[{index}]"
        if not _strict_keys(receipt, receipt_fields, label, errors):
            if not isinstance(receipt, dict):
                continue
        provider = receipt.get("provider")
        if not isinstance(provider, str) or provider not in PROVIDER_NETWORK:
            errors.append(f"{label}.provider is unsupported")
        elif provider in seen_providers:
            errors.append(f"runtime integration report contains duplicate {provider} receipt")
        else:
            seen_providers.add(provider)
            if receipt.get("network") != PROVIDER_NETWORK[provider]:
                errors.append(f"{label}.network does not match {provider}")
        for field in ("submission_id", "inclusion_reference"):
            value = receipt.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                errors.append(f"{label}.{field} must be a bounded non-empty string")
        if COMMITMENT_RE.fullmatch(str(receipt.get("commitment", ""))) is None:
            errors.append(f"{label}.commitment must be a 32-byte lowercase hex value")
        payload_hash = receipt.get("payload_sha256")
        retrieved_hash = receipt.get("retrieved_payload_sha256")
        if HASH_RE.fullmatch(str(payload_hash)) is None:
            errors.append(f"{label}.payload_sha256 is invalid")
        if HASH_RE.fullmatch(str(retrieved_hash)) is None:
            errors.append(f"{label}.retrieved_payload_sha256 is invalid")
        if payload_hash != retrieved_hash:
            errors.append(f"{label} retrieved payload hash does not match submission")
        if receipt.get("retrieval_verified") is not True:
            errors.append(f"{label} lacks successful retrieval verification")
        if receipt.get("mock_mode") is not False:
            errors.append(f"{label} is mock evidence")
        raw_submitter = receipt.get("submitter_identity")
        raw_observer = receipt.get("retrieval_observer_identity")
        submitter = raw_submitter.strip() if isinstance(raw_submitter, str) else ""
        observer = raw_observer.strip() if isinstance(raw_observer, str) else ""
        if not submitter or not observer:
            errors.append(f"{label} submitter and retrieval observer identities are required")
        elif submitter.casefold() == observer.casefold():
            errors.append(f"{label} retrieval observer must be independent of submitter")
        submitted_at = _parse_utc(receipt.get("submitted_at"), f"{label}.submitted_at", errors)
        retrieved_at = _parse_utc(receipt.get("retrieved_at"), f"{label}.retrieved_at", errors)
        if submitted_at and retrieved_at and retrieved_at < submitted_at:
            errors.append(f"{label} retrieval predates submission")
        if generated_at and retrieved_at and generated_at < retrieved_at:
            errors.append(f"{label} report predates retrieval")

        for kind in ("submission", "retrieval"):
            reference = receipt.get(f"{kind}_artifact")
            if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                artifact_path = reference["path"]
                if artifact_path in da_artifact_paths:
                    errors.append(f"DA evidence reuses artifact path: {artifact_path}")
                da_artifact_paths.add(artifact_path)
            _artifact_file(
                reference,
                root=root,
                allowed_root="docs/audit/evidence",
                label=f"{label}.{kind}_artifact",
                errors=errors,
                reject_simulation_markers=True,
            )
        submission_reference = receipt.get("submission_artifact")
        retrieval_reference = receipt.get("retrieval_artifact")
        if isinstance(retrieval_reference, dict) and (
            retrieval_reference.get("sha256") != retrieved_hash
        ):
            errors.append(f"{label} retrieval artifact is not the retrieved payload")
        if (
            isinstance(submission_reference, dict)
            and isinstance(retrieval_reference, dict)
            and submission_reference.get("sha256")
            == retrieval_reference.get("sha256")
        ):
            errors.append(f"{label} reuses payload bytes as its submission receipt")

    missing_providers = set(PROVIDER_NETWORK) - seen_providers
    if missing_providers:
        errors.append(
            "verified DA receipts missing providers: "
            + ", ".join(sorted(missing_providers))
        )

    excluded = report.get("excluded_live_routes")
    if not isinstance(excluded, list) or not all(
        isinstance(item, str) and item.strip() for item in excluded
    ):
        errors.append("excluded_live_routes must contain non-empty route names")
        excluded_set: set[str] = set()
    else:
        excluded_set = set(excluded)
        if len(excluded_set) != len(excluded):
            errors.append("excluded_live_routes contains duplicate routes")
    missing_routes = REQUIRED_EXCLUDED_ROUTES - excluded_set
    if missing_routes:
        errors.append("live route exclusions missing: " + ", ".join(sorted(missing_routes)))
    return errors


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.class_stack: list[str] = []
        self.symbols: set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.symbols.add(".".join([*self.class_stack, node.name]))
        self.generic_visit(node)

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function


def _symbols(path: Path, errors: list[str], label: str) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append(f"cannot inspect {label}: {exc}")
        return set()
    visitor = _SymbolVisitor()
    visitor.visit(tree)
    return visitor.symbols


def _discover_publishers(root: Path, errors: list[str]) -> set[tuple[str, str]]:
    discovered: set[tuple[str, str]] = set()
    for scope in PUBLISHER_SCOPE:
        directory = root / scope
        if not directory.is_dir():
            errors.append(f"publisher inventory scope is missing: {scope}")
            continue
        for path in sorted(directory.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative in {"neuron/da/adapters/base.py"} or path.name == "__init__.py":
                continue
            for symbol in _symbols(path, errors, relative):
                if symbol.rsplit(".", 1)[-1] in PUBLISH_METHODS:
                    discovered.add((relative, symbol))
    return discovered


def _validate_symbol_ref(reference: Any, root: Path, errors: list[str], label: str) -> None:
    if not isinstance(reference, str) or reference.count("::") != 1:
        errors.append(f"{label} must use path.py::Qualified.symbol")
        return
    relative, symbol = reference.split("::", 1)
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".py":
        errors.append(f"{label} contains an invalid source path")
        return
    path = root.joinpath(*pure.parts)
    try:
        path.resolve(strict=True).relative_to(root.resolve())
    except (FileNotFoundError, OSError, ValueError):
        errors.append(f"{label} source file is missing: {relative}")
        return
    if symbol not in _symbols(path, errors, relative):
        errors.append(f"{label} source symbol is missing: {reference}")


def validate_publisher_inventory(path: Path = PUBLISHER_INVENTORY_PATH, root: Path = ROOT) -> list[str]:
    """Require every external DA publisher to be classified and test-covered."""

    if not path.is_file():
        return [f"privacy publisher inventory is missing: {path}"]
    inventory = _load_json(path)
    errors: list[str] = []
    if not _strict_keys(
        inventory,
        {"schema_version", "scope", "publishers"},
        "privacy publisher inventory",
        errors,
    ):
        if not isinstance(inventory, dict):
            return errors
    if inventory.get("schema_version") != "1.0.0":
        errors.append("privacy publisher inventory schema_version must be 1.0.0")
    if inventory.get("scope") != list(PUBLISHER_SCOPE):
        errors.append("privacy publisher inventory scope is incomplete or reordered")
    publishers = inventory.get("publishers")
    if not isinstance(publishers, list):
        return [*errors, "privacy publisher inventory must contain a publishers array"]

    discovered = _discover_publishers(root, errors)
    recorded: set[tuple[str, str]] = set()
    ids: set[str] = set()
    order: list[tuple[str, str]] = []
    for index, publisher in enumerate(publishers):
        label = f"publishers[{index}]"
        if not _strict_keys(publisher, INVENTORY_FIELDS, label, errors):
            if not isinstance(publisher, dict):
                continue
        publisher_id = publisher.get("id")
        if not isinstance(publisher_id, str) or ID_RE.fullmatch(publisher_id) is None:
            errors.append(f"{label}.id is invalid")
        elif publisher_id in ids:
            errors.append(f"privacy publisher inventory contains duplicate id {publisher_id}")
        else:
            ids.add(publisher_id)
        key = (publisher.get("path"), publisher.get("symbol"))
        if not all(isinstance(item, str) and item for item in key):
            errors.append(f"{label} path and symbol are required")
            continue
        if key in recorded:
            errors.append(f"privacy publisher inventory contains duplicate publisher {key}")
        recorded.add(key)
        order.append(key)

        channel = publisher.get("channel")
        if channel not in {"public-da", "encrypted-da", "local-simulation"}:
            errors.append(f"{label}.channel is invalid")
        policy = publisher.get("payload_policy")
        if policy not in {
            "sanitized-public",
            "encrypted-only",
            "transport-only",
            "local-mock-only",
        }:
            errors.append(f"{label}.payload_policy is invalid")
        operational = publisher.get("operational_live_capable")
        release = publisher.get("release_evidence_eligible")
        if operational is not (key in OPERATIONAL_LIVE_PUBLISHERS):
            errors.append(f"{label} operational live capability contradicts source policy")
        if key in RELEASE_INELIGIBLE_PUBLISHERS and release is not False:
            errors.append(f"{label} cannot qualify as release evidence")
        if policy == "local-mock-only" and (operational is not False or release is not False):
            errors.append(f"{label} promotes a local mock publisher")
        if release is not True:
            reason = publisher.get("block_reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{label} requires a release block reason")

        controls = publisher.get("control_refs")
        if not isinstance(controls, list) or not controls or len(set(map(str, controls))) != len(controls):
            errors.append(f"{label}.control_refs must be a non-empty unique list")
        else:
            for control_index, reference in enumerate(controls):
                _validate_symbol_ref(
                    reference,
                    root,
                    errors,
                    f"{label}.control_refs[{control_index}]",
                )
        tests = publisher.get("tests")
        if not isinstance(tests, list) or not tests or len(set(map(str, tests))) != len(tests):
            errors.append(f"{label}.tests must be a non-empty unique list")
        else:
            for test_path in tests:
                if not isinstance(test_path, str) or not test_path.startswith(
                    ("neuron/tests/", "scripts/audit/")
                ):
                    errors.append(f"{label} has an invalid test path: {test_path}")
                    continue
                if not root.joinpath(*PurePosixPath(test_path).parts).is_file():
                    errors.append(f"{label} test file is missing: {test_path}")

    if order != sorted(order):
        errors.append("privacy publisher inventory must be sorted by path and symbol")
    missing = discovered - recorded
    extra = recorded - discovered
    if missing:
        errors.append(
            "privacy publisher inventory is missing: "
            + ", ".join(f"{path}::{symbol}" for path, symbol in sorted(missing))
        )
    if extra:
        errors.append(
            "privacy publisher inventory contains stale entries: "
            + ", ".join(f"{path}::{symbol}" for path, symbol in sorted(extra))
        )
    return errors


def validate_privacy_review(path: Path, commit_sha: str, root: Path = ROOT) -> list[str]:
    """Validate a human approval bound to concrete privacy artifacts."""

    if not path.is_file():
        return [f"privacy review is missing: {path}"]
    review = _load_json(path)
    expected_top = {
        "schema_version",
        "commit_sha",
        "reviewer",
        "reviewer_organization",
        "reviewed_at",
        "data_inventory_approved",
        "retention_policy_approved",
        "redaction_tests_passed",
        "public_content_reviewed",
        "publisher_inventory_complete",
        "blocking_findings_open",
        "evidence_artifacts",
    }
    errors: list[str] = []
    if not _strict_keys(review, expected_top, "privacy review", errors):
        if not isinstance(review, dict):
            return errors
    if review.get("schema_version") != "2.0.0":
        errors.append("privacy review schema_version must be 2.0.0")
    if review.get("commit_sha") != commit_sha:
        errors.append("privacy review commit does not match current commit")
    _parse_utc(review.get("reviewed_at"), "privacy review reviewed_at", errors)
    raw_reviewer = review.get("reviewer")
    raw_organization = review.get("reviewer_organization")
    reviewer = raw_reviewer.strip() if isinstance(raw_reviewer, str) else ""
    organization = raw_organization.strip() if isinstance(raw_organization, str) else ""
    if not reviewer or reviewer.casefold() in GENERIC_REVIEWERS:
        errors.append("privacy review requires a named human reviewer")
    if not organization or organization.casefold() in GENERIC_REVIEWERS:
        errors.append("privacy review requires a reviewer organization")
    for field in (
        "data_inventory_approved",
        "retention_policy_approved",
        "redaction_tests_passed",
        "public_content_reviewed",
        "publisher_inventory_complete",
    ):
        if review.get(field) is not True:
            errors.append(f"privacy review has not approved {field}")
    blocking_findings = review.get("blocking_findings_open")
    if (
        isinstance(blocking_findings, bool)
        or not isinstance(blocking_findings, int)
        or blocking_findings != 0
    ):
        errors.append("privacy review has open blocking findings")

    artifacts = review.get("evidence_artifacts")
    seen_paths: set[str] = set()
    if _strict_keys(artifacts, PRIVACY_ARTIFACTS, "privacy evidence_artifacts", errors):
        for name in sorted(PRIVACY_ARTIFACTS):
            reference = artifacts[name]
            relative = reference.get("path") if isinstance(reference, dict) else None
            if isinstance(relative, str):
                if relative in seen_paths:
                    errors.append(f"privacy evidence reuses artifact path: {relative}")
                seen_paths.add(relative)
            if name == "publisher_inventory":
                if relative != "docs/audit/privacy-publisher-inventory.json":
                    errors.append("privacy review binds the wrong publisher inventory")
                publisher_path = _artifact_file(
                    reference,
                    root=root,
                    allowed_root="docs/audit",
                    label="privacy evidence_artifacts.publisher_inventory",
                    errors=errors,
                )
                if publisher_path is not None:
                    errors.extend(validate_publisher_inventory(publisher_path, root))
            else:
                _artifact_file(
                    reference,
                    root=root,
                    allowed_root="docs/audit/evidence",
                    label=f"privacy evidence_artifacts.{name}",
                    errors=errors,
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=PUBLISHER_INVENTORY_PATH,
        help="Publisher inventory to validate",
    )
    args = parser.parse_args()
    errors = validate_publisher_inventory(args.inventory)
    if errors:
        print("Privacy publisher inventory validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Privacy publisher inventory validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
