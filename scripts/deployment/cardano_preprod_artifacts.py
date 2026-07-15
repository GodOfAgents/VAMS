#!/usr/bin/env python3
"""Extract four persistent validators and bind auxiliary policy templates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


COMMIT_RE = re.compile(r"[0-9a-f]{40}")
HASH_RE = re.compile(r"[0-9a-f]{56}")
HEX_RE = re.compile(r"(?:[0-9a-f]{2})+")
DEPLOYABLE_VALIDATORS = {
    "agent_registry.agent_registry.spend": (
        "agent-registry.plutus",
        "cardano/validators/agent_registry.ak",
    ),
    "governor.governor.spend": (
        "governor.plutus",
        "cardano/validators/governor.ak",
    ),
    "insurance_fund.insurance_fund.spend": (
        "insurance-fund.plutus",
        "cardano/validators/insurance_fund.ak",
    ),
    "timelock.timelock.spend": (
        "timelock.plutus",
        "cardano/validators/timelock.ak",
    ),
}
AUXILIARY_POLICY_TEMPLATES = {
    "agent_nft.agent_nft.mint": "cardano/validators/agent_nft.ak",
    "proposal_nft.proposal_nft.mint": "cardano/validators/proposal_nft.ak",
    "fund_nft.fund_nft.mint": "cardano/validators/fund_nft.ak",
}
ROOT = Path(__file__).resolve().parents[2]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def require_exact_repository_state(blueprint_path: Path, commit_sha: str) -> None:
    expected_blueprint = (ROOT / "cardano" / "plutus.json").resolve(strict=True)
    if blueprint_path.resolve(strict=True) != expected_blueprint:
        raise ValueError("blueprint must be the repository cardano/plutus.json")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if head != commit_sha:
        raise ValueError("commit SHA does not match repository HEAD")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", "cardano"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if status:
        raise ValueError("Cardano sources or blueprint are dirty; commit before extraction")


def extract(blueprint_path: Path, output_dir: Path, commit_sha: str) -> dict[str, Any]:
    """Extract deterministic, explicitly non-deployable blueprint templates."""
    if COMMIT_RE.fullmatch(commit_sha) is None:
        raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
    blueprint_bytes = blueprint_path.read_bytes()
    blueprint = json.loads(blueprint_bytes)
    validators = blueprint.get("validators")
    if not isinstance(validators, list):
        raise ValueError("Aiken blueprint must contain a validators array")

    by_title: dict[str, dict[str, Any]] = {}
    for validator in validators:
        if not isinstance(validator, dict) or not isinstance(validator.get("title"), str):
            raise ValueError("Aiken blueprint contains a malformed validator")
        title = validator["title"]
        if title in by_title:
            raise ValueError(f"Aiken blueprint contains duplicate validator title: {title}")
        by_title[title] = validator
        if "vdso" in title.casefold():
            raise ValueError("VDSO is conformance-only and must not enter the blueprint")

    missing = set(DEPLOYABLE_VALIDATORS) - set(by_title)
    if missing:
        raise ValueError("missing authoritative validators: " + ", ".join(sorted(missing)))
    missing_auxiliary = set(AUXILIARY_POLICY_TEMPLATES) - set(by_title)
    if missing_auxiliary:
        raise ValueError(
            "missing auxiliary policy templates: "
            + ", ".join(sorted(missing_auxiliary))
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for title, (filename, source) in DEPLOYABLE_VALIDATORS.items():
        validator = by_title[title]
        compiled_code = validator.get("compiledCode")
        script_hash = validator.get("hash")
        parameters = validator.get("parameters", [])
        if not isinstance(compiled_code, str) or HEX_RE.fullmatch(compiled_code) is None:
            raise ValueError(f"{title} compiledCode must be nonempty lowercase hexadecimal")
        if not isinstance(script_hash, str) or HASH_RE.fullmatch(script_hash) is None:
            raise ValueError(f"{title} script hash must be 56 lowercase hexadecimal characters")
        if not isinstance(parameters, list):
            raise ValueError(f"{title} parameters must be an array")
        template = {
            "compiledCode": compiled_code,
            "deployable": False,
            "parameters": parameters,
            "templateHash": script_hash,
            "title": title,
        }
        artifact_bytes = _json_bytes(template)
        artifact_path = output_dir / filename.replace(".plutus", ".template.json")
        artifact_path.write_bytes(artifact_bytes)
        records.append(
            {
                "applied": False,
                "artifact_path": artifact_path.name,
                "artifact_sha256": _sha256(artifact_bytes),
                "compiled_template_sha256": _sha256(bytes.fromhex(compiled_code)),
                "parameter_count": len(parameters),
                "source": source,
                "template_script_hash": script_hash,
                "title": title,
            }
        )

    auxiliary_records: list[dict[str, Any]] = []
    for title, source in AUXILIARY_POLICY_TEMPLATES.items():
        validator = by_title[title]
        compiled_code = validator.get("compiledCode")
        script_hash = validator.get("hash")
        parameters = validator.get("parameters")
        if not isinstance(compiled_code, str) or HEX_RE.fullmatch(compiled_code) is None:
            raise ValueError(f"{title} compiledCode must be nonempty lowercase hexadecimal")
        if not isinstance(script_hash, str) or HASH_RE.fullmatch(script_hash) is None:
            raise ValueError(f"{title} script hash must be 56 lowercase hexadecimal characters")
        if not isinstance(parameters, list) or not parameters:
            raise ValueError(f"{title} must remain an unapplied parameterized template")
        template = {
            "compiledCode": compiled_code,
            "deployable": False,
            "parameters": parameters,
            "templateHash": script_hash,
            "title": title,
        }
        template_bytes = _json_bytes(template)
        template_filename = title.split(".", 1)[0].replace("_", "-") + ".template.json"
        (output_dir / template_filename).write_bytes(template_bytes)
        auxiliary_records.append(
            {
                "blueprint_entry_sha256": _sha256(_json_bytes(validator)),
                "compiled_template_sha256": _sha256(bytes.fromhex(compiled_code)),
                "parameter_count": len(parameters),
                "source": source,
                "template_artifact_path": template_filename,
                "template_artifact_sha256": _sha256(template_bytes),
                "template_script_hash": script_hash,
                "title": title,
            }
        )

    manifest = {
        "artifacts_applied": False,
        "auxiliary_policy_templates": auxiliary_records,
        "blueprint_sha256": _sha256(blueprint_bytes),
        "commit_sha": commit_sha,
        "network": "cardano-preprod",
        "persistent_validator_count": 4,
        "schema_version": "2.1.0",
        "validators": records,
        "vdso": {
            "deployable": False,
            "module": "cardano/lib/vams/vdso.ak",
            "status": "conformance-only",
        },
    }
    (output_dir / "cardano-preprod-artifacts.json").write_bytes(_json_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint", type=Path, default=Path("cardano/plutus.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    args = parser.parse_args()
    try:
        require_exact_repository_state(args.blueprint, args.commit_sha)
        manifest = extract(args.blueprint, args.output_dir, args.commit_sha)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    print(
        "Bound "
        f"{len(manifest['validators'])} non-deployable persistent validator templates and "
        f"bound {len(manifest['auxiliary_policy_templates'])} auxiliary policy "
        f"templates in {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
