#!/usr/bin/env python3
"""Capture sanitized Aiken check results from temporary current-source copies."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path("/home/GodOfAgents/code/VAMS-testnet")
CARDANO = ROOT / "cardano"
TOOL = pathlib.Path(
    "/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/"
    "aiken-x86_64-unknown-linux-musl/aiken"
)
OUT = pathlib.Path(__file__).resolve().parent / "RESULT.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory() -> tuple[list[dict[str, str]], str]:
    files = []
    for path in sorted(CARDANO.rglob("*")):
        if not path.is_file() or any(part in {".git", "build"} for part in path.relative_to(CARDANO).parts):
            continue
        rel = path.relative_to(CARDANO).as_posix()
        files.append({"path": rel, "sha256": sha(path.read_bytes())})
    agg = hashlib.sha256()
    for item in files:
        agg.update(item["path"].encode())
        agg.update(b"\0")
        agg.update(item["sha256"].encode())
        agg.update(b"\n")
    return files, agg.hexdigest()


def run(label: str, args: list[str]) -> dict:
    bash_command = (
        "cp -a . /tmp/vams-cardano-check && "
        "cd /tmp/vams-cardano-check && "
        f"{TOOL} {' '.join(args)}"
    )
    command = [
        "bwrap", "--ro-bind", "/", "/", "--tmpfs", "/tmp",
        "--dev-bind", "/dev", "/dev", "--proc", "/proc",
        "--chdir", str(CARDANO), "/bin/bash", "-lc", bash_command,
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    stdout_text = completed.stdout.decode("utf-8", errors="replace")
    stderr_text = completed.stderr.decode("utf-8", errors="replace")
    combined = re.sub(r"\x1b\[[0-9;]*m", "", stdout_text + "\n" + stderr_text)
    start = stdout_text.find("{\n  \"seed\"")
    parsed = False
    summary = {}
    try:
        report, _ = json.JSONDecoder().raw_decode(stdout_text[start:]) if start >= 0 else ({}, 0)
        summary = report.get("summary", {})
        parsed = start >= 0
    except json.JSONDecodeError:
        pass
    diagnostic_lines = sorted({
        line.strip()
        for line in combined.splitlines()
        if re.search(r"\b(warning|warn|uncertain|error|deny|deprecated)\b", line, re.IGNORECASE)
    })
    warning_lines = [line for line in diagnostic_lines if re.search(r"warning|warn|uncertain", line, re.IGNORECASE)]
    return {
        "label": label,
        "command": ["aiken", *args],
        "exit_code": completed.returncode,
        "report_parse_ok": parsed,
        "summary": summary,
        "warning_count": len(warning_lines) if warning_lines else None,
        "warning_lines": warning_lines[:32],
        "warning_capture_note": (
            "No warning lines were extracted from ANSI-stripped machine-mode pipe output; exact count/text are not asserted."
            if not warning_lines else None
        ),
        "diagnostic_lines": diagnostic_lines[:64],
        "stdout_sha256": sha(completed.stdout),
        "stderr_sha256": sha(completed.stderr),
        "raw_output_retained": False,
    }


def main() -> int:
    files, source_hash = inventory()
    results = [
        run("workflow_gate", ["check", "--deny", "--seed", "20260711", "--max-success", "250"]),
        run("without_deny_diagnostic", ["check", "--seed", "20260711", "--max-success", "250"]),
    ]
    result = {
        "schema": "m7-aiken-check-sanitized-v1",
        "outer_isolation": "Canonical Cardano tree read-only; fresh temporary copy writable; network available for Aiken project dependency resolution; no tools fetched.",
        "source_file_count": len(files),
        "aiken_source_count": sum(item["path"].endswith(".ak") for item in files),
        "source_tree_sha256": source_hash,
        "source_files": files,
        "tool": {
            "path": str(TOOL),
            "version": "v1.1.21+42babe5",
            "sha256": sha(TOOL.read_bytes()),
        },
        "results": results,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if all(item["report_parse_ok"] for item in results) else 2


if __name__ == "__main__":
    sys.exit(main())
