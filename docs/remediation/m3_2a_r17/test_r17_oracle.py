from __future__ import annotations
import contextlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[3]
ORACLE_PATH=HERE/"docs/remediation/m3_2a_r9/address_value_oracle.py"
DATUM_PATH=HERE/"docs/remediation/m3_2a_r7/DATUM_VECTORS.json"
sys.path.insert(0,str(ORACLE_PATH.parent))
import address_value_oracle as oracle

class R17OracleTests(unittest.TestCase):
    def _record_datum(self):
        vector=next(v for v in json.loads(DATUM_PATH.read_text())["vectors"] if v["accepted"] and v["kind"]=="record")
        return vector,{"kind":"VoteLockRecordV1","constructor_index":0,
                       "fields":[[k,v] for k,v in vector["value"].items()],
                       "cbor_hex":vector["cbor_hex"]}

    def _module_copy(self,ancestor_symlink=False):
        td=tempfile.TemporaryDirectory()
        root=Path(td.name)
        if ancestor_symlink:
            real=root/"real-remediation"
            docs=root/"docs"
            docs.mkdir()
            (docs/"remediation").symlink_to(real, target_is_directory=True)
            module_dir=real/"m3_2a_r9"
            artifact_dir=real/"m3_2a_r7"
            module_dir.mkdir(parents=True)
            artifact_dir.mkdir(parents=True)
        else:
            module_dir=root/"docs/remediation/m3_2a_r9"
            artifact_dir=root/"docs/remediation/m3_2a_r7"
            module_dir.mkdir(parents=True)
            artifact_dir.mkdir(parents=True)
        shutil.copy2(ORACLE_PATH,module_dir/"address_value_oracle.py")
        shutil.copy2(DATUM_PATH,artifact_dir/"DATUM_VECTORS.json")
        spec=importlib.util.spec_from_file_location("r17_copy_"+str(id(td)),module_dir/"address_value_oracle.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return td,root,module,artifact_dir/"DATUM_VECTORS.json"

    def test_fixed_regular_file_and_no_descriptor_leak(self):
        vector,datum=self._record_datum()
        before=len(os.listdir("/proc/self/fd"))
        for _ in range(20):
            self.assertTrue(oracle.validate_inline_datum(datum,vector["id"]))
        after=len(os.listdir("/proc/self/fd"))
        self.assertEqual(before,after)

    def test_final_and_ancestor_symlink_rejected(self):
        vector,datum=self._record_datum()
        for ancestor in (False,True):
            td,root,module,registry=self._module_copy(ancestor)
            try:
                if ancestor:
                    with self.assertRaises(module.OracleError): module.validate_inline_datum(datum,vector["id"])
                else:
                    target=registry.with_name("copy.json")
                    shutil.copy2(registry,target)
                    registry.unlink()
                    registry.symlink_to(target)
                    before=len(os.listdir("/proc/self/fd"))
                    for _ in range(10):
                        with self.assertRaises(module.OracleError): module.validate_inline_datum(datum,vector["id"])
                    after=len(os.listdir("/proc/self/fd"))
                    self.assertEqual(before,after)
            finally:
                td.cleanup()

    def test_symlink_nonregular_and_oversized_rejected(self):
        vector,datum=self._record_datum()
        for mode in ("symlink","directory","oversized"):
            td,root,module,registry=self._module_copy()
            try:
                raw=registry.read_bytes()
                registry.unlink()
                if mode=="symlink":
                    target=registry.with_name("same.json")
                    target.write_bytes(raw); registry.symlink_to(target)
                elif mode=="directory":
                    registry.mkdir()
                else:
                    registry.write_bytes(b"x"* (module._MAX_REGISTRY_BYTES+1))
                with self.assertRaises(module.OracleError): module.validate_inline_datum(datum,vector["id"])
            finally:
                td.cleanup()

    def test_candidate_canonical_comparison_is_mutation_sensitive(self):
        vector,datum=self._record_datum()
        original=oracle._cbor_encode
        try:
            oracle._cbor_encode=lambda _node:b""
            with self.assertRaises(oracle.OracleError):
                oracle._parse_inline_fields(datum,"VoteLockRecordV1")
        finally:
            oracle._cbor_encode=original

    def _voter_output(self):
        vkh="11"*28
        return {"address_hex":oracle.enterprise_address(0,"key",vkh).hex(),
                "credential_kind":"key","network_id":0,"lovelace":10,
                "assets":{"locked_vams":100},"datum_form":"none",
                "transition_role":"voter_refund:"+vkh},[{"voter_vkh":vkh,"locked_vams":100,"reserve_lovelace":10}]

    def test_transition_is_closed_and_mandatory(self):
        output,refund=self._voter_output()
        for bad in (None,"", "unknown", False, 1):
            with self.assertRaises(oracle.OracleError):
                oracle.validate_reserve_outputs([output],refund,expected_network=0,transition=bad)
        with self.assertRaises(oracle.OracleError):
            oracle.validate_reserve_outputs([output],refund,expected_network=0,transition="expireintent",topology={})
        self.assertTrue(oracle.validate_reserve_outputs([output],refund,expected_network=0,transition="expireintent"))

    def _authority_state(self):
        vector=next(v for v in json.loads(DATUM_PATH.read_text())["vectors"] if v["accepted"] and v["kind"]=="authority")
        values=dict(vector["value"])
        pre_datum={"kind":"AuthorityDatumV1","constructor_index":0,
                   "fields":[[k,v] for k,v in values.items()],
                   "cbor_hex":vector["cbor_hex"]}
        pre={"address_hex":oracle.enterprise_address(0,"script","22"*28).hex(),
             "credential_kind":"script","network_id":0,"lovelace":5000000,
             "assets":{"authority_nft":1},"datum_form":"inline",
             "transition_role":"authority_continuation","datum":pre_datum}
        return vector,pre

    def test_authority_candidate_cannot_bind_expected_state(self):
        _vector,pre=self._authority_state()
        self.assertTrue(oracle._derive_authority_successor(pre,dict(pre),"vote",0))
        with self.assertRaises(oracle.OracleError):
            oracle._derive_authority_successor(pre,dict(pre),"create",0)
        wrong_address=dict(pre,address_hex=oracle.enterprise_address(0,"script","33"*28).hex())
        with self.assertRaises(oracle.OracleError):
            oracle._derive_authority_successor(pre,wrong_address,"vote",0)
        changed=dict(pre)
        changed["datum"]=dict(pre["datum"],fields=[["version",999]]+pre["datum"]["fields"][1:])
        with self.assertRaises(oracle.OracleError):
            oracle._derive_authority_successor(pre,changed,"vote",0)

if __name__=="__main__":
    unittest.main(verbosity=2)
