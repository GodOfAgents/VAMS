from __future__ import annotations

import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
