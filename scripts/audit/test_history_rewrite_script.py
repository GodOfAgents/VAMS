from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
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


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
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

    def test_script_has_no_remote_or_destructive_checkout_commands(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("git push", text)
        self.assertNotIn("git reset --hard", text)
        self.assertNotIn("git clean -fdx", text)
        self.assertNotIn("--force", text)
        self.assertIn("--sensitive-data-removal", text)
        self.assertIn("remote.origin.mirror", text)
        self.assertIn("+refs/*:refs/*", text)
        self.assertIn("NO REMOTE PUSH WAS PERFORMED", text)


if __name__ == "__main__":
    unittest.main()
