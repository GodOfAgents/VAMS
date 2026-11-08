"""Security-property regressions and reconciliation with the actual M0.3a set."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("m03", Path(__file__).with_name("m0_3a_adjudicator.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/remediation/m0_3a_r1"


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = M.PREFIX + "/test/token/Example.test.js"
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
            )
        )
        ref = self.root / "review.md"
        ref.write_text("Local reviewed proof\n")
        self.state = dict(head="a" * 40, submodule=M.PREFIX, submodule_commit="b" * 40,
                          submodule_head="b" * 40, submodule_clean=True)
        self.report = [{"File": self.path, "RuleID": "generic-api-key", "StartLine": 1, "EndLine": 1}]
        self.kw = dict(head=self.state["head"], commit=self.state["submodule_commit"], repo=self.root,
                       state=self.state, manifest_sha256="c" * 64)
        self.decision = M.build_records(self.report, **self.kw)[0]
        self.decision.update(file_role="upstream_js_test", source_review="expected_custom_error_assertion",
                             disposition="confirmed_noncredential_fixture", rationale="expected_custom_error_assertion",
                             reviewer_status="accepted", reviewer="codex_local_source_review",
                             reachability={k: "absent" for k in M.DOMAINS},
                             evidence_refs=[{"path": "review.md", "sha256": M.digest(ref.read_bytes())}])

    def build(self, decision=None, report=None, **kw):
        with mock.patch.object(M, "git", return_value=(self.root / self.path).read_bytes()):
            return M.build_records(self.report if report is None else report,
                                   decisions=[self.decision if decision is None else decision], **(self.kw | kw))

    def test_all_three_dispositions(self):
        self.assertEqual(self.build()[0]["disposition"], "confirmed_noncredential_fixture")
        d = copy.deepcopy(self.decision)
        d.update(disposition="potential_credential", rationale="credential_or_ambiguous_datum",
                 source_review="credential_or_ambiguous_datum")
        self.assertEqual(self.build(d)[0]["disposition"], "potential_credential")
        d.update(disposition="unresolved", rationale="review_incomplete", source_review="not_proven")
        self.assertEqual(self.build(d)[0]["disposition"], "unresolved")

    def test_missing_evidence_falls_back(self):
        self.assertEqual(M.build_records(self.report, **self.kw)[0]["disposition"], "unresolved")
        for key in M.DECISION_FIELDS - {"finding_id"}:
            with self.subTest(key=key):
                d = copy.deepcopy(self.decision)
                del d[key]
                self.assertEqual(self.build(d)[0]["disposition"], "unresolved")

    def test_ambiguous_evidence_overrides_conflicting_confirmation(self):
        d = copy.deepcopy(self.decision)
        d.update(source_review="credential_or_ambiguous_datum", reviewer_status="pending_review")
        actual = self.build(d)
        self.assertEqual(actual[0]["disposition"], "potential_credential")
        self.assertFalse(M.approved_gate(actual, [self.decision]))

    def test_pending_reviewer_cannot_confirm(self):
        d = copy.deepcopy(self.decision)
        d["reviewer_status"] = "pending_review"
        with self.assertRaises(M.AdjudicationError):
            M.validate_record(d)
        self.assertEqual(self.build(d)[0]["disposition"], "unresolved")

    def test_each_identity_mismatch(self):
        mutations = {"head": "d" * 40, "submodule_commit": "d" * 40, "submodule_head": "d" * 40,
                     "file_sha256": "d" * 64, "relative_path": M.PREFIX + "/test/other.js",
                     "line_start": 2, "line_end": 2, "rule_id": "another-rule", "source_manifest_sha256": "d" * 64}
        for key, value in mutations.items():
            with self.subTest(key=key):
                d = copy.deepcopy(self.decision)
                d[key] = value
                self.assertEqual(self.build(d)[0]["disposition"], "unresolved")

    def test_unknown_and_duplicate_decisions(self):
        d = copy.deepcopy(self.decision)
        d["finding_id"] = "e" * 64
        with self.assertRaises(M.AdjudicationError):
            self.build(d)
        with self.assertRaises(M.AdjudicationError):
            M.build_records(self.report, decisions=[self.decision, self.decision], **self.kw)

    def test_duplicate_json_keys(self):
        p = self.root / "duplicate.json"
        p.write_text('{"finding_id":1,"finding_id":2}')
        with self.assertRaises(M.AdjudicationError):
            M.read_json(p)

    def test_duplicate_findings(self):
        with self.assertRaises(M.AdjudicationError):
            self.build(report=self.report * 2)

    def test_forbidden_nested_fields(self):
        for field in ("Secret", "raw_match", "Fingerprint", "Entropy", "snippet", "source_line", "private_key", "value"):
            d = copy.deepcopy(self.decision)
            d["evidence_refs"].append({"nested": [{field: "removed"}]})
            with self.subTest(field=field), self.assertRaises(M.AdjudicationError):
                self.build(d)

    def test_suspicious_rationale_and_reference(self):
        for text in ("x" * 300, "a" * 64, "https://example.invalid/?token=abc", "Bearer abc", "pending"):
            d = copy.deepcopy(self.decision)
            d["rationale"] = text
            with self.subTest(text=len(text)), self.assertRaises(M.AdjudicationError):
                M.validate_record(d)
            d = copy.deepcopy(self.decision)
            d["evidence_refs"][0]["path"] = text
            with self.assertRaises(M.AdjudicationError):
                M.validate_record(d) if text != "pending" else M.references_valid(self.root, d["evidence_refs"])

    def test_placeholder_and_reachable_rejected(self):
        for key, value in (("source_review", "not_proven"), ("file_role", "unreviewed"), ("evidence_refs", [])):
            d = copy.deepcopy(self.decision)
            d[key] = value
            with self.assertRaises(M.AdjudicationError):
                M.validate_record(d)
        d = copy.deepcopy(self.decision)
        d["reachability"]["ci_execution"] = "reachable"
        self.assertEqual(self.build(d)[0]["disposition"], "unresolved")

    def test_source_and_submodule_drift(self):
        (self.root / self.path).write_text("changed\n")
        self.assertEqual(self.build()[0]["disposition"], "unresolved")
        state = self.state | {"submodule_head": "e" * 40, "submodule_clean": False}
        self.assertEqual(self.build(state=state)[0]["disposition"], "unresolved")

    def test_missing_or_changed_reference(self):
        (self.root / "review.md").write_text("Changed review\n")
        self.assertEqual(self.build()[0]["disposition"], "unresolved")
        (self.root / "review.md").unlink()
        self.assertEqual(self.build()[0]["disposition"], "unresolved")

    def test_source_proof_is_exact_not_path_based(self):
        self.assertEqual(M.source_proof(self.root, self.path, 1, 1)[0], "expected_custom_error_assertion")
        (self.root / self.path).write_text("const arbitrary = 'test';\n")
        self.assertEqual(M.source_proof(self.root, self.path, 1, 1)[0], "not_proven")

    def test_potential_blocker_published_before_nonzero(self):
        d = copy.deepcopy(self.decision)
        d.update(disposition="potential_credential", rationale="credential_or_ambiguous_datum",
                 source_review="credential_or_ambiguous_datum")
        scanner = self.root / "scanner"
        scanner.write_bytes(b"synthetic scanner fixture")
        decisions = self.root / "decisions.json"
        state = self.state | {"submodule_commit": M.PIN, "submodule_head": M.PIN}
        d.update(state)
        d["finding_id"] = M.stable_id(state["head"], M.PIN, self.path, "generic-api-key", 1, 1)
        d["source_manifest_sha256"] = M.digest(M.encoded({}))
        decisions.write_bytes(M.encoded([d]))
        def run(command, **kwargs):
            if command[-1] == "version":
                return mock.Mock(stdout=b"8.30.1\n")
            raw = Path(command[command.index("--report-path") + 1])
            self.assertEqual(raw.parent.stat().st_mode & 0o777, 0o700)
            raw.write_text(json.dumps(self.report))
            self.raw_dir = raw.parent
            return mock.Mock(returncode=1)
        output = self.root / "evidence"
        with mock.patch.object(M, "SCANNER_SHA256", M.digest(scanner.read_bytes())), \
             mock.patch.object(M, "provenance", return_value=state), \
             mock.patch.object(M, "source_manifest", return_value={}), \
             mock.patch.object(M, "git", return_value=(self.root / self.path).read_bytes()), \
             mock.patch.object(M.subprocess, "run", side_effect=run):
            self.assertEqual(M.run_adjudication(self.root, scanner, output, decisions), 1)
        self.assertFalse(self.raw_dir.exists())
        self.assertEqual(M.read_json(output / "adjudication-ledger.json")["records"][0]["disposition"], "potential_credential")
        for line in (output / "source-checksums.sha256").read_text().splitlines():
            sha, name = line.split("  ")
            self.assertEqual(M.digest((output / name).read_bytes()), sha)

    def test_exact_gate_rejects_new_removed_changed_and_blockers(self):
        records = self.build()
        approved = copy.deepcopy(records)
        self.assertTrue(M.approved_gate(records, approved))
        self.assertFalse(M.approved_gate([], approved))
        changed = copy.deepcopy(records)
        changed[0]["file_sha256"] = "d" * 64
        self.assertFalse(M.approved_gate(changed, approved))
        self.assertFalse(M.approved_gate(records * 2, approved))
        for disposition in ("potential_credential", "unresolved"):
            changed = copy.deepcopy(records)
            changed[0].update(disposition=disposition, rationale="credential_or_ambiguous_datum",
                              source_review="credential_or_ambiguous_datum")
            self.assertFalse(M.approved_gate(changed, approved))

    def test_unsafe_paths_and_missing_lines(self):
        for path in ("../outside", "/absolute", "C:/absolute", "test/../x", "test\\x"):
            with self.assertRaises(M.AdjudicationError):
                M.build_records([self.report[0] | {"File": path}], **self.kw)
        with self.assertRaises(M.AdjudicationError):
            M.build_records([self.report[0] | {"StartLine": None}], **self.kw)

    def test_real_161_identity_count_reconciliation(self):
        self.assertEqual(M.digest((DATA / "findings.json").read_bytes()),
                         "7a6828a1036a7d907fa68d393da606ee7d0f892aea1d70e1b64ffcb90345ba4f")
        baseline = M.read_json(DATA / "findings.json")
        decisions = M.read_json(DATA / "decisions.json")
        self.assertEqual(len(baseline), 161)
        self.assertEqual(len(decisions), 161)
        self.assertEqual(len({r["relative_path"] for r in baseline}), 23)
        self.assertEqual({r["finding_id"] for r in baseline}, {d["finding_id"] for d in decisions})
        self.assertEqual(len({r["finding_id"] for r in baseline}), 161)
        for d in decisions:
            M.validate_record(d)
        for b, d in zip(sorted(baseline, key=lambda x: x["finding_id"]), sorted(decisions, key=lambda x: x["finding_id"])):
            for k in b:
                self.assertEqual(b[k], d[k])

    def test_real_set_rechecks_current_source_and_stale_manifest(self):
        decisions = M.read_json(DATA / "decisions.json")
        report = [{"File": d["relative_path"], "RuleID": d["rule_id"], "StartLine": d["line_start"], "EndLine": d["line_end"]} for d in decisions]
        state = M.provenance(ROOT)
        manifest_sha = M.digest(M.encoded(M.source_manifest(ROOT)))
        kwargs = dict(head=state["head"], commit=state["submodule_commit"], repo=ROOT, state=state, decisions=decisions)
        actual = M.build_records(report, manifest_sha256=manifest_sha, **kwargs)
        self.assertTrue(M.approved_gate(actual, decisions))
        stale = M.build_records(report, manifest_sha256="f" * 64, **kwargs)
        self.assertEqual(sum(r["disposition"] == "unresolved" for r in stale), 161)

    def test_new_finding_cannot_inherit_approval(self):
        report = self.report + [self.report[0] | {"RuleID": "another-rule"}]
        actual = self.build(report=report)
        self.assertEqual(len(actual), 2)
        self.assertEqual(sum(r["disposition"] == "unresolved" for r in actual), 1)
        self.assertFalse(M.approved_gate(actual, [self.decision]))


if __name__ == "__main__":
    unittest.main()
