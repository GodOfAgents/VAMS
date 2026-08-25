from __future__ import annotations

import importlib.util
import tomllib
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = Path(__file__).with_name("gitleaks_allowlist_regression.py")
SPEC = importlib.util.spec_from_file_location("gitleaks_allowlist_regression", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gitleaks_regression = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gitleaks_regression)


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

    def test_regression_scan_uses_scan_root_relative_paths(self) -> None:
        source = Path("fixture-root")
        report = Path("fixture-report.json")
        completed = mock.Mock()
        with mock.patch.object(
            gitleaks_regression.subprocess,
            "run",
            return_value=completed,
        ) as run:
            self.assertIs(gitleaks_regression._run(source, report), completed)

        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["gitleaks", "dir", "."])
        self.assertEqual(run.call_args.kwargs["cwd"], source)

    def test_explicit_scanner_path_must_exist(self) -> None:
        missing = ROOT / "missing-gitleaks-binary"
        with mock.patch.dict(
            gitleaks_regression.os.environ,
            {"GITLEAKS_BIN": str(missing)},
        ):
            self.assertIsNone(gitleaks_regression._gitleaks_binary())


if __name__ == "__main__":
    unittest.main()
