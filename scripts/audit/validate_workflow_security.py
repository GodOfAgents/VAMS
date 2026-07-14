#!/usr/bin/env python3
"""Fail CI when workflow actions or security tools use mutable versions."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "security-gates.yml"
OPERATIONAL_WORKFLOW = ROOT / ".github" / "workflows" / "operational-evidence.yml"
AUDIT_PROGRAM = ROOT / "scripts" / "audit" / "audit_program.py"
REQUIRED_SEED = "20260713"
REQUIRED_RAW_GATES = {
    "audit-program",
    "public-content",
    "default-credentials",
    "mock-mode",
    "gitleaks",
    "trufflehog",
    "solidity",
    "slither",
    "aiken",
    "vir-core",
    "python",
    "semgrep",
    "frontend",
    "gateway-config",
    "sbom",
}
POSTGRES_IMAGE = "postgres:16.14-bookworm@sha256:c95fd5346040eba2de3c435e14874af18f5d681fb5848d4f081dbead0878af28"
CADDY_IMAGE = "caddy:2@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d"


def validate() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    operational_text = OPERATIONAL_WORKFLOW.read_text(encoding="utf-8")
    workflow_text = text + "\n" + operational_text
    audit_text = AUDIT_PROGRAM.read_text(encoding="utf-8")
    errors: list[str] = []
    action_refs = re.findall(
        r"^\s*uses:\s*[^@\s]+@([^\s#]+)", workflow_text, re.MULTILINE
    )
    if not action_refs:
        errors.append("security workflow contains no action references")
    for ref in action_refs:
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            errors.append(f"GitHub Action is not commit-pinned: {ref}")
    forbidden = (
        "txpipe/setup-aiken",
        "trufflesecurity/trufflehog@main",
        "version: stable",
        "pip install --upgrade pip",
        "pip install slither-analyzer\n",
        "pip install semgrep\n",
    )
    for value in forbidden:
        if value in workflow_text:
            errors.append(f"security workflow contains mutable tool reference: {value}")

    operational_bindings = {
        "operational target SHA input": r"(?m)^\s{6}target_sha:\s*$",
        "operational exact target checkout": r"ref:\s*\$\{\{\s*inputs\.target_sha\s*\}\}",
        "dedicated evidence runner": r"runs-on:\s*\[self-hosted, linux, x64, vams-testnet-evidence\]",
        "protected evidence environment": r"environment:\s*testnet-operational-evidence",
        "fixed read-only evidence root": r"/var/lib/vams/operational-evidence/\$TARGET_SHA/\$RELEASE_STAGE",
        "operational bundle validator": r"audit_program\.py operational[\s\S]*?--bundle-dir operational-evidence[\s\S]*?--target-sha",
        "operational immutable upload": r"name:\s*operational-evidence-bundle[\s\S]*?retention-days:\s*365",
        "aggregate manifest rejection": r"Operational input must not contain an aggregate evidence manifest",
    }
    for label, pattern in operational_bindings.items():
        if re.search(pattern, operational_text) is None:
            errors.append(f"operational evidence workflow is missing {label}")

    seeds = re.findall(r"--seed\s+([0-9]+)", text)
    seeds.extend(re.findall(r"(?m)^\s*AUDIT_SEED:\s*[\"']?([0-9]+)", text))
    if not seeds:
        errors.append("security workflow contains no deterministic seed")
    elif set(seeds) != {REQUIRED_SEED}:
        errors.append(
            "security workflow seeds must all equal "
            + REQUIRED_SEED
            + ": "
            + ", ".join(sorted(set(seeds)))
        )

    required_bindings = {
        "target_sha workflow_dispatch input": r"(?m)^\s{6}target_sha:\s*$",
        "stage_evidence_run_id workflow_dispatch input": r"(?m)^\s{6}stage_evidence_run_id:\s*$",
        "operational_evidence_run_id workflow_dispatch input": r"(?m)^\s{6}operational_evidence_run_id:\s*$",
        "target SHA checkout": r"ref:\s*\$\{\{\s*inputs\.target_sha\s*\}\}",
        "prior run artifact download": r"run-id:\s*\$\{\{\s*inputs\.stage_evidence_run_id\s*\}\}",
        "operational run artifact download": r"run-id:\s*\$\{\{\s*inputs\.operational_evidence_run_id\s*\}\}",
        "prior run GitHub token": r"github-token:\s*\$\{\{\s*github\.token\s*\}\}",
        "cross-run artifact read permission": r"(?m)^\s{6}actions:\s*read\s*$",
        "manifest bundle binding": r"audit_program\.py manifest[\s\S]*?--bundle-dir stage-evidence[\s\S]*?--target-sha[\s\S]*?--stage-evidence-run-id",
        "readiness bundle binding": r"audit_program\.py readiness[\s\S]*?--bundle-dir docs/audit/evidence/stage-evidence[\s\S]*?--target-sha[\s\S]*?--stage-evidence-run-id",
        "unsigned stage bundle": r"name:\s*stage-evidence-bundle",
        "complete signed bundle upload": r"(?m)^\s{12}stage-evidence/\s*$",
        "prior run target verification": r"\.head_sha[\s\S]*?TARGET_SHA",
        "prior run completion verification": r"\.conclusion[\s\S]*?success",
        "immutable first run attempt": r"\.run_attempt[\s\S]*?==\s*\"1\"",
        "operational evidence artifact name": r"name:\s*operational-evidence-bundle",
        "operational run target verification": r"operational-run\.json[\s\S]*?\.head_sha[\s\S]*?TARGET_SHA",
        "operational run dispatch verification": r"operational-run\.json[\s\S]*?\.event[\s\S]*?workflow_dispatch",
        "exact operational workflow binding": r"operational-run\.json[\s\S]*?\.path[\s\S]*?\.github/workflows/operational-evidence\.yml",
        "operational run manifest binding": r"--operational-evidence-run-id",
        "per-job raw gate artifact download": r"pattern:\s*raw-gate-\*[\s\S]*?merge-multiple:\s*false",
        "TruffleHog sanitized report contract": r"trufflehog-sanitized\.json",
        "pinned PostgreSQL service": re.escape(POSTGRES_IMAGE),
        "PostgreSQL health check": r"pg_isready -U vdso_ci -d vdso_ci",
        "disposable PostgreSQL reset opt-in": r"VDSO_TEST_POSTGRES_ALLOW_RESET:\s*[\"']1[\"']",
    }
    for label, pattern in required_bindings.items():
        if re.search(pattern, text) is None:
            errors.append(f"security workflow is missing {label}")
    if CADDY_IMAGE not in audit_text:
        errors.append("security gate runner is missing pinned Caddy evidence image")

    required_runner_commands = {
        "full-history Gitleaks git scan": (
            "gitleaks git .",
            "--redact=100",
            "--log-opts=--all",
            "--exit-code 1",
        ),
        "all-category TruffleHog git scan": (
            "trufflehog git",
            "--results=verified,unknown,unverified",
            "--json",
            "--fail",
        ),
        "explicit VDSO PostgreSQL integration test": (
            "neuron/tests/test_vdso_postgres_integration.py::test_postgres_atomicity_restart_and_six_figure_state",
        ),
    }
    for label, fragments in required_runner_commands.items():
        if any(fragment not in audit_text for fragment in fragments):
            errors.append(f"security gate runner is missing {label}")

    if "--result " in text:
        errors.append("security workflow must not synthesize result-only manifests")
    for forbidden_value in (
        "gate-artifact",
        "--status ",
        "--only-verified",
        "trufflehog filesystem",
        "gitleaks detect",
        "caddy:latest",
        ' caddy:2 caddy ',
        "cp -a docs/audit/evidence",
    ):
        if forbidden_value in text or forbidden_value in audit_text:
            errors.append(
                "security workflow contains forbidden synthetic or partial scan command: "
                + forbidden_value
            )

    gate_runs = re.findall(r"audit_program\.py run-gate[^\r\n]*--name ([a-z0-9-]+)", text)
    if len(gate_runs) != len(REQUIRED_RAW_GATES) or set(gate_runs) != REQUIRED_RAW_GATES:
        errors.append(
            "security workflow must execute exactly one raw runner for every required gate"
        )
    elif len(gate_runs) != len(set(gate_runs)):
        errors.append("security workflow contains duplicate raw gate runners")
    uploaded_gates = re.findall(r"(?m)^\s+name:\s*raw-gate-([a-z0-9-]+)\s*$", text)
    if len(uploaded_gates) != len(REQUIRED_RAW_GATES) or set(uploaded_gates) != REQUIRED_RAW_GATES:
        errors.append(
            "security workflow must upload one independently named artifact for every raw gate"
        )

    if text.count("git fetch --force --prune origin '+refs/heads/*:refs/remotes/origin/*'") < 2:
        errors.append("both secret scanners must fetch all remote heads before scanning")
    if text.count("git fetch --force --tags origin") < 2:
        errors.append("both secret scanners must fetch all tags before scanning")
    ordered_steps = [
        "- name: Download Complete Prior Stage-Evidence Bundle",
        "- name: Download Post-Freeze Operational Evidence Bundle",
        "- name: Merge Immutable Operational Evidence",
        "- name: Generate Commit-Bound Evidence Manifest",
        "- name: Sign Audit Evidence",
    ]
    positions = [text.find(step) for step in ordered_steps]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append(
            "security workflow must download the complete bundle, bind the manifest, then sign"
        )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Workflow supply-chain validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    action_count = sum(
        len(re.findall(r"uses:", path.read_text(encoding="utf-8")))
        for path in (WORKFLOW, OPERATIONAL_WORKFLOW)
    )
    print(
        "Workflow supply-chain validation passed: "
        f"all {action_count} actions are commit-pinned."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
