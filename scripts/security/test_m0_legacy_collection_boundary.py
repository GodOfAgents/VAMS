from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFTEST = ROOT / "conftest.py"
RETIRED = {
    "scripts/security/test_m0_3a_adjudicator.py",
    "docs/remediation/m0_3b_r1/tools/test_m0_3b_adjudicator.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_r7.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_r9.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_semantic_oracle.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_validator.py",
}


class M0LegacyCollectionBoundaryTests(unittest.TestCase):
    def test_exact_historical_modules_are_retired(self) -> None:
        tree = ast.parse(CONFTEST.read_text(encoding="utf-8"))
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "collect_ignore"
                for target in node.targets
            )
        )
        actual = ast.literal_eval(assignment.value)
        self.assertEqual(set(actual), RETIRED)
        self.assertEqual(len(actual), len(RETIRED))
        self.assertTrue(all((ROOT / path).is_file() for path in actual))

    def test_active_m0_4_gate_remains_collected(self) -> None:
        self.assertNotIn(
            "scripts/security/test_m0_4_vendor_baseline_gate.py", RETIRED
        )
        self.assertTrue(
            (ROOT / "scripts/security/test_m0_4_vendor_baseline_gate.py").is_file()
        )

    def test_retirement_boundary_has_no_globs_or_directories(self) -> None:
        for path in RETIRED:
            self.assertNotRegex(path, r"[*?\[\]]")
            self.assertTrue(path.endswith(".py"))
            self.assertTrue(Path(path).name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
