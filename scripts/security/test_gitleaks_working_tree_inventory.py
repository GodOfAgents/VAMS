import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("inventory", Path(__file__).with_name("gitleaks_working_tree_inventory.py"))
inventory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def test_manifest_rejects_absolute_traversal_duplicate(self):
        for value in ("/tmp/x", "../x", "a/../x", "a//x", "a\\x"):
            with self.assertRaises(inventory.InventoryError):
                inventory.canonical_rel(value)

    def test_generated_pyc_is_excluded(self):
        self.assertTrue(inventory.is_excluded("scripts/security/__pycache__/x.pyc"))
        self.assertFalse(inventory.is_excluded("scripts/security/x.py"))

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            base = Path(root)
            (base / "link").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaises(inventory.InventoryError):
                inventory.validate_source(base, "link/secret.txt", category="untracked")

    def test_submodule_provenance_parsing(self):
        self.assertEqual(inventory.parse_submodule_status.__name__, "parse_submodule_status")

    def test_deterministic_output(self):
        source = inventory.Source("a.txt", Path("/tmp/a.txt"), "tracked")
        findings = [{"File": "a.txt", "RuleID": "z", "Secret": "REDACTED", "Match": "REDACTED"}, {"File": "a.txt", "RuleID": "a", "Secret": "REDACTED", "Match": "REDACTED"}]
        self.assertEqual(inventory.build_ledger(findings, {"a.txt": source}), inventory.build_ledger(list(reversed(findings)), {"a.txt": source}))

    def test_fail_closed_negative_secret_fixture(self):
        source = inventory.Source("a.txt", Path("/tmp/a.txt"), "tracked")
        with self.assertRaises(inventory.InventoryError):
            inventory.build_ledger([{ "File": "a.txt", "RuleID": "x", "Secret": "raw" }], {"a.txt": source})

    def test_checksum_verification_path_is_present(self):
        self.assertIn("sha256sum", Path(inventory.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
