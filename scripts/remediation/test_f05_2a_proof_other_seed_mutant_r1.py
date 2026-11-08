from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_other_seed_mutant_r1_20261005/r2_signature_for_other_seed"
R18=ROOT/"docs/remediation/m3_f05_2a_proof_domain_family_r1_20261005/r2_signature_for_other_seed"
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
builder=load("proof_seed_mutant_builder",ROOT/"scripts/remediation/build_f05_2a_proof_other_seed_mutant_r1.py")
fam=load("proof_seed_mutant_family",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
cb=fam.cb
def proofs(path):
 tx=cb.roundtrip(path.read_bytes());red=cb.map_get(cb.map_get(tx[1],5),[1,0])
 assert red[0].number==121
 return [bytes(x) for x in red[0].value[0]]
def test_disposable_source_has_only_exact_seed_argument_change():
 original=(ROOT/"cardano/validators/f05_authority_policy.ak").read_text()
 mutant=(OUT/"mutant-policy-source.ak").read_text()
 assert original.count(builder.OLD)==1
 assert original.replace(builder.OLD,builder.NEW,1)==mutant
 assert "expect valid_initial_authority(state, genesis_ref, initial_keys)" in mutant
 assert "count_seed_input(tx.inputs, genesis_ref) == 1" in mutant
 assert "valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)" in mutant
 assert 'transaction_id: #"adadadadadadadadadadadadadadadadadadadadadadadadadadadadadadadad"' in mutant
 assert "verify_ed25519_signature" in (ROOT/"cardano/lib/vams/f05_authority.ak").read_text()
def test_mutant_reuses_exact_r18_parameters_message_and_pop_bytes():
 m=json.loads((OUT/"FIXTURE-MANIFEST.json").read_text())
 assert m["status"].startswith("candidate-awaiting-independent-byte-review")
 assert m["mutant_control"]["status"]=="PENDING" and m["execution"]=="NOT RUN; no simulator invocation in builder"
 for name in ("genesis_ref.cbor","initial_keys.cbor","proof-message.bin"):
  assert (OUT/f"mutant.{name}").read_bytes()==(R18/f"negative.{name}").read_bytes()
 assert (OUT/"mutant.raw_inputs.cbor").read_bytes()==(R18/"negative.raw_inputs.cbor").read_bytes()
 assert proofs(OUT/"mutant.tx.cbor")==proofs(R18/"negative.tx.cbor")
 assert proofs(OUT/"mutant.tx.cbor")==[bytes.fromhex(x) for x in m["preserved_R18_inputs"]["poP_signatures_hex"]]
 assert hashlib.sha256((R18/"negative.tx.cbor").read_bytes()).hexdigest()=="53526ecc1282cb83aaf9690a74c422361f25c4229da1378bbc68d8e78405534b"
def test_mutant_applied_id_v3_mint_funding_and_conservation_bind():
 m=json.loads((OUT/"FIXTURE-MANIFEST.json").read_text())
 code=(OUT/"mutant.applied-policy.cbor").read_bytes();tx=cb.roundtrip((OUT/"mutant.tx.cbor").read_bytes());body,wit=tx[0],tx[1]
 pid=bytes.fromhex(m["mutant"]["policy_id"])
 assert hashlib.blake2b(bytes([3])+code,digest_size=28).digest()==pid
 assert [k for k,_ in cb.map_get(body,9).pairs]==[pid]
 scripts=cb.map_get(wit,7);assert scripts.number==258 and scripts.value==[code]
 assert m["mutant_control"]["mint_applied_v3_witness_identity_verified"]
 v=m["mutant_control"]["validation"]
 assert v["valid_body_bound_ephemeral_signatures"] and v["funding_signatures"]==2
 assert v["private_keys_persisted"] is False and v["ada_conservation"] and v["native_asset_conservation"]
 c=m["funding_and_conservation"]
 assert c["inputs_lovelace"]==17000000
 assert c["authority_output_lovelace"]+c["change_output_lovelace"]+c["fee_lovelace"]==17000000
 assert m["credit"]=={"case_negative":None,"mutation_suite":None,"original_policy":False,"ledger_admission":False,"live_network":False}
def test_versioned_package_checksums():
 for d in (OUT,OUT.parent):
  for line in (d/"SHA256SUMS").read_text().splitlines():
   digest,name=line.split("  ",1)
   assert hashlib.sha256((d/name).read_bytes()).hexdigest()==digest
