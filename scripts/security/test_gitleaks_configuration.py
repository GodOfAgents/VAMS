from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class GitleaksConfigurationTests(unittest.TestCase):
    def test_allowlists_are_rule_targeted_and_exact(self) -> None:
        config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["extend"], {"useDefault": True})
        allowlists = config["allowlists"]
        self.assertEqual(len(allowlists), 2)
        for allowlist in allowlists:
            self.assertEqual(allowlist["targetRules"], ["generic-api-key"])
            self.assertEqual(allowlist["condition"], "AND")
        self.assertEqual(allowlists[0]["regexTarget"], "line")
        self.assertEqual(allowlists[0]["paths"], [r"^neuron/secp256k1\.py$"])
        self.assertEqual(
            allowlists[0]["regexes"],
            [r"^\s*key\.curve,\s*ec\.SECP256K1\s*$"],
        )
        self.assertEqual(allowlists[1]["regexTarget"], "match")
        self.assertEqual(
            allowlists[1]["paths"],
            [
                r"^neuron/config\.py$",
                r"^contracts/script/(?:DeployX402|EmergencyLockdown|RegisterAgent)\.s\.sol$",
            ],
        )
        self.assertEqual(allowlists[1]["regexes"], [r"0x[0-9a-fA-F]{40}"])

    def test_no_global_stopword_commit_or_path_allowlist_exists(self) -> None:
        text = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
        self.assertNotIn("stopwords", text)
        self.assertNotIn("commits =", text)
        self.assertNotIn("[allowlist]", text)


if __name__ == "__main__":
    unittest.main()
