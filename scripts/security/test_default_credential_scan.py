"""Positive and adversarial controls for the default-credential gate."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).with_name("default_credential_scan.py")
SPEC = importlib.util.spec_from_file_location("default_credential_scan", MODULE_PATH)
assert SPEC and SPEC.loader
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


class DefaultCredentialScanTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="vams-default-credential-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.paths = list(scanner.REGRESSION_EVIDENCE)
        for relative in self.paths:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((scanner.ROOT / relative).read_bytes())

    def test_exact_existing_negative_controls_and_detector_definitions_pass(self) -> None:
        self.assertEqual(scanner.scan(self.root, self.paths), [])

    def test_reviewed_evidence_uses_only_the_verified_buffer(self) -> None:
        with mock.patch.object(scanner, "_read_text", side_effect=AssertionError("frozen evidence reopened")):
            self.assertEqual(scanner.scan(self.root, self.paths), [])

    def test_git_inventory_preserves_path_bytes_and_backslashes(self) -> None:
        raw = [b".semgrep\\tests\\vams-security.js", b"gateway/invalid-\xff.py"]
        result = subprocess.CompletedProcess([], 0, stdout=b"\0".join(raw) + b"\0")
        with mock.patch.object(scanner.subprocess, "run", return_value=result):
            paths = scanner._git_files()
        self.assertEqual([os.fsencode(path) for path in paths], raw)
        self.assertEqual(paths[0], ".semgrep\\tests\\vams-security.js")

    def test_inventory_alias_cannot_substitute_for_a_reviewed_identity(self) -> None:
        for relative in self.paths:
            with self.subTest(path=relative):
                alias = relative.replace("/", "\\")
                paths = [alias if path == relative else path for path in self.paths]
                self.assertTrue(any(relative in item for item in scanner.scan(self.root, paths)))

    def test_all_banned_tokens_still_fail_in_live_code(self) -> None:
        for label, token in scanner.TOKENS.items():
            with self.subTest(label=label):
                relative = "gateway/new_auth.py"
                (self.root / "gateway").mkdir(exist_ok=True)
                (self.root / relative).write_text(f"configured_value = {token!r}\n")
                findings = scanner.scan(self.root, self.paths + [relative])
                self.assertTrue(any(relative in item and label in item for item in findings))

    def test_identical_fixture_bytes_are_not_exempt_at_another_path(self) -> None:
        relative = "gateway/copied_fixture.js"
        (self.root / "gateway").mkdir()
        (self.root / relative).write_bytes((self.root / self.paths[0]).read_bytes())
        self.assertTrue(any(relative in item for item in scanner.scan(self.root, self.paths + [relative])))

    def test_new_default_in_a_frozen_fixture_fails_closed(self) -> None:
        for relative in self.paths:
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b"\n" + scanner.TOKENS["default gateway password"].encode())
                self.assertTrue(any(relative in item for item in scanner.scan(self.root, self.paths)))
                path.write_bytes(original)

    def test_changed_fixture_without_new_tokens_still_requires_review(self) -> None:
        path = self.root / self.paths[0]
        path.write_bytes(path.read_bytes() + b"\n// changed test expectation\n")
        self.assertTrue(scanner.scan(self.root, self.paths))

    def test_missing_or_unlisted_negative_controls_fail_closed(self) -> None:
        for relative in self.paths:
            with self.subTest(path=relative):
                self.assertTrue(scanner.scan(self.root, [p for p in self.paths if p != relative]))
        (self.root / self.paths[0]).unlink()
        self.assertTrue(scanner.scan(self.root, self.paths))

    def test_symlinked_evidence_is_rejected_even_with_identical_bytes(self) -> None:
        path = self.root / self.paths[0]
        copy = self.root / "same-bytes.js"
        copy.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(copy)
        self.assertTrue(scanner.scan(self.root, self.paths))

    def test_oversized_evidence_fails_before_unbounded_read(self) -> None:
        (self.root / self.paths[0]).write_bytes(b"x" * 32_769)
        self.assertTrue(scanner.scan(self.root, self.paths))


if __name__ == "__main__":
    unittest.main()
