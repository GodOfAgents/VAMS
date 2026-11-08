"""Independent fixture arithmetic and bytes only, never native/ledger qualification."""
import copy
import unittest
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('vams_remainder_reference26',Path(__file__).with_name('remainder_reference26.py'))
reference=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
ACTIONS,TOPOLOGY,conserves=reference.ACTIONS,reference.TOPOLOGY,reference.conserves
data_bytes_cbor,envelope_resource_subset,frame,mutate=reference.data_bytes_cbor,reference.envelope_resource_subset,reference.frame,reference.mutate

class RemainderReferenceTests(unittest.TestCase):
    def test_base_value_flows_conserve_for_all_lifecycle_fixtures(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                self.assertTrue(conserves(frame(action)))
                self.assertTrue(envelope_resource_subset(frame(action)))

    def test_every_topology_probe_preserves_scalar_value(self):
        for action in ACTIONS[:-1]:
            for variant in TOPOLOGY:
                with self.subTest(action=action,variant=variant):self.assertTrue(conserves(mutate(action,variant)))

    def test_global_limits_reject_at_one_over_and_accept_resource_subset_at_bound(self):
        for action in ACTIONS[:-1]:
            for variant in ('inputs_global','outputs_global','assets','datum_bytes','signers'):
                self.assertFalse(envelope_resource_subset(mutate(action,variant)))
                bounded=mutate(action,variant,True)
                self.assertTrue(envelope_resource_subset(bounded))
                self.assertTrue(conserves(bounded))

    def test_exact_topology_probes_remain_inside_global_bounds(self):
        for action in ACTIONS[:-1]:
            self.assertTrue(envelope_resource_subset(mutate(action,'inputs_exact')))
            self.assertTrue(envelope_resource_subset(mutate(action,'outputs_exact')))

    def test_chunked_data_bytes_profile_has_exact_896_and_897_sizes(self):
        self.assertEqual(len(data_bytes_cbor(bytes(866))),896)
        self.assertEqual(len(data_bytes_cbor(bytes(867))),897)
        self.assertEqual(data_bytes_cbor(bytes(64))[:2],b'\x58\x40')
        encoded=data_bytes_cbor(bytes(65))
        self.assertEqual(encoded[:3],b'\x5f\x58\x40');self.assertEqual(encoded[-1:],b'\xff')

    def test_eighth_vote_retains_real_token_and_receipt_value_in_reference(self):
        value=frame('eighth_vote')
        self.assertEqual(value['inputs'][0]['VAMS'],700);self.assertEqual(value['inputs'][1]['VAMS'],100)
        self.assertEqual(value['outputs'][0]['VAMS'],800)
        self.assertEqual(sum(value['outputs'][0][f'R{i}'] for i in range(8)),8)
        self.assertTrue(conserves(mutate('eighth_vote','maximum_width')))

    def test_value_oracle_detects_fee_and_asset_deficits(self):
        for action in ACTIONS:
            value=frame(action);value['outputs'][0]['ADA']+=1;self.assertFalse(conserves(value))
            value=frame(action);value['outputs'][0]['UNFUNDED']+=1;self.assertFalse(conserves(value))

    def test_window_mutations_preserve_values_without_inventing_cancel_maturity(self):
        for action,variant in [('vote','negative_window'),('cancel','negative_window'),
            ('finalize_passed','before_deadline'),('finalize_rejected','before_deadline'),
            ('vote','after_deadline'),('cancel','after_deadline'),('create','create_at_deadline'),
            ('cancelintent','empty_window'),('executeintent','before_execute')]:
            value=mutate(action,variant);self.assertTrue(conserves(value))
        self.assertFalse(envelope_resource_subset(mutate('cancelintent','empty_window')))
        # Shape-only model makes no claim about authentic creation history or native permission.
        self.assertTrue(envelope_resource_subset(frame('cancelintent')))

if __name__=='__main__':unittest.main(verbosity=2)
