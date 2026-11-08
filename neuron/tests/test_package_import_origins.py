"""Focused package-origin and entry-point regressions for Neuron."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEURON = ROOT / "neuron"
EXPECTED = {
    "neuron.neuron": NEURON / "neuron.py",
    "neuron.storage.local": NEURON / "storage" / "local.py",
    "neuron.economic.circuit_breaker": NEURON / "economic" / "circuit_breaker.py",
    "neuron.payments.x402": NEURON / "payments" / "x402.py",
    "neuron.payments.payment_channel": NEURON / "payments" / "payment_channel.py",
    "neuron.gateway.server": NEURON / "gateway" / "server.py",
    "neuron.workflows": NEURON / "workflows.py",
    "neuron.providers": NEURON / "providers.py",
    "neuron.sdk.semantic_mmu": NEURON / "sdk" / "semantic_mmu.py",
}


def _env(home: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.defpath,
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "VAMS_ENV": "test",
        "NEURON_MOCK_MODE": "true",
        "X402_MOCK_MODE": "true",
        "PAYMENT_CHANNEL_MOCK_MODE": "true",
    }


def _runner() -> str:
    return textwrap.dedent(
        r"""
        import importlib, json, multiprocessing, sys
        from pathlib import Path

        names = (
            "neuron.neuron", "neuron.storage.local",
            "neuron.economic.circuit_breaker", "neuron.payments.x402",
            "neuron.payments.payment_channel", "neuron.gateway.server",
            "neuron.workflows", "neuron.providers", "neuron.sdk.semantic_mmu",
        )
        root = Path(sys.argv[1]).resolve()
        neuron_root = root / "neuron"
        legacy = {"config", "economic", "intelligence", "payments", "sdk", "storage"}

        def inspect_imports():
            before = tuple(sys.path)
            modules = {name: importlib.import_module(name) for name in names}
            origins = {name: str(Path(mod.__file__).resolve()) for name, mod in modules.items()}
            assert tuple(sys.path) == before, "package imports changed sys.path"
            for name in legacy:
                origin = getattr(sys.modules.get(name), "__file__", None)
                if origin:
                    assert neuron_root not in Path(origin).resolve().parents, (
                        f"legacy alias {name} resolves into neuron: {origin}"
                    )
            public = {
                "neuron.neuron": "VamsNeuron",
                "neuron.storage.local": "NeuronStorage",
                "neuron.economic.circuit_breaker": "CircuitBreaker",
                "neuron.payments.x402": "X402Client",
                "neuron.payments.payment_channel": "PaymentChannelManager",
                "neuron.gateway.server": "app",
                "neuron.workflows": "run_demo_workflow",
                "neuron.providers": "CelestiaProvider",
                "neuron.sdk.semantic_mmu": "SemanticMMU",
            }
            for module, symbol in public.items():
                assert hasattr(modules[module], symbol), f"{module}.{symbol} missing"

            # Exercise lazy imports only; no provider methods or network calls.
            provider = modules["neuron.providers"].CelestiaProvider(
                rpc_url="http://127.0.0.1:9", use_sdk=True
            )
            assert provider.use_sdk
            assert provider._sdk.__class__.__module__ == "neuron.sdk.celestia"
            mmu = modules["neuron.sdk.semantic_mmu"].SemanticMMU()
            assert isinstance(mmu, modules["neuron.sdk.semantic_mmu"].SemanticMMU)
            assert tuple(sys.path) == before, "lazy imports changed sys.path"
            return {"origins": origins, "before": list(before), "after": list(sys.path)}

        def worker(queue):
            queue.put(inspect_imports())

        if __name__ == "__main__":
            parent = inspect_imports()
            ctx = multiprocessing.get_context("spawn")
            queue = ctx.Queue()
            process = ctx.Process(target=worker, args=(queue,))
            try:
                process.start()
                process.join(timeout=20)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                assert not process.is_alive(), "spawn worker was not reaped"
                assert process.exitcode == 0, f"spawn child exit {process.exitcode}"
                child = queue.get(timeout=5)
                print(json.dumps({"parent": parent, "child": child, "child_exit": process.exitcode}))
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                queue.close()
                queue.join_thread()
                assert not process.is_alive(), "spawn child remained alive"
                process.close()
        """
    )


def _assert_report(report: dict[str, object]) -> None:
    assert report["before"] == report["after"]
    origins = report["origins"]
    assert isinstance(origins, dict)
    for name, expected in EXPECTED.items():
        assert Path(str(origins[name])).resolve() == expected.resolve()


def test_package_and_lazy_imports_from_external_cwd_use_expected_origins(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "package_probe.py"
    runner.write_text(_runner(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(runner), str(ROOT)],
        cwd=tmp_path,
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    print(f"package/spawn probe rc={result.returncode}\nstdout={result.stdout!r}\nstderr={result.stderr!r}")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.splitlines()[-1])
    _assert_report(report["parent"])
    _assert_report(report["child"])
    assert report["child_exit"] == 0


@pytest.mark.parametrize(
    "args",
    (("-m", "neuron.neuron", "--help"), (str(NEURON / "neuron.py"), "--help")),
    ids=("module", "direct-script"),
)
def test_supported_invocations_work_from_external_cwd(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=tmp_path,
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    print(f"invocation {args[0]} rc={result.returncode}\nstdout={result.stdout!r}\nstderr={result.stderr!r}")
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "--full-health" in result.stdout
