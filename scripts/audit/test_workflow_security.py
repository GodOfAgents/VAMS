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


if __name__ == "__main__":
    unittest.main()
