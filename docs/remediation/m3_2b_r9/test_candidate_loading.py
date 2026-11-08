"""M3.2b-R9 candidate-module isolation regressions."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docs.remediation.m3_2b_r8 import test_classification as r8


class CandidateIsolationTests(unittest.TestCase):
    def _constant_candidate(self, root: Path) -> Path:
        source = r8.HARNESS.read_text()
        anchor = "    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)"
        replacement = "    return MutationClassification.DETECTED\n    try:\n        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)"
        self.assertEqual(source.count(anchor), 1)
        candidate = root / "candidate" / "renamed_classifier.py"
        candidate.parent.mkdir()
        candidate.write_text(source.replace(anchor, replacement, 1))
        compile_run = subprocess.run(
            ["python3", "-m", "py_compile", str(candidate)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(compile_run.returncode, 0, compile_run.stderr)
        self.assertNotEqual(
            hashlib.sha256(candidate.read_bytes()).hexdigest(),
            hashlib.sha256(r8.HARNESS.read_bytes()).hexdigest(),
        )
        return candidate

    def test_constant_candidate_is_loaded_by_path_and_hash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m3-2b-r9-candidate-") as td:
            candidate = self._constant_candidate(Path(td))
            module = r8.load_candidate(candidate, require_mutation=True)
            try:
                metadata = module._candidate_metadata
                self.assertEqual(Path(metadata["requested_path"]), candidate.resolve())
                self.assertEqual(Path(metadata["loaded_path"]), candidate.resolve())
                self.assertEqual(
                    metadata["candidate_sha256"],
                    hashlib.sha256(candidate.read_bytes()).hexdigest(),
                )
                self.assertNotEqual(metadata["candidate_sha256"], metadata["canonical_sha256"])
                self.assertEqual(
                    module.classify_mutation(dict(r8.TRUTH_TABLE[1][1])).value,
                    "detected",
                )
            finally:
                sys.modules.pop(metadata["module_name"], None)

    def test_canonical_and_constant_candidate_cover_every_hard_coded_row(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m3-2b-r9-table-") as td:
            candidate = self._constant_candidate(Path(td))
            canonical = r8.load_candidate(r8.HARNESS)
            mutated = r8.load_candidate(candidate, require_mutation=True)
            try:
                for name, record, expected in r8.TRUTH_TABLE:
                    with self.subTest(name=name):
                        self.assertEqual(canonical.classify_mutation(record).value, expected)
                        observed = mutated.classify_mutation(record).value
                        if expected == "detected":
                            self.assertEqual(observed, "detected")
                        else:
                            self.assertNotEqual(observed, expected)
            finally:
                sys.modules.pop(canonical._candidate_metadata["module_name"], None)
                sys.modules.pop(mutated._candidate_metadata["module_name"], None)

    def test_renamed_candidate_and_poisoned_imports_cannot_redirect_loader(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m3-2b-r9-poison-") as td:
            root = Path(td)
            candidate = self._constant_candidate(root)
            moved = root / "moved" / "different_name.py"
            moved.parent.mkdir()
            candidate.rename(moved)
            poison = root / "poison"
            poison.mkdir()
            (poison / "test_m3_2b_compiled_mutations.py").write_text(
                "def classify_mutation(_):\n    return 'poisoned'\n"
            )
            stale_name = "test_m3_2b_compiled_mutations"
            sys.modules[stale_name] = object()
            old_path = os.environ.get("PYTHONPATH")
            try:
                os.environ["PYTHONPATH"] = f"{poison}:{r8.ROOT / 'scripts/remediation'}"
                module = r8.load_candidate(moved, require_mutation=True)
                try:
                    self.assertEqual(Path(module.__file__).resolve(), moved.resolve())
                    self.assertEqual(
                        module.classify_mutation(dict(r8.TRUTH_TABLE[1][1])).value,
                        "detected",
                    )
                finally:
                    sys.modules.pop(module._candidate_metadata["module_name"], None)
            finally:
                sys.modules.pop(stale_name, None)
                if old_path is None:
                    os.environ.pop("PYTHONPATH", None)
                else:
                    os.environ["PYTHONPATH"] = old_path

    def test_candidate_cli_is_sanitized_and_noncanonical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m3-2b-r9-cli-") as td:
            candidate = self._constant_candidate(Path(td))
            record = dict(r8.TRUTH_TABLE[1][1])
            raw = Path(td) / "facts.json"
            raw.write_text(json.dumps(record))
            run = subprocess.run(
                ["python3", str(candidate), "--classify-facts", str(raw)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(r8.ROOT / "scripts/remediation"),
                },
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout), {"classification": "detected", "status": "detected"})
            self.assertNotIn(str(raw), run.stdout)


if __name__ == "__main__":
    unittest.main()
