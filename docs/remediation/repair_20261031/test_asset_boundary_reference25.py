"""Independent bytes/value checks only; never native Aiken/ledger acceptance."""
from collections import Counter
import copy
import json
from pathlib import Path
import unittest
import importlib.util
spec = importlib.util.spec_from_file_location('vams_asset_boundary_reference25', Path(__file__).with_name('asset_boundary_reference25.py'))
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
conserves, definitions, fixture_flow = reference.conserves, reference.definitions, reference.fixture_flow
h, parts, vector = reference.h, reference.parts, reference.vector

E = Path(__file__).parent
R = E.parent

class AssetReferenceTests(unittest.TestCase):
    def setUp(self):
        self.golden = json.loads((R / 'repair_20261028/GOLDEN-VECTORS.json').read_text(encoding='utf-8'))
        self.timing = json.loads((R / 'repair_20261030/GOVERNANCE-TIME-VECTORS.json').read_text(encoding='utf-8'))
        self.parent = json.loads((R / 'm3_2a_r7/ACCEPTANCE_MATRIX.json').read_text(encoding='utf-8'))
        self.rows = definitions(self.golden, self.timing)

    def test_current_canonical_preimages_match_frozen_bytes(self):
        preimage = b''.join(parts(self.golden))
        self.assertEqual(preimage.hex(), vector(self.golden, 'proposal_name')['preimage_hex'])
        self.assertEqual(h(preimage).hex(), vector(self.golden, 'proposal_name')['digest_hex'])
        for row in self.golden['asset_vectors'] + self.timing['asset_vectors']:
            self.assertEqual(h(bytes.fromhex(row['preimage_hex'])).hex(), row['digest_hex'])

    def test_all25_parent_id_transition_reference_pairs_are_preserved(self):
        parent = [r for r in self.parent['rows'] if r['id'].startswith('asset_boundary_')]
        self.assertEqual(len(parent), 25)
        for original, defined in zip(parent, self.rows, strict=True):
            self.assertEqual((original['id'], original['transition'], original['reference']),
                (defined['parent_id'], defined['parent_transition'], defined['parent_reference']))
            self.assertEqual(original['expectation'], 'reject')

    def test_malformed_names_are_distinct_bounded_and_not_current_names(self):
        self.assertEqual(len({row['mutated_asset_hex'] for row in self.rows}), 25)
        for row in self.rows:
            name = bytes.fromhex(row['mutated_asset_hex'])
            self.assertNotEqual(name.hex(), row['correct_asset_hex'])
            self.assertEqual(len(name), 31 if row['index'] == 24 else 32)

    def test_domain_epoch_nonce_and_field_order_mutations_have_exact_shapes(self):
        original = parts(self.golden)
        self.assertTrue(bytes.fromhex(self.rows[0]['mutated_preimage_hex']).startswith(b'VAMS/intent/v1\0'))
        self.assertTrue(bytes.fromhex(self.rows[1]['mutated_preimage_hex']).startswith(b'VAMS/proposal/v1\0'))
        for index, component, expected in [(6,4,b'\2\0\0\0'),(7,4,(2).to_bytes(8,'big')),
            (8,5,bytes(4)),(9,5,(1).to_bytes(8,'big')),(17,11,(10).to_bytes(4,'big')),
            (18,11,(10).to_bytes(8,'little')),(19,12,(2000).to_bytes(8,'little'))]:
            modified = list(original); modified[component] = expected
            self.assertEqual(bytes.fromhex(self.rows[index]['mutated_preimage_hex']), b''.join(modified))
        swapped = list(original); swapped[8],swapped[9] = swapped[9],swapped[8]
        self.assertEqual(bytes.fromhex(self.rows[21]['mutated_preimage_hex']), b''.join(swapped))

    def test_truncation_preserves_preimage_but_not_full32byte_name(self):
        self.assertEqual(bytes.fromhex(self.rows[24]['mutated_preimage_hex']), b''.join(parts(self.golden)))
        self.assertEqual(bytes.fromhex(self.rows[24]['mutated_asset_hex']), h(b''.join(parts(self.golden)))[:31])

    def test_all25_synthetic_mutant_value_flows_conserve(self):
        for row in self.rows:
            with self.subTest(id=row['parent_id']):
                flow = fixture_flow(self.golden, self.timing, row)
                self.assertTrue(flow['conserves_arithmetically'])
                self.assertTrue(conserves(flow['inputs'],flow['outputs'],flow['mint'],flow['fee']))

    def test_value_oracle_detects_ada_and_token_deficits(self):
        for row in self.rows:
            flow = fixture_flow(self.golden, self.timing, row)
            outputs = copy.deepcopy(flow['outputs']); outputs[0][('', '')] += 1
            self.assertFalse(conserves(flow['inputs'], outputs, flow['mint'], flow['fee']))
            outputs = copy.deepcopy(flow['outputs']); outputs[0][('ab' * 28, 'cd' * 32)] += 1
            self.assertFalse(conserves(flow['inputs'], outputs, flow['mint'], flow['fee']))
        self.assertFalse(conserves([Counter({('', ''): 1})], [Counter({('', ''): 2})], [], 0))

    def test_every_new_definition_remains_unqualified(self):
        for row in self.rows:
            self.assertEqual(row['amendment_status'], 'PROPOSED_V2_REFINEMENT_REVIEW_PENDING')
            self.assertFalse(row['acceptance_credit'])
            for key in ['native_status', 'ledger_status', 'budget_status']:
                self.assertEqual(row[key], 'NOT_RUN')

if __name__ == '__main__':
    unittest.main(verbosity=2)
