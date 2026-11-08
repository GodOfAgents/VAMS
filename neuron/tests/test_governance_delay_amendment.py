import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).parents[2]
class GovernanceDelayAmendmentTests(unittest.TestCase):
    def setUp(self):
        self.amendment=json.loads((ROOT/'docs/remediation/repair_20261027/governance-48h-vectors.json').read_text())

    def test_frozen_parent_evidence_was_not_rewritten(self):
        for name,digest in self.amendment['parent_frozen_hashes'].items():
            self.assertEqual(hashlib.sha256((ROOT/'docs/remediation/m3_2a_r7'/name).read_bytes()).hexdigest(),digest)

    def test_source_uses_one_48_hour_delay(self):
        helper=(ROOT/'cardano/lib/vams/governance.ak').read_text()
        policy=(ROOT/'cardano/validators/governance_policies.ak').read_text()
        self.assertIn('normal_delay_ms: Int = 172_800_000',helper)
        self.assertIn('datum.queue_time + normal_delay_ms',policy)
        self.assertNotIn('86_400_000',helper+policy)
        self.assertFalse(self.amendment['execute_intent_enabled'])

    def test_new_datum_bytes_and_timing_are_bound(self):
        for row in self.amendment['vectors']:
            raw=bytes.fromhex(row['cbor_hex'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(len(raw),row['bytes'])
            self.assertEqual(row['native_evidence'],'NOT_RUN')
            value=row['value']
            if row['kind']=='authority':
                self.assertEqual(value['normal_delay_ms'],172800000)
                self.assertIn(b'\x1a'+(172800000).to_bytes(4,'big'),raw)
            else:self.assertEqual(value['execute_after']-value['queue_time'],172800000)

if __name__=='__main__':unittest.main()
