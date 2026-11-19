"""Regression for test-module imports and real spawn package resolution."""

from __future__ import annotations

import importlib
import importlib.util
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path
from queue import Empty

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_NEURON_DIR = _REPO_ROOT / "neuron"
_TEST_MODULES = (
    _NEURON_DIR / "tests" / "test_agentos_runtime.py",
    _NEURON_DIR / "tests" / "test_workflows.py",
)


def _spawn_import_worker(output: multiprocessing.Queue) -> None:
    import neuron
    import neuron.runtime_safety

    output.put(
        (
            str(Path(neuron.__file__).resolve()),
            tuple(str(Path(path).resolve()) for path in neuron.__path__),
            str(Path(neuron.runtime_safety.__file__).resolve()),
        )
    )


def _execute_test_module(path: Path) -> None:
    module_name = f"_vams_isolation_probe_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def _run_isolated_probe(output: multiprocessing.Queue) -> None:
    """Keep imported test modules and their dependencies out of the pytest process."""
    assert Path.cwd().resolve() == _REPO_ROOT
    before_path = tuple(sys.path)
    before_environment = dict(os.environ)
    before_cwd = Path.cwd().resolve()

    for path in _TEST_MODULES:
        _execute_test_module(path)
        assert tuple(sys.path) == before_path, f"{path.name} changed sys.path"
        if dict(os.environ) != before_environment:
            raise AssertionError(f"{path.name} changed environment")
        assert Path.cwd().resolve() == before_cwd, f"{path.name} changed cwd"

    # Runtime entrypoint imports must not reintroduce the package-directory
    # shadowing that makes a fresh spawn load neuron.py as the top-level package.
    importlib.import_module("neuron.demo_cli")
    assert tuple(sys.path) == before_path, "demo_cli import changed sys.path"
    if dict(os.environ) != before_environment:
        raise AssertionError("demo_cli import changed environment")
    assert Path.cwd().resolve() == before_cwd, "demo_cli import changed cwd"

    assert not any(
        Path(entry or os.getcwd()).resolve() == _NEURON_DIR for entry in sys.path
    ), "checkout/neuron was inserted into sys.path"

    context = multiprocessing.get_context("spawn")
    child_output = context.Queue()
    child = context.Process(target=_spawn_import_worker, args=(child_output,))
    try:
        child.start()
        child.join(timeout=15)
        assert not child.is_alive(), "spawned import worker exceeded 15 seconds"
        assert child.exitcode == 0, f"spawned import worker exited {child.exitcode}"
        package_origins = child_output.get(timeout=3)
        output.put(package_origins)
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
        if child.is_alive():
            child.kill()
            child.join(timeout=5)
        child_output.close()
        child_output.join_thread()
        child.close()


def test_test_module_imports_preserve_spawn_package_resolution() -> None:
    """Collection imports must leave a real spawned replay worker able to import neuron."""
    assert Path.cwd().resolve() == _REPO_ROOT
    before_path = tuple(sys.path)
    before_environment = dict(os.environ)
    before_cwd = Path.cwd().resolve()

    original_sys_path = list(sys.path)
    output = None
    probe = None
    try:
        sys.path[:] = [
            entry
            for entry in original_sys_path
            if Path(entry or os.getcwd()).resolve() != _NEURON_DIR
        ]
        assert any(
            Path(entry or os.getcwd()).resolve() == _REPO_ROOT for entry in sys.path
        ), "repository root is missing from the effective import path"

        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        probe = context.Process(target=_run_isolated_probe, args=(output,))
        probe.start()
        probe.join(timeout=25)
        assert not probe.is_alive(), "isolated import probe exceeded 25 seconds"
        assert probe.exitcode == 0, f"isolated import probe exited {probe.exitcode}"
        try:
            package_file, package_paths, runtime_file = output.get(timeout=3)
        except Empty:
            raise AssertionError("isolated import probe returned no module origins")
        assert package_file == str((_NEURON_DIR / "__init__.py").resolve())
        assert package_paths == (str(_NEURON_DIR.resolve()),)
        assert runtime_file == str((_NEURON_DIR / "runtime_safety.py").resolve())
    finally:
        try:
            if probe is not None and probe.pid is not None:
                if probe.is_alive():
                    probe.terminate()
                    probe.join(timeout=5)
                if probe.is_alive():
                    probe.kill()
                    probe.join(timeout=5)
                probe.close()
            if output is not None:
                output.close()
                output.join_thread()
        finally:
            sys.path[:] = original_sys_path

    assert tuple(sys.path) == before_path, "probe leaked sys.path state"
    if dict(os.environ) != before_environment:
        raise AssertionError("probe leaked environment state")
    assert Path.cwd().resolve() == before_cwd, "probe leaked cwd state"


@pytest.mark.parametrize(
    "args",
    (("-m", "neuron.demo_cli", "--help"),
     (str(_NEURON_DIR / "demo_cli.py"), "--help")),
    ids=("module", "direct-script"),
)
def test_demo_help_from_external_cwd_exits_before_demo(tmp_path: Path, args: tuple[str, ...]) -> None:
    """Real help execution must succeed in test mode without starting the demo."""
    environment = {
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONPATH": str(_REPO_ROOT),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "VAMS_ENV": "test",
    }
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
    assert "--step" in completed.stdout
    assert "--no-crash" in completed.stdout
