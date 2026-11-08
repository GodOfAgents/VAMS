"""Regression tests for package-safe imports from the Neuron entry module."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PACKAGE = REPOSITORY_ROOT / "neuron" / "__init__.py"
EXPECTED_ENTRY_MODULE = REPOSITORY_ROOT / "neuron" / "neuron.py"
EXPECTED_GATEWAY_SERVER = REPOSITORY_ROOT / "neuron" / "gateway" / "server.py"


def _isolated_environment(home: Path) -> dict[str, str]:
    """Pass only the paths and locale needed by the pinned Python runtime."""
    return {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.defpath,
        "PYTHONPATH": str(REPOSITORY_ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "VAMS_ENV": "test",
        "NEURON_MOCK_MODE": "true",
    }


def _assert_import_origins(result: dict[str, object]) -> None:
    assert Path(str(result["neuron"])).resolve() == EXPECTED_PACKAGE
    assert Path(str(result["entry"])).resolve() == EXPECTED_ENTRY_MODULE
    assert Path(str(result["gateway"])).resolve() == EXPECTED_GATEWAY_SERVER
    assert result["sys_path_before"] == result["sys_path_after"]


def test_package_import_from_external_cwd_uses_canonical_gateway(tmp_path: Path) -> None:
    runner = textwrap.dedent(
        """
        import json
        import sys

        sys_path_before = list(sys.path)
        import neuron
        import neuron.neuron
        sys_path_after = list(sys.path)

        from neuron.neuron import VamsNeuron
        import neuron.gateway.server

        instance = VamsNeuron(
            mock_mode=True,
            environ={"VAMS_ENV": "test", "NEURON_MOCK_MODE": "true"},
        )
        assert isinstance(instance, VamsNeuron)
        assert instance.mock_mode is True
        assert instance.runtime_policy.mode.value == "test"

        print(json.dumps({
            "neuron": neuron.__file__,
            "entry": neuron.neuron.__file__,
            "gateway": neuron.gateway.server.__file__,
            "sys_path_before": sys_path_before,
            "sys_path_after": sys_path_after,
        }))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", runner],
        cwd=tmp_path,
        env=_isolated_environment(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    print(f"package probe rc={completed.returncode}\nstdout={completed.stdout!r}\nstderr={completed.stderr!r}")
    assert completed.returncode == 0, completed.stderr
    _assert_import_origins(json.loads(completed.stdout.splitlines()[-1]))


def test_spawned_child_keeps_package_import_origins_and_is_reaped(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "spawn_import_probe.py"
    runner.write_text(
        textwrap.dedent(
            """
            import json
            import multiprocessing
            import sys

            sys_path_before = list(sys.path)
            import neuron
            import neuron.neuron
            sys_path_after = list(sys.path)

            from neuron.neuron import VamsNeuron
            import neuron.gateway.server


            def reap_child(process):
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                assert not process.is_alive(), "spawned import probe could not be reaped"


            def report_origins(result_queue):
                import neuron.gateway.server as child_gateway
                import neuron as child_neuron
                import neuron.neuron as child_entry
                from neuron.neuron import VamsNeuron as ChildVamsNeuron

                result_queue.put({
                    "neuron": child_neuron.__file__,
                    "entry": child_entry.__file__,
                    "gateway": child_gateway.__file__,
                    "vams_neuron_module": ChildVamsNeuron.__module__,
                    "sys_path_before": sys_path_before,
                    "sys_path_after": sys_path_after,
                })


            if __name__ == "__main__":
                context = multiprocessing.get_context("spawn")
                result_queue = context.Queue()
                child = context.Process(target=report_origins, args=(result_queue,))
                try:
                    child.start()
                    child.join(timeout=20)
                    reap_child(child)
                    if child.exitcode != 0:
                        raise RuntimeError(
                            "spawned import probe exited with " + str(child.exitcode)
                        )
                    origins = result_queue.get(timeout=5)
                    print(json.dumps({
                        "child_exit": child.exitcode,
                        "origins": origins,
                    }))
                finally:
                    try:
                        reap_child(child)
                    finally:
                        try:
                            result_queue.close()
                        finally:
                            try:
                                result_queue.join_thread()
                            finally:
                                assert not child.is_alive(), (
                                    "spawned import probe remained alive during cleanup"
                                )
                                child.close()
            """
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(runner)],
        cwd=tmp_path,
        env=_isolated_environment(tmp_path),
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )

    print(f"spawn probe rc={completed.returncode}\nstdout={completed.stdout!r}\nstderr={completed.stderr!r}")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.splitlines()[-1])
    assert result["child_exit"] == 0
    assert result["origins"]["vams_neuron_module"] == "neuron.neuron"
    _assert_import_origins(result["origins"])


def test_direct_script_help_works_from_external_cwd(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(EXPECTED_ENTRY_MODULE), "--help"],
        cwd=tmp_path,
        env=_isolated_environment(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    print(f"direct-script probe rc={completed.returncode}\nstdout={completed.stdout!r}\nstderr={completed.stderr!r}")
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
    assert "--full-health" in completed.stdout
