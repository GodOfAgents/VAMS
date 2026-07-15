#!/usr/bin/env python3
"""Apply public Cardano parameters and emit deployable Pre-Prod artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.deployment.cardano_preprod_artifacts import (
        AUXILIARY_POLICY_TEMPLATES,
        COMMIT_RE,
        DEPLOYABLE_VALIDATORS,
        HASH_RE,
        HEX_RE,
        require_exact_repository_state,
    )
except ModuleNotFoundError:
    from cardano_preprod_artifacts import (  # type: ignore[no-redef]
        AUXILIARY_POLICY_TEMPLATES,
        COMMIT_RE,
        DEPLOYABLE_VALIDATORS,
        HASH_RE,
        HEX_RE,
        require_exact_repository_state,
    )


PARAMETER_SCHEMA_VERSION = "1.0.0"
ARTIFACT_SCHEMA_VERSION = "3.0.0"
INSTANCE_ID_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
AUXILIARY_FILENAMES = {
    "agent_nft.agent_nft.mint": "agent-nft-policy.plutus",
    "proposal_nft.proposal_nft.mint": "proposal-nft-policy.plutus",
    "fund_nft.fund_nft.mint": "fund-nft-policy.plutus",
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _blueprint_entries(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validators = blueprint.get("validators")
    if not isinstance(validators, list):
        raise ValueError("Aiken blueprint must contain a validators array")
    entries: dict[str, dict[str, Any]] = {}
    for entry in validators:
        if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
            raise ValueError("Aiken blueprint contains a malformed validator")
        title = entry["title"]
        if title in entries:
            raise ValueError(f"Aiken blueprint contains duplicate validator title: {title}")
        if "vdso" in title.casefold():
            raise ValueError("VDSO is conformance-only and cannot be applied")
        entries[title] = entry
    return entries


def _validate_parameter_values(
    title: str, values: Any, entry: dict[str, Any]
) -> list[str]:
    # Aiken omits the `parameters` field for an already closed validator.
    # Normalize that representation to an empty list, while still rejecting
    # malformed non-list values when the field is present.
    expected_parameters = entry.get("parameters", [])
    if not isinstance(expected_parameters, list):
        raise ValueError(f"{title} blueprint parameters must be an array")
    if not isinstance(values, list) or len(values) != len(expected_parameters):
        raise ValueError(f"{title} requires exactly {len(expected_parameters)} CBOR parameters")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ValueError(f"{title} parameter {index} must be CBOR hexadecimal")
        lowered = value.casefold()
        if not lowered or HEX_RE.fullmatch(lowered) is None:
            raise ValueError(f"{title} parameter {index} must be nonempty even-length CBOR hex")
        normalized.append(lowered)
    return normalized


def validate_parameter_manifest(
    parameter_path: Path,
    blueprint: dict[str, Any],
    commit_sha: str,
) -> dict[str, Any]:
    try:
        manifest = json.loads(parameter_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"parameter manifest is not valid JSON: {exc}") from exc
    required = {
        "schema_version",
        "commit_sha",
        "network",
        "persistent_parameters_cbor",
        "auxiliary_policy_instances",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("parameter manifest fields are incomplete or unexpected")
    if manifest.get("schema_version") != PARAMETER_SCHEMA_VERSION:
        raise ValueError("parameter manifest schema_version must equal 1.0.0")
    if manifest.get("network") != "cardano-preprod":
        raise ValueError("parameter manifest network must equal cardano-preprod")
    if COMMIT_RE.fullmatch(commit_sha) is None or manifest.get("commit_sha") != commit_sha:
        raise ValueError("parameter manifest does not match the target commit")

    entries = _blueprint_entries(blueprint)
    all_titles = set(DEPLOYABLE_VALIDATORS) | set(AUXILIARY_POLICY_TEMPLATES)
    missing = all_titles - set(entries)
    if missing:
        raise ValueError("blueprint is missing scripts: " + ", ".join(sorted(missing)))

    persistent_raw = manifest.get("persistent_parameters_cbor")
    if not isinstance(persistent_raw, dict) or set(persistent_raw) != set(
        DEPLOYABLE_VALIDATORS
    ):
        raise ValueError("parameter manifest must contain exactly four persistent validators")
    persistent = {
        title: _validate_parameter_values(title, persistent_raw[title], entries[title])
        for title in sorted(DEPLOYABLE_VALIDATORS)
    }

    instances_raw = manifest.get("auxiliary_policy_instances")
    if not isinstance(instances_raw, list):
        raise ValueError("auxiliary_policy_instances must be an array")
    instances: list[dict[str, Any]] = []
    instance_ids: set[str] = set()
    fund_instances = 0
    for index, item in enumerate(instances_raw):
        if not isinstance(item, dict) or set(item) != {
            "instance_id",
            "title",
            "parameters_cbor",
        }:
            raise ValueError(f"auxiliary_policy_instances[{index}] is malformed")
        instance_id = item.get("instance_id")
        title = item.get("title")
        if not isinstance(instance_id, str) or INSTANCE_ID_RE.fullmatch(instance_id) is None:
            raise ValueError(f"auxiliary_policy_instances[{index}].instance_id is invalid")
        if instance_id in instance_ids:
            raise ValueError("auxiliary policy instance IDs must be unique")
        instance_ids.add(instance_id)
        if title not in AUXILIARY_POLICY_TEMPLATES:
            raise ValueError(f"auxiliary_policy_instances[{index}].title is invalid")
        if title == "fund_nft.fund_nft.mint":
            fund_instances += 1
        instances.append(
            {
                "instance_id": instance_id,
                "title": title,
                "parameters_cbor": _validate_parameter_values(
                    title, item.get("parameters_cbor"), entries[title]
                ),
            }
        )
    if fund_instances != 1:
        raise ValueError("exactly one canonical fund bootstrap policy instance is required")
    return {
        "schema_version": PARAMETER_SCHEMA_VERSION,
        "commit_sha": commit_sha,
        "network": "cardano-preprod",
        "persistent_parameters_cbor": persistent,
        "auxiliary_policy_instances": instances,
    }


def _apply_title(
    blueprint_path: Path,
    title: str,
    parameters: list[str],
    aiken_executable: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vams-cardano-apply-") as temp:
        directory = Path(temp)
        current = directory / "blueprint-000.json"
        current.write_bytes(blueprint_path.read_bytes())
        module, validator, _handler = title.split(".", 2)
        for step, parameter in enumerate(parameters, start=1):
            output = directory / f"blueprint-{step:03d}.json"
            subprocess.run(
                [
                    aiken_executable,
                    "blueprint",
                    "apply",
                    "--in",
                    str(current),
                    "--out",
                    str(output),
                    "--module",
                    module,
                    "--validator",
                    validator,
                    parameter,
                ],
                cwd=directory,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if not output.is_file() or output.stat().st_size == 0:
                raise ValueError(f"Aiken did not emit an applied blueprint for {title}")
            current = output
        applied = json.loads(current.read_text(encoding="utf-8"))
        entry = _blueprint_entries(applied).get(title)
        if entry is None:
            raise ValueError(f"applied blueprint is missing {title}")
        if entry.get("parameters") not in (None, []):
            raise ValueError(f"{title} still has unapplied parameters")
        return entry


def _emit_script(
    output_dir: Path,
    filename: str,
    title: str,
    source: str,
    kind: str,
    parameter_count: int,
    entry: dict[str, Any],
) -> dict[str, Any]:
    compiled_code = entry.get("compiledCode")
    script_hash = entry.get("hash")
    if not isinstance(compiled_code, str) or HEX_RE.fullmatch(compiled_code) is None:
        raise ValueError(f"{title} applied compiledCode is invalid")
    if not isinstance(script_hash, str) or HASH_RE.fullmatch(script_hash) is None:
        raise ValueError(f"{title} applied script hash is invalid")
    envelope = {
        "cborHex": compiled_code,
        "description": f"VAMS Cardano Pre-Prod {kind} {title}",
        "type": "PlutusScriptV3",
    }
    artifact_bytes = _json_bytes(envelope)
    (output_dir / filename).write_bytes(artifact_bytes)
    return {
        "applied": True,
        "artifact_path": filename,
        "artifact_sha256": _sha256(artifact_bytes),
        "compiled_code_sha256": _sha256(bytes.fromhex(compiled_code)),
        "parameter_count": parameter_count,
        "script_cbor_path": filename,
        "script_cbor_sha256": _sha256(artifact_bytes),
        "script_hash": script_hash,
        "source": source,
        "title": title,
    }


def apply_and_extract(
    blueprint_path: Path,
    parameter_path: Path,
    output_dir: Path,
    commit_sha: str,
    aiken_executable: str = "aiken",
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("applied artifact output directory must be empty")
    blueprint_bytes = blueprint_path.read_bytes()
    blueprint = json.loads(blueprint_bytes)
    parameters = validate_parameter_manifest(parameter_path, blueprint, commit_sha)
    base_entries = _blueprint_entries(blueprint)
    output_dir.mkdir(parents=True, exist_ok=True)

    parameter_bytes = _json_bytes(parameters)
    (output_dir / "cardano-preprod-parameters.json").write_bytes(parameter_bytes)
    persistent: list[dict[str, Any]] = []
    for title in sorted(DEPLOYABLE_VALIDATORS):
        values = parameters["persistent_parameters_cbor"][title]
        entry = _apply_title(blueprint_path, title, values, aiken_executable)
        filename, source = DEPLOYABLE_VALIDATORS[title]
        persistent.append(
            _emit_script(
                output_dir,
                filename,
                title,
                source,
                "persistent-validator",
                len(values),
                entry,
            )
        )

    auxiliary_instances: list[dict[str, Any]] = []
    for instance in parameters["auxiliary_policy_instances"]:
        title = instance["title"]
        values = instance["parameters_cbor"]
        entry = _apply_title(blueprint_path, title, values, aiken_executable)
        filename = f"{instance['instance_id']}-{AUXILIARY_FILENAMES[title]}"
        record = _emit_script(
            output_dir,
            filename,
            title,
            AUXILIARY_POLICY_TEMPLATES[title],
            "auxiliary-one-shot-policy",
            len(values),
            entry,
        )
        record["instance_id"] = instance["instance_id"]
        record["parameter_manifest_path"] = "cardano-preprod-parameters.json"
        record["parameter_manifest_sha256"] = _sha256(parameter_bytes)
        record["verification"] = "simulation-passed"
        observation = {
            "schema_version": "1.0.0",
            "kind": "cardano-auxiliary-policy-instance",
            "commit_sha": commit_sha,
            "network": "cardano-preprod",
            "name": title.split(".", 1)[0] + ".ak",
            "title": title,
            **{
                field: record[field]
                for field in (
                    "instance_id",
                    "script_hash",
                    "script_cbor_path",
                    "script_cbor_sha256",
                    "parameter_manifest_path",
                    "parameter_manifest_sha256",
                    "verification",
                )
            },
        }
        observation_bytes = _json_bytes(observation)
        observation_path = f"{instance['instance_id']}-observation.json"
        (output_dir / observation_path).write_bytes(observation_bytes)
        record["observation_evidence_path"] = observation_path
        record["observation_evidence_sha256"] = _sha256(observation_bytes)
        auxiliary_instances.append(record)

    auxiliary_templates: list[dict[str, Any]] = []
    for title in sorted(AUXILIARY_POLICY_TEMPLATES):
        entry = base_entries[title]
        compiled_code = entry.get("compiledCode")
        script_hash = entry.get("hash")
        blueprint_parameters = entry.get("parameters")
        if not isinstance(compiled_code, str) or HEX_RE.fullmatch(compiled_code) is None:
            raise ValueError(f"{title} compiled template is invalid")
        if not isinstance(script_hash, str) or HASH_RE.fullmatch(script_hash) is None:
            raise ValueError(f"{title} template hash is invalid")
        if not isinstance(blueprint_parameters, list) or not blueprint_parameters:
            raise ValueError(f"{title} must remain a parameterized auxiliary template")
        template = {
            "compiledCode": compiled_code,
            "deployable": False,
            "parameters": blueprint_parameters,
            "templateHash": script_hash,
            "title": title,
        }
        template_bytes = _json_bytes(template)
        template_filename = title.split(".", 1)[0].replace("_", "-") + ".template.json"
        (output_dir / template_filename).write_bytes(template_bytes)
        auxiliary_templates.append(
            {
                "blueprint_entry_sha256": _sha256(_json_bytes(entry)),
                "compiled_template_sha256": _sha256(bytes.fromhex(compiled_code)),
                "parameter_count": len(blueprint_parameters),
                "source": AUXILIARY_POLICY_TEMPLATES[title],
                "template_artifact_path": template_filename,
                "template_artifact_sha256": _sha256(template_bytes),
                "template_script_hash": script_hash,
                "title": title,
            }
        )

    manifest = {
        "artifacts_applied": True,
        "auxiliary_policy_instances": auxiliary_instances,
        "auxiliary_policy_templates": auxiliary_templates,
        "blueprint_sha256": _sha256(blueprint_bytes),
        "commit_sha": commit_sha,
        "network": "cardano-preprod",
        "parameter_manifest_sha256": _sha256(parameter_bytes),
        "persistent_validator_count": len(persistent),
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "validators": persistent,
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
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--aiken", default="aiken")
    args = parser.parse_args()
    try:
        require_exact_repository_state(args.blueprint, args.commit_sha)
        manifest = apply_and_extract(
            args.blueprint,
            args.parameters,
            args.output_dir,
            args.commit_sha,
            args.aiken,
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        parser.error(str(exc))
    print(
        f"Emitted {manifest['persistent_validator_count']} applied persistent "
        f"validators and {len(manifest['auxiliary_policy_instances'])} applied "
        f"auxiliary policy instances in {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
