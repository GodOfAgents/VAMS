from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_traceability.py")
SPEC = importlib.util.spec_from_file_location("validate_traceability", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class TraceabilityTests(unittest.TestCase):
    def test_architecture_and_invariant_anchors_resolve(self) -> None:
        self.assertEqual(module.validate(), [])

    def test_every_invariant_has_enforcement_and_tests(self) -> None:
        controls = module._load(module.AUDIT_DIR / "invariant-controls.json")
        self.assertEqual(len(controls["controls"]), 10)
        for control in controls["controls"]:
            self.assertTrue(control["enforcement"])
            self.assertTrue(control["tests"])


if __name__ == "__main__":
    unittest.main()
