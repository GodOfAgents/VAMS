from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("audit_program.py")
SPEC = importlib.util.spec_from_file_location("audit_program", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
audit_program = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_program)


class AuditProgramTests(unittest.TestCase):
    def test_audit_program_has_all_36_tracks(self) -> None:
        matrix = audit_program._load_json(audit_program.MATRIX_PATH)
        self.assertEqual(
            [track["id"] for track in matrix["tracks"]],
            [f"T{i:02d}" for i in range(1, 37)],
        )

    def test_audit_program_validation_passes(self) -> None:
        self.assertEqual(audit_program.validate_program(), [])

    def test_release_claim_scan_covers_readme_and_audit(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('"audit.md"', source)
        self.assertIn('"README.md"', source)

    def test_all_invariants_have_a_control(self) -> None:
        matrix = audit_program._load_json(audit_program.MATRIX_PATH)
        covered = {
            invariant for track in matrix["tracks"] for invariant in track["invariants"]
        }
        self.assertEqual(covered, {f"INV-{i}" for i in range(1, 11)})

    def test_blocked_tracks_cannot_be_mistaken_for_verified(self) -> None:
        matrix = audit_program._load_json(audit_program.MATRIX_PATH)
        statuses = {track["id"]: track["status"] for track in matrix["tracks"]}
        self.assertEqual(statuses["T16"], "blocked")
        self.assertEqual(statuses["T21"], "blocked")
        self.assertEqual(statuses["T30"], "blocked")
        self.assertEqual(statuses["T33"], "blocked")

    def test_current_program_is_not_testnet_ready(self) -> None:
        errors = audit_program.validate_readiness(stage="public")
        joined = "\n".join(errors)
        self.assertIn("T16=blocked", joined)
        self.assertIn("T30=blocked", joined)
        self.assertIn("clean working tree", joined)
        self.assertIn("evidence manifest", joined)

    def test_canary_excludes_g6_track_but_public_includes_it(self) -> None:
        canary = "\n".join(audit_program.validate_readiness(stage="canary"))
        public = "\n".join(audit_program.validate_readiness(stage="public"))
        self.assertNotIn("T36=partial", canary)
        self.assertIn("T36=partial", public)

    def test_evidence_manifest_is_commit_bound_clean_and_signed(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "evidence.json"
            signature = root / "evidence.sig"
            certificate = root / "evidence.pem"
            manifest.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "dirty": False,
                        "results": [{"name": "forge", "status": "success"}],
                    }
                ),
                encoding="utf-8",
            )
            signature.write_text("signature", encoding="utf-8")
            certificate.write_text("certificate", encoding="utf-8")

            self.assertEqual(
                audit_program._validate_evidence_manifest(
                    manifest, signature, certificate, commit
                ),
                [],
            )

            with mock.patch.object(audit_program, "_git", return_value=""):
                errors = audit_program._validate_evidence_manifest(
                    manifest, signature, certificate, "b" * 40
                )
            self.assertIn("commit does not match", errors[0])

    def test_deployment_manifests_require_both_networks_and_stage(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = []
            for network in sorted(audit_program.DEPLOYMENT_NETWORKS):
                path = root / f"{network}.json"
                authorities = {
                    "governance": {
                        "address": f"{network}-governance",
                        "owners": [f"governance-{i}" for i in range(5)],
                        "threshold": 3,
                    },
                    "treasury": {
                        "address": f"{network}-treasury",
                        "owners": [f"treasury-{i}" for i in range(5)],
                        "threshold": 3,
                    },
                    "emergency": {
                        "address": f"{network}-emergency",
                        "owners": [f"emergency-{i}" for i in range(3)],
                        "threshold": 2,
                        "scope": "pause-only",
                    },
                }
                path.write_text(
                    json.dumps(
                        {
                            "network": network,
                            "deployment_status": "rehearsed",
                            "commit_sha": commit,
                            "deployer_privileges_removed": True,
                            "mock_routes_disabled": True,
                            "timelock_seconds": 172800,
                            "authorities": authorities,
                            "artifacts": [
                                {"name": name}
                                for name in sorted(
                                    audit_program.CANARY_EVM_ARTIFACTS
                                    if network == "polygon-amoy"
                                    else audit_program.CARDANO_ARTIFACTS
                                )
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                paths.append(path)

            self.assertEqual(
                audit_program._validate_deployment_manifests(
                    paths, "canary", commit
                ),
                [],
            )
            public_errors = audit_program._validate_deployment_manifests(
                paths, "public", commit
            )
            self.assertEqual(
                sum("deployment_status=deployed" in item for item in public_errors),
                2,
            )
            self.assertTrue(any("missing deployment artifacts" in item for item in public_errors))

    def test_assurance_index_binds_track_artifacts(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "report.txt"
            artifact.write_text("verified evidence", encoding="utf-8")
            artifact_hash = audit_program.hashlib.sha256(artifact.read_bytes()).hexdigest()
            index = root / "assurance.json"
            index.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "tracks": [
                            {
                                "id": "T10",
                                "status": "verified",
                                "reviewer": "reviewer",
                                "independent_review": True,
                                "blocking_findings_open": 0,
                                "artifacts": [
                                    {
                                        "path": "report.txt",
                                        "sha256": artifact_hash,
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(audit_program, "ROOT", root):
                self.assertEqual(
                    audit_program._validate_assurance_index(
                        index, "public", commit, {"T10"}
                    ),
                    [],
                )

    def test_public_canary_report_requires_duration_and_all_drills(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "canary.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "consecutive_days": 7,
                        "stop_conditions_triggered": False,
                        "drills": {
                            drill: True for drill in audit_program.REQUIRED_DRILLS
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(audit_program._validate_canary_report(path, commit), [])

            report = json.loads(path.read_text(encoding="utf-8"))
            report["drills"]["rollback"] = False
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = audit_program._validate_canary_report(path, commit)
            self.assertIn("rollback", errors[0])

    def test_signed_manifest_binds_supporting_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "assurance-index.json"
            artifact.write_text("{}", encoding="utf-8")
            digest = audit_program.hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = root / "audit-evidence.json"
            manifest.write_text(
                json.dumps(
                    {
                        "evidence_artifacts": [
                            {"path": "assurance-index.json", "sha256": digest}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(audit_program, "ROOT", root):
                self.assertEqual(
                    audit_program._validate_manifest_artifact_binding(
                        manifest, [artifact]
                    ),
                    [],
                )
                artifact.write_text('{"changed":true}', encoding="utf-8")
                errors = audit_program._validate_manifest_artifact_binding(
                    manifest, [artifact]
                )
            self.assertIn("does not bind artifact", errors[0])

    def test_runtime_report_requires_gateway_da_and_mock_exclusion(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtime.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "environment": "testnet",
                        "gateway_checks": {
                            name: True for name in audit_program.REQUIRED_GATEWAY_CHECKS
                        },
                        "da_receipts": [
                            {
                                "provider": provider,
                                "submission_id": f"{provider}-receipt",
                                "payload_sha256": "b" * 64,
                                "retrieval_verified": True,
                            }
                            for provider in ("celestia", "near")
                        ],
                        "excluded_live_routes": sorted(
                            audit_program.REQUIRED_EXCLUDED_ROUTES
                        ),
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(audit_program._validate_runtime_report(path, commit), [])

            report = json.loads(path.read_text(encoding="utf-8"))
            report["gateway_checks"]["mtls"] = False
            path.write_text(json.dumps(report), encoding="utf-8")
            errors = audit_program._validate_runtime_report(path, commit)
            self.assertTrue(any("mtls" in error for error in errors))

    def test_privacy_review_requires_all_approvals(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "privacy.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "reviewer": "privacy-reviewer",
                        "data_inventory_approved": True,
                        "retention_policy_approved": True,
                        "redaction_tests_passed": True,
                        "public_content_reviewed": True,
                        "publisher_inventory_complete": True,
                        "blocking_findings_open": 0,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(audit_program._validate_privacy_review(path, commit), [])

    def test_public_requires_all_independent_review_domains(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_sha": commit,
                        "reviews": [
                            {
                                "domain": domain,
                                "reviewer": f"reviewer-{domain}",
                                "organization": "independent-org",
                                "approved": True,
                                "blocking_findings_open": 0,
                                "report_sha256": "c" * 64,
                            }
                            for domain in audit_program.REQUIRED_INDEPENDENT_DOMAINS
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                audit_program._validate_independent_reviews(path, commit), []
            )


if __name__ == "__main__":
    unittest.main()
