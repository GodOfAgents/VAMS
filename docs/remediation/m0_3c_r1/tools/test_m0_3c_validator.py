"""M0.3c-R3 closed-schema validator regressions."""
from __future__ import annotations

import copy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
TOOLS = Path(__file__).resolve().parent
EVIDENCE = Path(
    "/home/GodOfAgents/vams-evidence/m0-20260909/"
    "m0-3c-r1-20260917T140325Z-829ab544571f"
)
PREFIX = Path(
    "/home/GodOfAgents/vams-evidence/m0-20260909/"
    "m0-3c-r1-20260917T140325Z-829ab544571f/"
    "verification/m0_3c_validate.py"
)
PYTHON = Path("/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python")

SPEC = importlib.util.spec_from_file_location("m03c_validate", TOOLS / "m0_3c_validate.py")
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rebuild_manifest(root):
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{digest(path)}  {path.relative_to(root).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def rebuild_checksums(root):
    core = sorted(V.schema.CORE)
    (root / "source-checksums.sha256").write_text(
        "".join(f"{digest(root / name)}  {name}\n" for name in core),
        encoding="utf-8",
    )
    rebuild_manifest(root)


def checksum_layers_pass(root):
    inner = {}
    for line in (root / "source-checksums.sha256").read_text().splitlines():
        value, name = line.split("  ")
        if name in inner or digest(root / name) != value:
            return False
        inner[name] = value
    if set(inner) != V.schema.CORE:
        return False
    outer = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        value, name = line.split("  ")
        if name in outer or digest(root / name) != value:
            return False
        outer[name] = value
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    return set(outer) == actual


class M03CValidatorTests(unittest.TestCase):
    def copy_evidence(self):
        temporary = tempfile.TemporaryDirectory(prefix="m03c-r3-validator-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "evidence"
        shutil.copytree(EVIDENCE, root)
        environment = json.loads((root / "environment.json").read_text())
        environment["evidence_output"] = str(root)
        (root / "environment.json").write_bytes(encoded(environment))
        rebuild_checksums(root)
        return root

    def write_json(self, root, name, value):
        (root / name).write_bytes(encoded(value))
        rebuild_checksums(root)

    def run_validator(self, validator, root, repo=ROOT):
        return subprocess.run(
            [
                str(PYTHON), str(validator), "--repo", str(repo),
                "--evidence", str(root),
            ],
            cwd=ROOT,
            env=os.environ | {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(ROOT / "scripts/security"),
            },
            capture_output=True,
            text=True,
        )

    def assert_rejected(self, mutate, expected_code=None):
        root = self.copy_evidence()
        mutate(root)
        rebuild_checksums(root)
        self.assertTrue(checksum_layers_pass(root))
        with self.assertRaises(Exception) as raised:
            V.validate(ROOT, root)
        direct_code = str(raised.exception)
        if expected_code is not None:
            self.assertEqual(direct_code, expected_code)
        process = self.run_validator(TOOLS / "m0_3c_validate.py", root)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["schema"], "m0_3c_r5_validation")
        self.assertEqual(result["code"], direct_code)
        self.assertEqual(set(result), {"schema", "status", "type", "code"})
        self.assertEqual(process.stderr, "")

    def test_current_evidence_and_raw_removed_validate(self):
        result = V.validate(ROOT, EVIDENCE)
        self.assertEqual(result["status"], "pass")
        record = json.loads((EVIDENCE / "record.json").read_text())
        self.assertIs(record["raw_removed"], True)

    def test_exact_three_r2_bypasses_are_reproduced_then_rejected(self):
        cases = [
            ("api_secret_material", "removed"),
            ("raw_match_excerpt", "removed"),
            ("review_notes", "A" * 512),
        ]
        for key, value in cases:
            with self.subTest(case=key):
                root = self.copy_evidence()
                record = json.loads((root / "record.json").read_text())
                record["independent_probe"] = {key: value}
                self.write_json(root, "record.json", record)
                legacy_repo = root.parent / "legacy-repo"
                legacy_decisions = legacy_repo / "docs/remediation/m0_3c_r1/decisions.json"
                legacy_decisions.parent.mkdir(parents=True)
                shutil.copy2(root / "decisions.json", legacy_decisions)
                before = self.run_validator(PREFIX, root, legacy_repo)
                after = self.run_validator(TOOLS / "m0_3c_validate.py", root)
                self.assertEqual(before.returncode, 0, before.stdout + before.stderr)
                self.assertEqual(after.returncode, 1, after.stdout + after.stderr)

    def test_composite_sensitive_names_reject_at_depth(self):
        names = [
            "apiSecretMaterial", "api_secret_material",
            "api-secret-material", "api secret material",
            "rawMatchExcerpt", "raw_match_excerpt",
        ]
        for name in names:
            with self.subTest(name=name):
                def mutate(root, field=name):
                    record = json.loads((root / "record.json").read_text())
                    record["independent_probe"] = {
                        "level_one": [{"level_two": {field: "removed"}}]
                    }
                    (root / "record.json").write_bytes(encoded(record))
                self.assert_rejected(mutate)

    def test_unknown_nested_keys_reject(self):
        def mutate(root):
            commands = json.loads((root / "commands.json").read_text())
            commands[0]["result"]["unrecognized_metadata"] = "removed"
            (root / "commands.json").write_bytes(encoded(commands))
        self.assert_rejected(mutate)

    def test_overlong_metadata_and_oversized_collection_reject(self):
        def long_value(root):
            commands = json.loads((root / "commands.json").read_text())
            for item in commands:
                if item["name"] == "negative-fixture-regression":
                    item["result"] = "A" * 512
            (root / "commands.json").write_bytes(encoded(commands))
        self.assert_rejected(long_value)

        def large_collection(root):
            environment = json.loads((root / "environment.json").read_text())
            environment["dirty_status"] = ["safe"] * 2049
            (root / "environment.json").write_bytes(encoded(environment))
        self.assert_rejected(large_collection)

    def test_excessive_depth_rejects(self):
        def mutate(root):
            value = {"leaf": "removed"}
            for index in range(12):
                value = {f"level_{index}": value}
            record = json.loads((root / "record.json").read_text())
            record["independent_probe"] = value
            (root / "record.json").write_bytes(encoded(record))
        self.assert_rejected(mutate)

    def test_duplicate_json_keys_reject(self):
        root = self.copy_evidence()
        record_path = root / "record.json"
        original = record_path.read_text()
        record_path.write_text(
            original.replace(
                "{\n",
                '{\n  "schema": "m0_3c_r1_run",\n',
                1,
            )
        )
        rebuild_checksums(root)
        process = self.run_validator(TOOLS / "m0_3c_validate.py", root)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(json.loads(process.stdout)["status"], "failure")

    def test_malformed_identity_fields_and_scalar_types_reject(self):
        mutations = {
            "path": ("relative_path", "../escape"),
            "hash": ("file_sha256", "0" * 63),
            "enum": ("disposition", "approved"),
            "line_range": ("line_start", 0),
            "scalar_type": ("line_end", "1"),
        }
        for name, (field, value) in mutations.items():
            with self.subTest(name=name):
                def mutate(root, key=field, replacement=value):
                    decisions = json.loads((root / "decisions.json").read_text())
                    decisions["records"][0][key] = replacement
                    (root / "decisions.json").write_bytes(encoded(decisions))
                self.assert_rejected(mutate)

    def test_all_eight_r4_schema_bypasses_reject_after_valid_checksums(self):
        cases = {
            "bool_as_integer_raw_removed": (
                "record.json", lambda value: value.__setitem__("raw_removed", 1),
                "schema.raw_removed",
            ),
            "bool_as_integer_scanner_exit": (
                "record.json", lambda value: value.__setitem__("scanner_exit", True),
                "schema.scanner_exit",
            ),
            "bool_as_integer_disposition_total": (
                "summary.json",
                lambda value: value["disposition_totals"].__setitem__(
                    "potential_credential", False
                ),
                "schema.summary_totals.potential_credential",
            ),
            "null_unvalidated_record_field": (
                "record.json",
                lambda value: value.__setitem__("promotion_gates", None),
                "schema.run_metadata",
            ),
            "unexpected_scalar_environment_branch": (
                "environment.json", lambda value: value.__setitem__("branch", 1),
                "schema.branch",
            ),
            "sensitive_dynamic_reviewed_files_key": (
                "reviewed-hashes.json",
                lambda value: value["files"].__setitem__(
                    "apiSecretMaterial", "0" * 64
                ),
                "schema.sensitive_key",
            ),
            "sensitive_dynamic_pinned_binary_key": (
                "reviewed-hashes.json",
                lambda value: value["pinned_binaries"].__setitem__(
                    "credential material", "0" * 64
                ),
                "schema.sensitive_key",
            ),
            "changed_files_wrong_exact_set": (
                "changed-files.json",
                lambda value: value["paths"].__setitem__(
                    0, "safe/replacement.txt"
                ),
                "schema.changed_files",
            ),
        }
        for name, (artifact, mutate_value, code) in cases.items():
            with self.subTest(name=name):
                def mutate(root, file_name=artifact, operation=mutate_value):
                    path = root / file_name
                    value = json.loads(path.read_text())
                    operation(value)
                    path.write_bytes(encoded(value))
                self.assert_rejected(mutate, code)

    def test_checksum_corruption_fails_at_checksum_stage(self):
        inner = self.copy_evidence()
        (inner / "source-checksums.sha256").write_text(
            "0" * 64 + "  decisions.json\n", encoding="utf-8"
        )
        rebuild_manifest(inner)
        with self.assertRaises(Exception) as raised:
            V.validate(ROOT, inner)
        self.assertEqual(str(raised.exception), "checksum.inner")

        outer = self.copy_evidence()
        (outer / "record.json").write_text(
            (outer / "record.json").read_text() + " ", encoding="utf-8"
        )
        with self.assertRaises(Exception) as raised:
            V.validate(ROOT, outer)
        self.assertEqual(str(raised.exception), "checksum.outer")

    def test_failure_output_never_echoes_sensitive_input(self):
        marker = "DO_NOT_ECHO_THIS_PROBE_VALUE"
        root = self.copy_evidence()
        record = json.loads((root / "record.json").read_text())
        record["independent_probe"] = {"apiSecretMaterial": marker}
        self.write_json(root, "record.json", record)
        process = self.run_validator(TOOLS / "m0_3c_validate.py", root)
        self.assertEqual(process.returncode, 1)
        self.assertNotIn(marker, process.stdout)
        self.assertNotIn(marker, process.stderr)
        self.assertNotIn("apiSecretMaterial", process.stdout)
        self.assertNotIn("apiSecretMaterial", process.stderr)


if __name__ == "__main__":
    unittest.main()
