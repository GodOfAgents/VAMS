#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys, tempfile, unittest, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"m3_f04_design_r1"
VALIDATOR_PATH=(ROOT/"validate_design.py").resolve(strict=True)
def load_exact():
    name="_m3_f04_r5_validator_"+uuid.uuid4().hex
    spec=importlib.util.spec_from_file_location(name, VALIDATOR_PATH)
    if spec is None or spec.loader is None: raise AssertionError("validator module unavailable")
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
    loaded=Path(module.__file__).resolve(strict=True)
    if loaded != VALIDATOR_PATH or hashlib.sha256(loaded.read_bytes()).digest()!=hashlib.sha256(VALIDATOR_PATH.read_bytes()).digest(): raise AssertionError("validator path/hash mismatch")
    return module,name
class R5ContractTests(unittest.TestCase):
    def test_validator_cli_is_cwd_independent(self):
        with tempfile.TemporaryDirectory(prefix="m3-f04-r5-cwd-") as td:
            for cwd in (ROOT, ROOT.parents[2], Path(td)):
                result=subprocess.run([sys.executable,str(VALIDATOR_PATH)],cwd=cwd,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(json.loads(result.stdout)["matrix_rows"],49)
    def test_generator_cli_is_cwd_and_import_poisoning_independent(self):
        with tempfile.TemporaryDirectory(prefix="m3-f04-r5-poison-") as td:
            Path(td,"validate_design.py").write_text("raise RuntimeError('poisoned import')\n",encoding="utf-8")
            env={**os.environ,"PYTHONPATH":str(Path(td))}
            for cwd in (ROOT,ROOT.parents[2],Path(td)):
                result=subprocess.run([sys.executable,str(ROOT/"generate_vectors.py")],cwd=cwd,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(len(json.loads(result.stdout)["vectors"]),2)
    def test_exact_path_import(self):
        module,name=load_exact()
        try: self.assertTrue(module.validate(ROOT)["ok"])
        finally: sys.modules.pop(name,None)
    def test_r5_contract_and_rows(self):
        module,name=load_exact()
        try:
            identity=json.loads((ROOT/"IDENTITY_SPEC.json").read_text())
            self.assertEqual(set(identity["r5_contract"]),{"authority_reference","action_authorization","replay","f05_interface","inv10"})
            values=json.loads((ROOT/"VALUE_RULES.json").read_text())
            self.assertEqual(set(values["rules"]),{"register","update","slash_post_f05","deregister","replay","reserve","inv10","all"})
            rows=json.loads((ROOT/"ACCEPTANCE_MATRIX.json").read_text())["rows"]; ids={row["id"] for row in rows}
            self.assertEqual(len(rows),49)
            self.assertTrue({"update_replayed_nonce","update_parallel_nonce","update_stale_epoch_r5","slash_reserve_redirect","slash_evidence_identity_mismatch","slash_evidence_expired","slash_proof_payload_alias","slash_payload_substitution"}<=ids)
            self.assertEqual(module.validate(ROOT)["matrix_rows"],49)
        finally: sys.modules.pop(name,None)
    def test_r5_mutations_fail(self):
        module,name=load_exact()
        try:
            with tempfile.TemporaryDirectory(prefix="m3-f04-r5-mut-") as td:
                base=Path(td)
                names=("IDENTITY_SPEC.json","ASSET_VECTORS.json","DATUM_VECTORS.json","TRANSITION_TOPOLOGY.json","VALUE_RULES.json","ACCEPTANCE_MATRIX.json")
                for filename in names: (base/filename).write_bytes((ROOT/filename).read_bytes())
                muts=(("IDENTITY_SPEC.json",lambda v:v["r5_contract"]["inv10"].pop("payload_hash")),("VALUE_RULES.json",lambda v:v["rules"].pop("replay")),("ACCEPTANCE_MATRIX.json",lambda v:v["rows"].pop()))
                for filename,mutate in muts:
                    value=json.loads((base/filename).read_text()); mutate(value); (base/filename).write_text(json.dumps(value)+"\n")
                    with self.assertRaises(ValueError): module.validate(base)
                    (base/filename).write_bytes((ROOT/filename).read_bytes())
        finally: sys.modules.pop(name,None)
    def test_authority_action_reserve_bindings_fail_closed(self):
        module,name=load_exact()
        try:
            with tempfile.TemporaryDirectory(prefix="m3-f04-r5-bindings-") as td:
                base=Path(td)
                names=("IDENTITY_SPEC.json","ASSET_VECTORS.json","DATUM_VECTORS.json","TRANSITION_TOPOLOGY.json","VALUE_RULES.json","ACCEPTANCE_MATRIX.json")
                for filename in names: (base/filename).write_bytes((ROOT/filename).read_bytes())
                mutations=[
                    ("IDENTITY_SPEC.json",lambda v:v["r5_contract"]["authority_reference"].update(quantity=2)),
                    ("IDENTITY_SPEC.json",lambda v:v["r5_contract"]["authority_reference"].update(value="registry stake")),
                    ("IDENTITY_SPEC.json",lambda v:v["r5_contract"]["authority_reference"].update(datum_hash="wrong")),
                    ("IDENTITY_SPEC.json",lambda v:v["r5_contract"]["action_authorization"].update(burn_quantity=0)),
                    ("TRANSITION_TOPOLOGY.json",lambda v:v["transitions"][2]["inputs"].update(action_authorization=2)),
                    ("TRANSITION_TOPOLOGY.json",lambda v:v["transitions"][2].update(reserve="attacker")),
                    ("VALUE_RULES.json",lambda v:v["post_f05_slash_interface"].update(substitution="allow")),
                ]
                for filename,mutate in mutations:
                    path=base/filename; value=json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value)+"\n")
                    with self.assertRaises(ValueError): module.validate(base)
                    path.write_bytes((ROOT/filename).read_bytes())
        finally: sys.modules.pop(name,None)

if __name__=="__main__": unittest.main(verbosity=2)
