from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = Path(__file__).with_name("cardano_preprod_artifacts.py")
SPEC = importlib.util.spec_from_file_location("cardano_preprod_artifacts", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
ROOT = Path(__file__).resolve().parents[2]
COMMIT = "a" * 40


class CardanoPreProdArtifactTests(unittest.TestCase):
    def test_extracts_exact_four_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            first = module.extract(ROOT / "cardano" / "plutus.json", output, COMMIT)
            first_bytes = {
                path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
            }
            second = module.extract(ROOT / "cardano" / "plutus.json", output, COMMIT)
            second_bytes = {
                path.name: path.read_bytes() for path in output.iterdir() if path.is_file()
            }
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(len(first["validators"]), 4)
        self.assertEqual(first["persistent_validator_count"], 4)
        self.assertFalse(first["artifacts_applied"])
        self.assertTrue(all(not item["applied"] for item in first["validators"]))
        self.assertTrue(
            all(item["artifact_path"].endswith(".template.json") for item in first["validators"])
        )
        self.assertEqual(len(first["auxiliary_policy_templates"]), 3)
        self.assertTrue(
            all(
                item["parameter_count"] > 0
                for item in first["auxiliary_policy_templates"]
            )
        )
        self.assertEqual(first["vdso"]["deployable"], False)
        self.assertFalse(any("vdso" in item["title"] for item in first["validators"]))

    def test_rejects_missing_authoritative_validator(self) -> None:
        blueprint = json.loads((ROOT / "cardano" / "plutus.json").read_text("utf-8"))
        blueprint["validators"] = [
            item
            for item in blueprint["validators"]
            if item["title"] != "timelock.timelock.spend"
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "plutus.json"
            path.write_text(json.dumps(blueprint), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing authoritative validators"):
                module.extract(path, root / "output", COMMIT)

    def test_rejects_vdso_blueprint_entry(self) -> None:
        blueprint = json.loads((ROOT / "cardano" / "plutus.json").read_text("utf-8"))
        vdso = copy.deepcopy(blueprint["validators"][0])
        vdso["title"] = "vdso.vdso.spend"
        blueprint["validators"].append(vdso)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "plutus.json"
            path.write_text(json.dumps(blueprint), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "conformance-only"):
                module.extract(path, root / "output", COMMIT)

    def test_rejects_missing_auxiliary_policy_template(self) -> None:
        blueprint = json.loads((ROOT / "cardano" / "plutus.json").read_text("utf-8"))
        blueprint["validators"] = [
            item
            for item in blueprint["validators"]
            if item["title"] != "proposal_nft.proposal_nft.mint"
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "plutus.json"
            path.write_text(json.dumps(blueprint), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing auxiliary policy templates"):
                module.extract(path, root / "output", COMMIT)

    def test_cli_binding_rejects_wrong_head_or_dirty_cardano_tree(self) -> None:
        blueprint = ROOT / "cardano" / "plutus.json"
        with mock.patch.object(
            module.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="b" * 40 + "\n"),
        ):
            with self.assertRaisesRegex(ValueError, "does not match"):
                module.require_exact_repository_state(blueprint, COMMIT)

        clean_head = SimpleNamespace(stdout=COMMIT + "\n")
        dirty_tree = SimpleNamespace(stdout=" M cardano/plutus.json\n")
        with mock.patch.object(
            module.subprocess, "run", side_effect=(clean_head, dirty_tree)
        ):
            with self.assertRaisesRegex(ValueError, "dirty"):
                module.require_exact_repository_state(blueprint, COMMIT)


if __name__ == "__main__":
    unittest.main()
