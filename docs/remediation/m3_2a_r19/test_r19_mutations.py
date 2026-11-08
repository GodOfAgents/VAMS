from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]
ORACLE_PATH = HERE / "docs/remediation/m3_2a_r9/address_value_oracle.py"
DATUM_PATH = HERE / "docs/remediation/m3_2a_r7/DATUM_VECTORS.json"

def _record_fixture():
    document = json.loads(DATUM_PATH.read_text())
    vector = next(item for item in document["vectors"] if item["accepted"] and item["kind"] == "record")
    return vector, {"kind": "VoteLockRecordV1", "constructor_index": 0,
                    "fields": [[key, value] for key, value in vector["value"].items()],
                    "cbor_hex": vector["cbor_hex"]}

def _load(path):
    spec = importlib.util.spec_from_file_location("r19_mutation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class R19MutationTests(unittest.TestCase):
    def test_canonical_comparison_removal_is_detected(self):
        vector, datum = _record_fixture()
        import sys
        sys.path.insert(0, str(ORACLE_PATH.parent))
        import address_value_oracle as oracle
        original = oracle._cbor_encode
        try:
            oracle._cbor_encode = lambda _node: b""
            with self.assertRaises(oracle.OracleError):
                oracle._parse_inline_fields(datum, "VoteLockRecordV1")
        finally:
            oracle._cbor_encode = original
        source = ORACLE_PATH.read_text()
        mutated = source.replace("if encoded!=canonical:", "if False:", 1)
        self.assertNotEqual(mutated, source)
        with tempfile.TemporaryDirectory(prefix="m32a-r19-cbor-") as td:
            root = Path(td)
            path = root / "address_value_oracle.py"
            path.write_text(mutated)
            module = _load(path)
            module._cbor_encode = lambda _node: b""
            values, encoded, _node = module._parse_inline_fields(datum, "VoteLockRecordV1")
            self.assertEqual(values, dict(vector["value"]))
            self.assertEqual(encoded, bytes.fromhex(vector["cbor_hex"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
