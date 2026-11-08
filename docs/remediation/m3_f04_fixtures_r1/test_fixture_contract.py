#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, tempfile, unittest
from copy import deepcopy
from pathlib import Path
import fixture_contract as fc

class FixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=fc.load()

    def rejects(self,mutate):
        value=deepcopy(self.doc);mutate(value)
        with self.assertRaises(fc.FixtureError):fc.validate_document(value)

    def test_exact_49_rows_and_closed_contract(self):
        result=fc.validate_document(self.doc)
        self.assertEqual(result["rows"],49)
        self.assertGreater(result["serialized_evaluations"],49)
        self.assertEqual(len({r["id"] for r in self.doc["rows"]}),49)

    def test_independent_option_b_vectors(self):
        vectors=json.loads((fc.ROOT/"docs/remediation/m3_f04_design_r1/ASSET_VECTORS.json").read_text())["vectors"]
        for vector in vectors:
            did=bytes.fromhex(vector["did"]);owner=bytes.fromhex(vector["owner_vkh"])
            pre=b"VAMS/agent/v1\0"+len(did).to_bytes(2,"big")+did+owner+bytes.fromhex(vector["seed_tx_id"])+vector["seed_index"].to_bytes(4,"big")
            self.assertEqual(pre.hex(),vector["preimage_hex"])
            self.assertEqual(hashlib.blake2b(pre,digest_size=32).hexdigest(),vector["token_name"])
        minimum=vectors[0]
        ascii_did=minimum["did"].encode()
        alternate=b"VAMS/agent/v1\0"+len(ascii_did).to_bytes(2,"big")+ascii_did+bytes.fromhex(minimum["owner_vkh"])+bytes.fromhex(minimum["seed_tx_id"])+minimum["seed_index"].to_bytes(4,"big")
        self.assertNotEqual(hashlib.blake2b(alternate,digest_size=32).hexdigest(),minimum["token_name"])

    def test_phase_separation(self):
        phases={r["id"]:r["phase"] for r in self.doc["rows"]}
        for row in ("schema_unknown","schema_duplicate","schema_boolean_integer","slash_proof_payload_alias","slash_payload_substitution"):
            self.assertEqual(phases[row],"contract_decode")
        self.assertEqual(phases["update_parallel_nonce"],"ledger_replay")

    def test_unknown_duplicate_and_incomplete_reject(self):
        self.rejects(lambda d:d["rows"][0].update(unknown=True))
        self.rejects(lambda d:d["rows"][1].update(id=d["rows"][0]["id"]))
        self.rejects(lambda d:d["rows"][0]["evaluations"][0].pop("script_context"))

    def test_boolean_overflow_and_hex_reject(self):
        self.rejects(lambda d:d["rows"][0]["parameters"]["data"]["fields"][4].update(int=True))
        self.rejects(lambda d:d["rows"][0]["parameters"]["data"]["fields"][4].update(int=2**64))
        self.rejects(lambda d:d["rows"][0]["parameters"]["data"]["fields"][1].update(bytes="GG"))

    def test_cbor_and_hash_rebinding_reject(self):
        self.rejects(lambda d:d["rows"][0]["parameters"].update(cbor_hex="00"))
        self.rejects(lambda d:d["rows"][0]["evaluations"][0]["script_context"].update(sha256="00"*32))

    def test_redeemer_is_bound_into_each_script_context(self):
        for row in self.doc["rows"]:
            for evaluation in row["evaluations"]:
                self.assertEqual(evaluation["redeemer"]["data"],evaluation["script_context"]["data"]["fields"][1])
        self.rejects(lambda d:d["rows"][0]["evaluations"][0]["script_context"]["data"]["fields"][1].update(constructor=99))

    def test_semantic_metadata_and_identity_are_frozen(self):
        self.rejects(lambda d:d["identity_contract"].update(domain_hex="00"))
        self.rejects(lambda d:d["identity_contract"].update(accepted_max256_token_name="00"*32))
        self.rejects(lambda d:d["rows"][0].update(phase="contract_decode"))
        self.rejects(lambda d:d["rows"][0].update(transition="deregister"))
        self.rejects(lambda d:d["rows"][1].update(mutation={"operation":"none","path":None,"before":None,"after":None}))

    def test_contract_decode_rows_are_complete_single_reason_controls(self):
        for row in self.doc["rows"]:
            if row["phase"]!="contract_decode":continue
            raw=bytes.fromhex(row["scenario"]["contract_payload_hex"])
            with self.assertRaises(fc.FixtureError):fc.decode_contract_payload(raw)
            pairs=json.loads(raw,object_pairs_hook=list)
            keys=[item[0] for item in pairs]
            self.assertTrue(set(fc.CONTRACT_KEYS).issubset(set(keys)))

    def test_isolated_value_and_parameter_mutations(self):
        rows={row["id"]:row for row in self.doc["rows"]}
        payout=rows["deregister_non_ada_loss"]["evaluations"][0]["script_context"]["data"]["fields"][0]["fields"][2]["list"][0]["fields"][1]
        encoded=json.dumps(payout,sort_keys=True)
        self.assertNotIn(fc.IDENTITY.hex(),encoded)
        self.assertNotIn(fc.OTHER_POLICY.hex(),encoded)
        self.assertNotEqual(rows["slash_reserve_redirect"]["parameters"]["sha256"],rows["slash_redirected_reserve"]["parameters"]["sha256"])

    def test_stake_only_mutation_preserves_asset_topology_and_mint_control(self):
        rows={row["id"]:row for row in self.doc["rows"]}
        spend=rows["register_declared_stake_only"]["evaluations"][0]["script_context"]["data"]["fields"][0]["fields"][2]["list"][0]["fields"][1]
        assets=spend["map"]
        policies={item["k"].get("bytes") for item in assets}
        self.assertEqual(policies,{"",fc.POLICY.hex()})
        mint=rows["register_declared_stake_only"]["evaluations"][1]["script_context"]["data"]
        valid=rows["register_valid"]["evaluations"][1]["script_context"]["data"]
        self.assertEqual(mint,valid)

    def test_inv10_alias_reject(self):
        self.rejects(lambda d:d["rows"][0]["scenario"]["evidence_envelope"].update(payload_hash=d["rows"][0]["scenario"]["evidence_envelope"]["bridge_proof"]))

    def test_duplicate_json_key_rejects(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"x.json";path.write_text('{"schema_version":"x","schema_version":"y"}')
            with self.assertRaises(fc.FixtureError):fc.load(path)

    def test_no_production_oracle_import(self):
        source=Path(fc.__file__).read_text()
        self.assertNotIn("agent_registry",source.splitlines()[:15])
        self.assertNotIn("cardano.validators",source)

if __name__=="__main__":unittest.main()
