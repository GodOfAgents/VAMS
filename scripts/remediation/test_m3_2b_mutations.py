#!/usr/bin/env python3
"""M3.2b-R4 compiled public-row and mutation inventory gate."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/remediation/m3_2a_r7"
AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")


def _run_json(command: list[str]) -> tuple[int, dict]:
    with tempfile.NamedTemporaryFile(suffix=".json") as out:
        run = subprocess.run(
            [*command, "--output", out.name],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/remediation")},
        )
        payload = json.loads(Path(out.name).read_text()) if Path(out.name).stat().st_size else {}
    return run.returncode, payload


def main() -> int:
    matrix = json.loads((SPEC / "ACCEPTANCE_MATRIX.json").read_text())
    topology = json.loads((SPEC / "TRANSITION_TOPOLOGY.json").read_text())
    rows = matrix["rows"]
    mutations = [r["mutation_id"] for r in rows if r["mutation_id"] != "none"]
    if len(mutations) != len(set(mutations)):
        raise AssertionError("duplicate mutation identifiers in frozen matrix")
    if len(topology["transitions"]) != 9:
        raise AssertionError("transition topology is not the frozen nine-transition graph")
    source = (ROOT / "cardano/validators/timelock.ak").read_text()
    if "ExecuteIntent" not in source or "False" not in source:
        raise AssertionError("pre-F05 ExecuteIntent rejection is not visible")
    rows_exit, rows_payload = _run_json(
        ["python3", str(ROOT / "scripts/remediation/test_m3_2b_compiled_rows.py"), "--aiken", str(AIKEN)]
    )
    mutation_exit, mutation_payload = _run_json(
        [
            "python3",
            str(ROOT / "scripts/remediation/test_m3_2b_compiled_mutations.py"),
            "--aiken",
            str(AIKEN),
            "--adversarial",
        ]
    )
    if (
        rows_exit != 0
        or rows_payload.get("executed") != 36
        or rows_payload.get("pending") != 0
        or rows_payload.get("failed")
        or mutation_exit != 0
        or mutation_payload.get("status") != "detected"
        or mutation_payload.get("repetition_failures")
        or not mutation_payload.get("adversarial", {}).get("passed")
    ):
        raise AssertionError("compiled public-handler or mutation evaluator failed")
    print(
        json.dumps(
            {
                "matrix_mutations": len(mutations),
                "transitions": len(topology["transitions"]),
                "execute_disabled": True,
                "compiled_public_handler_rows": rows_payload.get("executed"),
                "compiled_mutation_repetitions": len(mutation_payload.get("repetitions", [])),
                "compiled_mutations": mutation_payload.get("status"),
                "adversarial": mutation_payload.get("adversarial", {}).get("passed"),
                "status": "mutation-evaluator-pass",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
