#!/usr/bin/env python3
import copy,hashlib,importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r7',HERE/'governance_spec.py'); r7=importlib.util.module_from_spec(spec); spec.loader.exec_module(r7)

def ru(n,w): return n.to_bytes(w,'big')
def rb(b):
 b=bytes(b); n=len(b)
 return (bytes([n]) if n<24 else b'\x58'+bytes([n]))+b
def ra(xs): return bytes([0x80+len(xs)])+b''.join(xs)
def ri(n):
 if n<24:return bytes([n])
 if n<256:return b'\x18'+bytes([n])
 if n<65536:return b'\x19'+ru(n,2)
 if n<1<<32:return b'\x1a'+ru(n,4)
 return b'\x1b'+ru(n,8)
def rc(alt,fields): return b'\xd8'+bytes([0x79+alt])+ra(fields)
def rbool(v): return rc(1 if v else 0,[])
def rec(d): return rc(0,[rb(bytes.fromhex(d['voter_vkh'])),ri(d['locked_vams']),rbool(d['support']),ri(d['weight']),rb(bytes.fromhex(d['receipt_name']))])
def authority(d): return rc(0,[ri(d['version']),ri(d['network_id']),ri(d['authority_state_lovelace']),ri(d['proposal_base_lovelace']),ri(d['per_voter_refund_lovelace']),ri(d['policy_epoch']),rb(bytes.fromhex(d['authority_policy_id'])),rb(bytes.fromhex(d['governor_script_hash'])),rb(bytes.fromhex(d['timelock_script_hash'])),rb(bytes.fromhex(d['seed_tx_id'])),ri(d['seed_index']),ra([rb(bytes.fromhex(x)) for x in d['members']]),ri(d['threshold']),ri(d['normal_delay_ms']),rbool(d['emergency_disabled']),ri(d['next_proposal_nonce']),ri(d['next_intent_nonce']),ri(d['max_lock_vams']),ra([ri(x) for x in d['caps']]),ra([rb(bytes.fromhex(x)) for x in d['target_domains']])])
def proposal(d):
 st={'pending':0,'passed':1,'rejected':2}[d['status']]
 return rc(0,[ri(d['version']),rc(st,[]),rb(bytes.fromhex(d['proposal_asset'])),ri(d['nonce']),rb(bytes.fromhex(d['proposer_vkh'])),rb(bytes.fromhex(d['description_hash'])),rb(bytes.fromhex(d['action_hash'])),rb(bytes.fromhex(d['target_domain'])),ri(d['policy_epoch']),ri(d['quorum']),ri(d['deadline']),ri(d['yes_weight']),ri(d['no_weight']),ra([rec(x) for x in d['locks']])])
def intent(d): return rc(0,[ri(d['version']),rb(bytes.fromhex(d['proposal_id'])),rb(bytes.fromhex(d['proposal_asset'])),rb(bytes.fromhex(d['action_hash'])),rb(bytes.fromhex(d['payload_hash'])),rb(bytes.fromhex(d['target_domain'])),ri(d['policy_epoch']),ri(d['nonce']),ri(d['queue_time']),ri(d['execute_after']),ri(d['lifetime']),rb(bytes.fromhex(d['proposer_vkh'])),rbool(d['consumed'])])
class R7SpecTests(unittest.TestCase):
 def test_closed_spec(self): self.assertTrue(r7.validate_spec()['ok'])
 def test_independent_asset_vectors(self):
  av=json.loads((HERE/'ASSET_VECTORS.json').read_text())
  for v in av['vectors']:
   pre=bytes.fromhex({"authority":"56414d532f617574686f726974792f763100","proposal":"56414d532f70726f706f73616c2f763100","receipt":"56414d532f726563656970742f763100","intent":"56414d532f696e74656e742f763100"}[v['kind']])+b''.join(bytes.fromhex(x) for x in v['fields_hex'])
   self.assertEqual(pre.hex(),v['preimage_hex']); self.assertEqual(hashlib.blake2b(pre,digest_size=32).hexdigest(),v['digest_hex'])
 def test_independent_datum_vectors(self):
  for v in json.loads((HERE/'DATUM_VECTORS.json').read_text())['vectors']:
   raw={'authority':authority,'proposal':proposal,'intent':intent,'record':rec}[v['kind']](v['value'])
   self.assertEqual(raw.hex(),v['cbor_hex']); self.assertEqual(len(raw),v['byte_length']); self.assertLessEqual(len(raw),896); self.assertEqual(v['accepted'], (v.get('record_count') != 9))
 def test_topology_and_matrix_mutations_fail(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); [shutil.copy(HERE/n,d/n) for n in ('GOVERNANCE_SPEC.json','ASSET_VECTORS.json','DATUM_VECTORS.json','TRANSITION_TOPOLOGY.json','ACCEPTANCE_MATRIX.json')]
   top=json.loads((d/'TRANSITION_TOPOLOGY.json').read_text()); top['transitions'][0]['outputs']['with_change']-=1; (d/'TRANSITION_TOPOLOGY.json').write_text(json.dumps(top))
   with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); [shutil.copy(HERE/n,d/n) for n in ('GOVERNANCE_SPEC.json','ASSET_VECTORS.json','DATUM_VECTORS.json','TRANSITION_TOPOLOGY.json','ACCEPTANCE_MATRIX.json')]
   matrix=json.loads((d/'ACCEPTANCE_MATRIX.json').read_text()); matrix['rows'][0]['evidence_status']='accepted'; (d/'ACCEPTANCE_MATRIX.json').write_text(json.dumps(matrix))
   with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)

class R9ClosedContractTests(unittest.TestCase):
 def _copy(self, d):
  for n in ("GOVERNANCE_SPEC.json","ASSET_VECTORS.json","DATUM_VECTORS.json","TRANSITION_TOPOLOGY.json","ACCEPTANCE_MATRIX.json"):
   shutil.copy(HERE/n,d/n)
 def test_duplicate_and_nested_schema_mutations(self):
  cases=[]
  def duplicate(d):
   (d/"GOVERNANCE_SPEC.json").write_text('{"schema_version":"x","schema_version":"y"}')
  cases.append(duplicate)
  def unknown(d):
   x=json.loads((d/"GOVERNANCE_SPEC.json").read_text()); x["network"]["unexpected"]=1; (d/"GOVERNANCE_SPEC.json").write_text(json.dumps(x))
  cases.append(unknown)
  def missing(d):
   x=json.loads((d/"GOVERNANCE_SPEC.json").read_text()); del x["network"]["source"]; (d/"GOVERNANCE_SPEC.json").write_text(json.dumps(x))
  cases.append(missing)
  def bool_count(d):
   x=json.loads((d/"TRANSITION_TOPOLOGY.json").read_text()); x["transitions"][0]["inputs"]["governed"]=True; (d/"TRANSITION_TOPOLOGY.json").write_text(json.dumps(x))
  cases.append(bool_count)
  for mutate in cases:
   with self.subTest(mutate=mutate):
    with tempfile.TemporaryDirectory() as td:
     d=Path(td); self._copy(d); mutate(d)
     with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)
 def test_reference_graph_mutations(self):
  for ref in ("topology:missing","spec:encoding","topology:executeintent"):
   with self.subTest(ref=ref):
    with tempfile.TemporaryDirectory() as td:
     d=Path(td); self._copy(d)
     x=json.loads((d/"ACCEPTANCE_MATRIX.json").read_text()); x["rows"][0]["reference"]=ref; (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
     with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)
 def test_rebuilt_derived_values_do_not_bypass_canonical_fixtures(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   x=json.loads((d/"ASSET_VECTORS.json").read_text()); v=x["vectors"][1]; v["fields_hex"][1]="55"*32
   raw=bytes.fromhex({"authority":"56414d532f617574686f726974792f763100","proposal":"56414d532f70726f706f73616c2f763100","receipt":"56414d532f726563656970742f763100","intent":"56414d532f696e74656e742f763100"}[v["kind"]])+b"".join(bytes.fromhex(y) for y in v["fields_hex"])
   v["preimage_hex"]=raw.hex(); v["digest_hex"]=hashlib.blake2b(raw,digest_size=32).hexdigest(); (d/"ASSET_VECTORS.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   x=json.loads((d/"DATUM_VECTORS.json").read_text()); v=x["vectors"][0]; v["value"]["network_id"]=1
   v["cbor_hex"]=r7.encode_datum(v["kind"],v["value"]).hex(); v["byte_length"]=len(bytes.fromhex(v["cbor_hex"])); (d/"DATUM_VECTORS.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)
 def test_control_registry_rejects_duplicate_or_unknown_mutation(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   x=json.loads((d/"ACCEPTANCE_MATRIX.json").read_text()); x["rows"][1]["mutation_id"]=x["rows"][0]["mutation_id"]; (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   x=json.loads((d/"ACCEPTANCE_MATRIX.json").read_text()); x["rows"][1]["mutation_id"]="future_control"; (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)


 def test_duplicate_ids_widths_and_ninth_voter_metadata(self):
  mutations=[]
  def dup_asset(d):
   x=json.loads((d/"ASSET_VECTORS.json").read_text()); x["vectors"][1]["id"]=x["vectors"][0]["id"]; (d/"ASSET_VECTORS.json").write_text(json.dumps(x))
  def dup_datum(d):
   x=json.loads((d/"DATUM_VECTORS.json").read_text()); x["vectors"][1]["id"]=x["vectors"][0]["id"]; (d/"DATUM_VECTORS.json").write_text(json.dumps(x))
  def dup_topology(d):
   x=json.loads((d/"TRANSITION_TOPOLOGY.json").read_text()); x["transitions"][1]["id"]=x["transitions"][0]["id"]; (d/"TRANSITION_TOPOLOGY.json").write_text(json.dumps(x))
  def dup_matrix(d):
   x=json.loads((d/"ACCEPTANCE_MATRIX.json").read_text()); x["rows"][1]["id"]=x["rows"][0]["id"]; (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
  def width(d):
   x=json.loads((d/"ASSET_VECTORS.json").read_text()); x["vectors"][0]["fields_hex"][0]="00"*27; (d/"ASSET_VECTORS.json").write_text(json.dumps(x))
  def ninth(d):
   x=json.loads((d/"DATUM_VECTORS.json").read_text()); v=next(y for y in x["vectors"] if y["id"]=="proposal_9_records"); v["record_count"]=8; (d/"DATUM_VECTORS.json").write_text(json.dumps(x))
  mutations.extend((dup_asset,dup_datum,dup_topology,dup_matrix,width,ninth))
  for mutate in mutations:
   with self.subTest(mutate=mutate):
    with tempfile.TemporaryDirectory() as td:
     d=Path(td); self._copy(d); mutate(d)
     with self.assertRaises(ValueError): r7.validate_spec(d, enforce_frozen=False)

 def test_r11_topology_semantics_reject_each_field_class(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   base=json.loads((d/"TRANSITION_TOPOLOGY.json").read_text())
   mutations=[]
   for key in ("governed","auxiliary_regular","authority_reference","allowed_reference_scripts","collateral"):
    x=copy.deepcopy(base); x["transitions"][0]["inputs"][key]+=1; mutations.append(x)
   for key in ("without_change","with_change"):
    x=copy.deepcopy(base); x["transitions"][0]["outputs"][key]+=1; mutations.append(x)
   for key in ("minted_assets","burned_assets","datums","redeemers","script_witnesses"):
    x=copy.deepcopy(base); x["transitions"][0][key].append("unexpected"); mutations.append(x)
   for key in ("authority_members","proposer","voter","distinct"):
    x=copy.deepcopy(base); x["transitions"][0]["signers"][key]+=1; mutations.append(x)
   for x in mutations:
    (d/"TRANSITION_TOPOLOGY.json").write_text(json.dumps(x))
    with self.assertRaises(ValueError): r7.validate_spec(d,enforce_frozen=False)

 def test_r11_matrix_semantics_and_frozen_bytes(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   base=json.loads((d/"ACCEPTANCE_MATRIX.json").read_text())
   for field,value in (("expectation","accept"),("transition","Queue"),("reason","ALLOW"),("mutation_id","none"),("reference","topology:genesis"),("evidence_status","accepted")):
    x=copy.deepcopy(base); row=next(v for v in x["rows"] if v["id"]=="execute_pre_f05"); row[field]=value; (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
    with self.assertRaises(ValueError): r7.validate_spec(d,enforce_frozen=False)
   x=copy.deepcopy(base); x["rows"].pop(); (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d,enforce_frozen=False)
   x=copy.deepcopy(base); x["rows"].append(copy.deepcopy(x["rows"][0])); (d/"ACCEPTANCE_MATRIX.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d,enforce_frozen=False)
   (d/"ACCEPTANCE_MATRIX.json").write_text((d/"ACCEPTANCE_MATRIX.json").read_text()+" ")
   with self.assertRaises(ValueError): r7.validate_spec(d)

 def test_r11_address_vectors_and_hash_gate(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td); self._copy(d)
   x=json.loads((d/"GOVERNANCE_SPEC.json").read_text()); x["address_vectors"][0]["header_hex"]="70"; (d/"GOVERNANCE_SPEC.json").write_text(json.dumps(x))
   with self.assertRaises(ValueError): r7.validate_spec(d,enforce_frozen=False)

if __name__=="__main__":
 unittest.main(verbosity=2)
