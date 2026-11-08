"""Focused M3.2b-R4 mutation-harness regressions."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/remediation"))
import test_m3_2b_compiled_mutations as harness
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
HARNESS = ROOT / "scripts/remediation/test_m3_2b_compiled_mutations.py"


class MutationHarnessTests(unittest.TestCase):
    def run_harness(self, repetitions: int = 10) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".json") as output:
            run = subprocess.run(
                [
                    "python3",
                    str(HARNESS),
                    "--aiken",
                    str(AIKEN),
                    "--adversarial",
                    "--repetitions",
                    str(repetitions),
                    "--output",
                    output.name,
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/remediation")},
            )
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            return json.loads(Path(output.name).read_text())

    def test_three_way_reachability_is_repeated_and_phase_separated(self) -> None:
        payload = self.run_harness(10)
        self.assertEqual(payload["status"], "detected")
        self.assertEqual(payload["repetition_failures"], [])
        self.assertEqual(len(payload["repetitions"]), 10)
        for result in payload["repetitions"]:
            self.assertEqual(
                result["outcomes"],
                {
                    "valid_original": "accept",
                    "targeted_invalid_original": "reject",
                    "targeted_invalid_mutant": "accept",
                },
            )
            self.assertTrue(result["valid_original"]["public_entrypoint_invoked"])
            self.assertTrue(result["targeted_invalid_mutant"]["public_entrypoint_invoked"])
            self.assertTrue(
                all(
                    result[name]["phase"] == "handler_outcome"
                    for name in (
                        "valid_original",
                        "targeted_invalid_original",
                        "targeted_invalid_mutant",
                    )
                )
            )

    def test_binding_guard_removal_is_rejected(self) -> None:
        original_guard = harness._validate_script_binding
        try:
            harness._validate_script_binding = lambda context, expected: (True, None)
            result = harness.adversarial_cases(AIKEN)
        finally:
            harness._validate_script_binding = original_guard
        self.assertFalse(result["passed"])
        self.assertFalse(result["cases"]["stale_binding_rejected"])
        self.assertFalse(result["cases"]["four_binding_cases"])

    def test_adversarial_harness_mutations_are_rejected(self) -> None:
        payload = self.run_harness(1)
        adversarial = payload["adversarial"]
        self.assertTrue(adversarial["passed"])
        self.assertTrue(all(adversarial["cases"].values()))
        self.assertTrue(adversarial["cases"]["stale_binding_rejected"])
        self.assertTrue(adversarial["cases"]["four_binding_cases"])
        self.assertTrue(payload["program_hash_changed"])
        self.assertNotEqual(
            payload["compiled_sha256_original"],
            payload["compiled_sha256_mutant"],
        )


if __name__ == "__main__":
    unittest.main()
