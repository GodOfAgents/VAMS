#!/usr/bin/env python3
"""Validate VDSO review provenance and fail-closed evidence semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "docs" / "audit" / "schemas" / "vdso-review-evidence.schema.json"
DEFAULT_EVIDENCE = ROOT / "docs" / "audit" / "evidence" / "vdso-review-evidence.json"
ADR_PATH = ROOT / "docs" / "adr" / "ADR-VDSO-001.md"
PROMPT_PATH = ROOT / "docs" / "team" / "vdso" / "VDSO_REVIEW_PROMPT.md"
REVIEW_PATH = ROOT / "docs" / "team" / "vdso" / "VDSO_PRINCIPLES_REVIEW.md"

PRINCIPLES = {
    "Sovereignty",
    "Privacy",
    "Security",
    "Modularity",
    "Post-Quantum Readiness",
    "Equality",
    "Decentralisation",
    "Safety",
}
MATURITY = [
    "implemented_verified",
    "implemented_unverified",
    "partial",
    "mock",
    "stub",
    "design_only",
    "not_found",
    "contradicted",
]
SEVERITIES = {"Critical", "High", "Medium", "Low", "Informational"}
INVARIANTS = {f"INV-{number}" for number in range(1, 11)}
TOP_LEVEL_KEYS = {
    "schema_version",
    "review_id",
    "status",
    "generated_at",
    "source_provenance",
    "dual_host_policy",
    "principle_definitions",
    "maturity_taxonomy",
    "verdict",
    "findings",
}
FINDING_KEYS = {
    "finding_id",
    "principle",
    "claim",
    "discussion_evidence",
    "repository_evidence",
    "external_primary_sources",
    "design_maturity",
    "current_maturity",
    "design_verdict",
    "current_verdict",
    "severity",
    "affected_invariants",
    "adr_requirements",
    "remediation",
    "verification_gate",
}


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} is missing: {path}")
        return {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is not valid UTF-8 JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return value


def _is_gitignored(relative: str) -> bool:
    """Return True if the relative path matches a .gitignore pattern."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=str(ROOT),
            capture_output=True,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def _repo_path(relative: object, label: str, errors: list[str]) -> Path | None:
    if not isinstance(relative, str) or not relative:
        errors.append(f"{label} path must be a non-empty string")
        return None
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{label} path escapes the repository: {relative}")
        return None
    if not path.is_file():
        if _is_gitignored(relative):
            return None  # gitignored files are intentionally absent
        errors.append(f"{label} path does not exist: {relative}")
        return None
    return path


def _validate_line_reference(
    ref: object,
    label: str,
    errors: list[str],
    *,
    require_classification: bool,
) -> None:
    if not isinstance(ref, dict):
        errors.append(f"{label} must be an object")
        return
    expected = {"path", "line_start", "line_end", "observation"}
    if require_classification:
        expected.add("classification")
    if set(ref) != expected:
        errors.append(f"{label} fields must be exactly {sorted(expected)}")
    path = _repo_path(ref.get("path"), label, errors)
    start = ref.get("line_start")
    end = ref.get("line_end")
    if not isinstance(start, int) or isinstance(start, bool) or start < 1:
        errors.append(f"{label} line_start must be a positive integer")
    if not isinstance(end, int) or isinstance(end, bool) or end < 1:
        errors.append(f"{label} line_end must be a positive integer")
    if isinstance(start, int) and isinstance(end, int) and start > end:
        errors.append(f"{label} line_start exceeds line_end")
    if path and isinstance(end, int):
        line_count = len(path.read_bytes().splitlines())
        if end > line_count:
            errors.append(f"{label} line_end {end} exceeds {line_count} lines")
    if not isinstance(ref.get("observation"), str) or len(ref["observation"].strip()) < 10:
        errors.append(f"{label} observation is too short")
    if require_classification and ref.get("classification") not in MATURITY:
        errors.append(f"{label} has an invalid classification")


def _validate_source(provenance: object, errors: list[str]) -> None:
    required = {
        "baseline_commit",
        "dirty",
        "source_path",
        "source_sha256",
        "source_bytes",
        "source_lines",
        "source_tracked",
    }
    if not isinstance(provenance, dict):
        errors.append("source_provenance must be an object")
        return
    if set(provenance) != required:
        errors.append(f"source_provenance fields must be exactly {sorted(required)}")
    commit = provenance.get("baseline_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("source_provenance baseline_commit must be a lowercase 40-character SHA")
    if provenance.get("source_tracked") is not False:
        errors.append("the reviewed discussion must record source_tracked=false")
    if not isinstance(provenance.get("dirty"), bool):
        errors.append("source_provenance dirty must be Boolean")
    source = _repo_path(provenance.get("source_path"), "source_provenance", errors)
    if not source:
        return
    raw = source.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest().upper()
    if provenance.get("source_sha256") != actual_hash:
        errors.append(
            "discussion SHA-256 mismatch: "
            f"expected {provenance.get('source_sha256')}, got {actual_hash}"
        )
    if provenance.get("source_bytes") != len(raw):
        errors.append(
            f"discussion byte count mismatch: expected {provenance.get('source_bytes')}, got {len(raw)}"
        )
    line_count = len(raw.splitlines())
    if provenance.get("source_lines") != line_count:
        errors.append(
            f"discussion line count mismatch: expected {provenance.get('source_lines')}, got {line_count}"
        )


def _validate_dual_host(policy: object, errors: list[str]) -> None:
    expected = {"polygon_role", "cardano_role", "authority_rule", "cross_host_rule"}
    if not isinstance(policy, dict):
        errors.append("dual_host_policy must be an object")
        return
    if set(policy) != expected:
        errors.append(f"dual_host_policy fields must be exactly {sorted(expected)}")
    if policy.get("authority_rule") != "one_authoritative_writer_per_state_domain":
        errors.append("dual_host_policy must enforce one_authoritative_writer_per_state_domain")
    if "Polygon Amoy" not in str(policy.get("polygon_role", "")):
        errors.append("dual_host_policy must name Polygon Amoy")
    if "Cardano Pre-Prod" not in str(policy.get("cardano_role", "")):
        errors.append("dual_host_policy must name Cardano Pre-Prod")
    cross_host = str(policy.get("cross_host_rule", "")).lower()
    if "never" not in cross_host or "two authoritative histories" not in cross_host:
        errors.append("dual_host_policy must prohibit two authoritative histories")


def _validate_finding(finding: object, index: int, errors: list[str]) -> None:
    label = f"findings[{index}]"
    if not isinstance(finding, dict):
        errors.append(f"{label} must be an object")
        return
    if set(finding) != FINDING_KEYS:
        errors.append(f"{label} fields must be exactly {sorted(FINDING_KEYS)}")
    if not re.fullmatch(r"VDSO-[A-Z]{3}-[0-9]{3}", str(finding.get("finding_id", ""))):
        errors.append(f"{label} has an invalid finding_id")
    if finding.get("principle") not in PRINCIPLES:
        errors.append(f"{label} has an invalid principle")
    for field in ("claim", "remediation", "verification_gate"):
        if not isinstance(finding.get(field), str) or len(finding[field].strip()) < 30:
            errors.append(f"{label}.{field} must contain at least 30 characters")
    for field in ("design_maturity", "current_maturity"):
        if finding.get(field) not in MATURITY:
            errors.append(f"{label}.{field} is not in the controlled maturity taxonomy")
    for field in ("design_verdict", "current_verdict"):
        if finding.get(field) not in {"strong", "adequate", "weak", "gap", "not_applicable"}:
            errors.append(f"{label}.{field} is invalid")
    if finding.get("severity") not in SEVERITIES:
        errors.append(f"{label}.severity is invalid")

    discussion = finding.get("discussion_evidence")
    if not isinstance(discussion, list) or not discussion:
        errors.append(f"{label}.discussion_evidence must be a non-empty array")
    else:
        for ref_index, ref in enumerate(discussion):
            _validate_line_reference(
                ref,
                f"{label}.discussion_evidence[{ref_index}]",
                errors,
                require_classification=True,
            )
            if isinstance(ref, dict) and ref.get("path") != "docs/team/VAMS-Discussions_001.txt":
                errors.append(f"{label} discussion evidence must cite the frozen source")

    repository = finding.get("repository_evidence")
    if not isinstance(repository, list) or not repository:
        errors.append(f"{label}.repository_evidence must be a non-empty array")
    else:
        for ref_index, ref in enumerate(repository):
            _validate_line_reference(
                ref,
                f"{label}.repository_evidence[{ref_index}]",
                errors,
                require_classification=True,
            )

    sources = finding.get("external_primary_sources")
    if not isinstance(sources, list):
        errors.append(f"{label}.external_primary_sources must be an array")
    else:
        for source_index, source in enumerate(sources):
            source_label = f"{label}.external_primary_sources[{source_index}]"
            if not isinstance(source, dict) or set(source) != {"title", "url", "supports"}:
                errors.append(f"{source_label} has invalid fields")
                continue
            if not str(source.get("url", "")).startswith("https://"):
                errors.append(f"{source_label} must use HTTPS")

    invariants = finding.get("affected_invariants")
    if not isinstance(invariants, list) or len(invariants) != len(set(invariants)):
        errors.append(f"{label}.affected_invariants must be a unique array")
    elif not set(invariants).issubset(INVARIANTS):
        errors.append(f"{label}.affected_invariants contains an unknown invariant")

    requirements = finding.get("adr_requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append(f"{label}.adr_requirements must be a non-empty array")
    elif len(requirements) != len(set(requirements)):
        errors.append(f"{label}.adr_requirements must be unique")
    elif any(not re.fullmatch(r"VDSO-[A-Z]+-[0-9]{3}", str(item)) for item in requirements):
        errors.append(f"{label}.adr_requirements contains an invalid ID")


def _validate_normative_documents(data: dict[str, Any], errors: list[str]) -> None:
    artifacts = [ADR_PATH, PROMPT_PATH, REVIEW_PATH]
    for path in artifacts:
        if not path.is_file():
            errors.append(f"required VDSO document is missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if "file:///" in text.lower():
            errors.append(f"{path.relative_to(ROOT)} contains a local file URI")

    if not ADR_PATH.is_file():
        return
    adr = ADR_PATH.read_text(encoding="utf-8")
    normalized_adr = " ".join(adr.split()).lower()
    required_phrases = [
        "**Status:** Proposed",
        "one authoritative writer per state domain",
        "Polygon Amoy",
        "Cardano Pre-Prod",
        "not** post-quantum confidentiality",
        "both secp256k1 and ML-DSA-65",
        "Expiry only enters `RECOVERY_PENDING`; it never unlocks value",
    ]
    for phrase in required_phrases:
        if " ".join(phrase.split()).lower() not in normalized_adr:
            errors.append(f"ADR-VDSO-001 is missing required policy text: {phrase}")
    for invariant in sorted(INVARIANTS, key=lambda item: int(item.split("-")[1])):
        if invariant not in adr:
            errors.append(f"ADR-VDSO-001 does not address {invariant}")
    for finding in data.get("findings", []):
        if isinstance(finding, dict):
            for requirement in finding.get("adr_requirements", []):
                if requirement not in adr:
                    errors.append(f"ADR-VDSO-001 does not define {requirement}")


def validate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    evidence_path: Path = DEFAULT_EVIDENCE,
) -> list[str]:
    errors: list[str] = []
    schema = _load_json(schema_path, "VDSO evidence schema", errors)
    data = _load_json(evidence_path, "VDSO evidence manifest", errors)
    if not schema or not data:
        return errors

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("VDSO evidence schema must use JSON Schema draft 2020-12")
    if schema.get("title") != "VDSO Principles Review Evidence":
        errors.append("VDSO evidence schema title is unexpected")
    if set(data) != TOP_LEVEL_KEYS:
        errors.append(f"manifest fields must be exactly {sorted(TOP_LEVEL_KEYS)}")
    if data.get("schema_version") != "1.0.0":
        errors.append("manifest schema_version must be 1.0.0")
    if data.get("review_id") != "VDSO-PRINCIPLES-001":
        errors.append("manifest review_id must be VDSO-PRINCIPLES-001")
    if data.get("status") != "proposed":
        errors.append("VDSO review status must remain proposed")
    try:
        datetime.fromisoformat(str(data.get("generated_at")))
    except ValueError:
        errors.append("generated_at must be an ISO-8601 timestamp")

    _validate_source(data.get("source_provenance"), errors)
    _validate_dual_host(data.get("dual_host_policy"), errors)

    definitions = data.get("principle_definitions")
    if not isinstance(definitions, dict) or set(definitions) != PRINCIPLES:
        errors.append("principle_definitions must define each principle exactly once")
    elif any(not isinstance(value, str) or len(value.strip()) < 20 for value in definitions.values()):
        errors.append("every principle definition must contain at least 20 characters")
    if data.get("maturity_taxonomy") != MATURITY:
        errors.append("maturity_taxonomy does not match the controlled order")

    verdict = data.get("verdict")
    expected_verdict_keys = {
        "improvement_over_current_head",
        "adoption_readiness",
        "deployment_readiness",
        "summary",
    }
    if not isinstance(verdict, dict) or set(verdict) != expected_verdict_keys:
        errors.append("verdict has invalid fields")
    else:
        if verdict.get("improvement_over_current_head") != "conditional_yes":
            errors.append("improvement verdict must remain conditional_yes at proposed maturity")
        if verdict.get("adoption_readiness") != "no":
            errors.append("adoption_readiness must remain no for this reviewed discussion")
        if verdict.get("deployment_readiness") != "no":
            errors.append("deployment_readiness must remain no at proposed maturity")

    findings = data.get("findings")
    if not isinstance(findings, list) or len(findings) != 8:
        errors.append("findings must contain exactly eight records")
    else:
        for index, finding in enumerate(findings):
            _validate_finding(finding, index, errors)
        finding_principles = [
            finding.get("principle") for finding in findings if isinstance(finding, dict)
        ]
        if set(finding_principles) != PRINCIPLES or len(finding_principles) != len(set(finding_principles)):
            errors.append("findings must cover each principle exactly once")
        finding_ids = [finding.get("finding_id") for finding in findings if isinstance(finding, dict)]
        if len(finding_ids) != len(set(finding_ids)):
            errors.append("finding_id values must be unique")

    _validate_normative_documents(data, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    errors = validate(schema_path=args.schema, evidence_path=args.evidence)
    if args.json:
        print(json.dumps({"status": "success" if not errors else "failure", "errors": errors}))
    elif errors:
        print("VDSO evidence validation failed:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("VDSO evidence validation passed.")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
