from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "gitleaks_ignore_reproof", Path(__file__).with_name("gitleaks_ignore_reproof.py"))
assert SPEC is not None and SPEC.loader is not None
reproof = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reproof
SPEC.loader.exec_module(reproof)

EVIDENCE = "docs/remediation/fixture_pkg/VECTORS.json"


class GitleaksIgnoreReproofTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="vams-reproof-"))
        self.addCleanup(shutil.rmtree, self.root)
        target = self.root / EVIDENCE
        target.parent.mkdir(parents=True)
        target.write_text('{\n  "synthetic_public_value": "x"\n}\n', encoding="utf-8")
        self.write_manifest([self.record(2)])
        self.write_ignore([f"{EVIDENCE}:generic-api-key:2"])

    def record(self, line, **overrides):
        data = (self.root / EVIDENCE).read_bytes()
        record = {
            "file": EVIDENCE, "line": line, "rule": "generic-api-key",
            "gitleaks_fingerprint": f"{EVIDENCE}:generic-api-key:{line}",
            "file_sha256": hashlib.sha256(data).hexdigest(),
            "disposition": "ACCEPTED_NON_CREDENTIAL", "owner_ruling": "ACCEPTED test",
        }
        record.update(overrides)
        return record

    def write_manifest(self, records):
        path = self.root / reproof.MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"findings": records}), encoding="utf-8")

    def write_ignore(self, entries):
        (self.root / ".gitleaksignore").write_text(
            "# header\n" + "".join(e + "\n" for e in entries), encoding="utf-8")

    def assert_fails(self, reason):
        with self.assertRaisesRegex(reproof.ReproofError, reason):
            reproof.reprove(self.root)

    def test_exact_accepted_entry_passes(self):
        self.assertEqual(reproof.reprove(self.root), 1)

    def test_extra_ignore_entry_fails(self):
        self.write_ignore([f"{EVIDENCE}:generic-api-key:2", f"{EVIDENCE}:generic-api-key:3"])
        self.assert_fails("differ")

    def test_edited_file_invalidates_entries(self):
        (self.root / EVIDENCE).write_text('{\n  "synthetic_public_value": "y"\n}\n', encoding="utf-8")
        self.assert_fails("changed")

    def test_pending_ruling_fails(self):
        self.write_manifest([self.record(2, disposition="PROPOSED_NON_CREDENTIAL")])
        self.assert_fails("accepted owner ruling")

    def test_product_source_path_cannot_be_ignored(self):
        self.write_ignore(["neuron/config.py:generic-api-key:2"])
        self.write_manifest([self.record(2, file="neuron/config.py",
                                         gitleaks_fingerprint="neuron/config.py:generic-api-key:2")])
        self.assert_fails("outside the reviewed scope")

    def test_other_rule_cannot_be_ignored(self):
        self.write_ignore([f"{EVIDENCE}:private-key:2"])
        self.write_manifest([self.record(2, rule="private-key",
                                         gitleaks_fingerprint=f"{EVIDENCE}:private-key:2")])
        self.assert_fails("outside the reviewed scope")

    def test_duplicate_ignore_entry_fails(self):
        self.write_ignore([f"{EVIDENCE}:generic-api-key:2"] * 2)
        self.assert_fails("duplicate")

    def test_missing_file_fails(self):
        (self.root / EVIDENCE).unlink()
        self.assert_fails("missing")

    def test_repository_ignore_file_reproves(self):
        # The committed .gitleaksignore must always reprove on the real tree.
        self.assertEqual(reproof.reprove(ROOT), 638)


if __name__ == "__main__":
    unittest.main()
