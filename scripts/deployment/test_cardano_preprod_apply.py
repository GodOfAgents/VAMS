from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("cardano_preprod_apply.py")
SPEC = importlib.util.spec_from_file_location("cardano_preprod_apply", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
COMMIT = "a" * 40
TITLES = sorted(
    set(module.DEPLOYABLE_VALIDATORS) | set(module.AUXILIARY_POLICY_TEMPLATES)
)


def _blueprint(applied: bool = False) -> dict:
    return {
        "validators": [
            {
                "title": title,
                "parameters": [] if applied else [{"title": "parameter"}],
                "compiledCode": "00",
                "hash": "1" * 56,
            }
            for title in TITLES
        ]
    }


def _manifest() -> dict:
    return {
        "schema_version": "1.0.0",
        "commit_sha": COMMIT,
        "network": "cardano-preprod",
        "persistent_parameters_cbor": {
            title: ["00"] for title in sorted(module.DEPLOYABLE_VALIDATORS)
        },
        "auxiliary_policy_instances": [
            {
                "instance_id": "fund-bootstrap",
                "title": "fund_nft.fund_nft.mint",
                "parameters_cbor": ["00"],
            }
        ],
    }


class CardanoPreProdApplyTests(unittest.TestCase):
    def test_parameter_manifest_requires_every_exact_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "parameters.json"
            path.write_text(json.dumps(_manifest()), encoding="utf-8")
            result = module.validate_parameter_manifest(path, _blueprint(), COMMIT)
        self.assertEqual(
            set(result["persistent_parameters_cbor"]),
            set(module.DEPLOYABLE_VALIDATORS),
        )
        self.assertEqual(result["auxiliary_policy_instances"][0]["instance_id"], "fund-bootstrap")

    def test_parameter_manifest_rejects_missing_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest = _manifest()
            manifest["persistent_parameters_cbor"].pop(
                sorted(module.DEPLOYABLE_VALIDATORS)[0]
            )
            path = Path(temp) / "parameters.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly four"):
                module.validate_parameter_manifest(path, _blueprint(), COMMIT)

    def test_applied_artifacts_are_separate_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blueprint = root / "plutus.json"
            parameter_path = root / "parameters.json"
            blueprint.write_text(json.dumps(_blueprint()), encoding="utf-8")
            parameter_path.write_text(json.dumps(_manifest()), encoding="utf-8")
            first_output = root / "first"
            second_output = root / "second"
            applied_entry = {
                "title": TITLES[0],
                "parameters": [],
                "compiledCode": "00",
                "hash": "1" * 56,
            }
            with mock.patch.object(module, "_apply_title", return_value=applied_entry):
                first = module.apply_and_extract(
                    blueprint, parameter_path, first_output, COMMIT
                )
                second = module.apply_and_extract(
                    blueprint, parameter_path, second_output, COMMIT
                )
            first_files = {
                path.name: path.read_bytes() for path in first_output.iterdir()
            }
            second_files = {
                path.name: path.read_bytes() for path in second_output.iterdir()
            }
        self.assertEqual(first, second)
        self.assertEqual(first_files, second_files)
        self.assertTrue(first["artifacts_applied"])
        self.assertEqual(len(first["validators"]), 4)
        self.assertEqual(len(first["auxiliary_policy_templates"]), 3)
        self.assertEqual(len(first["auxiliary_policy_instances"]), 1)
        self.assertFalse(any("vdso" in item["title"] for item in first["validators"]))


if __name__ == "__main__":
    unittest.main()
