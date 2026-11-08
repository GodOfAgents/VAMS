#!/usr/bin/env python3
"""Build and validate the frozen F04 Option-B fixture contract."""
from __future__ import annotations
import hashlib, json
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MATRIX=ROOT/"docs/remediation/m3_f04_design_r1/ACCEPTANCE_MATRIX.json"
FIXTURES=HERE/"FIXTURES.json"
DOMAIN=b"VAMS/agent/v1\0"
DID=bytes.fromhex("6469643a76616d733a6167656e743a0101010101010101010101010101010101")
OWNER=bytes.fromhex("22"*28); OPERATOR=bytes.fromhex("33"*28)
BOOT_TX=bytes.fromhex("11"*32); TXID=bytes.fromhex("44"*32)
POLICY=bytes.fromhex("3159ce21e42bce5f24599bf4e05565792492ca8ffc78fa60d9588bbc")
IDENTITY=bytes.fromhex("3643e533306496437abad612c84592b4f07e9cef3cf424125cb8bd4c36427145")
AUTH_SCRIPT=bytes.fromhex("55"*28); AUTH_POLICY=bytes.fromhex("66"*28)
AUTH_ASSET=bytes.fromhex("77"*32); RESERVE=bytes.fromhex("88"*28)
OTHER_POLICY=bytes.fromhex("99"*28); METADATA=bytes.fromhex("bb"*32)
STAKE=1_000_000_000

class FixtureError(RuntimeError): pass
def con(i,*f): return {"constructor":i,"fields":list(f)}
def integer(v):
    if type(v) is not int: raise FixtureError("strict integer")
    return {"int":v}
def bs(v):
    raw=bytes.fromhex(v) if isinstance(v,str) else v
    return {"bytes":raw.hex()}
def listing(*v): return {"list":list(v)}
def mapping(*p): return {"map":[{"k":k,"v":v} for k,v in p]}
def none(): return con(1)
def some(v): return con(0,v)
def boolean(v): return con(1 if v else 0)
def out_ref(t,i): return con(0,bs(t),integer(i))
def address(h): return con(0,con(1,bs(h)),none())
def key_address(h): return con(0,con(0,bs(h)),none())

def validate_data(n:Any)->None:
    if not isinstance(n,dict): raise FixtureError("data node object")
    keys=set(n)
    if keys=={"int"}:
        if type(n["int"]) is not int or not -(2**63)<=n["int"]<2**63: raise FixtureError("integer")
    elif keys=={"bytes"}:
        x=n["bytes"]
        if not isinstance(x,str) or x!=x.lower() or len(x)%2: raise FixtureError("hex")
        try: bytes.fromhex(x)
        except ValueError as e: raise FixtureError("hex") from e
    elif keys=={"list"}:
        if not isinstance(n["list"],list): raise FixtureError("list")
        for x in n["list"]: validate_data(x)
    elif keys=={"map"}:
        if not isinstance(n["map"],list): raise FixtureError("map")
        seen=set()
        for p in n["map"]:
            if not isinstance(p,dict) or set(p)!={"k","v"}: raise FixtureError("map pair")
            validate_data(p["k"]); validate_data(p["v"])
            k=cbor(p["k"])
            if k in seen: raise FixtureError("duplicate map key")
            seen.add(k)
    elif keys=={"constructor","fields"}:
        if type(n["constructor"]) is not int or not 0<=n["constructor"]<128 or not isinstance(n["fields"],list): raise FixtureError("constructor")
        for x in n["fields"]: validate_data(x)
    else: raise FixtureError("unknown data key")

def head(m,v):
    if v<24:return bytes([(m<<5)|v])
    if v<256:return bytes([(m<<5)|24,v])
    if v<65536:return bytes([(m<<5)|25])+v.to_bytes(2,"big")
    if v<2**32:return bytes([(m<<5)|26])+v.to_bytes(4,"big")
    if v<2**64:return bytes([(m<<5)|27])+v.to_bytes(8,"big")
    raise FixtureError("overflow")
def cbor(n):
    validate_data(n)
    if "int" in n:
        v=n["int"]; return head(0,v) if v>=0 else head(1,-1-v)
    if "bytes" in n:
        x=bytes.fromhex(n["bytes"]); return head(2,len(x))+x
    if "list" in n:return b"\x9f"+b"".join(cbor(x) for x in n["list"])+b"\xff"
    if "map" in n:
        pairs=sorted((cbor(p["k"]),cbor(p["v"])) for p in n["map"])
        return b"\xbf"+b"".join(k+v for k,v in pairs)+b"\xff"
    i=n["constructor"]; fields=b"\x9f"+b"".join(cbor(x) for x in n["fields"])+b"\xff"
    return head(6,121+i)+fields if i<7 else head(6,1280+i-7)+fields
def frozen(n):
    raw=cbor(n); return {"data":n,"cbor_hex":raw.hex(),"sha256":hashlib.sha256(raw).hexdigest()}

def identity_name(did=DID):
    raw=DOMAIN+len(did).to_bytes(2,"big")+did+OWNER+BOOT_TX+(7).to_bytes(4,"big")
    return hashlib.blake2b(raw,digest_size=32).digest()
def val(lovelace,qty=1,other=True):
    p=[(bs(b""),mapping((bs(b""),integer(lovelace))))]
    if qty:p.append((bs(POLICY),mapping((bs(IDENTITY),integer(qty)))))
    if other:p.append((bs(OTHER_POLICY),mapping((bs(b"\x01"),integer(7)))))
    return mapping(*p)
def datum(nonce=0,operator=OPERATOR,status=0,metadata=METADATA):
    return con(0,integer(1),bs(POLICY),bs(IDENTITY),integer(nonce),bs(DID),bs(OWNER),bs(operator),integer(STAKE),integer(5000),bs(metadata),integer(status),integer(1),integer(1_700_000_000_000),listing())
def authority_payload():
    return con(0,integer(1),bs(b""),out_ref(BOOT_TX,7),integer(0),boolean(False),bs(AUTH_SCRIPT),bs(AUTH_POLICY),bs(AUTH_ASSET),integer(1),integer(2_000_000),bs(RESERVE),bs(AUTH_SCRIPT))
# Pinned Aiken cbor.serialise(RegistryAuthorityPayloadV1) digest; verified in
# an isolated 1.1.21 test, then bound into every authority datum and parameter.
AUTH_COMMIT=bytes.fromhex("81b15740d52699325f42e848fd3aad7c1afcce8d5aca2c0e21a1fe7d0e6b7ca6")
def authority_datum(epoch=1):
    return con(0,integer(1),bs(POLICY),out_ref(BOOT_TX,7),integer(epoch),boolean(False),bs(AUTH_SCRIPT),bs(AUTH_POLICY),bs(AUTH_ASSET),integer(1),integer(2_000_000),bs(RESERVE),bs(AUTH_SCRIPT),bs(AUTH_COMMIT))
def output(addr,amount,d=None): return con(0,addr,amount,con(0) if d is None else con(2,d),none())
def input_(r,o): return con(0,r,o)
def interval(lo,hi): return con(0,con(0,con(1,integer(lo)),boolean(True)),con(0,con(1,integer(hi)),boolean(True)))
def tx(ins,refs,outs,mint,signers):
    return con(0,listing(*ins),listing(*refs),listing(*outs),integer(0),mint,listing(),mapping(),interval(1_700_000_000_000,1_700_000_300_000),listing(*(bs(x) for x in signers)),mapping(),mapping(),bs(TXID),mapping(),listing(),none(),none())
def red(t):
    if t=="register":return con(0,bs(DID),bs(METADATA),bs(OPERATOR))
    if t=="update":return con(1,bs(bytes.fromhex("cc"*32)),bs(bytes.fromhex("34"*28)),integer(0),integer(1))
    if t=="deregister":return con(2,integer(0),integer(1))
    return con(3,integer(0),integer(1),bs(bytes.fromhex("dd"*32)),integer(1))
def base(t):
    ref=out_ref(TXID,0); old=datum()
    own_value=val(STAKE,0,False) if t=="register" else val(STAKE)
    own=input_(ref,output(address(POLICY),own_value,old))
    boot=input_(out_ref(BOOT_TX,7),output(key_address(OWNER),val(2_000_000,0,False)))
    av=mapping((bs(b""),mapping((bs(b""),integer(2_000_000)))),(bs(AUTH_POLICY),mapping((bs(AUTH_ASSET),integer(1)))))
    auth=input_(out_ref(bytes.fromhex("45"*32),0),output(address(AUTH_SCRIPT),av,authority_datum()))
    outs=[]; mint=mapping()
    if t=="register":outs=[output(address(POLICY),val(STAKE,1,False),datum())]
    elif t=="update":outs=[output(address(POLICY),val(STAKE),datum(1,bytes.fromhex("34"*28),0,bytes.fromhex("cc"*32)))]
    elif t=="deregister":outs=[output(key_address(OWNER),val(STAKE,0))]
    elif t=="slash":
        outs=[output(address(POLICY),val(STAKE-1_000),datum()),output(key_address(RESERVE),val(1_000,0,False))]
    if t=="register":mint=mapping((bs(POLICY),mapping((bs(IDENTITY),integer(1)))))
    elif t=="deregister":mint=mapping((bs(POLICY),mapping((bs(IDENTITY),integer(-1)))))
    r=red(t); return old,r,con(0,tx([own,boot],[auth],outs,mint,[OWNER]),r,con(1,ref,some(old)))

PATHS={
"remove_lovelace":"transaction.outputs[0].value.lovelace","replace_bootstrap_ref":"transaction.inputs[1].output_reference",
"duplicate_bootstrap_input":"transaction.inputs","change_token_name":"transaction.mint.identity.asset_name","mint_two":"transaction.mint.identity.quantity",
"owner_not_signed":"transaction.extra_signatories","reputation_or_status":"transaction.outputs[0].datum.reputation_bps",
"remove_state_output":"transaction.outputs","add_state_output":"transaction.outputs","change_policy_or_token":"transaction.outputs[0].datum.identity_policy_id",
"change_owner":"transaction.outputs[0].datum.owner","reduce_stake_output":"transaction.outputs[0].value.lovelace","reuse_nonce":"redeemer.expected_nonce",
"stale_authority_reference":"transaction.reference_inputs[0].datum.action_epoch","operator_without_owner":"transaction.extra_signatories",
"wrong_or_duplicate_reference":"transaction.reference_inputs","drop_state_asset":"transaction.outputs[0].value.assets","operator_deregister":"redeemer.constructor",
"slash_all":"transaction.outputs[0].value.lovelace","stake_equation_mismatch":"transaction.outputs[0].value.lovelace","wrong_reserve":"transaction.outputs[1].address",
"unknown_signer":"transaction.extra_signatories","change_evidence_hash":"redeemer.evidence_hash","omit_burn":"transaction.mint",
"burn_wrong_token":"transaction.mint.identity.asset_name","burn_two":"transaction.mint.identity.quantity","retain_state_output":"transaction.outputs",
"payout_not_owner":"transaction.outputs[0].address","add_second_payout":"transaction.outputs","drop_non_identity_asset":"transaction.outputs[0].value.assets",
"datum_policy_alias":"datum.identity_policy_id","expired_attestation":"scenario.evidence_envelope.valid_until","add_unknown_field":"$.unknown",
"duplicate_json_key":"$.id","replace_integer_with_boolean":"parameters.data.fields[4].int","reuse_same_nonce":"scenario.consumed_refs",
"concurrent_same_input":"scenario.consumed_refs","change_reserve_credential":"parameters.data.fields[5].bytes",
"change_evidence_identity":"scenario.evidence_envelope.identity","expire_attestation":"scenario.evidence_envelope.valid_until",
"put_bridge_proof_in_payload_hash":"scenario.evidence_envelope.payload_hash","replace_payload_hash_with_proof":"scenario.evidence_envelope.payload_hash"}
def mutation(label):
    return {"operation":"none","path":None,"before":None,"after":None} if label=="none" else {"operation":"replace","path":PATHS.get(label,"scenario."+label),"before":"frozen-valid","after":label}
def params():return frozen(con(0,out_ref(BOOT_TX,7),bs(AUTH_SCRIPT),bs(AUTH_POLICY),bs(AUTH_ASSET),integer(2_000_000),bs(RESERVE),bs(AUTH_COMMIT)))

def mutate_context(ctx,label):
    value=deepcopy(ctx);transaction=value["fields"][0]
    inputs=transaction["fields"][0]["list"];refs=transaction["fields"][1]["list"]
    outputs=transaction["fields"][2]["list"];mint=transaction["fields"][4]
    signers=transaction["fields"][8];redeemer=value["fields"][1]
    if label=="none":return value
    if label=="remove_lovelace" and outputs:outputs[0]["fields"][1]=val(0,1,False)
    elif label=="replace_bootstrap_ref":inputs[1]["fields"][0]=out_ref(bytes.fromhex("12"*32),7)
    elif label=="duplicate_bootstrap_input":inputs.append(deepcopy(inputs[1]))
    elif label=="change_token_name":mint["map"][0]["v"]=mapping((bs(bytes.fromhex("35"*32)),integer(1)))
    elif label=="mint_two":mint["map"][0]["v"]=mapping((bs(IDENTITY),integer(2)))
    elif label in {"owner_not_signed","operator_without_owner","unknown_signer"}:signers["list"]=[bs(OPERATOR)]
    elif label=="reputation_or_status" and outputs:outputs[0]["fields"][2]["fields"][0]["fields"][8]=integer(4999)
    elif label=="remove_state_output":outputs.clear()
    elif label=="add_state_output" and outputs:outputs.append(deepcopy(outputs[0]))
    elif label in {"change_policy_or_token","datum_policy_alias"} and outputs:outputs[0]["fields"][2]["fields"][0]["fields"][1]=bs(bytes.fromhex("ab"*28))
    elif label=="change_owner" and outputs:outputs[0]["fields"][2]["fields"][0]["fields"][5]=bs(OPERATOR)
    elif label=="reduce_stake_output" and outputs:outputs[0]["fields"][1]=val(STAKE-1)
    elif label=="slash_all" and outputs:outputs[0]["fields"][1]=val(0)
    elif label=="stake_equation_mismatch" and outputs:outputs[0]["fields"][1]=val(STAKE-2_000)
    elif label in {"reuse_nonce","reuse_same_nonce"} and len(redeemer["fields"])>2:redeemer["fields"][2]=integer(-1)
    elif label in {"stale_authority_reference","expired_attestation","expire_attestation"}:
        refs[0]["fields"][1]["fields"][2]["fields"][0]["fields"][3]=integer(0)
    elif label=="wrong_or_duplicate_reference":refs.append(deepcopy(refs[0]))
    elif label=="drop_state_asset" and outputs:outputs[0]["fields"][1]=val(STAKE,1,False)
    elif label=="drop_non_identity_asset" and outputs:outputs[0]["fields"][1]=val(STAKE,0,False)
    elif label=="operator_deregister":value["fields"][1]=con(2,integer(0),integer(1));signers["list"]=[bs(OPERATOR)]
    elif label=="omit_burn":transaction["fields"][4]=mapping()
    elif label=="burn_wrong_token":mint["map"][0]["v"]=mapping((bs(bytes.fromhex("35"*32)),integer(-1)))
    elif label=="burn_two":mint["map"][0]["v"]=mapping((bs(IDENTITY),integer(-2)))
    elif label=="retain_state_output":outputs.append(output(address(POLICY),val(STAKE),datum()))
    elif label=="payout_not_owner" and outputs:outputs[0]["fields"][0]=key_address(OPERATOR)
    elif label=="add_second_payout" and outputs:outputs.append(deepcopy(outputs[0]))
    elif label=="change_evidence_hash" and len(redeemer["fields"])>2:redeemer["fields"][2]=bs(bytes.fromhex("de"*32))
    elif label=="wrong_reserve" and len(outputs)>1:outputs[1]["fields"][0]=key_address(OPERATOR)
    return value

def specialize_context(ctx,row_id):
    value=deepcopy(ctx)
    if row_id=="update_operator_metadata_valid":
        value["fields"][1]["fields"][0]=bs(bytes.fromhex("cd"*32))
        value["fields"][1]["fields"][1]=bs(bytes.fromhex("35"*28))
        out=value["fields"][0]["fields"][2]["list"][0]
        out["fields"][2]["fields"][0]["fields"][6]=bs(bytes.fromhex("35"*28))
        out["fields"][2]["fields"][0]["fields"][9]=bs(bytes.fromhex("cd"*32))
    return value

CONTRACT_KEYS={"schema_version","identity","bridge_proof","payload_hash","valid_until","expected_nonce"}
def contract_control():
    return {"schema_version":1,"identity":IDENTITY.hex(),"bridge_proof":"ee"*32,"payload_hash":"ff"*32,"valid_until":1_700_000_300_000,"expected_nonce":0}
def contract_payload(row_id):
    value=contract_control()
    if row_id=="schema_unknown":value["unknown"]=True
    elif row_id=="schema_duplicate":
        raw=json.dumps(value,sort_keys=True,separators=(",",":")).encode(); duplicated=raw[:-1]+b',"expected_nonce":0}'; return duplicated.hex(),hashlib.sha256(duplicated).hexdigest()
    elif row_id=="schema_boolean_integer":value["expected_nonce"]=True
    elif row_id in {"slash_proof_payload_alias","slash_payload_substitution"}:value["payload_hash"]=value["bridge_proof"]
    elif row_id in {"slash_expired_evidence","slash_evidence_expired"}:value["valid_until"]=1_699_999_999_999
    elif row_id=="slash_evidence_identity_mismatch":value["identity"]="00"*32
    else:return None,None
    raw=json.dumps(value,sort_keys=True,separators=(",",":")).encode()
    return raw.hex(),hashlib.sha256(raw).hexdigest()

def row_params(label):
    value=params()["data"]
    if label=="change_reserve_credential":value=deepcopy(value);value["fields"][5]=bs(OPERATOR)
    return frozen(value)

def build():
    source=json.loads(MATRIX.read_text(encoding="utf-8")); rows=[]
    for s in source["rows"]:
        t=s["transition"] if s["transition"]!="all" else "update"; old,r,ctx=base(t)
        decode_rows={"slash_proof_payload_alias","slash_payload_substitution","slash_expired_evidence","slash_evidence_expired","slash_evidence_identity_mismatch"}
        phase="contract_decode" if s["id"].startswith("schema_") or s["id"] in decode_rows else "ledger_replay" if s["id"]=="update_parallel_nonce" else "uplc"
        ctx=mutate_context(ctx,s["mutation"]) if phase=="uplc" else ctx
        if phase=="contract_decode" and s["id"].startswith("schema_"):ctx["fields"][1]=con(99)
        ctx=specialize_context(ctx,s["id"])
        r=ctx["fields"][1]
        ev=[{"entrypoint":"agent_registry.spend","datum":frozen(old),"redeemer":frozen(r),"script_context":frozen(ctx),"expected":s["expectation"]}]
        if t in {"register","deregister"}:
            mr=con(0,bs(DID),bs(OWNER)) if t=="register" else con(1,bs(IDENTITY),bs(OWNER)); mc=deepcopy(ctx); mc["fields"][1]=deepcopy(mr); mc["fields"][2]=con(0,bs(POLICY))
            if s["id"]=="register_declared_stake_only":
                mc["fields"][0]["fields"][2]["list"][0]["fields"][1]=val(STAKE,1,False)
            if t == "deregister":
                mc["fields"][0]["fields"][0]["list"] = [deepcopy(ctx["fields"][0]["fields"][0]["list"][0])]
            mint_only_insensitive = {"register_wrong_initial_state", "register_declared_stake_only", "deregister_wrong_payout", "deregister_duplicate_payout", "deregister_non_ada_loss"}
            mint_expected = "accept" if s["id"] in mint_only_insensitive else s["expectation"]
            ev.append({"entrypoint":"agent_registry.mint","datum":frozen(none()),"redeemer":frozen(mr),"script_context":frozen(mc),"expected":mint_expected})
        refs=["44"*32+"#0"]*(2 if phase=="ledger_replay" else 1)
        payload_hex,payload_hash=contract_payload(s["id"])
        rows.append({"id":s["id"],"transition":s["transition"],"expectation":s["expectation"],"reason":s["reason"],"phase":phase,
          "mutation":mutation(s["mutation"]),"parameters":row_params(s["mutation"]),"evaluations":ev,
          "scenario":{"kind":"parallel_ledger_consumption" if phase=="ledger_replay" else "single_transaction","consumed_refs":refs,
          "produced_refs":["45"*32+"#0"] if t in {"register","update"} else [],
          "evidence_envelope":{"bridge_proof":"ee"*32,"payload_hash":"ff"*32,"identity":IDENTITY.hex(),"valid_until":1_700_000_300_000},
          "contract_payload_hex":payload_hex,"contract_payload_sha256":payload_hash}})
    return {"schema_version":"m3-f04-option-b-fixtures-v1","identity_contract":{"representation":"raw-utf8-bytes","minimum_bytes":32,"maximum_bytes":256,
      "normalization":"forbidden","domain_hex":DOMAIN.hex(),"accepted_min32_token_name":IDENTITY.hex(),
      "accepted_max256_token_name":"4f8613ad20953f8d4be12217f639705516501866bfee5c5c82098f3589cd350e"},"rows":rows}
def _no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise FixtureError("duplicate JSON key")
        result[key]=value
    return result
def decode_contract_payload(raw):
    try:value=json.loads(raw.decode("utf-8"),object_pairs_hook=_no_duplicates)
    except FixtureError:raise
    except (UnicodeError,ValueError) as exc:raise FixtureError("invalid contract payload") from exc
    if not isinstance(value,dict):raise FixtureError("contract payload object")
    if set(value)!=CONTRACT_KEYS:
        if set(value)-CONTRACT_KEYS:raise FixtureError("unknown contract field")
        raise FixtureError("missing contract field")
    if type(value["schema_version"]) is not int or value["schema_version"]!=1 or type(value["expected_nonce"]) is not int or value["expected_nonce"]<0:raise FixtureError("strict contract integer")
    if type(value["valid_until"]) is not int:raise FixtureError("strict contract integer")
    for key in ("identity","bridge_proof","payload_hash"):
        item=value[key]
        if not isinstance(item,str) or len(item)!=64 or item!=item.lower():raise FixtureError("contract hex")
        try:bytes.fromhex(item)
        except ValueError as exc:raise FixtureError("contract hex") from exc
    if value["identity"]!=IDENTITY.hex():raise FixtureError("evidence identity binding")
    if value["valid_until"]<1_700_000_000_000:raise FixtureError("evidence expiry")
    if value["bridge_proof"]==value["payload_hash"]:raise FixtureError("INV-10 proof payload alias")
    return value
def load(path=FIXTURES):
    try:return json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=_no_duplicates)
    except (OSError,UnicodeError,ValueError) as exc:raise FixtureError("invalid fixture JSON") from exc
def validate_serialized(value):
    if not isinstance(value,dict) or set(value)!={"data","cbor_hex","sha256"}:raise FixtureError("serialized schema")
    validate_data(value["data"]); raw=cbor(value["data"])
    if value["cbor_hex"]!=raw.hex() or value["sha256"]!=hashlib.sha256(raw).hexdigest():raise FixtureError("serialized binding")
def validate_document(doc):
    if not isinstance(doc,dict) or set(doc)!={"schema_version","identity_contract","rows"}:raise FixtureError("document schema")
    if doc["schema_version"]!="m3-f04-option-b-fixtures-v1":raise FixtureError("schema version")
    identity=doc["identity_contract"]
    if not isinstance(identity,dict) or set(identity)!={"representation","minimum_bytes","maximum_bytes","normalization","domain_hex","accepted_min32_token_name","accepted_max256_token_name"}:raise FixtureError("identity schema")
    if identity["representation"]!="raw-utf8-bytes" or identity["minimum_bytes"]!=32 or identity["maximum_bytes"]!=256 or identity["normalization"]!="forbidden" or identity["domain_hex"]!=DOMAIN.hex():raise FixtureError("identity contract")
    if identity_name()!=IDENTITY or identity["accepted_min32_token_name"]!=IDENTITY.hex() or identity["accepted_max256_token_name"]!="4f8613ad20953f8d4be12217f639705516501866bfee5c5c82098f3589cd350e":raise FixtureError("identity vector")
    rows=doc["rows"]
    if not isinstance(rows,list) or len(rows)!=49:raise FixtureError("row cardinality")
    ids=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"id","transition","expectation","reason","phase","mutation","parameters","evaluations","scenario"}:raise FixtureError("row schema")
        if not all(isinstance(row[k],str) for k in ("id","transition","expectation","reason","phase")):raise FixtureError("row scalar")
        if row["expectation"] not in {"accept","reject"} or row["phase"] not in {"uplc","contract_decode","ledger_replay"}:raise FixtureError("row classification")
        ids.append(row["id"])
        mut=row["mutation"]
        if not isinstance(mut,dict) or set(mut)!={"operation","path","before","after"}:raise FixtureError("mutation schema")
        validate_serialized(row["parameters"])
        ev=row["evaluations"]
        if not isinstance(ev,list) or not ev:raise FixtureError("missing evaluation")
        expected_count=2 if row["transition"] in {"register","deregister"} else 1
        if len(ev)!=expected_count:raise FixtureError("entrypoint cardinality")
        for item in ev:
            if not isinstance(item,dict) or set(item)!={"entrypoint","datum","redeemer","script_context","expected"}:raise FixtureError("evaluation schema")
            mint_exception = item["entrypoint"].endswith(".mint") and row["id"] in {"register_wrong_initial_state", "register_declared_stake_only", "deregister_wrong_payout", "deregister_duplicate_payout", "deregister_non_ada_loss"} and item["expected"]=="accept"
            if item["expected"]!=row["expectation"] and not mint_exception:raise FixtureError("expectation binding")
            for key in ("datum","redeemer","script_context"):validate_serialized(item[key])
            context_data=item["script_context"]["data"]
            if context_data.get("constructor")!=0 or not isinstance(context_data.get("fields"),list) or len(context_data["fields"])!=3:raise FixtureError("script context shape")
            if item["redeemer"]["data"]!=context_data["fields"][1]:raise FixtureError("redeemer context binding")
        scenario=row["scenario"]
        if not isinstance(scenario,dict) or set(scenario)!={"kind","consumed_refs","produced_refs","evidence_envelope","contract_payload_hex","contract_payload_sha256"}:raise FixtureError("scenario schema")
        if not isinstance(scenario["consumed_refs"],list) or not isinstance(scenario["produced_refs"],list):raise FixtureError("references")
        if len(scenario["produced_refs"])!=len(set(scenario["produced_refs"])):raise FixtureError("duplicate produced reference")
        envelope=scenario["evidence_envelope"]
        if not isinstance(envelope,dict) or set(envelope)!={"bridge_proof","payload_hash","identity","valid_until"} or type(envelope["valid_until"]) is not int:raise FixtureError("evidence envelope")
        if envelope["bridge_proof"]==envelope["payload_hash"]:raise FixtureError("INV-10 alias")
        payload_hex=scenario["contract_payload_hex"];payload_hash=scenario["contract_payload_sha256"]
        if row["phase"]=="contract_decode":
            if not isinstance(payload_hex,str) or not isinstance(payload_hash,str):raise FixtureError("missing contract payload")
            try:raw=bytes.fromhex(payload_hex)
            except ValueError as exc:raise FixtureError("malformed contract payload") from exc
            if hashlib.sha256(raw).hexdigest()!=payload_hash:raise FixtureError("contract payload binding")
            expected_errors={"schema_unknown":"unknown contract field","schema_duplicate":"duplicate JSON key","schema_boolean_integer":"strict contract integer","slash_expired_evidence":"evidence expiry","slash_evidence_expired":"evidence expiry","slash_evidence_identity_mismatch":"evidence identity binding","slash_proof_payload_alias":"INV-10 proof payload alias","slash_payload_substitution":"INV-10 proof payload alias"}
            try:decode_contract_payload(raw)
            except FixtureError as exc:
                if str(exc)!=expected_errors[row["id"]]:raise FixtureError("contract payload reason binding") from exc
            else:raise FixtureError("contract payload unexpectedly valid")
        elif payload_hex is not None or payload_hash is not None:raise FixtureError("unexpected contract payload")
    if len(ids)!=len(set(ids)):raise FixtureError("duplicate fixture identity")
    accepted=json.loads(MATRIX.read_text(encoding="utf-8"))
    if ids!=[row["id"] for row in accepted["rows"]]:raise FixtureError("fixture identity ordering")
    if [(row["expectation"],row["reason"]) for row in rows]!=[(row["expectation"],row["reason"]) for row in accepted["rows"]]:raise FixtureError("accepted contract drift")
    expected=build()
    if doc!=expected:raise FixtureError("frozen fixture drift")
    return {"rows":len(rows),"serialized_evaluations":sum(len(row["evaluations"]) for row in rows)}
def dump():
    doc=build();validate_document(doc)
    FIXTURES.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__":dump()
