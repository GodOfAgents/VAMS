import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts/security/m0_4_vendor_baseline.json"
BASELINE_SHA256 = "3a4526acf33ab4adeff87da1553cb5e4493799c3696664c2d60a126a9aa086f4"
SPEC = importlib.util.spec_from_file_location("m0_4_gate", Path(__file__).with_name("m0_4_vendor_baseline_gate.py"))
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def local_digest(record):
    fields = ("scope", "owner_commit", "path", "rule", "start", "end", "file_sha256")
    payload = {field: record[field] for field in fields}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


class M04VendorBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, digest = gate.load_baseline(BASELINE, expected_digest=BASELINE_SHA256)
        assert digest == BASELINE_SHA256

    def owner_states(self):
        return {
            item["scope"]: gate.OwnerState(item["scope"], item["path"], item["commit"], True)
            for item in self.baseline["owners"]
        }

    def reconcile(self, observed, **overrides):
        args = {
            "first_party": 0,
            "unknown": 0,
            "scanner_version": "8.30.1",
            "scanner_sha256": "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509",
            "owner_states": self.owner_states(),
        }
        args.update(overrides)
        return gate.reconcile(self.baseline, observed, **args)

    def test_exact_valid_aggregate(self):
        counts = self.reconcile(copy.deepcopy(self.baseline["records"]))
        self.assertEqual(counts, {"first_party": 0, "m0_3a": 161, "m0_3b": 160, "m0_3c": 158, "vendor": 479, "unknown": 0})

    def test_first_party_finding(self):
        with self.assertRaises(gate.GateError):
            self.reconcile(copy.deepcopy(self.baseline["records"]), first_party=1)

    def test_added_omitted_and_duplicate_vendor_findings(self):
        records = copy.deepcopy(self.baseline["records"])
        added = copy.deepcopy(records[0])
        added["start"] += 100000
        added["end"] += 100000
        added["identity_sha256"] = local_digest(added)
        for observed in (records + [added], records[:-1], records + [copy.deepcopy(records[0])]):
            with self.subTest(size=len(observed)), self.assertRaises(gate.GateError):
                self.reconcile(observed)

    def test_identity_binding_mutations(self):
        mutations = {
            "moved_path": ("path", "contracts/lib/openzeppelin-contracts/test/moved.js"),
            "changed_rule": ("rule", "changed-rule"),
            "changed_start": ("start", 999999),
            "changed_end": ("end", 999999),
            "changed_file_hash": ("file_sha256", "0" * 64),
            "wrong_owner": ("scope", "m0_3b"),
            "wrong_owner_commit": ("owner_commit", "0" * 40),
        }
        for name, (field, value) in mutations.items():
            observed = copy.deepcopy(self.baseline["records"])
            observed[0][field] = value
            observed[0]["identity_sha256"] = local_digest(observed[0])
            with self.subTest(name=name), self.assertRaises(gate.GateError):
                self.reconcile(observed)

    def test_submodule_pin_drift_and_dirty_vendor(self):
        for name, replacement in {
            "pin": gate.OwnerState("m0_3a", gate.EXPECTED_OWNERS["m0_3a"][0], "0" * 40, True),
            "dirty": gate.OwnerState("m0_3a", gate.EXPECTED_OWNERS["m0_3a"][0], gate.EXPECTED_OWNERS["m0_3a"][1], False),
        }.items():
            states = self.owner_states()
            states["m0_3a"] = replacement
            with self.subTest(name=name), self.assertRaises(gate.GateError):
                self.reconcile(copy.deepcopy(self.baseline["records"]), owner_states=states)

    def test_unknown_ownership(self):
        with self.assertRaises(gate.GateError):
            self.reconcile(copy.deepcopy(self.baseline["records"]), unknown=1)

    def test_nested_finding_uses_deepest_gitlink_and_parent_rebinding_fails(self):
        nested = gate.EXPECTED_OWNERS["m0_3c"][0] + "/test/vector.json"
        submodules = {
            gate.EXPECTED_OWNERS["m0_3b"][0]: gate.EXPECTED_OWNERS["m0_3b"][1],
            gate.EXPECTED_OWNERS["m0_3c"][0]: gate.EXPECTED_OWNERS["m0_3c"][1],
        }
        self.assertEqual(gate.resolve_scope(nested, submodules), "m0_3c")
        observed = copy.deepcopy(self.baseline["records"])
        index = next(i for i, item in enumerate(observed) if item["scope"] == "m0_3c")
        observed[index]["scope"] = "m0_3b"
        observed[index]["owner_commit"] = gate.EXPECTED_OWNERS["m0_3b"][1]
        observed[index]["identity_sha256"] = local_digest(observed[index])
        with self.assertRaises(gate.GateError):
            self.reconcile(observed)

    def test_wrong_scanner_version_or_hash(self):
        for overrides in ({"scanner_version": "8.30.0"}, {"scanner_sha256": "0" * 64}):
            with self.subTest(overrides=overrides), self.assertRaises(gate.GateError):
                self.reconcile(copy.deepcopy(self.baseline["records"]), **overrides)

    def test_malformed_and_duplicate_baseline_entry(self):
        malformed = copy.deepcopy(self.baseline)
        del malformed["records"][0]["rule"]
        duplicate = copy.deepcopy(self.baseline)
        duplicate["records"][-1] = copy.deepcopy(duplicate["records"][0])
        for document in (malformed, duplicate):
            with self.assertRaises(gate.GateError):
                gate.validate_baseline(document)

    def test_baseline_matches_reviewed_repository_identity_sources(self):
        paths = {
            "m0_3a": ROOT / "docs/remediation/m0_3a_r1/decisions.json",
            "m0_3b": ROOT / "docs/remediation/m0_3b_r1/decisions.json",
            "m0_3c": ROOT / "docs/remediation/m0_3c_r1/decisions.json",
        }
        expected = []
        for scope, path in paths.items():
            document = json.loads(path.read_text(encoding="utf-8"))
            rows = document if isinstance(document, list) else document["records"]
            owner_path, owner_commit = gate.EXPECTED_OWNERS[scope]
            self.assertEqual(len(rows), self.baseline["counts"][scope])
            for row in rows:
                self.assertEqual((row["submodule"], row["submodule_commit"]), (owner_path, owner_commit))
                record = {
                    "scope": scope,
                    "owner_commit": owner_commit,
                    "path": row["relative_path"],
                    "rule": row["rule_id"],
                    "start": row["line_start"],
                    "end": row["line_end"],
                    "file_sha256": row["file_sha256"],
                }
                record["identity_sha256"] = local_digest(record)
                expected.append(record)
        expected.sort(key=lambda item: (item["scope"], item["path"], item["rule"], item["start"], item["end"], item["file_sha256"]))
        self.assertEqual(expected, self.baseline["records"])


if __name__ == "__main__":
    unittest.main()
