#!/usr/bin/env python3
"""Fail CI when workflow actions or security tools use mutable versions."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "security-gates.yml"
TRUFFLEHOG_GATE = ROOT / "scripts" / "security" / "trufflehog_gate.py"
REQUIRED_GITLEAKS_HISTORY_COMMAND = (
    'gitleaks git --log-opts="--all -m" . --config .gitleaks.toml '
    '--redact=100 --report-format json '
    '--report-path raw-gate/gitleaks-report.json --exit-code 1'
)
FRONTEND_TEST_COMMAND = "npm test"
FRONTEND_BUILD_COMMAND = "npm run build"
FRONTEND_BUNDLE_SCAN_COMMAND = "npm run scan:bundle"
PYTHON_AIKEN_SETUP = (
    "      - name: Setup Pinned Aiken For Python Regressions\n"
    "        uses: aiken-lang/setup-aiken@1728a4be43be099752e22d8b841706caaa6fdd88 # v1\n"
    "        with:\n"
    "          version: 'v1.1.21'"
)
PYTHON_TEST_RUN = "\n".join((
    "set -euo pipefail",
    'VAMS_AIKEN_BIN="$(command -v aiken)"',
    '[[ "$VAMS_AIKEN_BIN" = /* && -f "$VAMS_AIKEN_BIN" && -x "$VAMS_AIKEN_BIN" ]]',
    'echo "07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79  $VAMS_AIKEN_BIN" | sha256sum --check --strict',
    'test "$("$VAMS_AIKEN_BIN" --version)" = \'aiken v1.1.21+42babe5\'',
    "export VAMS_AIKEN_BIN",
    'VAMS_ENVOY_BIN="$RUNNER_TEMP/envoy" pytest -v --tb=short --ignore=docs/remediation/m3_f05_design_r2/test_design.py',
    'VAMS_ENVOY_BIN="$RUNNER_TEMP/envoy" pytest -v --tb=short docs/remediation/m3_f05_design_r2/test_design.py',
))
READINESS_AUDIT_VERIFY_RUN = "\n".join((
    "cosign verify-blob \\",
    '  --bundle "$RUNNER_TEMP/vams-audit-evidence/audit-evidence.sigstore.json" \\',
    "  --certificate-identity-regexp '^https://github.com/GodOfAgents/VAMS/.github/workflows/security-gates.yml@refs/.+$' \\",
    "  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \\",
    '  "$RUNNER_TEMP/vams-audit-evidence/audit-evidence.json"',
))
READINESS_AUDIT_RUN = "\n".join((
    "python scripts/audit/audit_program.py readiness \\",
    '  --stage "$RELEASE_STAGE" \\',
    '  --evidence-manifest "$RUNNER_TEMP/vams-audit-evidence/audit-evidence.json" \\',
    '  --evidence-signature-bundle "$RUNNER_TEMP/vams-audit-evidence/audit-evidence.sigstore.json"',
))
FRONTEND_STEP_CONTRACTS = (
    ("Install Dependencies", "dependency installation", "npm ci"),
    ("Run Frontend Telemetry Security Tests", "frontend telemetry/security test", FRONTEND_TEST_COMMAND),
    ("Build Verification", "frontend production build", FRONTEND_BUILD_COMMAND),
    ("Scan Production Bundle", "frontend production-bundle scan", FRONTEND_BUNDLE_SCAN_COMMAND),
)
SECRET_SCANNER_RESULT_CONTRACTS = (
    (
        "secret-scanning",
        "Gitleaks",
        "Run Complete-History GitLeaks",
        "gitleaks_scan",
        "Upload GitLeaks Raw Gate Evidence",
        "Enforce GitLeaks Result",
    ),
    (
        "trufflehog-scanning",
        "TruffleHog",
        "Run Complete-History All-Category TruffleHog",
        "trufflehog_scan",
        "Upload TruffleHog Sanitized Gate Evidence",
        "Enforce TruffleHog Result",
    ),
)

REQUIRED_ACTION_PINS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
}


def validate() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    return validate_workflow_text(text)


def _job_section(text: str, job_name: str) -> str:
    match = re.search(rf"^  {re.escape(job_name)}:\n", text, re.MULTILINE)
    if not match:
        return ""
    remainder = text[match.end():]
    next_job = re.search(r"^  [a-z0-9][a-z0-9-]*:\n", remainder, re.MULTILINE)
    return remainder[: next_job.start() if next_job else len(remainder)]


def _active_lines(section: str) -> list[str]:
    return [line.split("#", 1)[0].rstrip() for line in section.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _named_steps(job_section: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^      - name:\s*(.+?)\s*$", job_section, re.MULTILINE))
    return [
        (
            match.group(1),
            job_section[
                match.start():
                matches[index + 1].start() if index + 1 < len(matches) else len(job_section)
            ],
        )
        for index, match in enumerate(matches)
    ]


def _step_properties(step_block: str) -> tuple[str, ...]:
    return tuple(re.findall(r"^        ([a-z][a-z0-9-]*):", step_block, re.MULTILINE))


def _step_run_value(step_block: str) -> str | None:
    marker = "        run: |\n"
    if step_block.count(marker) != 1:
        return None
    body = step_block.split(marker, 1)[1]
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("          "):
            lines.append(line[10:])
        elif not line.strip():
            lines.append("")
        else:
            break
    return "\n".join(lines).strip("\n")


def _validate_audit_import_root(text: str) -> list[str]:
    """Keep direct-script audit commands importable from a clean runner."""
    job = _job_section(text, "audit-program-gate")
    errors: list[str] = []
    if not re.search(
        r"^    env:\n      PYTHONPATH: \$\{\{ github\.workspace \}\}\s*$",
        job,
        re.MULTILINE,
    ):
        errors.append("audit-program-gate must bind PYTHONPATH to github.workspace")
    if re.search(r"^\s{8,}PYTHONPATH\s*:|\b(?:export|unset)\s+PYTHONPATH|\bPYTHONPATH\s*=", "\n".join(_active_lines(job)), re.MULTILINE):
        errors.append("audit-program-gate must not override its repository import root")
    steps = [block for name, block in _named_steps(job) if name == "Run Audit Program Regression Tests"]
    if len(steps) != 1:
        errors.append("audit-program-gate must contain one mandatory audit regression step")
    elif _step_properties(steps[0]) != ("run",) or _step_run_value(steps[0]) != "python scripts/audit/test_audit_program.py":
        errors.append("audit regression tests must retain their exact mandatory command")
    dependencies = [block for name, block in _named_steps(job) if name == "Install Audit Test Dependencies"]
    install = "python -m pip install pip==26.2\npython -m pip install pytest==9.1.1 git-filter-repo==2.47.0"
    if (len(dependencies) != 1 or _step_properties(dependencies[0]) != ("run",)
            or _step_run_value(dependencies[0]) != install):
        errors.append("audit-program-gate must install its exact pytest and history-test dependencies")
    elif steps and job.index(dependencies[0]) > job.index(steps[0]):
        errors.append("audit-program-gate must install test dependencies before regression tests")
    return errors


def _validate_python_aiken(text: str) -> list[str]:
    """Retain the real compiler dependency of active Python native regressions."""
    job = _job_section(text, "python-gate")
    steps = _named_steps(job)
    setup = [block for name, block in steps if name == "Setup Pinned Aiken For Python Regressions"]
    tests = [block for name, block in steps if name == "Run PyTest Suite"]
    errors: list[str] = []
    if len(setup) != 1 or setup[0].rstrip() != PYTHON_AIKEN_SETUP:
        errors.append("python-gate must retain its exact mandatory pinned Aiken setup")
    if (len(tests) != 1 or _step_properties(tests[0]) != ("shell", "run")
            or not re.search(r"^        shell: bash$", tests[0], re.MULTILINE)
            or _step_run_value(tests[0]) != PYTHON_TEST_RUN):
        errors.append("python-gate must verify Aiken before execution and retain both exact pytest commands")
    if len(setup) == 1 and len(tests) == 1 and job.index(setup[0]) > job.index(tests[0]):
        errors.append("python-gate must install its pinned Aiken before the pytest suite")
    return errors


def _validate_readiness_artifact_location(text: str) -> list[str]:
    """Keep generated signed evidence outside the strictly clean source tree."""
    job = _job_section(text, "testnet-readiness-gate")
    steps = _named_steps(job)
    downloads = [block for name,block in steps if name == "Download Signed Audit Evidence"]
    verifies = [block for name,block in steps if name == "Verify Audit Evidence Signature"]
    gates = [block for name,block in steps if name == "Require Stage-Specific Evidence"]
    errors: list[str] = []
    expected_download = (
        "      - name: Download Signed Audit Evidence\n"
        "        uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1\n"
        "        with:\n"
        "          name: testnet-audit-evidence\n"
        "          path: ${{ runner.temp }}/vams-audit-evidence"
    )
    if len(downloads) != 1 or downloads[0].rstrip() != expected_download:
        errors.append("readiness must download signed audit evidence only outside the source checkout")
    if len(verifies) != 1 or _step_properties(verifies[0]) != ("run",) or _step_run_value(verifies[0]) != READINESS_AUDIT_VERIFY_RUN:
        errors.append("readiness must verify the exact downloaded audit artifact without bypass")
    if len(gates) != 1 or _step_properties(gates[0]) != ("env","run") or _step_run_value(gates[0]) != READINESS_AUDIT_RUN:
        errors.append("readiness must consume the same verified external audit artifact")
    if len(downloads) == len(verifies) == len(gates) == 1:
        positions = [job.index(block) for block in (downloads[0],verifies[0],gates[0])]
        if positions != sorted(positions):
            errors.append("readiness must download, verify, then consume audit evidence")
    return errors


def _validate_frontend_ci(text: str) -> list[str]:
    errors: list[str] = []
    frontend_job = _job_section(text, "frontend-gate")
    if not frontend_job:
        return ["security workflow is missing frontend-gate"]

    if any(
        line.strip().startswith("continue-on-error:")
        for line in _active_lines(frontend_job)
    ):
        errors.append("frontend-gate must not use job-level continue-on-error")

    steps = _named_steps(frontend_job)
    contract_steps: dict[str, str] = {}
    for expected_name, label, command in FRONTEND_STEP_CONTRACTS:
        named = [block for name, block in steps if name == expected_name]
        if len(named) != 1:
            errors.append(f"frontend-gate must contain exactly one {label} step: {expected_name}")
            continue

        block = named[0]
        expected_run = f"cd frontend-vite\n{command}"
        if _step_properties(block) != ("run",):
            errors.append(
                f"frontend-gate {label} step must contain only the reviewed run property"
            )
        if _step_run_value(block) != expected_run:
            errors.append(
                f"frontend-gate {label} run body must exactly equal the reviewed command contract"
            )

        command_occurrences = sum(
            line.strip() == command
            for _, candidate in steps
            for line in _active_lines(candidate)
        )
        if command_occurrences != 1:
            errors.append(
                f"frontend-gate must contain exactly one mandatory {label} command: {command}"
            )
        contract_steps[expected_name] = block

    ordered_names = tuple(contract[0] for contract in FRONTEND_STEP_CONTRACTS)
    if all(name in contract_steps for name in ordered_names):
        positions = [frontend_job.index(contract_steps[name]) for name in ordered_names]
        if positions != sorted(positions) or len(set(positions)) != len(positions):
            errors.append(
                "frontend-gate must install dependencies, test telemetry security, "
                "build production assets, then scan the bundle in that order"
            )
    return errors


def _validate_secret_scanner_result_enforcement(text: str) -> list[str]:
    errors: list[str] = []
    expected_guard_command = '        run: test "$SCAN_OUTCOME" = "success"'

    for job_name, scanner, scan_name, scan_id, upload_name, guard_name in SECRET_SCANNER_RESULT_CONTRACTS:
        job = _job_section(text, job_name)
        if not job:
            errors.append(f"{job_name} is missing the required {scanner} result enforcement job")
            continue

        steps = _named_steps(job)
        scan_blocks = [block for name, block in steps if name == scan_name]
        upload_blocks = [block for name, block in steps if name == upload_name]
        guard_blocks = [block for name, block in steps if name == guard_name]

        if len(scan_blocks) != 1:
            errors.append(f"{job_name} must contain exactly one {scanner} scan step: {scan_name}")
        else:
            scan_lines = _active_lines(scan_blocks[0])
            scan_properties = _step_properties(scan_blocks[0])
            # The outcome must belong to the reviewed scanner, not a no-op.
            expected_properties = {"id", "continue-on-error", "run"}
            if job_name == "secret-scanning":
                expected_properties.add("shell")
                expected_body = 'set -euo pipefail\nmkdir -p raw-gate\ngitleaks git --log-opts="--all -m" . --config .gitleaks.toml --redact=100 --report-format json --report-path raw-gate/gitleaks-report.json --exit-code 1\ntest -s raw-gate/gitleaks-report.json'
                if scan_lines.count("        shell: bash") != 1:
                    errors.append(f"{job_name} must retain the reviewed Bash scanner shell")
            else:
                expected_body = 'python scripts/security/trufflehog_gate.py \\\n  --output raw-gate/trufflehog-sanitized.json'
            if len(scan_properties) != len(expected_properties) or set(scan_properties) != expected_properties:
                errors.append(f"{job_name} must retain the reviewed scanner step properties")
            if _step_run_value(scan_blocks[0]) != expected_body:
                errors.append(f"{job_name} must retain the reviewed unsuppressed scanner run body")
            expected_id_line = f"        id: {scan_id}"
            expected_continue_line = "        continue-on-error: true"
            if scan_lines.count(expected_id_line) != 1 or _active_lines(job).count(expected_id_line) != 1:
                errors.append(f"{job_name} {scanner} scan step must uniquely retain id {scan_id}")
            if (
                scan_properties.count("continue-on-error") != 1
                or scan_lines.count(expected_continue_line) != 1
            ):
                errors.append(f"{job_name} {scanner} scan step must retain continue-on-error: true")

        if len(upload_blocks) != 1:
            errors.append(f"{job_name} must contain exactly one {scanner} evidence upload step: {upload_name}")
        else:
            upload_lines = _active_lines(upload_blocks[0])
            upload_properties = _step_properties(upload_blocks[0])
            if (
                upload_properties.count("if") != 1
                or upload_lines.count("        if: always()") != 1
            ):
                errors.append(f"{job_name} {scanner} evidence upload must retain if: always()")
            if f"        uses: actions/upload-artifact@{REQUIRED_ACTION_PINS['actions/upload-artifact']}" not in upload_lines:
                errors.append(f"{job_name} {scanner} evidence upload must use the reviewed upload-artifact action")

        if len(guard_blocks) != 1:
            errors.append(f"{job_name} must contain exactly one mandatory result guard: {guard_name}")
        else:
            guard_lines = _active_lines(guard_blocks[0])
            guard_properties = _step_properties(guard_blocks[0])
            expected_guard_lines = {
                f"      - name: {guard_name}",
                "        if: always()",
                "        env:",
                f"          SCAN_OUTCOME: ${{{{ steps.{scan_id}.outcome }}}}",
                expected_guard_command,
            }
            if (
                len(guard_properties) != 3
                or set(guard_properties) != {"if", "env", "run"}
                or len(guard_lines) != len(expected_guard_lines)
                or set(guard_lines) != expected_guard_lines
            ):
                errors.append(
                    f"{job_name} {scanner} result guard must always fail unless the bound scan outcome is success"
                )

        job_lines = _active_lines(job)
        expected_binding = f"          SCAN_OUTCOME: ${{{{ steps.{scan_id}.outcome }}}}"
        if job_lines.count(expected_binding) != 1:
            errors.append(f"{job_name} must bind SCAN_OUTCOME exactly once to {scan_id}.outcome")
        if job_lines.count(expected_guard_command) != 1:
            errors.append(f"{job_name} must contain exactly one unsuppressed result test for {scanner}")

        if any(re.match(r"^    continue-on-error:", line) for line in job_lines):
            errors.append(f"{job_name} must not make the scanner result enforcement job nonblocking")

        if len(scan_blocks) == len(upload_blocks) == len(guard_blocks) == 1:
            scan_position = job.index(scan_blocks[0])
            upload_position = job.index(upload_blocks[0])
            guard_position = job.index(guard_blocks[0])
            if not scan_position < upload_position < guard_position:
                errors.append(
                    f"{job_name} must run the {scanner} scan, upload evidence, then enforce its result"
                )

    return errors


def _version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def validate_workflow_text(text: str) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_frontend_ci(text))
    errors.extend(_validate_audit_import_root(text))
    errors.extend(_validate_python_aiken(text))
    errors.extend(_validate_readiness_artifact_location(text))
    errors.extend(_validate_secret_scanner_result_enforcement(text))
    action_refs = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", text, re.MULTILINE)
    if not action_refs:
        errors.append("security workflow contains no action references")
    for ref in action_refs:
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            errors.append(f"GitHub Action is not commit-pinned: {ref}")
    for action, ref in REQUIRED_ACTION_PINS.items():
        if f"uses: {action}@{ref}" not in text:
            errors.append(f"security workflow does not use reviewed Node 24 pin: {action}")
    forbidden = (
        "txpipe/setup-aiken",
        "trufflesecurity/trufflehog@main",
        "version: stable",
        "pip install --upgrade pip",
        "pip install slither-analyzer\n",
        "pip install semgrep\n",
    )
    for value in forbidden:
        if value in text:
            errors.append(f"security workflow contains mutable tool reference: {value}")
    required_controls = (
        "submodules: recursive",
        "version: v1.7.1",
        "--fail-high --json slither-report.json",
        "contracts/slither-adjudications.yml",
        "git-filter-repo==2.47.0",
        "cargo +1.92.0 install cargo-audit --version 0.22.2 --locked",
        "cargo +1.92.0 audit --deny warnings",
        'python -m unittest discover -s scripts/audit -p "test_*.py"',
        "semgrep scan --metrics off --config .semgrep/vams-security.yml --error",
        "--json --output semgrep-reviewed.json",
        ".semgrep/discovery-adjudications.yml",
        "https://github.com/envoyproxy/envoy/releases/download/v1.39.1/envoy-1.39.1-linux-x86_64",
        "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8",
        "python scripts/security/validate_envoy_gateway.py",
        "npm audit --omit=dev --audit-level=high",
        "npm run lint",
    )
    for value in required_controls:
        if value not in text:
            errors.append(f"security workflow is missing required control: {value}")
    envoy_url = "https://github.com/envoyproxy/envoy/releases/download/v1.39.1/envoy-1.39.1-linux-x86_64"
    envoy_digest = "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8"
    if text.count(envoy_url) != 2 or text.count(envoy_digest) != 2:
        errors.append("Envoy must be acquired and digest-verified exactly once in each required job")
    if "caddy:2.11.4-alpine@" in "\n".join(_active_lines(text)):
        errors.append("retired Caddy ingress remains active in the security workflow")
    if text.count("submodules: recursive") < 2:
        errors.append("Forge and Slither checkouts must both initialize recursive submodules")
    trufflehog_text = TRUFFLEHOG_GATE.read_text(encoding="utf-8")
    if '"--no-verification"' not in trufflehog_text:
        errors.append("TruffleHog gate must not transmit candidate credentials for verification")
    manifest_index = text.find("- name: Generate Commit-Bound Evidence Manifest")
    enforcement_index = text.find("- name: Enforce Required Job Results")
    if manifest_index < 0 or enforcement_index < 0 or manifest_index > enforcement_index:
        errors.append("failure evidence must be generated before aggregate enforcement")

    python_job = _job_section(text, "python-gate")
    active = _active_lines(python_job)
    workflow_active = _active_lines(text)
    python_install_lines = [line for line in active if "pip install" in line]
    install_lines = [line for line in workflow_active if "pip install" in line]
    pip_pins = re.findall(r"\bpip==([0-9]+(?:\.[0-9]+)+)", "\n".join(python_install_lines))
    if not pip_pins:
        errors.append("python-gate has no exact pip bootstrap pin")
    elif any(_version(pin) < (26, 2) for pin in pip_pins):
        errors.append("python-gate pip bootstrap pin is below 26.2")
    if any(_version(pin) < (26, 2) for pin in re.findall(r"\bpip==([0-9]+(?:\.[0-9]+)+)", "\n".join(install_lines))):
        errors.append("active workflow contains a pip bootstrap pin below 26.2")
    if "pip==26.1.2" in "\n".join(workflow_active):
        errors.append("active workflow contains retired pip==26.1.2")
    httpx_pins = re.findall(r"\bhttpx2==([0-9]+(?:\.[0-9]+)+)", "\n".join(install_lines))
    if not httpx_pins:
        errors.append("python-gate has no exact httpx2 pin")
    elif any(_version(pin) < (2, 12, 0) for pin in httpx_pins):
        errors.append("python-gate httpx2 pin is below 2.12.0")
    if "httpx2==2.5.0" in "\n".join(workflow_active):
        errors.append("active workflow contains retired httpx2==2.5.0")
    httpcore_pins = re.findall(r"\bhttpcore2==([0-9]+(?:\.[0-9]+)+)", "\n".join(install_lines))
    if any(_version(pin) < (2, 12, 0) for pin in httpcore_pins):
        errors.append("active workflow directly pins vulnerable httpcore2")
    audit_lines = [line.strip() for line in active if "pip-audit" in line]
    installed = [line for line in audit_lines if "--local" in line]
    if len(installed) != 1:
        errors.append("python-gate must contain exactly one installed-environment pip-audit command")
    else:
        command = installed[0]
        if "--vulnerability-service pypi" not in command:
            errors.append("installed-environment pip-audit must select the PyPI service explicitly")
        if any(flag in command for flag in ("--ignore-vuln", "--fix", "--exit-zero", "|| true")):
            errors.append("installed-environment pip-audit contains suppression options")
    if not audit_lines:
        errors.append("python-gate has no pip-audit command")

    gitleaks_job = _job_section(text, "secret-scanning")
    gitleaks_commands = [
        line.strip()
        for line in _active_lines(gitleaks_job)
        if line.strip().startswith("gitleaks git")
    ]
    if len(gitleaks_commands) != 1:
        errors.append("secret-scanning must contain exactly one Gitleaks history command")
    elif gitleaks_commands[0] != REQUIRED_GITLEAKS_HISTORY_COMMAND:
        errors.append(
            "secret-scanning Gitleaks history command must use exactly one "
            '--log-opts="--all -m" before the repository target `.`'
        )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Workflow supply-chain validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Workflow supply-chain validation passed: all {len(re.findall(r'uses:', WORKFLOW.read_text(encoding='utf-8')))} actions are commit-pinned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
