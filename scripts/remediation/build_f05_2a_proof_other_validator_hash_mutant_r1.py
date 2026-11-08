#!/usr/bin/env python3
"""Build a disposable one-guard PoP validator-hash mutant attribution candidate."""
from __future__ import annotations
import difflib, hashlib, importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CID="r2_signature_for_other_validator_hash"
OUT=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_mutant_r1_20261005"
BASE=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_r1_20261005"/CID
R41=ROOT/"docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json"
REG=ROOT/"docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
NEG_RUN=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_negative_attempt_r1_20261005/RUN.json"
NEG_REVIEW=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_negative_review_r1_20261005/INDEPENDENT-REVIEW.md"
PRE_REVIEW=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_preexecution_review_r1_20261005/INDEPENDENT-REVIEW.md"
POS_RUN=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_positive_attempt_r1_20261005/RUN.json"
POS_REVIEW=ROOT/"docs/remediation/m3_f05_2a_proof_other_validator_hash_positive_review_r1_20261005/INDEPENDENT-REVIEW.md"
POLICY_SOURCE=ROOT/"cardano/validators/f05_authority_policy.ak"
AIKEN_SHA="07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79"
APPLIED_POLICY="409712d7175aa2f7d372364919d50f55a048b83c7770a646826a1df4"
ALT_HASH=bytes.fromhex("cd"*28)
OLD_CALL="""let bootstrap_message = authority_genesis_pop_preimage(
    genesis_ref,
    state_validator_script_hash,
    initial_keys,
  )"""
NEW_CALL="""let bootstrap_message = authority_genesis_pop_preimage(
    genesis_ref,
    #"cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
    initial_keys,
  )"""
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path)
 if spec is None or spec.loader is None:raise RuntimeError("cannot load local F05 helper")
 m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def sums(directory,recursive=False):
 paths=sorted(directory.rglob("*") if recursive else directory.iterdir())
 return "".join(f"{sha(p.read_bytes())}  {p.relative_to(directory).as_posix()}\n"
  for p in paths if p.is_file() and p.relative_to(directory).as_posix()!="SHA256SUMS")
def build(aiken):
 fam=load("f05_hash_mutant_family",ROOT/"scripts/remediation/build_f05_2a_applied_parameter_tx_family.py")
 h,cb=fam.h,fam.cb
 if OUT.exists():raise FileExistsError("preserve any existing mutant package")
 contract=json.loads(R41.read_text());registry=json.loads(REG.read_text())
 row=next((x for x in contract["case_overrides"] if x["id"]==CID),None)
 if row is None:raise ValueError("R4.1 case row missing")
 if row["amended_contract"]["changed_condition"]!="ephemeral committee signs validator hash cd repeated 28 bytes; test policy uses derived hash":
  raise ValueError("R4.1 alternate-hash decision changed")
 assertion=next((x for x in registry["negative_cases"] if x["id"]==CID),None)
 if assertion!={"id":CID,"mutation":"sign_tuple_with_another_state_validator_hash"}:raise ValueError("original assertion changed")
 if not NEG_REVIEW.exists() or "PASS for attempt integrity only" not in NEG_REVIEW.read_text() or "named-condition attribution remains PENDING" not in NEG_REVIEW.read_text():
  raise ValueError("prior negative integrity review is not the expected pending-attribution review")
 if "PASS for pre-execution fixture integrity" not in PRE_REVIEW.read_text() or "PASS for the executed synthetic positive-control record" not in POS_REVIEW.read_text():
  raise ValueError("required positive/preexecution review is missing")
 for d in (BASE,NEG_REVIEW.parent,PRE_REVIEW.parent,POS_REVIEW.parent):
  for line in (d/"SHA256SUMS").read_text().splitlines():
   digest,name=line.split("  ",1)
   if sha((d/name).read_bytes())!=digest:raise ValueError(f"source evidence checksum mismatch: {d.name}/{name}")
 neg=json.loads(NEG_RUN.read_text());pos=json.loads(POS_RUN.read_text())
 base_manifest=json.loads((BASE/"FIXTURE-MANIFEST.json").read_text())
 if neg["case_id"]!=CID or pos["case_id"]!=CID or base_manifest["case_id"]!=CID:raise ValueError("case identity mismatch")
 if neg["fixture"]["transaction_sha256"]!=sha((BASE/"negative.tx.cbor").read_bytes()):
  raise ValueError("prior negative tx no longer matches reviewed run")
 if pos["fixture"]["transaction_sha256"]!=sha((BASE/"positive-control.tx.cbor").read_bytes()):
  raise ValueError("prior positive tx no longer matches reviewed run")
 for line in (BASE/"SHA256SUMS").read_text().splitlines():
  digest,name=line.split("  ",1)
  if sha((BASE/name).read_bytes())!=digest:raise ValueError("reviewed source fixture checksum mismatch")
 source_files={n:(BASE/n).read_bytes() for n in (
  "negative.tx.cbor","negative.raw_inputs.cbor","negative.raw_outputs.cbor","negative.proof-message.bin",
  "negative.applied-policy.cbor","negative.genesis_ref.cbor","negative.initial_keys.cbor",
  "positive-control.tx.cbor","positive-control.raw_inputs.cbor","positive-control.raw_outputs.cbor",
  "positive-control.proof-message.bin","positive-control.applied-policy.cbor",
  "positive-control.genesis_ref.cbor","positive-control.initial_keys.cbor")}
 old_policy=source_files["negative.applied-policy.cbor"]
 if sha(old_policy)!=base_manifest["applied_policy"]["compiled_script_sha256"] or base_manifest["applied_policy"]["policy_id"]!=APPLIED_POLICY:
  raise ValueError("source applied policy identity mismatch")
 n_tx=cb.roundtrip(source_files["negative.tx.cbor"])
 n_pair=cb.map_get(cb.map_get(n_tx[1],5),[1,0])
 if not isinstance(n_pair,list) or len(n_pair)!=2 or not isinstance(n_pair[0],cb.Tag) or n_pair[0].number!=121:
  raise ValueError("reviewed negative Mint[0] redeemer/ex-unit pair missing")
 negproofs=n_pair[0].value[0]
 if [p.hex() for p in negproofs]!=base_manifest["negative"]["validation"]["mint0_redeemer"]["proof_signatures_hex"]:
  raise ValueError("exact reviewed negative proof bytes disagree with fixture manifest")
 negmsg=source_files["negative.proof-message.bin"]
 if sha(negmsg)!=base_manifest["negative"]["proof_message_sha256"] or negmsg[82:110]!=ALT_HASH:
  raise ValueError("reviewed negative message does not contain exact cd validator-hash domain")
 posmsg=source_files["positive-control.proof-message.bin"]
 if posmsg[82:110]!=bytes.fromhex(base_manifest["applied_parameters"]["derived_applied_state_validator_hash"]):
  raise ValueError("positive control does not use applied validator hash")
 if source_files["negative.genesis_ref.cbor"]!=source_files["positive-control.genesis_ref.cbor"] or source_files["negative.initial_keys.cbor"]!=source_files["positive-control.initial_keys.cbor"]:
  raise ValueError("reviewed positive/negative parameters differ")
 keys=[bytes.fromhex(k) for k in base_manifest["applied_parameters"]["committee_public_keys_hex"]]
 seedmeta=base_manifest["applied_parameters"]["seed_ref"]
 seed=(bytes.fromhex(seedmeta["tx_hash"]),seedmeta["output_index"])
 params={"genesis_ref":h._output_reference(*seed),"initial_keys":h.list_data([h.byte_string(k) for k in keys])}
 if h.cbor(h._output_reference(*seed))!=source_files["negative.genesis_ref.cbor"] or h.cbor(h.list_data([h.byte_string(k) for k in keys]))!=source_files["negative.initial_keys.cbor"]:
  raise ValueError("public applied parameter CBOR does not match manifest")
 with tempfile.TemporaryDirectory(prefix="f05-validator-hash-mutant-") as td:
  temp=Path(td)
  normal=fam.compile_policy(aiken,params,temp/"normal")
  if normal["code"]!=old_policy or normal["policy_id"].hex()!=APPLIED_POLICY:
   raise ValueError("canonical source rebuild does not reproduce reviewed policy bytes")
  staged=temp/"mutant-source";shutil.copytree(ROOT/"cardano",staged)
  policy_path=staged/"validators/f05_authority_policy.ak"
  before=policy_path.read_text(encoding="utf-8")
  if before.count(OLD_CALL)!=1:raise ValueError("PoP preimage call site is not unique")
  after=before.replace(OLD_CALL,NEW_CALL,1)
  if after==before or after.count(NEW_CALL)!=1:raise ValueError("exact PoP-domain one-guard edit failed")
  policy_path.write_text(after,encoding="utf-8")
  diff="".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
   fromfile="a/cardano/validators/f05_authority_policy.ak",tofile="b/cardano/validators/f05_authority_policy.ak"))
  mutant_raw=h._compile(staged,aiken,temp/"mutant",params)
  mutant={"code":mutant_raw["code"],"policy_id":mutant_raw["policy_id"],"state_credential":mutant_raw["state_credential"]}
  if mutant["state_credential"]!=normal["state_credential"] or mutant["state_credential"]!=bytes.fromhex(base_manifest["applied_parameters"]["derived_applied_state_validator_hash"]):
   raise ValueError("PoP-only mutation changed actual state validator identity")
  if mutant["code"]==normal["code"] or hashlib.blake2b(b"\x03"+mutant["code"],digest_size=28).digest()!=mutant["policy_id"]:
   raise ValueError("mutant code/policy binding invalid")
  # Rebind the same reviewed negative proof/message/parameters/input refs to the mutant.
  fam.ORIGINAL=APPLIED_POLICY
  rebuilt=fam.build_tx(source_files["negative.tx.cbor"],source_files["negative.raw_inputs.cbor"],
   source_files["negative.raw_outputs.cbor"],mutant,seed,keys,negproofs,False)
  mutant_tx,mutant_ins,mutant_outs,validation=rebuilt
  final=cb.roundtrip(mutant_tx);body,wit=final[0],final[1]
  mint=cb.map_get(body,9);scripts=cb.map_get(wit,7)
  if [p for p,_ in mint.pairs]!=[mutant["policy_id"]]:raise ValueError("mutant mint does not bind its applied policy")
  if not isinstance(scripts,cb.Tag) or scripts.number!=258 or scripts.value!=[mutant["code"]]:
   raise ValueError("mutant V3 witness does not bind compiled mutant")
  if mutant_ins!=source_files["negative.raw_inputs.cbor"]:raise ValueError("raw input reference context changed")
  # Confirm authority output retains the canonical state-validator address; the
  # changed constant is used only in the bootstrap PoP preimage argument.
  address=cb.map_get(cb.map_get(body,1)[0],0)
  if address[1:]!=mutant["state_credential"]:raise ValueError("authority output address changed from canonical state hash")
  out=OUT/CID;out.mkdir(parents=True)
  artifacts={
   "reviewed-negative.tx.cbor":source_files["negative.tx.cbor"],
   "reviewed-negative.raw_inputs.cbor":source_files["negative.raw_inputs.cbor"],
   "reviewed-negative.raw_outputs.cbor":source_files["negative.raw_outputs.cbor"],
   "reviewed-negative.applied-policy.cbor":old_policy,
   "reviewed-negative.proof-message.bin":negmsg,
   "reviewed-negative.genesis_ref.cbor":source_files["negative.genesis_ref.cbor"],
   "reviewed-negative.initial_keys.cbor":source_files["negative.initial_keys.cbor"],
   "positive-control.tx.cbor":source_files["positive-control.tx.cbor"],
   "positive-control.raw_inputs.cbor":source_files["positive-control.raw_inputs.cbor"],
   "positive-control.raw_outputs.cbor":source_files["positive-control.raw_outputs.cbor"],
   "positive-control.applied-policy.cbor":source_files["positive-control.applied-policy.cbor"],
   "positive-control.proof-message.bin":posmsg,
   "positive-control.genesis_ref.cbor":source_files["positive-control.genesis_ref.cbor"],
   "positive-control.initial_keys.cbor":source_files["positive-control.initial_keys.cbor"],
   "mutant.tx.cbor":mutant_tx,"mutant.raw_inputs.cbor":mutant_ins,"mutant.raw_outputs.cbor":mutant_outs,
   "mutant.applied-policy.cbor":mutant["code"],"mutant.proof-message.bin":negmsg,
   "mutant.genesis_ref.cbor":source_files["negative.genesis_ref.cbor"],
   "mutant.initial_keys.cbor":source_files["negative.initial_keys.cbor"],"SOURCE-DIFF.patch":diff.encode(),
   "prior-negative-run.json":NEG_RUN.read_bytes(),"prior-negative-review.md":NEG_REVIEW.read_bytes(),
   "prior-preexecution-review.md":PRE_REVIEW.read_bytes(),"prior-positive-run.json":POS_RUN.read_bytes(),
   "prior-positive-review.md":POS_REVIEW.read_bytes()}
  records={}
  for name,data in artifacts.items():
   (out/name).write_bytes(data);records[name]={"sha256":sha(data),"bytes":len(data)}
  line_no=next(i for i,line in enumerate(before.splitlines(),1) if "state_validator_script_hash," in line)
  python_version=subprocess.run([sys.executable,"--version"],capture_output=True,text=True,check=True).stdout.strip()
  manifest={"schema_version":"f05-2a-proof-domain-validator-hash-mutant-r1",
   "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit",
   "case_id":CID,"original_case_id_preserved":True,"assertion":"sign_tuple_with_another_state_validator_hash",
   "decision":"R4.1 proof-domain B","contract_row":row,
   "scope":"synthetic one-guard alternate applied-policy mutant; no original-policy, ledger-admission, Pre-Prod, or live-network credit",
   "execution":"NOT RUN; builder and tests do not invoke simulator",
   "entrypoint":"f05_authority_policy.f05_authority_policy.mint / Plutus V3 / Mint[0]",
   "source_mutation":{"source_file":"cardano/validators/f05_authority_policy.ak","function":"f05_authority_policy.mint",
    "changed_site":"authority_genesis_pop_preimage validator-hash argument","line":line_no,
    "before":"state_validator_script_hash","after":"byte literal cd repeated 28 bytes","replacement_count":1,
    "canonical_state_validator_hash_constant_unchanged":True,"source_before_sha256":sha(before.encode()),
    "source_mutant_sha256":sha(after.encode()),"patch_artifact":"SOURCE-DIFF.patch"},
   "prior_negative":{"run_sha256":sha(NEG_RUN.read_bytes()),"review_sha256":sha(NEG_REVIEW.read_bytes()),
    "prior_review_scope":"PASS attempt integrity only; named-condition attribution remains PENDING",
    "original_applied_policy_id":APPLIED_POLICY,"proof_message_sha256":sha(negmsg),
    "proof_signatures_hex":[p.hex() for p in negproofs],"parameters_sha256":base_manifest["applied_parameters"]["parameter_cbor_sha256"],
    "raw_input_refs_sha256":sha(source_files["negative.raw_inputs.cbor"])},
   "positive_control":{"status":"prior accepted synthetic control; copied byte-identically",
    "run_sha256":sha(POS_RUN.read_bytes()),"review_sha256":sha(POS_REVIEW.read_bytes()),
    "transaction_sha256":sha(source_files["positive-control.tx.cbor"]),"applied_policy_id":APPLIED_POLICY,
    "proof_message_sha256":sha(posmsg),"accepted_control_credit_scope":"synthetic positive only"},
   "toolchain":{"aiken_version":"aiken v1.1.21+42babe5","aiken_binary_sha256":AIKEN_SHA,"python_version":python_version},
   "applied_parameters":{"seed_ref":seedmeta,"committee_public_keys_hex":base_manifest["applied_parameters"]["committee_public_keys_hex"],
    "parameter_cbor_sha256":base_manifest["applied_parameters"]["parameter_cbor_sha256"],
    "actual_state_validator_hash":mutant["state_credential"].hex(),"alternate_signed_hash":ALT_HASH.hex(),
    "private_key_material_persisted":False},
   "mutant_policy":{"policy_id":mutant["policy_id"].hex(),"compiled_script_sha256":sha(mutant["code"]),
    "state_validator_hash":mutant["state_credential"].hex(),"mint_applied_v3_witness_binding_verified":True},
   "mutant_control":{"status":"PENDING","transaction_sha256":sha(mutant_tx),"raw_inputs_sha256":sha(mutant_ins),
    "raw_outputs_sha256":sha(mutant_outs),"proof_message_sha256":sha(negmsg),
    "proof_signatures_hex":[p.hex() for p in negproofs],"same_reviewed_negative_proofs_parameters_and_input_refs":True,
    "canonical_authority_output_address_retained":True,"validation":validation,
    "named_condition_attribution":"await independent exact-byte review; no simulator result inferred"},
   "body_context_note":"Policy ID/mint/native NFT and compiled V3 witness are rebound to mutant. Input references and state output semantics remain from reviewed negative. Funding signatures are freshly generated for final body because the original ephemeral private keys were not retained.",
   "credit":{"negative_case":None,"mutant_acceptance":None,"mutation_suite":None,"original_policy":False,"ledger_admission":False,"live_network":False},
   "funding_and_conservation":{"validation":validation,"collateral_present":False,"private_keys_ephemeral":True},
   "artifacts":records}
  (out/"FIXTURE-MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
  (out/"SHA256SUMS").write_text(sums(out))
  (OUT/"SUMMARY.md").write_text("""# F05.2a validator-hash one-guard mutant candidate r1

Status: **candidate; independent byte review required; tx-sim not run; no credit**.

The disposable policy source changes only the bootstrap-message validator-hash argument from the canonical state-validator hash to the R4.1 alternate hash cd repeated 28 bytes. The canonical state-validator constant and output-address guards remain unchanged. The mutant is separately compiled, and its policy ID, mint, and Plutus V3 witness are rebound.

The mutant transaction reuses the exact reviewed negative PoP message, signatures, public parameters, and raw input references. Its authority output remains at the canonical state-validator address; only the proof-domain argument changes in the source. Fresh ephemeral funding keys sign the final rebound body. The previously accepted synthetic positive control and its run/review records are copied byte-identically. No private key material is persisted.

All mutant evidence remains PENDING until independent exact-byte review and authorized execution. There is no original-policy, full-ledger-admission, Pre-Prod, or live-network credit. F05/M3 remains open.
""")
  fm={"schema_version":"f05-2a-proof-domain-validator-hash-mutant-family-r1",
   "status":"candidate-awaiting-independent-byte-review; tx-sim-not-run; no credit","case_ids_in_scope":[CID],
   "case_package":str(out.relative_to(ROOT)),"R4_1_sha256":sha(R41.read_bytes()),
   "original_registry_sha256":sha(REG.read_bytes()),"prior_negative_run_sha256":sha(NEG_RUN.read_bytes()),
   "prior_positive_run_sha256":sha(POS_RUN.read_bytes()),"source_before_sha256":sha(before.encode()),
   "source_mutant_sha256":sha(after.encode()),"source_registry_status_handoff_unchanged":True,
   "scope":manifest["scope"],"files":{}}
  for p in sorted(OUT.rglob("*")):
   rel=p.relative_to(OUT).as_posix()
   if p.is_file() and rel not in {"FAMILY-MANIFEST.json","SHA256SUMS"}:
    data=p.read_bytes();fm["files"][rel]={"sha256":sha(data),"bytes":len(data)}
  (OUT/"FAMILY-MANIFEST.json").write_text(json.dumps(fm,indent=2,sort_keys=True)+"\n")
  (OUT/"SHA256SUMS").write_text(sums(OUT,recursive=True))
  return manifest
def main():
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--aiken",type=Path,required=True)
 a=p.parse_args();binary=a.aiken.resolve(strict=True)
 v=subprocess.run([str(binary),"--version"],capture_output=True,text=True,timeout=20)
 if v.returncode or v.stdout.strip()!="aiken v1.1.21+42babe5" or sha(binary.read_bytes())!=AIKEN_SHA:
  raise SystemExit("refusing non-pinned Aiken")
 result=build(binary)
 print(json.dumps({"case_id":CID,"status":result["status"],"mutant_policy_id":result["mutant_policy"]["policy_id"],
  "mutant_tx_sha256":result["mutant_control"]["transaction_sha256"],"artifact_dir":str(OUT/CID)},sort_keys=True))
 return 0
if __name__=="__main__":raise SystemExit(main())

