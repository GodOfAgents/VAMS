from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from scripts.security import trufflehog_gate
from scripts.security.trufflehog_gate import sanitize_event


class TruffleHogGateTests(unittest.TestCase):
    def test_sanitizer_drops_every_candidate_value(self) -> None:
        event = {
            "DetectorName": "FixtureDetector",
            "Verified": False,
            "Raw": "candidate-value",
            "RawV2": "candidate-value-v2",
            "ExtraData": {"token": "candidate-value"},
            "SourceMetadata": {
                "Data": {
                    "Git": {
                        "commit": "a" * 40,
                        "file": "fixture.txt",
                        "line": 7,
                        "repository": "https://example.invalid/repository",
                        "email": "private@example.invalid",
                    }
                }
            },
        }
        sanitized = sanitize_event(event)
        serialized = json.dumps(sanitized)
        self.assertEqual(sanitized["detector"], "FixtureDetector")
        self.assertFalse(sanitized["verified"])
        self.assertEqual(sanitized["file"], "fixture.txt")
        self.assertNotIn("candidate-value", serialized)
        self.assertNotIn("private@example.invalid", serialized)
        self.assertNotIn("Raw", serialized)

    def test_scanner_uses_canonical_file_uri_and_explicit_binary(self) -> None:
        output = Path("sanitized-report.json")
        process = mock.Mock()
        process.stdout = iter(())
        process.wait.return_value = 0
        with (
            mock.patch.object(
                trufflehog_gate,
                "_trufflehog_binary",
                return_value="pinned-trufflehog",
            ),
            mock.patch.object(trufflehog_gate.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(Path, "write_text"),
        ):
            self.assertEqual(trufflehog_gate.run(output), 0)

        command = popen.call_args.args[0]
        self.assertEqual(command[:2], ["pinned-trufflehog", "git"])
        self.assertEqual(command[2], Path.cwd().resolve().as_uri())
        self.assertIn("--no-verification", command)
        self.assertIn("--results=verified,unknown,unverified", command)

    def test_explicit_scanner_path_must_exist(self) -> None:
        with mock.patch.dict(os.environ, {"TRUFFLEHOG_BIN": str(Path("missing"))}):
            self.assertIsNone(trufflehog_gate._trufflehog_binary())


if __name__ == "__main__":
    unittest.main()
