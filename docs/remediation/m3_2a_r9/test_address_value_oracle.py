import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

import address_value_oracle as oracle
from address_value_oracle import (
    OracleError, LedgerSnapshot, OutputRecord, asset_preimage,
    enterprise_address, check_datum_size, validate_topology_record,
    validate_topology_counts, validate_value_flow, floor_sqrt,
    majority_result, validate_lifecycle, require_ledger_snapshot,
    parse_snapshot_mapping, validate_reserve_outputs, validate_output_record,
    validate_inline_datum,
)

ROOT = Path(__file__).resolve().parents[3]
DATUMS = ROOT / "docs/remediation/m3_2a_r7/DATUM_VECTORS.json"
TOPOLOGY = ROOT / "docs/remediation/m3_2a_r7/TRANSITION_TOPOLOGY.json"

class R13OracleTests(unittest.TestCase):
    def test_addresses_and_canonical_target(self):
        for network, key_header, script_header in ((0,"60","70"),(1,"61","71"),(15,"6f","7f")):
            self.assertTrue(enterprise_address(network,"key","44"*28).hex().startswith(key_header))
            self.assertTrue(enterprise_address(network,"script","55"*28).hex().startswith(script_header))
        for args in ((True,"key","44"*28),(16,"key","44"*28),(1,"stake","44"*28),(1,"key","44"*27)):
            with self.assertRaises(OracleError): enterprise_address(*args)
        fields=["00"*28,"44"*32,"0000000000000009","22"*28,"55"*32,"0664656d6f2f31"]
        pre,digest=asset_preimage("proposal",fields)
        self.assertEqual(digest.hex(),"dcdaf2493970b87ad996e01f97bdcf9b8a1c866c650f3e210cace22dbcdf4420")
        for bad in ("0664656d6f2f31 ","0664656d6f2f31\t","0564656d6f2f31","0764656d6f2f31","00","21"+"aa"*32):
            mutated=list(fields); mutated[-1]=bad
            with self.assertRaises(OracleError): asset_preimage("proposal",mutated)

    def test_topology_literal_records_and_every_field_mutation(self):
        records=json.loads(TOPOLOGY.read_text())["transitions"]
        for record in records:
            name=record["id"]
            self.assertTrue(validate_topology_record(name,record))
            for field in record:
                mutated=json.loads(json.dumps(record))
                if isinstance(mutated[field], dict): mutated[field]["_mutation"]=True
                elif isinstance(mutated[field], list): mutated[field].append("mutation")
                elif isinstance(mutated[field], int): mutated[field]+=1
                else: mutated[field]=str(mutated[field])+"-mutation"
                with self.assertRaises(OracleError): validate_topology_record(name,mutated)
        counts={"inputs":2,"outputs":1,"change_outputs":2,"mint":1,"burn":0,"authority_reference":0}
        self.assertTrue(validate_topology_counts("genesis",counts))
        bad=dict(counts); bad["authority_reference"]=99
        with self.assertRaises(OracleError): validate_topology_counts("genesis",bad)
        with self.assertRaises(OracleError): validate_topology_counts([],counts)

    def test_bounded_value_arithmetic_and_boundaries(self):
        maxv=(1<<64)-1
        validate_value_flow({"lovelace":maxv},{"lovelace":maxv},{},{},0)
        for bad in (1<<256, True, None, -1, 1.0, "1"):
            with self.assertRaises(OracleError): validate_value_flow({"lovelace":bad},{"lovelace":bad},{},{},0)
            with self.assertRaises(OracleError): floor_sqrt(bad)
            with self.assertRaises(OracleError): majority_result(bad,0,1,bad)
            with self.assertRaises(OracleError): validate_lifecycle(bad,bad,0,bad)
        with self.assertRaises(OracleError): validate_value_flow({"lovelace":maxv},{"lovelace":maxv},{ "lovelace":1},{},0)
        with self.assertRaises(OracleError): majority_result(maxv,1,1,maxv)
        with self.assertRaises(OracleError): validate_lifecycle(maxv,maxv,1,0)
        with self.assertRaises(OracleError): majority_result(0,0,0,1)
        self.assertEqual(validate_lifecycle(100,200,100,100),"at")

    def _snapshot(self):
        return {"schema_version":"m3.2a-ledger-snapshot-v1","network_id":1,
                "fetched_at_ms":1000,"max_age_ms":100,"min_fee_a":44,
                "min_fee_b":155381,"max_tx_size":16384,"max_value_size":5000,
                "max_tx_ex_units":10,"max_block_ex_units":20,
                "cost_models_digest":"aa"*32}

    def test_snapshot_cli_closed_schema_and_sanitized_failures(self):
        good=json.dumps(self._snapshot())
        rc=oracle.main(["--snapshot-json",good,"--expected-network","1","--now-ms","1050"])
        self.assertEqual(rc,0)
        bads=[{},{"network_id":"wrong"},[],None,
              dict(self._snapshot(),unknown=1),
              dict(self._snapshot(),network_id=2),
              dict(self._snapshot(),fetched_at_ms=0,max_age_ms=1),
              dict(self._snapshot(),min_fee_a=1<<256)]
        for value in bads:
            payload="null" if value is None else json.dumps(value)
            out=io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc=oracle.main(["--snapshot-json",payload,"--expected-network","1","--now-ms","1050"])
            self.assertNotEqual(rc,0)
            self.assertEqual(json.loads(out.getvalue()),{"error":"oracle validation failed","ok":False})
            self.assertNotIn("Traceback",out.getvalue())
        duplicate='{"schema_version":"m3.2a-ledger-snapshot-v1","schema_version":"x"}'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(oracle.main(["--snapshot-json",duplicate,"--expected-network","1","--now-ms","1050"]),0)
        self.assertNotEqual(oracle.main(["--snapshot-json",good]),0)

    def test_snapshot_callable_types(self):
        good=LedgerSnapshot(1,1000,100,44,155381,16384,5000,10,20,"aa"*32)
        self.assertTrue(require_ledger_snapshot(good,1,1050))
        for bad in (LedgerSnapshot(True,1000,100,44,155381,16384,5000,10,20,"aa"*32),
                    LedgerSnapshot(1,1000,True,44,155381,16384,5000,10,20,"aa"*32)):
            with self.assertRaises(OracleError): require_ledger_snapshot(bad,1,1050)
        with self.assertRaises(OracleError): parse_snapshot_mapping([],1,1050)

    def test_concrete_reserve_destinations_and_mutations(self):
        voter="11"*28; proposer="22"*28
        outputs=[
            {"address_hex":enterprise_address(1,"key",voter).hex(),"credential_kind":"key","network_id":1,"lovelace":10,"assets":{"locked_vams":100},"datum_form":"none","transition_role":"voter_refund:"+voter},
            {"address_hex":enterprise_address(1,"key",proposer).hex(),"credential_kind":"key","network_id":1,"lovelace":30,"assets":{},"datum_form":"none","transition_role":"proposer_refund"},
        ]
        voters=[{"voter_vkh":voter,"locked_vams":100,"reserve_lovelace":10}]
        self.assertTrue(validate_reserve_outputs(outputs,voters,{"proposer_vkh":proposer,"lovelace":30},transition="cancelintent"))
        for mutation in (
            lambda: [dict(outputs[0],address_hex=enterprise_address(0,"key",voter).hex(),network_id=0)],
            lambda: [dict(outputs[0],credential_kind="script")],
            lambda: [dict(outputs[0],lovelace=9)],
            lambda: [dict(outputs[0],assets={"locked_vams":50})],
            lambda: [dict(outputs[0],transition_role="proposer_refund")],
        ):
            with self.assertRaises(OracleError):
                validate_reserve_outputs(mutation(),voters,{"proposer_vkh":proposer,"lovelace":30},transition="cancelintent")
        with self.assertRaises(OracleError): validate_reserve_outputs({},[],None)

    def test_canonical_datums_and_mutations(self):
        vectors=json.loads(DATUMS.read_text())["vectors"]
        kinds={"authority":"AuthorityDatumV1","proposal":"ProposalDatumV1","record":"VoteLockRecordV1","intent":"IntentDatumV1"}
        for vector in vectors:
            kind=kinds[vector["kind"]]
            datum={"kind":kind,"constructor_index":0,
                   "fields":[[key,value] for key,value in vector["value"].items()],
                   "cbor_hex":vector["cbor_hex"]}
            frozen=dict(vector); frozen["kind"]=kind
            if not vector["accepted"]:
                with self.assertRaises(OracleError): validate_inline_datum(datum,vector["id"])
                continue
            self.assertTrue(validate_inline_datum(datum,vector["id"]))
            for mutated in (
                dict(datum,constructor_index=1),
                dict(datum,fields=datum["fields"][:-1]),
                dict(datum,cbor_hex=datum["cbor_hex"][:-2]+"00"),
            ):
                with self.assertRaises(OracleError): validate_inline_datum(mutated,frozen)
        malformed={"kind":"VoteLockRecordV1","constructor_index":0,
                    "fields":[["voter_vkh","11"*28],["locked_vams",1],["support",True],["weight",1],["receipt_name","aa"*32]],
                    "cbor_hex":"d879"}
        with self.assertRaises(OracleError): validate_inline_datum(dict(malformed,fields=malformed["fields"][:-1]))

    def test_r15_datum_registry_and_exact_reserves(self):
        vectors=json.loads(DATUMS.read_text())["vectors"]
        vector=next(v for v in vectors if v["accepted"] and v["kind"]=="record")
        datum={"kind":"VoteLockRecordV1","constructor_index":0,"fields":[[k,v] for k,v in vector["value"].items()],"cbor_hex":vector["cbor_hex"]}
        self.assertTrue(validate_inline_datum(datum,vector["id"]))
        fake=dict(vector,cbor_hex="d87900",byte_length=3)
        with self.assertRaises(OracleError): validate_inline_datum(datum,fake)
        with self.assertRaises(OracleError): validate_inline_datum(datum,"unknown-vector")
        voter="11"*28
        outputs=[{"address_hex":enterprise_address(1,"key",voter).hex(),"credential_kind":"key","network_id":1,"lovelace":10,"assets":{"locked_vams":101},"datum_form":"none","transition_role":"voter_refund:"+voter}]
        with self.assertRaises(OracleError): validate_reserve_outputs(outputs,[{"voter_vkh":voter,"locked_vams":100,"reserve_lovelace":10}],transition="expireintent")
        with self.assertRaises(OracleError): validate_value_flow({"locked_vams":101},{"locked_vams":101},{},{},0,{"locked_vams":100})
        wrong={"address_hex":enterprise_address(1,"script","22"*28).hex(),"credential_kind":"script","network_id":1,"lovelace":999,"assets":{"authority_nft":99},"datum_form":"inline","transition_role":"authority_continuation"}
        with self.assertRaises(OracleError): validate_reserve_outputs([wrong],[],authority_output=wrong)

    def test_public_entry_points_never_leak_raw_exceptions(self):
        calls=[
            lambda: validate_topology_record([],{}),
            lambda: validate_topology_counts([],{}),
            lambda: validate_reserve_outputs({},{}),
            lambda: validate_inline_datum([]),
            lambda: validate_output_record([]),
            lambda: asset_preimage("proposal",{}),
        ]
        for call in calls:
            with self.assertRaises(OracleError) as raised: call()
            self.assertNotIn(type(raised.exception).__name__, {"TypeError","KeyError","IndexError","AttributeError"})

    def test_datum_size_and_legacy_contract(self):
        self.assertEqual(check_datum_size("00"*75,75,True),75)
        with self.assertRaises(OracleError): check_datum_size("00"*897,897,True)
        with self.assertRaises(OracleError): check_datum_size("00",2,True)
        self.assertEqual(floor_sqrt(8),2)
        self.assertEqual(majority_result(5,5,1,10),"tie")
        with self.assertRaises(OracleError): majority_result(True,0,1,10)

if __name__ == "__main__":
    unittest.main(verbosity=2)
