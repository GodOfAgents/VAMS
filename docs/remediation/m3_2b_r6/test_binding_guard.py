"""M3.2b-R6 binding-guard focused regressions."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# CI supplies the reviewed native executable; retain the approved local default
# only when no override is set. An invalid explicit selection never falls back.
_configured_aiken = os.environ.get("VAMS_AIKEN_BIN")
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken") if _configured_aiken is None else Path(_configured_aiken)
if _configured_aiken is not None and (not _configured_aiken or not AIKEN.is_absolute()):
    raise ValueError("VAMS_AIKEN_BIN must be a nonempty absolute executable path")
HARNESS_PATH = ROOT / "scripts/remediation/test_m3_2b_compiled_mutations.py"
sys.path.insert(0, str(ROOT / "scripts/remediation"))


def load_harness():
    spec = importlib.util.spec_from_file_location("m3_2b_r6_harness", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BindingGuardTests(unittest.TestCase):
    def test_public_result_has_four_binding_cases_and_stale_rejection(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json") as output:
            run = subprocess.run(
                [
                    "python3",
                    str(HARNESS_PATH),
                    "--aiken",
                    str(AIKEN),
                    "--adversarial",
                    "--repetitions",
                    "10",
                    "--output",
                    output.name,
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/remediation")},
            )
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            payload = json.loads(Path(output.name).read_text())
        self.assertEqual(payload["status"], "detected")
        self.assertEqual(payload["repetition_failures"], [])
        self.assertEqual(len(payload["repetitions"]), 10)
        adversarial = payload["adversarial"]
        self.assertTrue(adversarial["passed"])
        self.assertTrue(adversarial["cases"]["four_binding_cases"])
        self.assertTrue(adversarial["cases"]["stale_binding_rejected"])
        self.assertEqual(
            payload["repetitions"][0]["outcomes"],
            {
                "valid_original": "accept",
                "targeted_invalid_original": "reject",
                "targeted_invalid_mutant": "accept",
            },
        )

    def test_guard_removal_mutation_fails_closed(self) -> None:
        harness = load_harness()
        original_guard = harness._validate_script_binding
        try:
            harness._validate_script_binding = lambda context, expected: (True, None)
            result = harness.adversarial_cases(AIKEN)
        finally:
            harness._validate_script_binding = original_guard
        self.assertFalse(result["passed"])
        self.assertFalse(result["cases"]["stale_binding_rejected"])
        self.assertFalse(result["cases"]["four_binding_cases"])


if __name__ == "__main__":
    unittest.main()
