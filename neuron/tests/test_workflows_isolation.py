"""Regression tests for workflow-test database isolation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys


WORKFLOW_TEST_MODULE = Path(__file__).with_name("test_workflows.py").resolve()


def test_import_does_not_delete_working_directory_database(tmp_path: Path) -> None:
    sentinel = tmp_path / "dbos_test_workflows.db"
    sentinel.write_bytes(b"VAMS workflow sentinel; preserve exactly\n")
    before = hashlib.sha256(sentinel.read_bytes()).hexdigest()

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(WORKFLOW_TEST_MODULE.parents[2]), env.get("PYTHONPATH"))))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util; "
                f"spec = importlib.util.spec_from_file_location('workflow_tests', {str(WORKFLOW_TEST_MODULE)!r}); "
                "module = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(module)"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert sentinel.is_file()
    assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == before
    assert sentinel.read_bytes() == b"VAMS workflow sentinel; preserve exactly\n"
