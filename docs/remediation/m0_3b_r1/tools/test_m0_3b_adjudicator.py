"""Focused M0.3b-R1 security, provenance, and real-scanner regressions."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "m03b", Path(__file__).with_name("m0_3b_adjudicator.py")
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "docs/remediation/m0_3b_r1"
SCANNER = Path(
    "/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks"
)


class M03BAdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.relative = "test/token/Example.test.js"
        self.path = M.PREFIX + "/" + self.relative
        source = self.root / self.path
        source.parent.mkdir(parents=True)
        source.write_text(
            "".join(
                [
                    ".to.be.revertedWithCustom",
                    "Error(this.token, '",
                    "ERC20InvalidReceiver",
                    "')\n",
                ]
            ),
            encoding="utf-8",
        )
        reference = self.root / "review.md"
        reference.write_text("Local reviewed proof\n", encoding="utf-8")
        self.state = {
            "head": "a" * 40,
            "submodule": M.PREFIX,
            "submodule_commit": M.PIN,
            "submodule_head": M.PIN,
            "submodule_clean": True,
        }
        self.owned = {self.relative: {"object_id": "f" * 40, "mode": "100644"}}
        self.report = [
            {
                "File": self.relative,
                "RuleID": "generic-api-key",
                "StartLine": 1,
                "EndLine": 1,
            }
        ]
        self.kwargs = {
            "head": self.state["head"],
            "commit": M.PIN,
            "repo": self.root,
            "state": self.state,
            "manifest_sha256": "c" * 64,
            "owned_blobs": self.owned,
        }
        self.identity = M.build_records(self.report, **self.kwargs)[0]
        self.decision = copy.deepcopy(self.identity)
        self.decision.update(
            file_role="upstream_js_test",
            source_review="expected_custom_error_assertion",
            disposition="confirmed_noncredential_fixture",
            rationale="expected_custom_error_assertion",
            reviewer_status="accepted",
            reviewer="codex_local_source_review",
            reachability={domain: "absent" for domain in M.DOMAINS},
            evidence_refs=[
                {
                    "path": "review.md",
                    "sha256": M.base.digest(reference.read_bytes()),
                }
            ],
        )

    def build(self, decisions=None, report=None, **overrides):
        selected = [self.decision] if decisions is None else decisions
        with mock.patch.object(
            M,
            "pinned_blob",
            return_value=(self.root / self.path).read_bytes(),
        ):
            return M.build_records(
                self.report if report is None else report,
                decisions=selected,
                **(self.kwargs | overrides),
            )

    def real_decisions(self):
        document = M.base.read_json(DATA / "decisions.json")
        return document["records"]

    def test_all_three_dispositions_fail_closed_correctly(self):
        confirmed = self.build()
        self.assertEqual(
            confirmed[0]["disposition"], "confirmed_noncredential_fixture"
        )
        potential = copy.deepcopy(self.decision)
        potential.update(
            disposition="potential_credential",
            rationale="credential_or_ambiguous_datum",
            source_review="credential_or_ambiguous_datum",
        )
        potential_records = self.build([potential])
        self.assertEqual(
            potential_records[0]["disposition"], "potential_credential"
        )
        self.assertFalse(M.approved_gate(potential_records, [potential]))
        unresolved = copy.deepcopy(self.decision)
        unresolved.update(
            disposition="unresolved",
            rationale="review_incomplete",
            source_review="not_proven",
            file_role="unreviewed",
            reviewer_status="pending_review",
            reviewer="pending",
            reachability={domain: "not_assessed" for domain in M.DOMAINS},
        )
        unresolved_records = self.build([unresolved])
        self.assertEqual(unresolved_records[0]["disposition"], "unresolved")
        self.assertFalse(M.approved_gate(unresolved_records, [unresolved]))

    def test_missing_pending_and_reachable_evidence_cannot_confirm(self):
        self.assertEqual(
            M.build_records(self.report, **self.kwargs)[0]["disposition"],
            "unresolved",
        )
        for mutation in (
            ("reviewer_status", "pending_review"),
            ("evidence_refs", []),
            ("submodule_clean", False),
        ):
            with self.subTest(mutation=mutation):
                decision = copy.deepcopy(self.decision)
                decision[mutation[0]] = mutation[1]
                self.assertEqual(
                    self.build([decision])[0]["disposition"], "unresolved"
                )
        decision = copy.deepcopy(self.decision)
        decision["reachability"]["ci_execution"] = "reachable"
        self.assertEqual(
            self.build([decision])[0]["disposition"], "unresolved"
        )

    def test_every_binding_and_manifest_drift_fails_closed(self):
        mutations = {
            "head": "d" * 40,
            "submodule_commit": "d" * 40,
            "submodule_head": "d" * 40,
            "file_sha256": "d" * 64,
            "source_manifest_sha256": "d" * 64,
            "relative_path": M.PREFIX + "/test/token/Other.test.js",
            "rule_id": "another-rule",
            "line_start": 2,
            "line_end": 2,
        }
        for key, value in mutations.items():
            with self.subTest(key=key):
                decision = copy.deepcopy(self.decision)
                decision[key] = value
                self.assertEqual(
                    self.build([decision])[0]["disposition"], "unresolved"
                )

    def test_add_omit_duplicate_and_rebind_fail_exact_gate(self):
        baseline = self.build()
        self.assertTrue(M.approved_gate(baseline, [self.decision]))
        added_report = self.report + [
            {**self.report[0], "RuleID": "another-rule"}
        ]
        added = self.build(report=added_report)
        self.assertFalse(M.approved_gate(added, [self.decision]))
        self.assertEqual(
            sum(record["disposition"] == "unresolved" for record in added), 1
        )
        self.assertFalse(M.approved_gate([], [self.decision]))
        with self.assertRaises(M.base.AdjudicationError):
            self.build(report=self.report * 2)
        changed = copy.deepcopy(baseline)
        changed[0]["file_sha256"] = "d" * 64
        self.assertFalse(M.approved_gate(changed, [self.decision]))

    def test_unknown_and_duplicate_decisions_reject(self):
        unknown = copy.deepcopy(self.decision)
        unknown["finding_id"] = "e" * 64
        with self.assertRaises(M.base.AdjudicationError):
            self.build([unknown])
        with self.assertRaises(M.base.AdjudicationError):
            self.build([self.decision, self.decision])

    def test_nested_sensitive_fields_reject_recursively(self):
        for field in (
            "Secret",
            "raw_match",
            "Fingerprint",
            "Entropy",
            "snippet",
            "source_line",
            "private_key",
            "value",
        ):
            decision = copy.deepcopy(self.decision)
            decision["evidence_refs"].append(
                {"nested": [{"deeper": [{field: "removed"}]}]}
            )
            with self.subTest(field=field), self.assertRaises(
                M.base.AdjudicationError
            ):
                self.build([decision])

    def test_arbitrary_vendor_test_content_is_not_proof(self):
        (self.root / self.path).write_text(
            "const arbitrary = 'test';\n", encoding="utf-8"
        )
        self.assertEqual(
            M.source_proof(self.root, self.path, 1, 1),
            ("not_proven", "unreviewed"),
        )

    def test_direct_tree_excludes_nested_gitlinks_by_provenance(self):
        blobs, gitlinks = M.direct_tree(ROOT)
        self.assertEqual(
            gitlinks[M.NESTED_OPENZEPPELIN],
            M.NESTED_OPENZEPPELIN_PIN,
        )
        self.assertFalse(
            any(
                path == M.NESTED_OPENZEPPELIN
                or path.startswith(M.NESTED_OPENZEPPELIN + "/")
                for path in blobs
            )
        )
        nested = [
            {
                "File": M.NESTED_OPENZEPPELIN
                + "/test/token/ERC20/ERC20.test.js",
                "RuleID": "generic-api-key",
                "StartLine": 1,
                "EndLine": 1,
            }
        ]
        state = M.provenance(ROOT)
        with self.assertRaises(M.base.AdjudicationError):
            M.build_records(
                nested,
                head=state["head"],
                commit=state["submodule_commit"],
                repo=ROOT,
                state=state,
                manifest_sha256=M.base.digest(
                    M.base.encoded(M.base.source_manifest(ROOT))
                ),
                owned_blobs=blobs,
            )

    def test_direct_submodule_provenance_and_clean_pin(self):
        state = M.provenance(ROOT)
        self.assertEqual(state["submodule_commit"], M.PIN)
        self.assertEqual(state["submodule_head"], M.PIN)
        self.assertTrue(state["submodule_clean"])
        dirty_state = dict(self.state, submodule_clean=False)
        self.assertEqual(
            self.build(state=dirty_state)[0]["disposition"], "unresolved"
        )

    def test_real_source_semantics_cover_all_records(self):
        decisions = self.real_decisions()
        counts = {}
        for decision in decisions:
            proof = M.source_proof(
                ROOT,
                decision["relative_path"],
                decision["line_start"],
                decision["line_end"],
            )[0]
            counts[proof] = counts.get(proof, 0) + 1
        self.assertEqual(
            counts,
            {
                "expected_custom_error_assertion": 83,
                "ecdsa_public_key_der": 75,
                "erc7201_storage_slot_constant": 2,
            },
        )

    def test_real_160_identity_and_exact_gate(self):
        decisions = self.real_decisions()
        self.assertEqual(len(decisions), 160)
        self.assertEqual(len({item["finding_id"] for item in decisions}), 160)
        self.assertEqual(
            len({item["relative_path"] for item in decisions}), 24
        )
        state = M.provenance(ROOT)
        blobs, _ = M.direct_tree(ROOT)
        manifest_sha = M.base.digest(M.base.encoded(M.base.source_manifest(ROOT)))
        report = [
            {
                "File": item["relative_path"],
                "RuleID": item["rule_id"],
                "StartLine": item["line_start"],
                "EndLine": item["line_end"],
            }
            for item in decisions
        ]
        records = M.build_records(
            report,
            head=state["head"],
            commit=state["submodule_commit"],
            decisions=decisions,
            repo=ROOT,
            state=state,
            manifest_sha256=manifest_sha,
            owned_blobs=blobs,
        )
        self.assertTrue(M.approved_gate(records, decisions))

    def test_fresh_scanner_reconciliation_uses_independent_executable(self):
        command = [
            sys.executable,
            str(Path(__file__).with_name("m0_3b_reconcile.py")),
            "--repo",
            str(ROOT),
            "--scanner",
            str(SCANNER),
            "--decisions",
            str(DATA / "decisions.json"),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["finding_count"], 160)
        self.assertEqual(result["path_count"], 24)
        self.assertTrue(result["nested_openzeppelin_excluded"])
        self.assertTrue(result["raw_removed"])

    def test_actual_raw_scanner_directory_is_deleted(self):
        state = M.provenance(ROOT)
        report, _, _, command, scanner_exit = M.scan_direct_tree(
            ROOT, SCANNER, state
        )
        raw_path = Path(command[command.index("--report-path") + 1])
        self.assertEqual(scanner_exit, 1)
        self.assertEqual(len(report), 160)
        self.assertFalse(raw_path.exists())
        self.assertFalse(raw_path.parent.exists())

    def test_potential_blocker_publication_is_sanitized(self):
        potential = copy.deepcopy(self.decision)
        potential.update(
            disposition="potential_credential",
            rationale="credential_or_ambiguous_datum",
            source_review="credential_or_ambiguous_datum",
        )
        output = self.root / "published"
        metadata = {
            **self.state,
            "schema": "m0_3b_r1_run",
            "source_manifest_sha256": "c" * 64,
        }
        M.publish(
            output,
            [self.identity],
            [potential],
            metadata,
            [potential],
            {},
            {M.NESTED_OPENZEPPELIN: M.NESTED_OPENZEPPELIN_PIN},
        )
        ledger = M.base.read_json(output / "ledger.json")
        self.assertEqual(
            ledger["records"][0]["disposition"], "potential_credential"
        )
        self.assertNotIn("raw", (output / "ledger.json").read_text())
        for line in (output / "source-checksums.sha256").read_text().splitlines():
            sha256, name = line.split("  ")
            self.assertEqual(
                M.base.digest((output / name).read_bytes()), sha256
            )

    def test_m03a_artifacts_remain_byte_for_byte_unchanged(self):
        expected = {
            ROOT / "scripts/security/m0_3a_adjudicator.py":
                "4a8dc8fc1f53aaa1728dc2952fda5168582f1caf0fd94f336897456a9a78c485",
            ROOT / "scripts/security/test_m0_3a_adjudicator.py":
                "f0acabff5552842be578390e34dc694655206e8e4970df500ea3b74e34a38a9f",
            ROOT / "docs/remediation/m0_3a_r1/findings.json":
                "7a6828a1036a7d907fa68d393da606ee7d0f892aea1d70e1b64ffcb90345ba4f",
            ROOT / "docs/remediation/m0_3a_r1/decisions.json":
                "5f41aa64b31ead7918c2d9d07ec0a803f44af8e213aa2e1d55e404e7d67f16e4",
        }
        for path, expected_hash in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(M.base.digest(path.read_bytes()), expected_hash)

    def test_executable_mutation_matrix_passes(self):
        command = [
            sys.executable,
            str(Path(__file__).with_name("m0_3b_mutations.py")),
            "--repo",
            str(ROOT),
            "--decisions",
            str(DATA / "decisions.json"),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
