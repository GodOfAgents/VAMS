from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "history_rewrite.sh"
EXPECTED_ORIGIN = "https://github.com/GodOfAgents/VAMS.git"


def _bash() -> str:
    candidates: list[str | None] = []
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files\Git\usr\bin\bash.exe",
            ]
        )
    candidates.append(shutil.which("bash"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise unittest.SkipTest("Bash is unavailable")


def _run(
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _git(*args: str, cwd: Path | None = None) -> str:
    result = _run("git", *args, cwd=cwd)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class HistoryRewriteScriptTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        source = root / "source"
        mirror = root / "mirror.git"
        source.mkdir()
        _git("init", "--initial-branch=main", cwd=source)
        _git("config", "user.name", "VAMS Test", cwd=source)
        _git("config", "user.email", "test@invalid.example", cwd=source)
        (source / "README.md").write_text("safe fixture\n", encoding="utf-8")
        _git("add", "README.md", cwd=source)
        _git("commit", "-m", "test fixture", cwd=source)
        _git("clone", "--mirror", str(source), str(mirror), cwd=root)
        _git("remote", "set-url", "origin", EXPECTED_ORIGIN, cwd=mirror)
        return source, mirror

    def test_inventory_accepts_only_mirror_and_does_not_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            evidence = root / "evidence"
            before = _git("rev-parse", "refs/heads/main", cwd=mirror)

            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                evidence.as_posix(),
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No history was changed", result.stdout)
            self.assertEqual(before, _git("rev-parse", "refs/heads/main", cwd=mirror))
            self.assertTrue((evidence / "pre-refs.tsv").is_file())
            self.assertTrue((evidence / "pre-target-paths.tsv").is_file())
            self.assertTrue((evidence / "evidence-sha256.txt").is_file())
            self.assertFalse((evidence / "post-refs.tsv").exists())

    def test_rejects_working_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _ = self._fixture(root)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                source.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bare mirror clone", result.stderr)

    def test_rejects_wrong_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            _git("remote", "set-url", "origin", "https://example.invalid/not-vams.git", cwd=mirror)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("origin does not match", result.stderr)

    def test_rejects_evidence_inside_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            evidence = Path(tempfile.mkdtemp(prefix=".history-evidence-", dir=ROOT))
            try:
                result = _run(
                    _bash(),
                    SCRIPT.as_posix(),
                    "--mirror",
                    mirror.as_posix(),
                    "--evidence-dir",
                    evidence.as_posix(),
                    cwd=ROOT,
                )
            finally:
                shutil.rmtree(evidence, ignore_errors=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the source checkout", result.stderr)

    def test_execute_requires_external_rotation_and_approval_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            before = _git("rev-parse", "refs/heads/main", cwd=mirror)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sanitized rotation evidence is required", result.stderr)
            self.assertEqual(before, _git("rev-parse", "refs/heads/main", cwd=mirror))

    def test_execute_requires_external_replacement_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            rotation = root / "rotation.json"
            approval = root / "approval.json"
            rotation.write_text('{"status":"decommissioned"}', encoding="utf-8")
            approval.write_text('{"approved":true}', encoding="utf-8")
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-empty --replace-text", result.stderr)

    def test_execute_rejects_empty_replacement_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            rotation = root / "rotation.json"
            approval = root / "approval.json"
            replacement = root / "replacements.txt"
            rotation.write_text('{"status":"decommissioned"}', encoding="utf-8")
            approval.write_text('{"approved":true}', encoding="utf-8")
            replacement.write_text(
                "literal:fixture-source==>\n", encoding="utf-8"
            )
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "non-empty source and replacement values", result.stderr
            )

    def test_rejects_execution_inputs_inside_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--rotation-evidence",
                SCRIPT.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the source checkout", result.stderr)

    def test_rejects_replacement_map_inside_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            evidence = root / "evidence"
            evidence.mkdir()
            replacement = evidence / "replacements.txt"
            replacement.write_text(
                "literal:fixture-source==>fixture-target\n", encoding="utf-8"
            )
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                evidence.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the evidence directory", result.stderr)

    def test_script_has_no_remote_or_destructive_checkout_commands(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("git push", text)
        self.assertNotIn("git reset --hard", text)
        self.assertNotIn("git clean -fdx", text)
        self.assertNotIn("--force", text)
        self.assertIn("--sensitive-data-removal", text)
        self.assertIn("remote.origin.mirror", text)
        self.assertIn("+refs/*:refs/*", text)
        self.assertIn("--replace-text", text)
        self.assertIn("replacement_map_sha256", text)
        self.assertIn("NO REMOTE PUSH WAS PERFORMED", text)

    def test_execute_rewrites_targets_and_rehearses_only_local_mirror_push(self) -> None:
        if _run("git", "filter-repo", "-h", cwd=ROOT).returncode != 0:
            self.skipTest("git-filter-repo is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, mirror = self._fixture(root)
            shutil.rmtree(mirror)
            (source / ".foundry").mkdir()
            (source / ".foundry" / "fixture.txt").write_text(
                "vendored fixture\n", encoding="utf-8"
            )
            (source / "node_identity.pem").write_text(
                "fixture identity marker\n", encoding="utf-8"
            )
            old_uri = (
                "https://" + "fixture-user" + ":" + "fixture-pass" + "@example.invalid"
            )
            (source / "uri.txt").write_text(old_uri + "\n", encoding="utf-8")
            _git("add", ".", cwd=source)
            _git("commit", "-m", "add rewrite targets", cwd=source)
            _git("clone", "--mirror", str(source), str(mirror), cwd=root)
            _git("remote", "set-url", "origin", EXPECTED_ORIGIN, cwd=mirror)

            rotation = root / "rotation.json"
            approval = root / "approval.json"
            replacement = root / "replacements.txt"
            evidence = root / "evidence"
            rotation.write_text('{"status":"decommissioned"}', encoding="utf-8")
            approval.write_text('{"approved":true}', encoding="utf-8")
            replacement.write_text(
                f"literal:{old_uri}==>https://example.invalid\n", encoding="utf-8"
            )
            env = os.environ.copy()
            env["PYTHON_BIN"] = sys.executable
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                evidence.as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(_git("log", "--all", "--format=%H", "--", ".foundry", cwd=mirror), "")
            self.assertEqual(
                _git("log", "--all", "--format=%H", "--", "node_identity.pem", cwd=mirror),
                "",
            )
            combined_evidence = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in evidence.iterdir()
                if path.is_file()
            )
            self.assertNotIn(old_uri, combined_evidence)
            self.assertIn("replacement_map_sha256=", combined_evidence)
            self.assertTrue((evidence / "git-fsck.txt").is_file())

            local_remote = root / "local-rehearsal.git"
            _git("init", "--bare", str(local_remote), cwd=root)
            _git("push", "--mirror", str(local_remote), cwd=mirror)
            self.assertEqual(
                _git("for-each-ref", "--format=%(refname) %(objectname)", cwd=mirror),
                _git(
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                    cwd=local_remote,
                ),
            )


if __name__ == "__main__":
    unittest.main()
