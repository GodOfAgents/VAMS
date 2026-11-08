#!/usr/bin/env python3
"""Dependency-free M3.2a-R7 governance specification validator/generator."""
from __future__ import annotations
import hashlib,json,struct,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DOMAINS={
 'authority':'56414d532f617574686f726974792f763100',
 'proposal':'56414d532f70726f706f73616c2f763100',
 'receipt':'56414d532f726563656970742f763100',
 'intent':'56414d532f696e74656e742f763100',
}
LIMITS={'max_members':5,'authority_threshold':3,'max_voters':8,'max_inputs':16,'max_outputs':16,'max_assets':16,'max_datum_bytes':896,'max_signers':5,'max_validity_width_ms':300000,'max_voting_duration_ms':2592000000,'normal_delay_ms':86400000,'max_intent_lifetime_ms':604800000,'vkh_bytes':28,'policy_id_bytes':28,'asset_name_bytes':32,'tx_id_bytes':32,'action_hash_bytes':32,'target_domain_bytes':32}

def uint(n,w):
 if type(n) is not int or n<0 or n>=1<<(8*w): raise ValueError('u%d out of range'%(8*w))
 return n.to_bytes(w,'big')
def bstr(b):
 b=bytes(b); n=len(b)
 if n<24: h=bytes([n])
 elif n<256: h=b'\x58'+bytes([n])
 elif n<65536: h=b'\x59'+n.to_bytes(2,'big')
 else: raise ValueError('bytes too long')
 return h+b
def arr(xs):
 n=len(xs)
 if n<24: return bytes([0x80+n])+b''.join(xs)
 if n<256: return b'\x98'+bytes([n])+b''.join(xs)
 raise ValueError('array too long')
def integer(n):
 if n>=0:
  if n<24:return bytes([n])
  if n<256:return b'\x18'+bytes([n])
  if n<65536:return b'\x19'+n.to_bytes(2,'big')
  if n<1<<32:return b'\x1a'+n.to_bytes(4,'big')
  if n<1<<64:return b'\x1b'+n.to_bytes(8,'big')
  raise ValueError('integer too large')
 return b'\x20' if n==-1 else b'\x38'+(-1-n).to_bytes(1,'big')
def constr(alt,fields):
 if not 0<=alt<=6: raise ValueError('unsupported constructor')
 return bytes([0xd8,0x79+alt])+arr(fields)
def bool_data(v): return constr(1 if v else 0,[])
def hexbytes(h,n=None):
 b=bytes.fromhex(h)
 if n is not None and len(b)!=n: raise ValueError('wrong byte length')
 return b

def encode_record(r):
 return constr(0,[bstr(hexbytes(r['voter_vkh'],28)),integer(r['locked_vams']),bool_data(r['support']),integer(r['weight']),bstr(hexbytes(r['receipt_name'],32))])
def encode_authority(d):
 return constr(0,[integer(d["version"]),integer(d["network_id"]),integer(d["authority_state_lovelace"]),integer(d["proposal_base_lovelace"]),integer(d["per_voter_refund_lovelace"]),integer(d["policy_epoch"]),bstr(hexbytes(d["authority_policy_id"],28)),bstr(hexbytes(d["governor_script_hash"],28)),bstr(hexbytes(d["timelock_script_hash"],28)),bstr(hexbytes(d["seed_tx_id"],32)),integer(d["seed_index"]),arr([bstr(hexbytes(x,28)) for x in d["members"]]),integer(d["threshold"]),integer(d["normal_delay_ms"]),bool_data(d["emergency_disabled"]),integer(d["next_proposal_nonce"]),integer(d["next_intent_nonce"]),integer(d["max_lock_vams"]),arr([integer(x) for x in d["caps"]]),arr([bstr(bytes.fromhex(x)) for x in d["target_domains"]])])
def encode_proposal(d):
 status={'pending':0,'passed':1,'rejected':2}[d['status']]
 return constr(0,[integer(d['version']),constr(status,[]),bstr(hexbytes(d['proposal_asset'],32)),integer(d['nonce']),bstr(hexbytes(d['proposer_vkh'],28)),bstr(hexbytes(d['description_hash'],32)),bstr(hexbytes(d['action_hash'],32)),bstr(bytes.fromhex(d['target_domain'])),integer(d['policy_epoch']),integer(d['quorum']),integer(d['deadline']),integer(d['yes_weight']),integer(d['no_weight']),arr([encode_record(x) for x in d['locks']])])
def encode_intent(d):
 return constr(0,[integer(d['version']),bstr(hexbytes(d['proposal_id'],32)),bstr(hexbytes(d['proposal_asset'],32)),bstr(hexbytes(d['action_hash'],32)),bstr(hexbytes(d['payload_hash'],32)),bstr(bytes.fromhex(d['target_domain'])),integer(d['policy_epoch']),integer(d['nonce']),integer(d['queue_time']),integer(d['execute_after']),integer(d['lifetime']),bstr(hexbytes(d['proposer_vkh'],28)),bool_data(d['consumed'])])
def encode_datum(kind,d):
 return {'authority':encode_authority,'proposal':encode_proposal,'intent':encode_intent,'record':encode_record}[kind](d)
def digest(h): return hashlib.blake2b(bytes.fromhex(h),digest_size=32).hexdigest()
def asset_preimage(kind,fields):
 out=bytes.fromhex(DOMAINS[kind])
 for h in fields: out += bytes.fromhex(h)
 return out.hex()
def sample_fields(kind):
 z='11'*32; v='22'*28; p='33'*28; a='44'*32; t='55'*32; idx='00000007'; epoch='00000002'; nonce='0000000000000009'; dom='0564656d6f2f31'
 if kind=='authority': return ['00'*28,t,idx,'01',epoch]
 if kind=='proposal': return ['00'*28,a,nonce,v,t,dom]
 if kind=='receipt': return ['22'*28,'11'*28,a,v,'0000000000000064','01','00000000']
 return ['33'*28,'11'*28,a,v, '000000006553f100',t]

def sample_record(i):
 return {'voter_vkh':f'{i+1:02x}'*28,'locked_vams':1000+i,'support':i%2==0,'weight':31+i,'receipt_name':f'{0xa0+i:02x}'*32}
def sample_authority(): return {'version':1,'network_id':0,'authority_state_lovelace':5000000,'proposal_base_lovelace':3000000,'per_voter_refund_lovelace':1000000,'policy_epoch':2,'authority_policy_id':'00'*28,'governor_script_hash':'11'*28,'timelock_script_hash':'22'*28,'seed_tx_id':'11'*32,'seed_index':7,'members':[f'{i+1:02x}'*28 for i in range(5)],'threshold':3,'normal_delay_ms':86400000,'emergency_disabled':True,'next_proposal_nonce':9,'next_intent_nonce':4,'max_lock_vams':1000000000,'caps':[8,16,16,16,896],'target_domains':['64656d6f2f31']}
def sample_proposal(n,status='pending'):
 return {'version':1,'status':status,'proposal_asset':'44'*32,'nonce':9,'proposer_vkh':'33'*28,'description_hash':'66'*32,'action_hash':'55'*32,'target_domain':'64656d6f2f31','policy_epoch':2,'quorum':100,'deadline':1700000000000,'yes_weight':0,'no_weight':0,'locks':[sample_record(i) for i in range(n)]}
def sample_intent(): return {'version':1,'proposal_id':'77'*32,'proposal_asset':'44'*32,'action_hash':'55'*32,'payload_hash':'88'*32,'target_domain':'64656f2f31','policy_epoch':2,'nonce':4,'queue_time':1700000000000,'execute_after':1700086400000,'lifetime':604800000,'proposer_vkh':'33'*28,'consumed':False}

def load(name,base=ROOT): return json.loads((base/name).read_text())
def validate_spec(base=ROOT):
 spec=load('GOVERNANCE_SPEC.json',base); av=load('ASSET_VECTORS.json',base); dv=load('DATUM_VECTORS.json',base); tv=load('TRANSITION_TOPOLOGY.json',base); am=load('ACCEPTANCE_MATRIX.json',base)
 if spec['schema_version']!='m3.2a-r7-governance-spec-v1' or spec['status']!='design-only': raise ValueError('spec identity')
 if spec['limits']!=LIMITS: raise ValueError('limits drift')
 if spec['encoding']['domains']!=DOMAINS: raise ValueError('domains drift')
 if spec['encoding']['hash']!='BLAKE2b-256' or spec['encoding']['output_reference_index_bytes']!=4: raise ValueError('encoding drift')
 for v in av['vectors']:
  pre=asset_preimage(v['kind'],v['fields_hex']); dg=digest(pre)
  if pre!=v['preimage_hex'] or dg!=v['digest_hex'] or len(bytes.fromhex(dg))!=32: raise ValueError('asset vector '+v['id'])
 for v in dv['vectors']:
  raw=encode_datum(v['kind'],v['value'])
  if raw.hex()!=v['cbor_hex'] or len(raw)!=v['byte_length']: raise ValueError('datum vector '+v['id'])
  if v['byte_length']>LIMITS['max_datum_bytes'] and v['accepted']: raise ValueError('accepted datum over cap')
 seen=set()
 for row in tv['transitions']:
  if row['id'] in seen: raise ValueError('duplicate topology id')
  seen.add(row['id'])
  for k in ('without_change','with_change'):
   if row['outputs'][k] != row['outputs']['without_change'] + (1 if k=='with_change' else 0): raise ValueError('change equation')
   if row['collateral_return'][k] != 0: raise ValueError('unexpected collateral return')
  if row['inputs']['collateral']!=1 or row['inputs']['auxiliary_regular']!=1: raise ValueError('funding topology')
 if len(am['rows'])<40: raise ValueError('matrix incomplete')
 ids=set(); required={'counter_cross_mutation','immutable_authority_field','duplicate_signer','non_member_signer','authority_asset_preimage','receipt_substitution','redirected_refund','governed_asset_change','fee_governed_ada','ninth_voter','maximum_width_datum','quorum_tie','tally_overflow','time_before','time_at','time_after','execute_pre_f05'}
 for row in am['rows']:
  if set(row)!= {'id','handler','transition','expectation','reason','mutation_id','reference','evidence_status'}: raise ValueError('matrix row schema')
  if row['id'] in ids or row['evidence_status']!='pending': raise ValueError('matrix row status')
  ids.add(row['id'])
 if not required.issubset(ids): raise ValueError('matrix required cases')
 return {'ok':True,'asset_vectors':len(av['vectors']),'datum_vectors':len(dv['vectors']),'topology_rows':len(tv['transitions']),'matrix_rows':len(am['rows'])}

def main():
 try: print(json.dumps(validate_spec(),sort_keys=True)); return 0
 except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'ok':False,'error':str(e)})); return 1

# R9 closed-contract validation: all artifact schemas and references are exact.
def _r9_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out

def _r9_json(path):
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8 JSON") from exc
    return json.loads(raw, object_pairs_hook=_r9_pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("non-finite JSON number")))

def _r9_load(name, base=ROOT):
    return _r9_json(base / name)

def _r9_keys(obj, keys, label):
    if type(obj) is not dict or set(obj) != set(keys):
        raise ValueError(label + " keys")
    return obj

def _r9_str(v, label, allowed=None):
    if type(v) is not str or (allowed is not None and v not in allowed):
        raise ValueError(label + " value")
    return v

def _r9_bool(v, label):
    if type(v) is not bool:
        raise ValueError(label + " boolean")
    return v

def _r9_int(v, label, maximum=None):
    if type(v) is not int or v < 0 or (maximum is not None and v > maximum):
        raise ValueError(label + " integer")
    return v

def _r9_hex(v, label, widths=None):
    _r9_str(v, label)
    if len(v) % 2 or any(c not in "0123456789abcdefABCDEF" for c in v):
        raise ValueError(label + " hex")
    out = bytes.fromhex(v)
    if widths is not None and len(out) not in widths:
        raise ValueError(label + " width")
    return out

_R9_ASSET_FIELDS = {
 "authority": (("authority_policy_id",28),("seed_tx_id",32),("seed_index_u32",4),("network_id_u8",1),("policy_epoch_u32",4)),
 "proposal": (("authority_policy_id",28),("authority_asset_name",32),("proposal_counter_u64",8),("proposer_vkh",28),("action_hash",32),("target_domain",None)),
 "receipt": (("receipt_policy_id",28),("proposal_policy_id",28),("proposal_asset_name",32),("voter_vkh",28),("locked_vams_u64",8),("vote_choice_u8",1),("record_index_u32",4)),
 "intent": (("intent_policy_id",28),("proposal_policy_id",28),("proposal_asset_name",32),("proposer_vkh",28),("queue_time_u64",8),("action_hash",32)),
}
_R9_TOPOLOGY_IDS = ("genesis","create","vote","finalize-passed","finalize-rejected","cancel","queue","cancelintent","expireintent")
_R9_TOPOLOGY_NAMES = dict(zip(_R9_TOPOLOGY_IDS,("Genesis","Create","Vote","Finalize-Passed","Finalize-Rejected","Cancel","Queue","CancelIntent","ExpireIntent")))
_R9_MATRIX_TRANSITIONS = ("create","vote","finalize-passed","finalize-rejected","cancel","queue","cancelintent","expireintent","executeintent")
_R9_MATRIX_IDS = ("genesis_valid","genesis_rebind","counter_cross_mutation","immutable_authority_field","duplicate_signer","non_member_signer","authority_asset_preimage","receipt_substitution","redirected_refund","governed_asset_change","fee_governed_ada","ninth_voter","maximum_width_datum","quorum_tie","tally_overflow","time_before","time_at","time_after","execute_pre_f05","output_ref_width") + tuple(f"{t}_{s}" for t in _R9_MATRIX_TRANSITIONS for s in ("destination","topology_one_over","datum_mutation","timing_boundary")) + tuple(f"asset_boundary_{i:02d}" for i in range(25))
_R9_MUTATIONS = {"none","wrong_seed","counter_cross_mutation","immutable_authority_field","duplicate_signer","non_member_signer","authority_asset_preimage","receipt_substitution","redirected_refund","governed_asset_change","fee_governed_ada","ninth_voter","maximum_width_datum","quorum_tie","tally_overflow","time_before","time_at","time_after","execute_pre_f05","output_ref_width"} | {f"{p}_{t}" for t in _R9_MATRIX_TRANSITIONS for p in ("destination","topology","datum","timing")} | {f"asset_boundary_{i}" for i in range(25)}
_R9_SPEC_REFS = {"spec:authority_immutability","spec:lifecycle","spec:implementation_boundary","spec:encoding.output_reference"}
_R9_ASSET_NAMES = {"authority_nft","proposal_nft","receipt_nft","intent_nft","locked_vams","all_receipts"}
_R9_FROZEN_ARTIFACT_SHA256 = {
 "GOVERNANCE_SPEC.json":"973fa224f3ac46017be18c378027c8cf5067d103b8c118a86ae2e0e4ce0d2302",
 "ASSET_VECTORS.json":"05e14cbfa65ff9d804f5a6483612d5a3925e2f51e54b3a542fce2be53aa45125",
 "DATUM_VECTORS.json":"ab811013d75c40f89a75d3de16803cea4c3ac93bdfd65d8a8614d1fde3efba04",
 "TRANSITION_TOPOLOGY.json":"dcd4b8aaacc73df5ef3a7508818ffd96b2a756aff0c599cde0345d11376ef6f0",
 "ACCEPTANCE_MATRIX.json":"3a5a9d7e1e84f6c625d276ac6ac2e21ca775b665c23a25a73f196c7dbe022fc4",
}
_R9_TOPOLOGY_SEMANTIC_SHA256 = "6c906694ea9fa9a3aa5728771f50c595abbb2bcdd8b468af68285b344800987c"
_R9_MATRIX_SEMANTIC_SHA256 = "1f6ce63107df95efc5c1f837cb51c9db3a0637a40d4408787242fd33ee1e2beb"

def _r9_addresses(vectors):
    if type(vectors) is not list or len(vectors) != 6: raise ValueError("address vectors")
    seen=set()
    for v in vectors:
        _r9_keys(v,("id","credential_kind","network_id","credential_hash","stake_credential","header_hex","address_hex","declared_length"),"address vector")
        ident=_r9_str(v["id"],"address id")
        if ident in seen: raise ValueError("duplicate address id")
        seen.add(ident)
        kind=_r9_str(v["credential_kind"],"credential kind",{"key","script"})
        n=_r9_int(v["network_id"],"network id",15)
        if v["stake_credential"] != "none": raise ValueError("stake credential")
        raw=_r9_hex(v["credential_hash"],"credential hash",{28})
        header=(0x60 if kind=="key" else 0x70) | n
        if v["header_hex"] != f"{header:02x}" or v["address_hex"] != f"{header:02x}" + raw.hex() or v["declared_length"] != 29: raise ValueError("address bytes")
    if seen != {f"{kind}_network_{n}" for kind in ("key","script") for n in (0,1,15)}: raise ValueError("address coverage")

def _r9_validate_spec(s):
    _r9_keys(s,("schema_version","status","normative_artifacts","network","addresses","address_vectors","value_parameters","value_rules","equations","encoding","bootstrap","lifecycle","limits","topology_file","asset_vectors_file","datum_vectors_file","acceptance_file","implementation_boundary","config_schema"),"spec")
    if s["schema_version"]!="m3.2a-r7-governance-spec-v1" or s["status"]!="design-only": raise ValueError("spec identity")
    if s["normative_artifacts"]!=["GOVERNANCE_SPEC.json","ASSET_VECTORS.json","DATUM_VECTORS.json","TRANSITION_TOPOLOGY.json","ACCEPTANCE_MATRIX.json","governance_spec.py","test_governance_spec.py"]: raise ValueError("spec artifacts")
    n=_r9_keys(s["network"],("field","type","source","alternate_networks"),"network")
    if n!={"field":"network_id","type":"u8","source":"immutable GovernanceConfigV1 genesis datum","alternate_networks":"reject"}: raise ValueError("network")
    for name,obj in s["addresses"].items():
        if name not in {"authority_output","proposal_output","intent_output","voter_refund","proposer_refund","fee_change"}: raise ValueError("address")
        _r9_keys(obj,("kind","payment_credential","stake_credential","header"),"address")
        for v in obj.values(): _r9_str(v,"address field")
    _r9_keys(s["addresses"],("authority_output","proposal_output","intent_output","voter_refund","proposer_refund","fee_change"),"addresses")
    if any(s["addresses"][name]["header"] != "0x70 | network_id" for name in ("authority_output","proposal_output","intent_output")): raise ValueError("script address header formula")
    if any(s["addresses"][name]["header"] != "0x60 | network_id" for name in ("voter_refund","proposer_refund")): raise ValueError("key address header formula")
    _r9_addresses(s["address_vectors"])
    _r9_keys(s["value_parameters"],("authority_state_lovelace","proposal_base_lovelace","per_voter_refund_lovelace"),"value_parameters")
    for obj in s["value_parameters"].values():
        _r9_keys(obj,("type","source","fixture_values"),"value_parameter")
        for v in obj.values(): _r9_str(v,"value_parameter")
    rules=_r9_keys(s["value_rules"],("governed_state_assets","auxiliary_funding","fees","change","min_ada"),"value_rules")
    if rules["governed_state_assets"]!=["authority_nft","proposal_nft","receipt_nft","intent_nft","locked_vams"]: raise ValueError("value assets")
    for k in ("auxiliary_funding","fees","change","min_ada"): _r9_str(rules[k],"value rule")
    eq=_r9_keys(s["equations"],("authority_state","proposal","vote","finalize_passed","finalize_rejected_cancel","queue","cancel_expire_intent"),"equations")
    for v in eq.values(): _r9_str(v,"equation")
    enc=_r9_keys(s["encoding"],("domains","domain_ascii","hash","output_reference","integer_widths","verification_key_hash_bytes","policy_id_bytes","asset_name_bytes","action_hash_bytes","target_domain","truncation","output_reference_index_bytes"),"encoding")
    if enc["domains"]!=DOMAINS or enc["domain_ascii"]!={"authority":"VAMS/authority/v1\\0","proposal":"VAMS/proposal/v1\\0","receipt":"VAMS/receipt/v1\\0","intent":"VAMS/intent/v1\\0"}: raise ValueError("encoding domains")
    if enc["hash"]!="BLAKE2b-256" or enc["output_reference"]!="tx_id[32] || output_index[u32be]" or enc["integer_widths"]!={"u8":1,"u32":4,"u64":8}: raise ValueError("encoding")
    if enc["verification_key_hash_bytes"]!=28 or enc["policy_id_bytes"]!=28 or enc["asset_name_bytes"]!=32 or enc["action_hash_bytes"]!=32 or enc["target_domain"]!="u8(length 0..32) || bytes" or enc["truncation"]!="reject" or enc["output_reference_index_bytes"]!=4: raise ValueError("encoding limits")
    if type(s["bootstrap"]) is not list or len(s["bootstrap"])!=6 or any(type(x) is not str for x in s["bootstrap"]): raise ValueError("bootstrap")
    life=_r9_keys(s["lifecycle"],("quadratic_weight","quorum","pass","tie","queue_time","execute_after","pre_f05_execute","post_f05_execute"),"lifecycle")
    for v in life.values(): _r9_str(v,"lifecycle")
    if life["pre_f05_execute"]!="always reject" or life["post_f05_execute"]!="outside M3.2a and not an accepted R7 case": raise ValueError("lifecycle boundary")
    if _r9_keys(s["limits"],LIMITS.keys(),"limits")!=LIMITS: raise ValueError("limits")
    for k in ("topology_file","asset_vectors_file","datum_vectors_file","acceptance_file","implementation_boundary"): _r9_str(s[k],"spec file")
    if (s["topology_file"],s["asset_vectors_file"],s["datum_vectors_file"],s["acceptance_file"])!=("TRANSITION_TOPOLOGY.json","ASSET_VECTORS.json","DATUM_VECTORS.json","ACCEPTANCE_MATRIX.json"): raise ValueError("spec file binding")
    cfg=_r9_keys(s["config_schema"],("name","fields","runtime_overrides","fixture_values"),"config")
    if cfg["name"]!="GovernanceConfigV1" or cfg["runtime_overrides"]!="reject" or cfg["fixture_values"]!="non-admission only": raise ValueError("config")
    fields=cfg["fields"]
    expected=(("network_id","u8","immutable genesis datum"),("authority_state_lovelace","u64","immutable genesis datum"),("proposal_base_lovelace","u64","immutable genesis datum"),("per_voter_refund_lovelace","u64","immutable genesis datum"),("authority_seed","OutputReference","one-shot genesis input"),("authority_script_hash","bytes28","compiled artifact"),("governor_script_hash","bytes28","compiled artifact"),("timelock_script_hash","bytes28","compiled artifact"),("fixed_authorizers","array[5] bytes28","immutable genesis datum"),("threshold","u32","immutable genesis datum"))
    if type(fields) is not list or len(fields)!=len(expected): raise ValueError("config fields")
    for field, want in zip(fields,expected):
        _r9_keys(field,("name","type","source"),"config field")
        if tuple(field[k] for k in ("name","type","source"))!=want: raise ValueError("config field")

def _r9_assets(av):
    _r9_keys(av,("schema_version","vectors"),"assets")
    if av["schema_version"]!="m3.2a-r7-asset-vectors-v1" or type(av["vectors"]) is not list or len(av["vectors"])!=4: raise ValueError("assets")
    ids=set()
    for v in av["vectors"]:
        _r9_keys(v,("id","kind","fixture_only","field_order","fields_hex","preimage_hex","digest_hex"),"asset vector")
        ident=_r9_str(v["id"],"asset id"); kind=_r9_str(v["kind"],"asset kind")
        if ident in ids or kind not in _R9_ASSET_FIELDS or v["fixture_only"] is not True: raise ValueError("asset identity")
        ids.add(ident); fieldspec=_R9_ASSET_FIELDS[kind]
        canonical={"authority":["00"*28,"55"*32,"00000007","01","00000002"],"proposal":["00"*28,"44"*32,"0000000000000009","22"*28,"55"*32,"0664656d6f2f31"],"receipt":["22"*28,"11"*28,"44"*32,"22"*28,"0000000000000064","01","00000000"],"intent":["33"*28,"11"*28,"44"*32,"22"*28,"000000006553f100","55"*32]}[kind]
        if v["fields_hex"] != canonical: raise ValueError("asset canonical fixture")
        if v["field_order"]!= [x[0] for x in fieldspec] or type(v["fields_hex"]) is not list or len(v["fields_hex"])!=len(fieldspec): raise ValueError("asset fields")
        for value,(_,width) in zip(v["fields_hex"],fieldspec):
            raw=_r9_hex(value,"asset field")
            if width is not None and len(raw)!=width: raise ValueError("asset width")
            if width is None and (len(raw)<1 or len(raw)>33 or raw[0]!=len(raw)-1 or len(raw)-1>32): raise ValueError("target domain")
        pre=asset_preimage(kind,v["fields_hex"])
        if v["preimage_hex"]!=pre or v["digest_hex"]!=digest(pre): raise ValueError("asset vector "+ident)
    if ids!={"authority_fixture_v1","proposal_fixture_v1","receipt_fixture_v1","intent_fixture_v1"}: raise ValueError("asset ids")

def _r9_record(d,label):
    _r9_keys(d,("voter_vkh","locked_vams","support","weight","receipt_name"),label)
    _r9_hex(d["voter_vkh"],label+" vkh",{28}); _r9_int(d["locked_vams"],label+" locked",(1<<64)-1); _r9_bool(d["support"],label+" support"); _r9_int(d["weight"],label+" weight",(1<<64)-1); _r9_hex(d["receipt_name"],label+" receipt",{32})

def _r9_datum_value(kind,d,label):
    if kind=="record": _r9_record(d,label); return
    if kind=="authority":
        keys=("version","network_id","authority_state_lovelace","proposal_base_lovelace","per_voter_refund_lovelace","policy_epoch","authority_policy_id","governor_script_hash","timelock_script_hash","seed_tx_id","seed_index","members","threshold","normal_delay_ms","emergency_disabled","next_proposal_nonce","next_intent_nonce","max_lock_vams","caps","target_domains")
        _r9_keys(d,keys,label)
        for k in ("version","authority_state_lovelace","proposal_base_lovelace","per_voter_refund_lovelace","policy_epoch","seed_index","threshold","normal_delay_ms","next_proposal_nonce","next_intent_nonce","max_lock_vams"): _r9_int(d[k],label+" "+k,(1<<64)-1)
        _r9_int(d["network_id"],label+" network",255)
        for k,w in (("authority_policy_id",28),("governor_script_hash",28),("timelock_script_hash",28),("seed_tx_id",32)): _r9_hex(d[k],label+" "+k,{w})
        if type(d["members"]) is not list or len(d["members"])!=5: raise ValueError(label+" members")
        for x in d["members"]: _r9_hex(x,label+" member",{28})
        _r9_bool(d["emergency_disabled"],label+" emergency")
        if d["caps"]!=[8,16,16,16,896]: raise ValueError(label+" caps")
        if type(d["target_domains"]) is not list: raise ValueError(label+" domains")
        for x in d["target_domains"]:
            if len(_r9_hex(x,label+" domain"))>32: raise ValueError(label+" domain width")
        return
    if kind=="proposal":
        keys=("version","status","proposal_asset","nonce","proposer_vkh","description_hash","action_hash","target_domain","policy_epoch","quorum","deadline","yes_weight","no_weight","locks")
        _r9_keys(d,keys,label); _r9_int(d["version"],label+" version",(1<<64)-1); _r9_str(d["status"],label+" status",{"pending","passed","rejected"}); _r9_hex(d["proposal_asset"],label+" asset",{32})
        for k in ("nonce","policy_epoch","quorum","deadline","yes_weight","no_weight"): _r9_int(d[k],label+" "+k,(1<<64)-1)
        _r9_hex(d["proposer_vkh"],label+" proposer",{28}); _r9_hex(d["description_hash"],label+" desc",{32}); _r9_hex(d["action_hash"],label+" action",{32}); 
        if len(_r9_hex(d["target_domain"],label+" domain"))>32 or type(d["locks"]) is not list or len(d["locks"])>9: raise ValueError(label+" proposal limits")
        for i,x in enumerate(d["locks"]): _r9_record(x,label+" lock")
        return
    if kind=="intent":
        keys=("version","proposal_id","proposal_asset","action_hash","payload_hash","target_domain","policy_epoch","nonce","queue_time","execute_after","lifetime","proposer_vkh","consumed")
        _r9_keys(d,keys,label)
        for k in ("version","policy_epoch","nonce","queue_time","execute_after","lifetime"): _r9_int(d[k],label+" "+k,(1<<64)-1)
        for k in ("proposal_id","proposal_asset","action_hash","payload_hash"): _r9_hex(d[k],label+" "+k,{32})
        _r9_hex(d["proposer_vkh"],label+" proposer",{28}); _r9_hex(d["target_domain"],label+" domain")
        if len(bytes.fromhex(d["target_domain"]))>32: raise ValueError(label+" domain width")
        _r9_bool(d["consumed"],label+" consumed"); return
    raise ValueError("datum kind")

def _r9_datums(dv):
    _r9_keys(dv,("schema_version","max_datum_bytes","vectors"),"datums")
    if dv["schema_version"]!="m3.2a-r7-datum-vectors-v1" or dv["max_datum_bytes"]!=LIMITS["max_datum_bytes"] or type(dv["vectors"]) is not list or len(dv["vectors"])!=7: raise ValueError("datum document")
    ids=set()
    for v in dv["vectors"]:
        _r9_keys(v,("id","kind","accepted","record_count","value","cbor_hex","byte_length"),"datum vector")
        ident=_r9_str(v["id"],"datum id"); kind=_r9_str(v["kind"],"datum kind",{"authority","proposal","intent","record"})
        if ident in ids: raise ValueError("duplicate datum id")
        ids.add(ident); _r9_bool(v["accepted"],"datum accepted")
        canonical={"authority_maximal_fixture":sample_authority(),"intent_maximal_fixture":sample_intent(),"record_fixture":sample_record(0),"proposal_0_records":sample_proposal(0),"proposal_1_records":sample_proposal(1),"proposal_8_records":sample_proposal(8),"proposal_9_records":sample_proposal(9)}[ident]
        if v["value"] != canonical: raise ValueError("datum canonical fixture")
        if v["record_count"] is not None: _r9_int(v["record_count"],"datum records",9)
        _r9_datum_value(kind,v["value"],"datum value")
        raw=encode_datum(kind,v["value"]); _r9_hex(v["cbor_hex"],"datum cbor")
        if v["cbor_hex"]!=raw.hex() or v["byte_length"]!=len(raw): raise ValueError("datum vector "+ident)
        if kind=="proposal":
            count=len(v["value"]["locks"])
            if v["record_count"]!=count or v["accepted"] != (count<=8 and len(raw)<=LIMITS["max_datum_bytes"]): raise ValueError("datum acceptance")
        elif v["record_count"] is not None: raise ValueError("datum record count")
        if v["accepted"] and len(raw)>LIMITS["max_datum_bytes"]: raise ValueError("datum cap")
    if ids!={"authority_maximal_fixture","intent_maximal_fixture","record_fixture","proposal_0_records","proposal_1_records","proposal_8_records","proposal_9_records"}: raise ValueError("datum ids")

def _r9_topology(tv):
    _r9_keys(tv,("schema_version","status","transitions"),"topology")
    if tv["schema_version"]!="m3.2a-r7-topology-v1" or tv["status"]!="design-only" or type(tv["transitions"]) is not list or len(tv["transitions"])!=9: raise ValueError("topology document")
    ids=set()
    for r in tv["transitions"]:
        _r9_keys(r,("id","transition","enforcement","inputs","collateral_return","outputs","minted_assets","burned_assets","datums","redeemers","signers","script_witnesses","one_over_limit_mutations"),"topology row")
        ident=_r9_str(r["id"],"topology id")
        if ident in ids or ident not in _R9_TOPOLOGY_NAMES or r["transition"]!=_R9_TOPOLOGY_NAMES[ident] or r["enforcement"]!="script_and_deployment_envelope": raise ValueError("topology identity")
        ids.add(ident)
        inp=_r9_keys(r["inputs"],("governed","auxiliary_regular","authority_reference","allowed_reference_scripts","collateral"),"topology inputs")
        for v in inp.values(): _r9_int(v,"topology input",LIMITS["max_inputs"])
        for group in ("collateral_return","outputs"):
            vals=_r9_keys(r[group],("without_change","with_change"),"topology "+group)
            for v in vals.values(): _r9_int(v,"topology output",LIMITS["max_outputs"])
        if inp["auxiliary_regular"]!=1 or inp["collateral"]!=1 or r["collateral_return"]!={"without_change":0,"with_change":0} or r["outputs"]["with_change"]!=r["outputs"]["without_change"]+1: raise ValueError("topology equation")
        for key in ("minted_assets","burned_assets","datums","redeemers","script_witnesses"):
            vals=r[key]
            if type(vals) is not list or any(type(x) is not str for x in vals): raise ValueError("topology list")
        if any(x not in _R9_ASSET_NAMES for x in r["minted_assets"]+r["burned_assets"]): raise ValueError("topology assets")
        sign=_r9_keys(r["signers"],("authority_members","proposer","voter","distinct"),"topology signers")
        for v in sign.values(): _r9_int(v,"topology signer",LIMITS["max_signers"])
        if type(r["one_over_limit_mutations"]) is not list or r["one_over_limit_mutations"]!=["inputs","outputs","assets","datum_bytes","signers"]: raise ValueError("topology mutation set")
    if ids!=set(_R9_TOPOLOGY_IDS): raise ValueError("topology ids")
    actual=hashlib.sha256(json.dumps(tv["transitions"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if actual != _R9_TOPOLOGY_SEMANTIC_SHA256: raise ValueError("topology semantic drift")

def _r9_matrix(am, asset_ids, datum_ids, topology_ids):
    _r9_keys(am,("schema_version","status","evidence_status_default","rows"),"matrix")
    if am["schema_version"]!="m3.2a-r7-acceptance-matrix-v1" or am["status"]!="design-only" or am["evidence_status_default"]!="pending" or type(am["rows"]) is not list or len(am["rows"])!=81: raise ValueError("matrix document")
    ids=set(); mutations=set(); refs=set()
    valid_refs=_R9_SPEC_REFS | {f"asset:{x}" for x in asset_ids} | {f"datum:{x}" for x in datum_ids} | {f"topology:{x}" for x in topology_ids}
    for r in am["rows"]:
        _r9_keys(r,("id","handler","transition","expectation","reason","mutation_id","reference","evidence_status"),"matrix row")
        ident=_r9_str(r["id"],"matrix id"); mutation=_r9_str(r["mutation_id"],"matrix mutation"); ref=_r9_str(r["reference"],"matrix reference")
        if ident in ids or ident not in set(_R9_MATRIX_IDS) or mutation in mutations or mutation not in _R9_MUTATIONS: raise ValueError("matrix identity")
        if _r9_str(r["expectation"],"matrix expectation",{"accept","reject"}) not in {"accept","reject"} or r["evidence_status"]!="pending": raise ValueError("matrix state")
        for k in ("handler","transition","reason"):
            if not _r9_str(r[k],"matrix "+k): raise ValueError("matrix empty")
        if ref.count(":")!=1 or ref not in valid_refs: raise ValueError("matrix dangling reference")
        ids.add(ident); mutations.add(mutation); refs.add(ref)
    required=_R9_SPEC_REFS | {f"asset:{x}" for x in asset_ids} | {f"topology:{x}" for x in topology_ids} | {"datum:proposal_0_records","datum:proposal_8_records","datum:proposal_9_records"}
    if ids!=set(_R9_MATRIX_IDS) or mutations!=_R9_MUTATIONS or not required.issubset(refs): raise ValueError("matrix coverage")
    pre=next((row for row in am["rows"] if row["id"]=="execute_pre_f05"),None)
    if pre is None or pre["transition"] != "ExecuteIntent" or pre["expectation"] != "reject" or pre["reason"] != "EXECUTE_DISABLED_PRE_F05" or pre["evidence_status"] != "pending": raise ValueError("pre-f05 execute boundary")
    actual=hashlib.sha256(json.dumps(am["rows"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if actual != _R9_MATRIX_SEMANTIC_SHA256: raise ValueError("matrix semantic drift")

def _r9_closed_validate(base=ROOT, *, enforce_frozen=True):
    spec=_r9_load("GOVERNANCE_SPEC.json",base); av=_r9_load("ASSET_VECTORS.json",base); dv=_r9_load("DATUM_VECTORS.json",base); tv=_r9_load("TRANSITION_TOPOLOGY.json",base); am=_r9_load("ACCEPTANCE_MATRIX.json",base)
    if enforce_frozen:
        for name, expected in _R9_FROZEN_ARTIFACT_SHA256.items():
            if hashlib.sha256((base/name).read_bytes()).hexdigest() != expected: raise ValueError("frozen artifact drift: "+name)
    _r9_validate_spec(spec); _r9_assets(av); _r9_datums(dv); _r9_topology(tv); _r9_matrix(am,{v["id"] for v in av["vectors"]},{v["id"] for v in dv["vectors"]},{v["id"] for v in tv["transitions"]})
    return {"ok":True,"asset_vectors":len(av["vectors"]),"datum_vectors":len(dv["vectors"]),"topology_rows":len(tv["transitions"]),"matrix_rows":len(am["rows"])}

validate_spec = _r9_closed_validate

def main():
    try:
        print(json.dumps(validate_spec(), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(json.dumps({"ok":False,"error":str(exc)}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
