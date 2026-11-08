#!/usr/bin/env python3
"""Focused public-boundary tests for the M3.1b-R11 provenance contract."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess, run
import sys
from unittest import mock

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
MODULE_PATH = ROOT / "scripts/remediation/verify_m3_1b_r9.py"
SPEC = importlib.util.spec_from_file_location("m3_r11", MODULE_PATH)
assert SPEC and SPEC.loader
R11 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R11)
MANIFEST_PATH = ROOT / "cardano/aiken-dependency-manifest.json"
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
EXPECTED_SOURCES = [
    "lib/vams/f05_authority.ak", "lib/vams/governance.ak", "lib/vams/icb.ak", "lib/vams/types.ak", "lib/vams/utils.ak", "lib/vams/vdso.ak",
    "validators/agent_nft.ak", "validators/agent_registry.ak", "validators/agent_registry.test.ak", "validators/f05_authority_policy.ak", "validators/f05_authority_policy.test.ak",
    "validators/f05_authority_state.ak", "validators/governance_policies.ak", "validators/governor.ak", "validators/insurance_fund.ak", "validators/timelock.ak",
]
EXPECTED_PACKAGES = ["aiken-lang/fuzz", "aiken-lang/stdlib"]


class R11BoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = R11.validate_manifest(MANIFEST_PATH)

    def _fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory(prefix="m3-r11-fixture-", dir="/tmp")
        root = Path(holder.name)
        cardano = root / "cardano"
        records = [(x["path"], x["sha256"]) for x in self.manifest["compilation_sources"]]
        records += [(x["path"], x["sha256"]) for x in self.manifest["project_inputs"]]
        records.append((self.manifest["blueprint"]["path"], self.manifest["blueprint"]["sha256"]))
        for dep in self.manifest["dependencies"]:
            records.extend((f"build/packages/{dep['package_dir']}/{f['path']}", f["sha256"]) for f in dep["files"])
        for rel, _digest in records:
            target = cardano / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "cardano" / rel, target)
        shutil.copyfile(MANIFEST_PATH, cardano / "aiken-dependency-manifest.json")
        self.addCleanup(holder.cleanup)
        return holder, root

    def test_authoritative_contract(self) -> None:
        self.assertEqual(self.manifest["schema_version"], "m7-f05-current-forward-v1")
        self.assertEqual(self.manifest["compiler"]["version"], "v1.1.21")
        self.assertEqual([x["path"] for x in self.manifest["compilation_sources"]], EXPECTED_SOURCES)
        self.assertEqual([x["name"] for x in self.manifest["package_cache"]["index"]["packages"]], EXPECTED_PACKAGES)
        self.assertEqual(len(self.manifest["blueprint"]["programs"]), 26)

    def test_m7_forward_manifest_rebinds_current_lock_without_false_continuity(self) -> None:
        self.assertEqual(self.manifest["manifest_version"], 7)
        self.assertEqual(self.manifest["schema_version"], "m7-f05-current-forward-v1")
        self.assertEqual(self.manifest["project"]["lock_sha256"], '7c69f0a484d3b42862dc0ab0773cf6b3edf72709c921b2ad3648a0753af8cafc')
        self.assertEqual(self.manifest["project"]["lock_normalized_sha256"], 'f28b9d1a1db06f402c875417061f3a442bf46adcd0d2b448d0e8310bd6484e18')
        self.assertEqual(self.manifest["project_inputs"][1]["sha256"], self.manifest["project"]["lock_sha256"])
        self.assertEqual(self.manifest["forward_provenance"]["baseline"], "m3-f04-option-b-r1")
        self.assertEqual(self.manifest["forward_provenance"]["historical_r1_raw_lock_sha256"], "8fc8bf1ccf3cf0c91acc94232646ebabb23469eb7c2d4acb1f4f0b0b67f8213b")
        self.assertEqual(self.manifest["forward_provenance"]["current_canonical_raw_lock_sha256"], self.manifest["project"]["lock_sha256"])
        self.assertEqual(self.manifest["forward_provenance"]["raw_lock_continuity"], "historically unresolved; R1 bytes unavailable")
        R11.validate_repository_inputs(ROOT, self.manifest)

    def test_m7_dependency_commits_reject_tag_and_malformed_identity(self) -> None:
        for dep in self.manifest["dependencies"]:
            self.assertEqual(dep["revision_kind"], "commit")
            self.assertRegex(dep["revision"], r"^[0-9a-f]{40}$")
        for kind, revision in (("tag", "v2"), ("commit", "v2"), ("commit", "0" * 40)):
            mutated = copy.deepcopy(self.manifest)
            mutated["dependencies"][0]["revision_kind"] = kind
            mutated["dependencies"][0]["revision"] = revision
            mutated["dependencies"][0]["version"] = revision
            mutated["package_cache"]["index"]["packages"][0]["version"] = revision
            with self.subTest(kind=kind, revision=revision), tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
                json.dump(mutated, handle); handle.flush()
                with self.assertRaises(R11.VerificationError):
                    R11.validate_manifest(Path(handle.name))

    def test_m7_forward_reset_binding_mutations_reject(self) -> None:
        cases = (
            ("schema", lambda m: m.update(schema_version="m3.2b-r3-dependency-manifest-v1")),
            ("baseline", lambda m: m["forward_provenance"].update(baseline="m3-f04-option-b-r0")),
            ("historical_lock", lambda m: m["forward_provenance"].update(historical_r1_raw_lock_sha256="0" * 64)),
            ("current_lock", lambda m: m["forward_provenance"].update(current_canonical_raw_lock_sha256="0" * 64)),
            ("continuity_claim", lambda m: m["forward_provenance"].update(raw_lock_continuity="verified")),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.manifest)
                mutate(mutated)
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
                    json.dump(mutated, handle); handle.flush()
                    with self.assertRaises(R11.VerificationError):
                        R11.validate_manifest(Path(handle.name))

    def test_r9_normalized_lock_digest_allows_timestamp_only_bytes(self) -> None:
        original = (ROOT / "cardano/aiken.lock").read_bytes()
        mutated = re.sub(rb"(secs_since_epoch = )[0-9]+", rb"\g<1>1", original, count=1)
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(mutated); handle.flush()
            self.assertEqual(R11.normalized_lock_digest(Path(handle.name)), self.manifest["project"]["lock_normalized_sha256"])

    def test_r9_rebound_raw_hash_trailing_byte_fails_normalized_binding(self) -> None:
        holder, root = self._fixture()
        lock = root / "cardano/aiken.lock"
        mutated = lock.read_bytes() + b"\n"
        lock.write_bytes(mutated)
        manifest_path = root / "cardano/aiken-dependency-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        digest = __import__("hashlib").sha256(mutated).hexdigest()
        manifest["project"]["lock_sha256"] = digest
        for record in manifest["project_inputs"]:
            if record["path"] == "aiken.lock":
                record["sha256"] = digest; record["size"] = len(mutated)
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(R11.VerificationError, "authoritative project hash mismatch|normalized lock hash|invalid lockfile"):
            R11.validate_repository_inputs(root, manifest)

    def test_r5_timestamp_only_semantic_rewrite_passes_nonvolatile_rewrite_fails(self) -> None:
        original = R11.parse_lock(ROOT / "cardano/aiken.lock")
        timestamp_only = copy.deepcopy(original)
        for value in timestamp_only["etags"].values():
            value[0]["secs_since_epoch"] += 17
            value[0]["nanos_since_epoch"] = (value[0]["nanos_since_epoch"] + 23) % 1_000_000_000
        R11.validate_semantic_lock(timestamp_only, self.manifest)
        nonvolatile = copy.deepcopy(timestamp_only)
        nonvolatile["packages"][0]["requirements"] = list(nonvolatile["packages"][0]["requirements"]) + ["unexpected"]
        with self.assertRaises(R11.VerificationError):
            R11.validate_semantic_lock(nonvolatile, self.manifest)

    def test_r13_malformed_manifest_containers_rejected(self) -> None:
        cases = []
        for value in (None, True, 1, "inputs", [], {}):
            cases.append((f"project_inputs_{type(value).__name__}", lambda m, value=value: m.update(project_inputs=value)))
        cases.extend([
            ("project_inputs_empty", lambda m: m.update(project_inputs=[])),
            ("project_inputs_undersized", lambda m: m.update(project_inputs=m["project_inputs"][:2])),
            ("project_input_missing_key", lambda m: m["project_inputs"][0].pop("sha256")),
            ("project_input_unknown_key", lambda m: m["project_inputs"][0].update(unknown=True)),
            ("project_input_boolean_size", lambda m: m["project_inputs"][0].update(size=True)),
        ])
        for value in (None, True, 1, "cache", [], {}):
            cases.append((f"package_cache_{type(value).__name__}", lambda m, value=value: m.update(package_cache=value)))
        cases.extend([
            ("package_cache_missing_key", lambda m: m["package_cache"].pop("directories")),
            ("package_cache_unknown_key", lambda m: m["package_cache"].update(unknown=True)),
        ])
        for value in (None, True, 1, "index", [], {}):
            cases.append((f"package_index_{type(value).__name__}", lambda m, value=value: m["package_cache"].update(index=value)))
        cases.extend([
            ("package_index_missing_key", lambda m: m["package_cache"]["index"].pop("packages")),
            ("package_index_unknown_key", lambda m: m["package_cache"]["index"].update(unknown=True)),
            ("package_index_malformed_record", lambda m: m["package_cache"]["index"].update(packages=[{"name": "bad"}])),
            ("package_file_boolean_size", lambda m: m["dependencies"][0]["files"][0].update(size=False)),
            ("package_file_missing_key", lambda m: m["dependencies"][0]["files"][0].pop("sha256")),
            ("manifest_version_boolean", lambda m: m.update(manifest_version=True)),
        ])
        for name, mutate in cases:
            with self.subTest(name=name):
                mutated = copy.deepcopy(self.manifest)
                mutate(mutated)
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
                    json.dump(mutated, handle); handle.flush()
                    with self.assertRaises(R11.VerificationError):
                        R11.validate_manifest(Path(handle.name))

    def test_r13_canonical_manifest_and_cli_failure_are_controlled(self) -> None:
        self.assertEqual(R11.validate_manifest(MANIFEST_PATH)["schema_version"], "m7-f05-current-forward-v1")
        with tempfile.TemporaryDirectory(prefix="m3-r13-cli-") as folder:
            root = Path(folder); cardano = root / "cardano"; cardano.mkdir()
            malformed = copy.deepcopy(self.manifest); malformed["project_inputs"] = None
            (cardano / "aiken-dependency-manifest.json").write_text(json.dumps(malformed))
            result = run([sys.executable, str(MODULE_PATH), "--repo-root", str(root)], capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            self.assertIn('"ok": false', result.stdout)

    def test_unknown_and_duplicate_manifest_keys_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest); mutated["unknown"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(mutated, handle); handle.flush()
            with self.assertRaises(R11.VerificationError): R11.validate_manifest(Path(handle.name))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            handle.write('{"schema_version": 1, "schema_version": 2}'); handle.flush()
            with self.assertRaises(R11.VerificationError): R11._read_json(Path(handle.name))

    def test_dependency_identifiers_and_path_escape_rejected(self) -> None:
        for name in ("..", ".", "", "a//b", "a\\b", "/absolute", "a/../b", "a/／b"):
            mutated = copy.deepcopy(self.manifest); mutated["dependencies"][0]["name"] = name
            with self.subTest(name=name), tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
                json.dump(mutated, handle); handle.flush()
                with self.assertRaises(R11.VerificationError): R11.validate_manifest(Path(handle.name))

    def test_source_omission_addition_and_rebinding_rejected(self) -> None:
        for mutation in ("omit", "add", "digest", "path"):
            mutated = copy.deepcopy(self.manifest)
            if mutation == "omit": mutated["compilation_sources"].pop()
            elif mutation == "add": mutated["compilation_sources"].append(copy.deepcopy(mutated["compilation_sources"][-1]))
            elif mutation == "digest": mutated["compilation_sources"][0]["sha256"] = "0" * 64
            else: mutated["compilation_sources"][0]["path"] = "lib/vams/renamed.ak"
            with self.subTest(mutation=mutation), self.assertRaises(R11.VerificationError):
                R11.validate_repository_inputs(ROOT, mutated)

    def test_r15_lock_timestamp_boolean_and_scalar_matrix(self) -> None:
        original = (ROOT / "cardano/aiken.lock").read_text()
        for field in ("secs_since_epoch", "nanos_since_epoch"):
            for token in ("true", "false", "1.0", '"1"', "none"):
                with self.subTest(field=field, token=token):
                    mutated = re.sub(rf"({field}\s*=\s*)[0-9]+", rf"\g<1>{token}", original, count=1)
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock") as handle:
                        handle.write(mutated); handle.flush()
                        with self.assertRaisesRegex(R11.VerificationError, "lock timestamp|invalid lockfile"):
                            R11.parse_lock(Path(handle.name))
        for field in ("secs_since_epoch", "nanos_since_epoch"):
            for token in ("true", "false"):
                mutated = re.sub(rf"({field}\s*=\s*)[0-9]+", rf"\g<1>{token}", original, count=1)
                with tempfile.NamedTemporaryFile(mode="w", suffix=".lock") as handle:
                    handle.write(mutated); handle.flush()
                    with self.assertRaises(R11.VerificationError):
                        R11.parse_lock(Path(handle.name))
        self.assertIsInstance(R11.parse_lock(ROOT / "cardano/aiken.lock"), dict)
        for value in ("0", "9223372036854775807"):
            mutated = re.sub(r"(secs_since_epoch\s*=\s*)[0-9]+", rf"\g<1>{value}", original, count=1)
            mutated = re.sub(r"(nanos_since_epoch\s*=\s*)[0-9]+", rf"\g<1>{value}", mutated, count=1)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".lock") as handle:
                handle.write(mutated); handle.flush()
                self.assertIsInstance(R11.parse_lock(Path(handle.name)), dict)

    def test_r15_cli_lock_timestamp_failure_is_sanitized(self) -> None:
        holder, root = self._fixture()
        lock = root / "cardano/aiken.lock"
        mutated = re.sub(r"(secs_since_epoch\s*=\s*)[0-9]+", r"\g<1>true", lock.read_text(), count=1)
        lock.write_text(mutated)
        manifest_path = root / "cardano/aiken-dependency-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        import hashlib
        digest = hashlib.sha256(mutated.encode()).hexdigest()
        manifest["project"]["lock_sha256"] = digest
        manifest["forward_provenance"]["current_canonical_raw_lock_sha256"] = digest
        for record in manifest["project_inputs"]:
            if record["path"] == "aiken.lock":
                record["sha256"] = digest
                record["size"] = len(mutated.encode())
        manifest_path.write_text(json.dumps(manifest))
        result = run([sys.executable, str(MODULE_PATH), "--repo-root", str(root), "--aiken", str(AIKEN)], capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertIn('"ok": false', result.stdout)
        self.assertIn("malformed lock timestamp", result.stdout)

    def test_r15_package_index_parser_direct_matrix(self) -> None:
        parser = R11._parse_package_index
        canonical = parser(ROOT / "cardano/build/packages/packages.toml")
        self.assertEqual([item["name"] for item in canonical], EXPECTED_PACKAGES)
        cases = [
            ("missing_root", "[unexpected]\nvalue=1\n", "unexpected package index fields"),
            ("scalar_packages", "packages = true\n", "unexpected package index fields"),
            ("object_packages", "packages = {}\n", "unexpected package index fields"),
            ("missing_item_key", "[[packages]]\nname = \"aiken-lang/fuzz\"\n", "unexpected package index item fields"),
            ("unknown_item_key", "[[packages]]\nname = \"aiken-lang/fuzz\"\nversion = \"v2\"\nsource = \"github\"\nextra = 1\n", "unexpected package index item fields"),
            ("bad_name", "[[packages]]\nname = \"../fuzz\"\nversion = \"v2\"\nsource = \"github\"\n", "unsafe dependency identifier"),
            ("bad_version_type", "[[packages]]\nname = \"aiken-lang/fuzz\"\nversion = 2\nsource = \"github\"\n", "malformed package index item"),
            ("bad_source_type", "[[packages]]\nname = \"aiken-lang/fuzz\"\nversion = \"v2\"\nsource = false\n", "malformed package index item"),
            ("duplicate_name", "[[packages]]\nname = \"aiken-lang/fuzz\"\nversion = \"v2\"\nsource = \"github\"\n[[packages]]\nname = \"aiken-lang/fuzz\"\nversion = \"v2\"\nsource = \"github\"\n", "duplicate package index item"),
        ]
        for name, content, reason in cases:
            with self.subTest(name=name), tempfile.NamedTemporaryFile(mode="w", suffix=".toml") as handle:
                handle.write(content); handle.flush()
                with self.assertRaisesRegex(R11.VerificationError, reason):
                    parser(Path(handle.name))

    def test_package_index_missing_unknown_and_mutated_rejected(self) -> None:
        for mutation in ("missing", "unknown", "mutated"):
            holder, root = self._fixture(); index = root / "cardano/build/packages/packages.toml"
            if mutation == "missing": index.unlink()
            elif mutation == "unknown": index.write_text(index.read_text() + "\n[unexpected]\nvalue=1\n")
            else: index.write_text(index.read_text().replace('version = "' + self.manifest["dependencies"][0]["version"] + '"', 'version = "v9"', 1))
            with self.subTest(mutation=mutation), self.assertRaises(R11.VerificationError):
                R11.validate_repository_inputs(root, self.manifest)

    def test_package_topology_and_file_mutations_rejected(self) -> None:
        for mutation in ("extra_dir", "missing_dir", "extra_file", "missing_file", "content"):
            holder, root = self._fixture(); cache = root / "cardano/build/packages"; dep = self.manifest["dependencies"][0]; package = cache / dep["package_dir"]
            if mutation == "extra_dir": (cache / "unreviewed").mkdir()
            elif mutation == "missing_dir": shutil.rmtree(cache / dep["package_dir"])
            elif mutation == "extra_file": (package / "extra.ak").write_text("x")
            elif mutation == "missing_file": (package / dep["files"][0]["path"]).unlink()
            else: (package / dep["files"][0]["path"]).write_bytes(b"changed")
            with self.subTest(mutation=mutation), self.assertRaises(R11.VerificationError):
                R11.validate_repository_inputs(root, self.manifest)

    def test_missing_cache_symlink_and_special_file_rejected(self) -> None:
        holder, root = self._fixture(); shutil.rmtree(root / "cardano/build/packages")
        with self.assertRaises(R11.VerificationError): R11.validate_repository_inputs(root, self.manifest)
        holder, root = self._fixture(); package = root / "cardano/build/packages/aiken-lang-fuzz"; victim = package / self.manifest["dependencies"][0]["files"][0]["path"]; victim.unlink(); victim.symlink_to(ROOT / "cardano/README.md")
        with self.assertRaises(R11.VerificationError): R11.validate_repository_inputs(root, self.manifest)
        holder, root = self._fixture(); os.mkfifo(root / "cardano/build/packages/aiken-lang-fuzz/pipe")
        with self.assertRaises(R11.VerificationError): R11.validate_repository_inputs(root, self.manifest)

    def test_package_and_lock_nonvolatile_mutations_fail_but_timestamps_pass(self) -> None:
        lock = R11.parse_lock(ROOT / "cardano/aiken.lock"); changed = copy.deepcopy(lock)
        for value in changed["etags"].values(): value[0]["secs_since_epoch"] += 1; value[0]["nanos_since_epoch"] += 1
        R11.validate_semantic_lock(changed, self.manifest)
        changed["etags"][next(iter(changed["etags"]))][1] = "0" * 64
        with self.assertRaises(R11.VerificationError): R11.validate_semantic_lock(changed, self.manifest)

    def test_blueprint_drift_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m3-r11-blueprint-", dir="/tmp") as folder:
            generated = Path(folder) / "plutus.json"; shutil.copyfile(ROOT / "cardano/plutus.json", generated)
            doc = json.loads(generated.read_text()); doc["validators"][0]["compiledCode"] = "00"; generated.write_text(json.dumps(doc))
            with self.assertRaises(R11.VerificationError): R11.verify_blueprint(ROOT / "cardano/plutus.json", generated, self.manifest)

    def test_cleanup_after_injected_failure_and_network_boundary(self) -> None:
        before = set(Path("/tmp").glob("m3-r11-aiken-*")); seen = []
        def fail(command, cwd, env):
            seen.append((command[-1], dict(env)))
            if command[-1] == "--version": return CompletedProcess(command, 0, stdout="aiken v1.1.21\n", stderr="")
            return CompletedProcess(command, 1, stdout="", stderr="")
        with mock.patch.object(R11, "_run", side_effect=fail):
            with self.assertRaises(R11.VerificationError): R11.verify_repository(ROOT, AIKEN)
        self.assertEqual(before, set(Path("/tmp").glob("m3-r11-aiken-*")))
        check_env = next(env for command, env in seen if command == "check")
        self.assertEqual(check_env["AIKEN_NO_NETWORK"], "1")
        self.assertNotIn("AIKEN_HOME", check_env)

    def test_authoritative_mutation_detected(self) -> None:
        holder, fixture = self._fixture(); original = R11._run; mutated = False
        def mutate(command, cwd, env):
            nonlocal mutated
            result = original(command, cwd, env)
            if command[-1] == "check" and not mutated:
                path = fixture / "cardano/lib/vams/types.ak"; path.write_bytes(path.read_bytes() + b"\n"); mutated = True
            return result
        with mock.patch.object(R11, "_run", side_effect=mutate):
            with self.assertRaisesRegex(R11.VerificationError, "source changed"):
                R11.verify_repository(fixture, AIKEN)


if __name__ == "__main__":
    unittest.main()
