from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.security.secret_history_prevention_scan import scan_paths


class SecretHistoryPreventionScanTests(unittest.TestCase):
    def test_rejects_every_removed_path_class(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = [
                ".foundry",
                ".foundry/bin/forge.exe",
                "node_identity.pem",
                "register-agent.mjs",
                "contracts/clean_output.json",
                "neuron/eth_client/sequence_wallet.py",
                "telegram-bot/bot.js",
            ]
            self.assertEqual(len(scan_paths(root, paths)), len(paths))

    def test_rejects_concrete_uri_but_allows_environment_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad = (
                "postgresql://"
                + "fixture-user"
                + ":"
                + "fixture-pass"
                + "@db.invalid/x"
            )
            (root / "bad.md").write_text(bad, encoding="utf-8")
            (root / "safe.md").write_text(
                "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}/${DB_NAME}",
                encoding="utf-8",
            )
            self.assertEqual(len(scan_paths(root, ["bad.md"])), 1)
            self.assertEqual(scan_paths(root, ["safe.md"]), [])

    def test_rejects_replacement_map_name_and_directive_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            value = (
                "https://" + "fixture" + ":" + "fixture" + "@example.invalid"
            )
            (root / "captured.log").write_text(
                f"literal:{value}==>https://example.invalid", encoding="utf-8"
            )
            findings = scan_paths(root, ["captured.log", "replacements.txt"])
            self.assertEqual(len(findings), 3)
            self.assertNotIn(value, "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
