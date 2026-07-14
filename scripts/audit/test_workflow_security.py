from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("validate_workflow_security.py")
SPEC = importlib.util.spec_from_file_location("validate_workflow_security", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class WorkflowSecurityTests(unittest.TestCase):
    def test_actions_and_security_tools_are_pinned(self) -> None:
        self.assertEqual(module.validate(), [])

    def test_workflow_binds_prior_run_target_and_fixed_seed(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        audit_text = module.AUDIT_PROGRAM.read_text(encoding="utf-8")
        self.assertIn("target_sha:", text)
        self.assertIn("stage_evidence_run_id:", text)
        self.assertIn("operational_evidence_run_id:", text)
        self.assertIn("run-id: ${{ inputs.stage_evidence_run_id }}", text)
        self.assertIn("run-id: ${{ inputs.operational_evidence_run_id }}", text)
        self.assertIn('AUDIT_SEED: "20260713"', text)
        self.assertNotIn("--result ", text)
        self.assertNotIn("gate-artifact", text)
        self.assertNotIn("--only-verified", text)
        self.assertNotIn("cp -a docs/audit/evidence", text)
        self.assertLess(
            text.index("Download Complete Prior Stage-Evidence Bundle"),
            text.index("Generate Commit-Bound Evidence Manifest"),
        )
        self.assertLess(
            text.index("Download Post-Freeze Operational Evidence Bundle"),
            text.index("Merge Immutable Operational Evidence"),
        )
        self.assertLess(
            text.index("Merge Immutable Operational Evidence"),
            text.index("Generate Commit-Bound Evidence Manifest"),
        )
        self.assertLess(
            text.index("Generate Commit-Bound Evidence Manifest"),
            text.index("Sign Audit Evidence"),
        )

    def test_operational_workflow_is_separate_and_fail_closed(self) -> None:
        text = module.OPERATIONAL_WORKFLOW.read_text(encoding="utf-8")
        security = module.WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, linux, x64, vams-testnet-evidence]", text)
        self.assertIn("environment: testnet-operational-evidence", text)
        self.assertIn("audit_program.py operational", text)
        self.assertIn("BEGIN ([A-Z0-9 ]+ )?PRIVATE KEY", text)
        self.assertNotIn("--exclude='*.pem'", text)
        self.assertIn(
            '== ".github/workflows/operational-evidence.yml"', security
        )

    def test_validator_rejects_stale_seed_and_missing_run_binding(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        text = text.replace('AUDIT_SEED: "20260713"', 'AUDIT_SEED: "20260711"', 1)
        text = text.replace(
            "run-id: ${{ inputs.stage_evidence_run_id }}", "run-id: latest", 1
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Path(temp_dir) / "security-gates.yml"
            workflow.write_text(text, encoding="utf-8")
            with mock.patch.object(module, "WORKFLOW", workflow):
                errors = "\n".join(module.validate())
        self.assertIn("seeds must all equal 20260713", errors)
        self.assertIn("prior run artifact download", errors)

    def test_workflow_runs_all_raw_gates_and_full_history_secret_scans(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        audit_text = module.AUDIT_PROGRAM.read_text(encoding="utf-8")
        gate_runs = module.re.findall(
            r"audit_program\.py run-gate[^\r\n]*--name ([a-z0-9-]+)", text
        )
        self.assertEqual(set(gate_runs), module.REQUIRED_RAW_GATES)
        self.assertEqual(len(gate_runs), len(module.REQUIRED_RAW_GATES))
        self.assertIn("--log-opts=--all", audit_text)
        self.assertIn("--redact=100", audit_text)
        self.assertIn("--results=verified,unknown,unverified", audit_text)
        self.assertIn("pattern: raw-gate-*", text)
        self.assertIn(module.POSTGRES_IMAGE, text)
        self.assertIn(module.CADDY_IMAGE, audit_text)
        self.assertIn("VDSO_TEST_POSTGRES_ALLOW_RESET: \"1\"", text)

    def test_validator_rejects_partial_secret_scan_and_unpinned_postgres(self) -> None:
        text = module.WORKFLOW.read_text(encoding="utf-8")
        audit_text = module.AUDIT_PROGRAM.read_text(encoding="utf-8").replace(
            "--results=verified,unknown,unverified", "--only-verified", 1
        )
        text = text.replace(module.POSTGRES_IMAGE, "postgres:16", 1)
        audit_text = audit_text.replace(module.CADDY_IMAGE, "caddy:2")
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Path(temp_dir) / "security-gates.yml"
            audit_program = Path(temp_dir) / "audit_program.py"
            workflow.write_text(text, encoding="utf-8")
            audit_program.write_text(audit_text, encoding="utf-8")
            with mock.patch.object(module, "WORKFLOW", workflow), mock.patch.object(
                module, "AUDIT_PROGRAM", audit_program
            ):
                errors = "\n".join(module.validate())
        self.assertIn("runner is missing all-category TruffleHog git scan", errors)
        self.assertIn("forbidden synthetic or partial scan command", errors)
        self.assertIn("pinned PostgreSQL service", errors)
        self.assertIn("pinned Caddy evidence image", errors)


if __name__ == "__main__":
    unittest.main()
