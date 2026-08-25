from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_workflow_security.py")
SPEC = importlib.util.spec_from_file_location("validate_workflow_security", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class WorkflowSecurityTests(unittest.TestCase):
    def test_actions_and_security_tools_are_pinned(self) -> None:
        self.assertEqual(module.validate(), [])

    def test_required_github_actions_use_reviewed_node24_releases(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for action, ref in module.REQUIRED_ACTION_PINS.items():
            self.assertIn(f"uses: {action}@{ref}", text)

    def test_failure_manifest_precedes_aggregate_enforcement(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(
            text.index("- name: Generate Commit-Bound Evidence Manifest"),
            text.index("- name: Enforce Required Job Results"),
        )


if __name__ == "__main__":
    unittest.main()
