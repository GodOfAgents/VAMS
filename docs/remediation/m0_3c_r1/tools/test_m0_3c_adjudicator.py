"""Focused M0.3c-R1 security, provenance, and real-scanner regressions."""
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
    "m03c", Path(__file__).with_name("m0_3c_adjudicator.py")
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "docs/remediation/m0_3c_r1"
SCANNER = Path(
    "/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks"
)


class M03CAdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.relative = "test/token/ERC20/Example.test.js"
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
            "parent_submodule": M.PARENT_PREFIX,
            "parent_submodule_commit": M.PARENT_PIN,
            "parent_submodule_head": M.PARENT_PIN,
            "parent_submodule_clean": True,
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
        self.declarations = {
            "ERC20InvalidReceiver": [
                ("contracts/interfaces/draft-IERC6093.sol", "20")
            ]
        }
        self.kwargs = {
            "head": self.state["head"],
            "commit": M.PIN,
            "repo": self.root,
            "state": self.state,
            "manifest_sha256": "c" * 64,
            "owned_blobs": self.owned,
            "declared_errors": self.declarations,
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
        self.semantic = {
            "finding_id": self.identity["finding_id"],
            "relative_path": self.path,
            "rule_id": "generic-api-key",
            "line_start": 1,
            "line_end": 1,
            "file_sha256": self.identity["file_sha256"],
            "source_object_id": "f" * 40,
            "classification": "expected_custom_error_assertion",
            "verdict": "confirmed_noncredential_fixture",
            "context": {
                "kind": "custom_error_execution",
                "assertion_target": "this.token",
                "call_target": "this.token",
                "invoked_operation": "transfer",
                "error_name": "ERC20InvalidReceiver",
                "error_signature": "ERC20InvalidReceiver(address)",
                "error_selector": "ec442f05",
                "declaration_owner": {
                    "name": "IERC20Errors", "kind": "interface",
                    "path": "contracts/interfaces/draft-IERC6093.sol",
                    "source_sha256": "e" * 64, "source_object_id": "e" * 40,
                },
                "execution_targets": [{
                    "artifact": "$ERC20", "caller_path": self.relative,
                    "caller_sha256": "d" * 64, "caller_object_id": "f" * 40,
                }],
                "reachability_chains": [{
                    "artifact": "$ERC20", "containers": [
                        {"name": "$ERC20", "kind": "contract", "path": "contracts/mocks/token/ERC20Mock.sol"},
                        {"name": "IERC20Errors", "kind": "interface", "path": "contracts/interfaces/draft-IERC6093.sol"},
                    ],
                }],
            },
        }

    def build(self, decisions=None, report=None, **overrides):
        selected = [self.decision] if decisions is None else decisions
        proof = {(
            self.path, 1, 1
        ): ("expected_custom_error_assertion", "upstream_js_test", self.semantic["context"])}
        with mock.patch.object(M, "pinned_blob", return_value=(self.root / self.path).read_bytes()), mock.patch.object(M, "production_semantics", return_value=proof):
            return M.build_records(
                self.report if report is None else report,
                decisions=selected,
                semantic_records={self.identity["finding_id"]: self.semantic},
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
        self.assertFalse(M.approved_gate(
            potential_records, [potential],
            {self.identity["finding_id"]: self.semantic},
        ))
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
        self.assertFalse(M.approved_gate(
            unresolved_records, [unresolved],
            {self.identity["finding_id"]: self.semantic},
        ))

    def test_missing_stale_or_disagreeing_semantics_fail_closed(self):
        with mock.patch.object(
            M,
            "pinned_blob",
            return_value=(self.root / self.path).read_bytes(),
        ):
            missing = M.build_records(
                self.report,
                decisions=[self.decision],
                semantic_records={},
                **self.kwargs,
            )
        self.assertEqual(missing[0]["disposition"], "unresolved")
        stale = copy.deepcopy(self.semantic)
        stale["file_sha256"] = "d" * 64
        disagreeing = copy.deepcopy(self.semantic)
        disagreeing["classification"] = "ecdsa_public_key_der"
        for semantic in (stale, disagreeing):
            with self.subTest(semantic=semantic["classification"]):
                with mock.patch.object(
                    M,
                    "pinned_blob",
                    return_value=(self.root / self.path).read_bytes(),
                ):
                    records = M.build_records(
                        self.report,
                        decisions=[self.decision],
                        semantic_records={
                            self.identity["finding_id"]: semantic
                        },
                        **self.kwargs,
                    )
                self.assertEqual(records[0]["disposition"], "unresolved")
                self.assertFalse(M.approved_gate(
                    records,
                    [self.decision],
                    {self.identity["finding_id"]: semantic},
                ))

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
            "parent_submodule_commit": "d" * 40,
            "parent_submodule_head": "d" * 40,
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
        self.assertTrue(M.approved_gate(
            baseline, [self.decision],
            {self.identity["finding_id"]: self.semantic},
        ))
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

    def test_direct_tree_excludes_child_gitlinks_by_provenance(self):
        blobs, gitlinks = M.direct_tree(ROOT)
        self.assertEqual(gitlinks, M.CHILD_GITLINKS)
        self.assertEqual(len(blobs), 821)
        self.assertFalse(
            any(
                path == child or path.startswith(child + "/")
                for child in M.CHILD_GITLINKS
                for path in blobs
            )
        )
        child = next(iter(M.CHILD_GITLINKS))
        nested = [{
            "File": child + "/test/OwnedByChild.test.js",
            "RuleID": "generic-api-key",
            "StartLine": 1,
            "EndLine": 1,
        }]
        state = M.provenance(ROOT)
        with self.assertRaises(M.base.AdjudicationError):
            M.build_records(
                nested,
                head=state["head"],
                commit=state["submodule_commit"],
                repo=ROOT,
                state=state,
                manifest_sha256=M.base.digest(M.base.encoded(M.base.source_manifest(ROOT))),
                owned_blobs=blobs,
            )

    def test_parent_and_target_provenance_and_clean_pins(self):
        state = M.provenance(ROOT)
        self.assertEqual(state["parent_submodule_commit"], M.PARENT_PIN)
        self.assertEqual(state["parent_submodule_head"], M.PARENT_PIN)
        self.assertTrue(state["parent_submodule_clean"])
        self.assertEqual(state["submodule_commit"], M.PIN)
        self.assertEqual(state["submodule_head"], M.PIN)
        self.assertTrue(state["submodule_clean"])
        for field in ("parent_submodule_clean", "submodule_clean"):
            dirty_state = dict(self.state, **{field: False})
            self.assertEqual(self.build(state=dirty_state)[0]["disposition"], "unresolved")

    def test_generated_decisions_match_production_classifier_non_independent(self):
        """Generated-data consistency only; independent proof is the fresh scan test."""
        decisions = self.real_decisions()
        blobs, _ = M.direct_tree(ROOT)
        report = [{"File": d["relative_path"], "RuleID": d["rule_id"], "StartLine": d["line_start"], "EndLine": d["line_end"]} for d in decisions]
        semantics = M.production_semantics(ROOT, report, M.PIN, blobs)
        counts = {}
        for decision in decisions:
            proof = semantics[(decision["relative_path"], decision["line_start"], decision["line_end"])][0]
            counts[proof] = counts.get(proof, 0) + 1
        self.assertEqual(
            counts,
            {
                "expected_custom_error_assertion": 83,
                "ecdsa_public_key_der": 75,
            },
        )

    def test_path_normalization_and_no_cross_tranche_inheritance(self):
        relative = self.build(report=[{**self.report[0], "File": self.relative}])[0]
        dotted = self.build(report=[{**self.report[0], "File": "./" + self.relative}])[0]
        self.assertEqual(relative["finding_id"], dotted["finding_id"])
        self.assertEqual(relative["relative_path"], self.path)
        prior = M.base.read_json(ROOT / "docs/remediation/m0_3b_r1/decisions.json")["records"][0]
        with self.assertRaises(M.base.AdjudicationError):
            self.build([prior])

    def test_same_content_under_different_commit_fails_closed(self):
        changed = copy.deepcopy(self.decision)
        changed["submodule_commit"] = "d" * 40
        changed["submodule_head"] = "d" * 40
        self.assertEqual(self.build([changed])[0]["disposition"], "unresolved")
        old_id = M.base.stable_id(
            self.state["head"], M.PARENT_PIN, self.path, "generic-api-key", 1, 1
        )
        self.assertNotEqual(old_id, self.identity["finding_id"])

    def test_fresh_scanner_real_set_uses_independent_semantic_oracles(self):
        command = [
            sys.executable,
            str(Path(__file__).with_name("m0_3c_reconcile.py")),
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
        self.assertEqual(result["finding_count"], 158)
        self.assertEqual(result["path_count"], 22)
        self.assertTrue(result["child_gitlinks_excluded"])
        self.assertTrue(result["raw_removed"])
        self.assertEqual(result["proof_counts"], {
            "ecdsa_public_key_der": 75,
            "expected_custom_error_assertion": 83,
        })
        self.assertEqual(result["semantic_oracles"]["javascript"], "bounded_token_parser_v1")
        self.assertEqual(result["semantic_oracles"]["der"], "cryptography_load_der_public_key")
        self.assertEqual(result["semantic_oracles"]["der_library_version"], "50.0.1")

    def test_actual_raw_scanner_directory_is_deleted(self):
        state = M.provenance(ROOT)
        report, _, _, command, scanner_exit = M.scan_direct_tree(
            ROOT, SCANNER, state
        )
        raw_path = Path(command[command.index("--report-path") + 1])
        self.assertEqual(scanner_exit, 1)
        self.assertEqual(len(report), 158)
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
            "schema": "m0_3c_r1_run",
            "source_manifest_sha256": "c" * 64,
        }
        M.publish(
            output,
            [self.identity],
            [potential],
            metadata,
            [potential],
            {},
            self.owned,
            M.CHILD_GITLINKS,
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

    def test_m03a_and_m03b_artifacts_remain_byte_for_byte_unchanged(self):
        expected = {
            ROOT / "scripts/security/m0_3a_adjudicator.py":
                "4a8dc8fc1f53aaa1728dc2952fda5168582f1caf0fd94f336897456a9a78c485",
            ROOT / "scripts/security/test_m0_3a_adjudicator.py":
                "f0acabff5552842be578390e34dc694655206e8e4970df500ea3b74e34a38a9f",
            ROOT / "docs/remediation/m0_3a_r1/findings.json":
                "7a6828a1036a7d907fa68d393da606ee7d0f892aea1d70e1b64ffcb90345ba4f",
            ROOT / "docs/remediation/m0_3a_r1/decisions.json":
                "5f41aa64b31ead7918c2d9d07ec0a803f44af8e213aa2e1d55e404e7d67f16e4",
            ROOT / "docs/remediation/m0_3b_r1/tools/m0_3b_adjudicator.py":
                "784f31094ee9159d72706e2b62e34597f103bf6b318330042c469aa7ef7112fd",
            ROOT / "docs/remediation/m0_3b_r1/tools/test_m0_3b_adjudicator.py":
                "21432ebd83219d34fc0f144765441e50af76910380411af40456d0c2c12e7d81",
            ROOT / "docs/remediation/m0_3b_r1/decisions.json":
                "94a2e56f5682031b443eea77cad4f9d1324e7079dcc09dd1a46afcf10e14dbaf",
            ROOT / "docs/remediation/m0_3b_r1/findings.json":
                "965b2e4c98f78b0e352f5757cef8589988116630e5d4b3384b55aa560854fd75",
        }
        for path, expected_hash in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(M.base.digest(path.read_bytes()), expected_hash)

    def test_executable_mutation_matrix_passes(self):
        attestation = self.root / "semantic-attestation.json"
        oracle = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("m0_3c_semantic_oracle.py")),
                "--repo", str(ROOT),
                "--scanner", str(SCANNER),
                "--decisions", str(DATA / "decisions.json"),
                "--output", str(attestation),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(oracle.returncode, 0, oracle.stdout + oracle.stderr)
        oracle_result = json.loads(oracle.stdout)
        command = [
            sys.executable,
            str(Path(__file__).with_name("m0_3c_mutations.py")),
            "--repo",
            str(ROOT),
            "--decisions",
            str(DATA / "decisions.json"),
            "--semantic-attestation",
            str(attestation),
            "--semantic-attestation-sha256",
            oracle_result["attestation_sha256"],
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
