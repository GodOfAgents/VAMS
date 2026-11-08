#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ("IDENTITY_SPEC.json", "ASSET_VECTORS.json", "DATUM_VECTORS.json", "TRANSITION_TOPOLOGY.json", "VALUE_RULES.json", "ACCEPTANCE_MATRIX.json")


def load_exact(path: Path):
    path = path.resolve(strict=True)
    name = "_m3_f04_test_validator_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError("module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        loaded = Path(module.__file__).resolve(strict=True)
        if loaded != path or hashlib.sha256(loaded.read_bytes()).hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest():
            raise AssertionError("exact-path/hash mismatch")
        module._test_module_name = name
        return module
    except BaseException:
        sys.modules.pop(name, None)
        raise


VALIDATOR = load_exact(ROOT / "validate_design.py")


class DesignTests(unittest.TestCase):
    def clone(self):
        td = tempfile.TemporaryDirectory(prefix="m3-f04-spec-")
        base = Path(td.name)
        for name in FILES:
            (base / name).write_bytes((ROOT / name).read_bytes())
        return td, base

    def mutate_rejects(self, name, mutation):
        td, base = self.clone()
        try:
            value = json.loads((base / name).read_text())
            mutation(value)
            (base / name).write_text(json.dumps(value) + "\n")
            with self.assertRaises(ValueError):
                VALIDATOR.validate(base)
        finally:
            td.cleanup()

    def test_baseline_and_exact_boundary_contract(self):
        self.assertEqual(VALIDATOR.validate(ROOT), {"ok": True, "asset_vectors": 2, "datum_vectors": 2, "topology_rows": 4, "matrix_rows": 49})
        assets = json.loads((ROOT / "ASSET_VECTORS.json").read_text())
        self.assertEqual({row["id"] for row in assets["boundary_vectors"]}, {"did_len_31_rejected", "did_len_32_accepted", "did_len_256_accepted", "did_len_257_rejected", "did_invalid_utf8_rejected"})
        self.assertEqual([len(bytes.fromhex(row["did"])) for row in assets["vectors"]], [32, 256])

    def test_cli_boundary(self):
        run = subprocess.run([sys.executable, str(ROOT / "validate_design.py")], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)["ok"])

    def test_generator_matches(self):
        run = subprocess.run([sys.executable, str(ROOT / "generate_vectors.py")], cwd=ROOT, text=True, capture_output=True, check=True)
        generated = json.loads(run.stdout)
        source = json.loads((ROOT / "ASSET_VECTORS.json").read_text())
        self.assertEqual(generated["vectors"], [{"id": x["id"], "preimage_hex": x["preimage_hex"], "token_name": x["token_name"]} for x in source["vectors"]])

    def test_exact_path_validator_ignores_poisoned_import(self):
        with tempfile.TemporaryDirectory(prefix="m3-f04-poison-") as td:
            poison = Path(td) / "validate_design.py"
            poison.write_text("def validate(*args, **kwargs): raise AssertionError('poisoned')\n")
            old_path = os.environ.get("PYTHONPATH")
            poisoned_name = "validate_design"
            old_module = sys.modules.get(poisoned_name)
            sys.modules[poisoned_name] = object()
            try:
                os.environ["PYTHONPATH"] = str(Path(td))
                module = load_exact(ROOT / "validate_design.py")
                self.assertEqual(module.validate(ROOT)["ok"], True)
            finally:
                sys.modules.pop(module._test_module_name, None)
                if old_module is None:
                    sys.modules.pop(poisoned_name, None)
                else:
                    sys.modules[poisoned_name] = old_module
                if old_path is None:
                    os.environ.pop("PYTHONPATH", None)
                else:
                    os.environ["PYTHONPATH"] = old_path

    def test_generator_exact_path_ignores_poisoned_import(self):
        with tempfile.TemporaryDirectory(prefix="m3-f04-generator-poison-") as td:
            Path(td, "validate_design.py").write_text("raise RuntimeError('poisoned')\n")
            run = subprocess.run([sys.executable, str(ROOT / "generate_vectors.py")], cwd=ROOT, env={**os.environ, "PYTHONPATH": td}, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(json.loads(run.stdout)["vectors"]), 2)

    def test_bool_integer_rejected(self):
        self.mutate_rejects("IDENTITY_SPEC.json", lambda x: x["limits"].update(max_inputs=True))

    def test_schema_unknown_missing_duplicate_rejected(self):
        self.mutate_rejects("IDENTITY_SPEC.json", lambda x: x["identity"].update(unknown=True))
        self.mutate_rejects("ASSET_VECTORS.json", lambda x: x["vectors"][0].pop("did"))
        td, base = self.clone()
        try:
            path = base / "IDENTITY_SPEC.json"
            raw = path.read_text()
            path.write_text(raw.replace('"status": "design-frozen-not-implemented",', '"status": "design-frozen-not-implemented",\n  "status": "duplicate",', 1))
            with self.assertRaises(ValueError):
                VALIDATOR.validate(base)
        finally:
            td.cleanup()

    def test_hex_utf8_and_boundary_mutations_rejected(self):
        self.mutate_rejects("ASSET_VECTORS.json", lambda x: x["vectors"][0].update(token_name="AA" * 32))
        self.mutate_rejects("ASSET_VECTORS.json", lambda x: x["vectors"][0].update(did="ff" + "01" * 31))
        self.mutate_rejects("ASSET_VECTORS.json", lambda x: x["boundary_vectors"].pop())
        self.mutate_rejects("DATUM_VECTORS.json", lambda x: x["vectors"][0]["fields"].update(did="00" * 31))


if __name__ == "__main__":
    unittest.main(verbosity=2)
