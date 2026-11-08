"""Canonical wire corpus only; no authorization/proof/live qualification."""
import json
from pathlib import Path
import unittest
from neuron.action_context import ActionContextV1, ActionContextError, WIRE_FIELDS

class ActionWireVectorTests(unittest.TestCase):
    def vectors(self):
        return json.loads((Path(__file__).parents[2] / 'docs/remediation/repair_20261030/ACTION-WIRE-VECTORS.json').read_text(encoding='utf-8'))['vectors']

    def test_shared_corpus_accepts_and_rejects(self):
        for row in self.vectors():
            with self.subTest(vector=row['id']):
                raw = bytes.fromhex(row['canonical_hex'])
                if row['accepted']:
                    value = ActionContextV1.from_bytes(raw)
                    self.assertEqual(value.canonical_bytes(), raw)
                    self.assertEqual(value.digest.hex(), row['sha256'])
                else:
                    with self.assertRaises(ActionContextError):
                        ActionContextV1.from_bytes(raw)

    def test_all_decoded_fields_match_frozen_words(self):
        for row in self.vectors():
            if row['accepted']:
                with self.subTest(vector=row['id']):
                    value = ActionContextV1.from_bytes(bytes.fromhex(row['canonical_hex']))
                    for index, field in enumerate(WIRE_FIELDS):
                        expected = bytes.fromhex(row['words_hex'][index]) if index < 13 else int(row['words_hex'][index], 16)
                        self.assertEqual(getattr(value, field), expected)

    def test_original_golden_vector_is_unchanged(self):
        path = Path(__file__).parents[2] / 'docs/remediation/repair_20261027/action-context-v1.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(self.vectors()[0]['canonical_hex'], original['canonical_hex'])
        self.assertEqual(self.vectors()[0]['sha256'], original['sha256'])
