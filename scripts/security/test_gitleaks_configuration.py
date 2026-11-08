from __future__ import annotations

import importlib.util
import sys
import tomllib
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = Path(__file__).with_name("gitleaks_allowlist_regression.py")
SPEC = importlib.util.spec_from_file_location("gitleaks_allowlist_regression", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gitleaks_regression = importlib.util.module_from_spec(SPEC)
# Register before execution: dataclasses resolve string annotations via sys.modules.
sys.modules[SPEC.name] = gitleaks_regression
SPEC.loader.exec_module(gitleaks_regression)


class GitleaksConfigurationTests(unittest.TestCase):
    def test_allowlists_are_rule_targeted_and_exact(self) -> None:
        config = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["extend"], {"useDefault": True})
        allowlists = config["allowlists"]
        self.assertEqual(len(allowlists), 3)
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
            [r"^scripts/security/gitleaks_allowlist_regression\.py$"],
        )
        self.assertEqual(
            allowlists[1]["regexes"],
            [r"^key\.curve,\s*ec\.SECP256K1\\n$"],
        )
        # Tightened 2026-11-05 (repair_20261105/SCANNER-ADDRESS-CAPTURE.md):
        # only a complete captured 20-byte address is exempt.
        self.assertEqual(allowlists[2]["regexTarget"], "secret")
        self.assertEqual(
            allowlists[2]["paths"],
            [
                r"^neuron/config\.py$",
                r"^contracts/script/(?:DeployX402|EmergencyLockdown|RegisterAgent)\.s\.sol$",
            ],
        )
        self.assertEqual(allowlists[2]["regexes"], [r"^0x[0-9a-fA-F]{40}$"])

    def test_no_global_stopword_commit_or_path_allowlist_exists(self) -> None:
        text = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
        self.assertNotIn("stopwords", text)
        self.assertNotIn("commits =", text)
        self.assertNotIn("[allowlist]", text)

    def test_regression_scan_uses_scan_root_relative_paths(self) -> None:
        binary = Path("/opt/gitleaks")
        source = Path("fixture-root")
        config = Path("fixture-config.toml")
        report = Path("fixture-report.json")
        # Fixtures always contain blocked secrets, so the scanner must exit 1.
        completed = mock.Mock(stdout=b"", stderr=b"", returncode=1)
        with mock.patch.object(
            gitleaks_regression.subprocess,
            "run",
            return_value=completed,
        ) as run:
            self.assertIsNone(gitleaks_regression.scan(binary, source, config, report))

        command = run.call_args.args[0]
        self.assertEqual(command[:3], [str(binary), "dir", "."])
        self.assertEqual(run.call_args.kwargs["cwd"], source)

    def test_clean_scan_exit_is_not_accepted(self) -> None:
        completed = mock.Mock(stdout=b"", stderr=b"", returncode=0)
        with mock.patch.object(gitleaks_regression.subprocess, "run", return_value=completed):
            with self.assertRaises(gitleaks_regression.InputError):
                gitleaks_regression.scan(Path("/opt/gitleaks"), Path("t"), Path("c"), Path("r"))

    def test_explicit_scanner_path_must_exist(self) -> None:
        missing = ROOT / "missing-gitleaks-binary"
        # A missing explicit path must never fall back to a PATH lookup.
        with mock.patch.dict(
            gitleaks_regression.os.environ,
            {"GITLEAKS_BIN": str(missing)},
        ), mock.patch.object(
            gitleaks_regression.shutil, "which", return_value="/usr/bin/true"
        ):
            with self.assertRaises((gitleaks_regression.InputError, OSError)):
                gitleaks_regression.scanner_binary()


if __name__ == "__main__":
    unittest.main()
