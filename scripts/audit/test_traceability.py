from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_traceability.py")
SPEC = importlib.util.spec_from_file_location("validate_traceability", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


NON_INV5_INV10_CONTROL_DIGEST = (
    "51cd195d1287ebdb080cd642a967a967839967faa0ec7fa6320441bff1c4a78e"
)


def _controls() -> dict:
    return module._load(module.AUDIT_DIR / "invariant-controls.json")


def _inv5(controls: dict) -> dict:
    return next(item for item in controls["controls"] if item["id"] == "INV-5")


def _inv10(controls: dict) -> dict:
    return next(item for item in controls["controls"] if item["id"] == "INV-10")


def _copy_control_sources(destination: Path, controls: dict) -> None:
    paths = {
        anchor["path"]
        for control in controls["controls"]
        for group in ("enforcement", "tests")
        for anchor in control[group]
    }
    for relative_path in paths:
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(module.ROOT / relative_path, target)


def _mutate_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise AssertionError(f"mutation target occurs {source.count(old)} times: {old!r}")
    path.write_text(source.replace(old, new), encoding="utf-8")


class TraceabilityTests(unittest.TestCase):
    def test_architecture_and_invariant_anchors_resolve(self) -> None:
        self.assertEqual(module.validate(), [])

    def test_every_invariant_has_enforcement_and_tests(self) -> None:
        controls = _controls()
        self.assertEqual(len(controls["controls"]), 10)
        for control in controls["controls"]:
            self.assertTrue(control["enforcement"])
            self.assertTrue(control["tests"])

    def test_historical_stale_inv5_prose_anchor_fails_for_original_reason(self) -> None:
        controls = _controls()
        inv5 = _inv5(controls)
        inv5["enforcement"][0] = {
            "path": "neuron/clr_router.py",
            "must_contain": [
                "Institutional compliance routing requires an OMS verified identity"
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            errors = module.validate_invariant_controls(root, controls)

        self.assertIn(
            "INV-5 anchor neuron/clr_router.py lacks "
            "'Institutional compliance routing requires an OMS verified identity'",
            errors,
        )

    def test_inv5_control_ignores_harmless_prose_changes(self) -> None:
        controls = _controls()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            _mutate_once(
                root / "neuron/clr_router.py",
                "Institutional compliance routing requires a live OMS verified identity.",
                "Compliance evidence did not satisfy the institutional route policy.",
            )

            self.assertEqual(module.validate_invariant_controls(root, controls), [])

    def test_inv5_control_detects_removed_oms_denial_guard(self) -> None:
        controls = _controls()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            _mutate_once(
                root / "neuron/clr_router.py",
                "if not self.identity_verifier.is_compliance_verified(metadata.agent_address):",
                "if False:",
            )
            errors = module.validate_invariant_controls(root, controls)

        self.assertTrue(any("missing call" in error for error in errors), errors)
        self.assertTrue(any("lacks fail-closed" in error for error in errors), errors)

    def test_inv5_control_detects_permissive_p3_fallback(self) -> None:
        controls = _controls()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            _mutate_once(
                root / "neuron/clr_router.py",
                """raise PermissionError(
                "Institutional compliance routing requires a live OMS verified identity."
            )""",
                "return self._route_default(metadata, metrics)",
            )
            errors = module.validate_invariant_controls(root, controls)

        self.assertTrue(any("lacks fail-closed" in error for error in errors), errors)

    def test_inv5_control_detects_test_rename(self) -> None:
        controls = _controls()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            _mutate_once(
                root / "neuron/tests/test_m1_2a_identity_tee_runtime.py",
                "def test_p3_blocks_simulated_oms_success(",
                "def test_p3_simulation_case_was_renamed(",
            )
            errors = module.validate_invariant_controls(root, controls)

        self.assertTrue(any("missing exact test identifier" in error for error in errors), errors)

    def test_inv5_metadata_fails_closed_when_incomplete_or_malformed(self) -> None:
        mutations = {}

        incomplete = _controls()
        del _inv5(incomplete)["enforcement"][0]["python_ast"]["guarded_denials"]
        mutations["incomplete"] = incomplete

        unknown = _controls()
        _inv5(unknown)["enforcement"][0]["python_ast"]["unsupported"] = True
        mutations["unknown"] = unknown

        malformed = _controls()
        _inv5(malformed)["enforcement"][0]["python_ast"] = "not-an-object"
        mutations["malformed"] = malformed

        missing = _controls()
        del _inv5(missing)["enforcement"][0]["python_ast"]
        mutations["missing"] = missing

        duplicate = _controls()
        duplicate_anchor = copy.deepcopy(_inv5(duplicate)["enforcement"][0])
        _inv5(duplicate)["enforcement"].append(duplicate_anchor)
        mutations["duplicate"] = duplicate

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, _controls())
            for name, controls in mutations.items():
                with self.subTest(name=name):
                    self.assertTrue(
                        module.validate_invariant_controls(root, controls),
                        f"{name} metadata unexpectedly passed",
                    )

    def test_inv10_boundary_rejects_merged_or_removed_fields(self) -> None:
        controls = _controls()
        inv10 = _inv10(controls)
        anchor = inv10["enforcement"][1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            target = root / anchor["path"]
            _mutate_once(
                target,
                "Deposit { amount: _, bridge_proof: _, payload_hash: _ } -> False",
                "Deposit { amount: _, bridge_proof: _, payload_hash: _ } -> True",
            )
            self.assertTrue(module.validate_invariant_controls(root, controls))
        controls = _controls()
        inv10 = _inv10(controls)
        inv10["enforcement"][1]["aiken_boundary"]["required_fields"] = ["bridge_proof"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            self.assertTrue(module.validate_invariant_controls(root, controls))

    def test_inv10_boundary_rejects_structural_bridge_authorizer(self) -> None:
        controls = _controls()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _copy_control_sources(root, controls)
            target = root / "cardano/validators/insurance_fund.ak"
            target.write_text(
                target.read_text(encoding="utf-8") + chr(10) + "fn verify_bridge_proof() { True }" + chr(10),
                encoding="utf-8",
            )
            errors = module.validate_invariant_controls(root, controls)
        self.assertTrue(any("forbidden structural authorizer" in error for error in errors), errors)

    def test_non_inv5_control_contract_is_byte_for_byte_unchanged(self) -> None:
        controls = _controls()
        other_controls = [
            control for control in controls["controls"] if control["id"] not in {"INV-5", "INV-10"}
        ]
        encoded = json.dumps(
            other_controls, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        self.assertEqual(hashlib.sha256(encoded).hexdigest(), NON_INV5_INV10_CONTROL_DIGEST)


if __name__ == "__main__":
    unittest.main()
