from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_workflow_security.py")
SPEC = importlib.util.spec_from_file_location("validate_workflow_security", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

SECRET_SCANNER_RESULT_STEPS = (
    (
        "secret-scanning",
        "Run Complete-History GitLeaks",
        "gitleaks_scan",
        "Upload GitLeaks Raw Gate Evidence",
        "Enforce GitLeaks Result",
    ),
    (
        "trufflehog-scanning",
        "Run Complete-History All-Category TruffleHog",
        "trufflehog_scan",
        "Upload TruffleHog Sanitized Gate Evidence",
        "Enforce TruffleHog Result",
    ),
)


class WorkflowSecurityTests(unittest.TestCase):
    def validate_temporary_workflow(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory(prefix="vams-workflow-security-") as directory:
            workflow = Path(directory) / "security-gates.yml"
            workflow.write_text(text, encoding="utf-8")
            return module.validate_workflow_text(workflow.read_text(encoding="utf-8"))

    def named_step_block(self, text: str, job_name: str, step_name: str) -> str:
        job = module._job_section(text, job_name)
        matches = [block for name, block in module._named_steps(job) if name == step_name]
        self.assertEqual(len(matches), 1, (job_name, step_name, len(matches)))
        return matches[0]

    def replace_named_step(
        self,
        text: str,
        job_name: str,
        step_name: str,
        replacement: str,
    ) -> str:
        original = self.named_step_block(text, job_name, step_name)
        self.assertEqual(text.count(original), 1, (job_name, step_name))
        return text.replace(original, replacement, 1)

    def test_actions_and_security_tools_are_pinned(self) -> None:
        self.assertEqual(module.validate(), [])

    def test_required_github_actions_use_reviewed_node24_releases(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for action, ref in module.REQUIRED_ACTION_PINS.items():
            self.assertIn(f"uses: {action}@{ref}", text)

    def test_failure_manifest_precedes_aggregate_enforcement(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(
            text.index("- name: Generate Commit-Bound Evidence Manifest"),
            text.index("- name: Enforce Required Job Results"),
        )

    def test_frontend_security_controls_are_mandatory_and_ordered(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(module.validate_workflow_text(text), [])
        frontend = module._job_section(text, "frontend-gate")
        self.assertLess(frontend.index("npm ci"), frontend.index(module.FRONTEND_TEST_COMMAND))
        self.assertLess(
            frontend.index(module.FRONTEND_TEST_COMMAND),
            frontend.index(module.FRONTEND_BUILD_COMMAND),
        )
        self.assertLess(
            frontend.index(module.FRONTEND_BUILD_COMMAND),
            frontend.index(module.FRONTEND_BUNDLE_SCAN_COMMAND),
        )

    def test_frontend_security_control_removal_is_rejected(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for command in (module.FRONTEND_TEST_COMMAND, module.FRONTEND_BUNDLE_SCAN_COMMAND):
            with self.subTest(command=command):
                bad = text.replace(f"          {command}\n", "", 1)
                errors = self.validate_temporary_workflow(bad)
                self.assertTrue(any("frontend" in error for error in errors), errors)

    def test_frontend_security_controls_cannot_be_ignored(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for command in (module.FRONTEND_TEST_COMMAND, module.FRONTEND_BUNDLE_SCAN_COMMAND):
            with self.subTest(command=command):
                bad = text.replace(f"          {command}\n", f"          {command} || true\n", 1)
                errors = self.validate_temporary_workflow(bad)
                self.assertTrue(any("frontend" in error for error in errors), errors)

    def test_frontend_security_controls_reject_nonblocking_command_bodies(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        mutations = (
            ("npm test", "set +e\n          npm test\n          true"),
            ("npm run scan:bundle", "set +e\n          npm run scan:bundle\n          true"),
            ("npm test", "npm test\n          true"),
            ("npm run scan:bundle", "npm run scan:bundle\n          true"),
        )
        for command, replacement in mutations:
            with self.subTest(command=command, replacement=replacement):
                bad = text.replace(f"          {command}\n", f"          {replacement}\n", 1)
                errors = self.validate_temporary_workflow(bad)
                self.assertTrue(any("run body" in error for error in errors), errors)

    def test_frontend_security_control_duplication_is_rejected(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for command in (module.FRONTEND_TEST_COMMAND, module.FRONTEND_BUNDLE_SCAN_COMMAND):
            with self.subTest(command=command):
                bad = text.replace(f"          {command}\n", f"          {command}\n          {command}\n", 1)
                errors = self.validate_temporary_workflow(bad)
                self.assertTrue(any("frontend" in error for error in errors), errors)

    def test_frontend_security_steps_cannot_be_nonblocking_or_conditional(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for step_name in ("Run Frontend Telemetry Security Tests", "Scan Production Bundle"):
            with self.subTest(step_name=step_name):
                marker = f"      - name: {step_name}\n"
                for directive in ("        continue-on-error: true\n", "        if: always()\n"):
                    bad = text.replace(marker, marker + directive, 1)
                    errors = self.validate_temporary_workflow(bad)
                    self.assertTrue(any("frontend" in error for error in errors), errors)

        job_marker = "  frontend-gate:\n"
        bad = text.replace(job_marker, job_marker + "    continue-on-error: true\n", 1)
        errors = self.validate_temporary_workflow(bad)
        self.assertTrue(any("job-level continue-on-error" in error for error in errors), errors)

    def test_frontend_bundle_scan_must_follow_production_build(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        build_step = """      - name: Build Verification
        run: |
          cd frontend-vite
          npm run build

"""
        scan_step = """      - name: Scan Production Bundle
        run: |
          cd frontend-vite
          npm run scan:bundle
"""
        self.assertIn(build_step + scan_step, text)
        bad = text.replace(build_step + scan_step, scan_step + "\n" + build_step.rstrip("\n"), 1)
        errors = self.validate_temporary_workflow(bad)
        self.assertTrue(any("in that order" in error for error in errors), errors)

    def test_candidate_dependency_and_installed_audit_are_present(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pip install pip==26.2", text)
        self.assertIn("httpx2==2.12.0", text)
        self.assertIn("pip-audit --local --vulnerability-service pypi", text)
        self.assertNotIn("pip==26.1.2", text)
        self.assertNotIn("httpx2==2.5.0", text)

    def test_retired_and_lower_pins_are_rejected(self) -> None:
        for old in ("pip==26.2", "httpx2==2.12.0"):
            text = module.WORKFLOW.read_text(encoding="utf-8")
            bad = text.replace(old, old.split("==")[0] + "==1.0.0")
            self.assertTrue(module.validate_workflow_text(bad))

    def test_direct_vulnerable_httpcore_pin_is_rejected(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        bad = text.replace("pip install httpx==0.28.1", "pip install httpcore2==2.5.0 httpx==0.28.1", 1)
        self.assertTrue(module.validate_workflow_text(bad))

    def test_installed_audit_requirements_and_suppression_are_rejected(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for replacement in (
            "pip-audit --local",
            "pip-audit --local --vulnerability-service pypi --ignore-vuln CVE-1",
            "pip-audit --local --vulnerability-service pypi --fix",
            "pip-audit --local --vulnerability-service pypi --exit-zero",
            "pip-audit --local --vulnerability-service pypi || true",
        ):
            bad = text.replace("pip-audit --local --vulnerability-service pypi", replacement, 1)
            self.assertTrue(module.validate_workflow_text(bad))

    def test_missing_installed_environment_audit_is_rejected(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        bad = text.replace("          pip-audit --local --vulnerability-service pypi\n", "", 1)
        self.assertTrue(module.validate_workflow_text(bad))

    def test_ordinary_httpx_and_httpcore_are_not_confused(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(module.validate_workflow_text(text), [])

    def test_gitleaks_history_command_covers_all_refs_and_merge_parents(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count(module.REQUIRED_GITLEAKS_HISTORY_COMMAND), 1)
        self.assertEqual(module.validate_workflow_text(text), [])

    def test_gitleaks_history_command_drift_is_rejected(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        required = module.REQUIRED_GITLEAKS_HISTORY_COMMAND
        replacements = (
            'gitleaks git . --config .gitleaks.toml --redact=100 --report-format json --report-path raw-gate/gitleaks-report.json --log-opts="--all -m" --exit-code 1',
            required.replace('--log-opts="--all -m"', '--log-opts="-m"'),
            required.replace('--log-opts="--all -m"', '--log-opts="--all"'),
            required.replace(" . --config", " alternate-target --config"),
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                self.assertTrue(module.validate_workflow_text(text.replace(required, replacement, 1)))

        duplicate = text.replace(required, required + "\n          " + required, 1)
        self.assertTrue(module.validate_workflow_text(duplicate))

    def test_secret_scanner_result_contracts_match_the_existing_workflow(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(module.validate_workflow_text(text), [])

        for job_name, scan_name, scan_id, upload_name, guard_name in SECRET_SCANNER_RESULT_STEPS:
            with self.subTest(job=job_name):
                job = module._job_section(text, job_name)
                scan = self.named_step_block(text, job_name, scan_name)
                upload = self.named_step_block(text, job_name, upload_name)
                guard = self.named_step_block(text, job_name, guard_name)

                self.assertIn(f"        id: {scan_id}", module._active_lines(scan))
                self.assertIn("        continue-on-error: true", module._active_lines(scan))
                self.assertIn("        if: always()", module._active_lines(upload))
                self.assertIn("        if: always()", module._active_lines(guard))
                self.assertIn(
                    f"          SCAN_OUTCOME: ${{{{ steps.{scan_id}.outcome }}}}",
                    module._active_lines(guard),
                )
                self.assertIn(
                    '        run: test "$SCAN_OUTCOME" = "success"',
                    module._active_lines(guard),
                )
                self.assertLess(job.index(upload), job.index(guard))

    def test_secret_scanner_result_guard_mutants_are_rejected_for_both_scanners(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")

        def replace_once(block: str, old: str, new: str) -> str:
            self.assertEqual(block.count(old), 1, old)
            return block.replace(old, new, 1)

        for job_name, scan_name, scan_id, _upload_name, guard_name in SECRET_SCANNER_RESULT_STEPS:
            wrong_scan_id = "trufflehog_scan" if scan_id == "gitleaks_scan" else "gitleaks_scan"
            with self.subTest(job=job_name):
                guard = self.named_step_block(text, job_name, guard_name)
                mutations = (
                    ("removed guard", ""),
                    (
                        "success-only condition",
                        replace_once(guard, "        if: always()\n", "        if: success()\n"),
                    ),
                    (
                        "guard continue-on-error",
                        replace_once(
                            guard,
                            f"      - name: {guard_name}\n",
                            f"      - name: {guard_name}\n        continue-on-error: true\n",
                        ),
                    ),
                    (
                        "outcome replaced with conclusion",
                        replace_once(
                            guard,
                            f"steps.{scan_id}.outcome",
                            f"steps.{scan_id}.conclusion",
                        ),
                    ),
                    (
                        "fixed successful outcome",
                        replace_once(
                            guard,
                            f"SCAN_OUTCOME: ${{{{ steps.{scan_id}.outcome }}}}",
                            "SCAN_OUTCOME: success",
                        ),
                    ),
                    (
                        "failure suppressed with || true",
                        replace_once(
                            guard,
                            'run: test "$SCAN_OUTCOME" = "success"',
                            'run: test "$SCAN_OUTCOME" = "success" || true',
                        ),
                    ),
                    (
                        "failure suppressed by appended successful command",
                        replace_once(
                            guard,
                            'run: test "$SCAN_OUTCOME" = "success"',
                            'run: |\n          test "$SCAN_OUTCOME" = "success"\n          true',
                        ),
                    ),
                    ("duplicate guard", guard + guard),
                    (
                        "wrong scanner-step binding",
                        replace_once(
                            guard,
                            f"steps.{scan_id}.outcome",
                            f"steps.{wrong_scan_id}.outcome",
                        ),
                    ),
                )

                for description, replacement in mutations:
                    with self.subTest(mutant=description):
                        bad = self.replace_named_step(text, job_name, guard_name, replacement)
                        errors = self.validate_temporary_workflow(bad)
                        self.assertTrue(errors, (job_name, description, errors))

                scan = self.named_step_block(text, job_name, scan_name)
                bad_scan = replace_once(
                    scan,
                    "        continue-on-error: true\n",
                    "        continue-on-error: false\n",
                )
                bad = self.replace_named_step(text, job_name, scan_name, bad_scan)
                errors = self.validate_temporary_workflow(bad)
                self.assertTrue(errors, (job_name, "scan result semantics changed", errors))

    def test_secret_scanner_result_guard_cannot_precede_evidence_upload(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")

        for job_name, _scan_name, _scan_id, upload_name, guard_name in SECRET_SCANNER_RESULT_STEPS:
            with self.subTest(job=job_name):
                upload = self.named_step_block(text, job_name, upload_name)
                guard = self.named_step_block(text, job_name, guard_name)
                job = module._job_section(text, job_name)
                ordered = upload + guard
                self.assertEqual(job.count(ordered), 1)
                reordered = guard + upload
                bad_job = job.replace(ordered, reordered, 1)
                header = f"  {job_name}:\n"
                section_start = text.index(header) + len(header)
                bad = text[:section_start] + bad_job + text[section_start + len(job):]
                errors = self.validate_temporary_workflow(bad)
                self.assertTrue(errors, (job_name, "result guard precedes evidence upload", errors))

    def test_secret_scanner_bodies_cannot_be_noops_or_suppress_failures(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for job_name, scan_name, _scan_id, _upload_name, _guard_name in SECRET_SCANNER_RESULT_STEPS:
            scan = self.named_step_block(text, job_name, scan_name)
            body = module._step_run_value(scan)
            self.assertIsNotNone(body)
            if job_name == "secret-scanning":
                no_op = ("set -euo pipefail\nmkdir -p raw-gate\nif false; then\n  "
                         + module.REQUIRED_GITLEAKS_HISTORY_COMMAND
                         + "\nfi\nprintf '{}' > raw-gate/gitleaks-report.json")
                suppressed = body.replace("set -euo pipefail", "set +e", 1) + "\ntrue"
            else:
                no_op = "mkdir -p raw-gate\nprintf '{}' > raw-gate/trufflehog-sanitized.json"
                suppressed = "set +e\n" + body + "\ntrue"
            prefix = scan.split("        run: |\n", 1)[0]
            for label, replacement_body in (("no scanner executed", no_op),
                                             ("scanner failure suppressed", suppressed)):
                with self.subTest(job=job_name, mutation=label):
                    replacement = prefix + "        run: |\n" + "\n".join(
                        "          " + line for line in replacement_body.splitlines()) + "\n\n"
                    bad = self.replace_named_step(text, job_name, scan_name, replacement)
                    self.assertTrue(self.validate_temporary_workflow(bad), (job_name, label))

    def test_secret_scanner_shell_cannot_discard_the_scanner_script(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        for job_name, scan_name, _scan_id, _upload_name, _guard_name in SECRET_SCANNER_RESULT_STEPS:
            with self.subTest(job=job_name):
                scan = self.named_step_block(text, job_name, scan_name)
                bad_shell = "        shell: bash -c 'true' -- {0}\n"
                if "        shell: bash\n" in scan:
                    replacement = scan.replace("        shell: bash\n", bad_shell, 1)
                else:
                    replacement = scan.replace("        run: |\n", bad_shell + "        run: |\n", 1)
                bad = self.replace_named_step(text, job_name, scan_name, replacement)
                self.assertTrue(self.validate_temporary_workflow(bad), job_name)

    def test_envoy_release_and_digest_are_immutable(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("envoy-1.39.1-linux-x86_64", text)
        self.assertIn("002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8", text)
        self.assertNotIn("envoyproxy/envoy:latest", text)
        for removed in (
            "envoy-1.39.1-linux-x86_64",
            "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8",
            "python scripts/security/validate_envoy_gateway.py",
        ):
            self.assertTrue(module.validate_workflow_text(text.replace(removed, "", 1)))


if __name__ == "__main__":
    unittest.main()
