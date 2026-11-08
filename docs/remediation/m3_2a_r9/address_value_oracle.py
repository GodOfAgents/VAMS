"""Independent closed oracle for the M3.2a governance design (R13)."""
from dataclasses import dataclass
from hashlib import blake2b, sha256
from pathlib import Path
import argparse, contextlib, io, json, math, os, re, stat, sys

class OracleError(ValueError): pass
MAX_U8=(1<<8)-1
MAX_U32=(1<<32)-1
MAX_U64=(1<<64)-1
MAX_DATUM_BYTES=896
MAX_INPUTS=MAX_OUTPUTS=MAX_ASSETS=16
MAX_VOTERS=8
MAX_MEMBERS=5
EXPECTED_NETWORK_ID=1
SNAPSHOT_SCHEMA_VERSION="m3.2a-ledger-snapshot-v1"
_HEX=re.compile(r"^[0-9a-fA-F]+$")
def _strict(value,label,maximum):
    if type(value) is not int or value<0 or value>maximum: raise OracleError(label+" integer")
    return value
def strict_u8(value,label="u8"): return _strict(value,label,MAX_U8)
def strict_u32(value,label="u32"): return _strict(value,label,MAX_U32)
def strict_u64(value,label="u64"): return _strict(value,label,MAX_U64)
def checked_add(left,right,label="arithmetic",maximum=MAX_U64):
    left=_strict(left,label+" left",maximum); right=_strict(right,label+" right",maximum)
    if right>maximum-left: raise OracleError(label+" overflow")
    return left+right
def checked_sub(left,right,label="arithmetic",maximum=MAX_U64):
    left=_strict(left,label+" left",maximum); right=_strict(right,label+" right",maximum)
    if right>left: raise OracleError(label+" underflow")
    return left-right
def checked_mul(left,right,label="arithmetic",maximum=MAX_U64):
    left=_strict(left,label+" left",maximum); right=_strict(right,label+" right",maximum)
    if left and right>maximum//left: raise OracleError(label+" overflow")
    return left*right
DOMAINS={"authority":b"VAMS/authority/v1\x00","proposal":b"VAMS/proposal/v1\x00","receipt":b"VAMS/receipt/v1\x00","intent":b"VAMS/intent/v1\x00"}
FIELD_WIDTHS={"authority":(28,32,4,1,4),"proposal":(28,32,8,28,32,-1),"receipt":(28,28,32,28,8,1,4),"intent":(28,28,32,28,8,32)}
TARGET_DOMAIN_ALLOWLIST=frozenset({"0664656d6f2f31"})
TARGET_PAYLOAD_ALLOWLIST=frozenset({"64656d6f2f31","64656f2f31"})
DATUM_VECTOR_SHA256="ab811013d75c40f89a75d3de16803cea4c3ac93bdfd65d8a8614d1fde3efba04"
TOPOLOGY_SHA256="dcd4b8aaacc73df5ef3a7508818ffd96b2a756aff0c599cde0345d11376ef6f0"
_DATUM_REGISTRY_RELATIVE=("docs","remediation","m3_2a_r7","DATUM_VECTORS.json")
_MAX_REGISTRY_BYTES=65536
_AUTHORITY_SCRIPT_HASH="22"*28

def _fixed_repo_root():
    # Keep the path lexical: descriptor walking below, not resolve(), enforces
    # no-follow semantics for every repository ancestor.
    return Path(os.path.abspath(__file__)).parents[3]

def _open_fixed_registry():
    flags_dir=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
    flags_file=os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC
    root=_fixed_repo_root()
    if not root.is_absolute() or any(part in ("",".","..") for part in root.parts):
        raise OracleError("datum registry path")
    fds=[]
    try:
        fd=os.open(os.path.sep,flags_dir); fds.append(fd)
        for part in root.parts[1:]+_DATUM_REGISTRY_RELATIVE[:-1]:
            if part in ("",".","..") or os.path.isabs(part): raise OracleError("datum registry path")
            nxt=os.open(part,flags_dir,dir_fd=fd); fds.append(nxt); fd=nxt
        final=os.open(_DATUM_REGISTRY_RELATIVE[-1],flags_file,dir_fd=fd)
        try:
            st=os.fstat(final)
            if not stat.S_ISREG(st.st_mode) or st.st_size>_MAX_REGISTRY_BYTES:
                raise OracleError("datum registry file")
            chunks=[]; total=0
            while True:
                chunk=os.read(final,min(65536,_MAX_REGISTRY_BYTES-total+1))
                if not chunk: break
                total+=len(chunk)
                if total>_MAX_REGISTRY_BYTES: raise OracleError("datum registry size")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(final)
    except OracleError:
        raise
    except (OSError,ValueError) as exc:
        raise OracleError("datum registry") from exc
    finally:
        for open_fd in reversed(fds):
            try: os.close(open_fd)
            except OSError: pass
def _hex(value,width,label):
    if type(value) is not str or len(value)!=width*2 or _HEX.fullmatch(value) is None: raise OracleError(label+" encoding")
    try: return bytes.fromhex(value)
    except (TypeError,ValueError) as exc: raise OracleError(label+" encoding") from exc
def _target_domain(value,label="target domain"):
    if type(value) is not str or value not in TARGET_DOMAIN_ALLOWLIST or value!=value.lower() or _HEX.fullmatch(value) is None: raise OracleError(label+" encoding")
    raw=bytes.fromhex(value)
    if len(raw)<2 or len(raw)>33 or raw[0]!=len(raw)-1: raise OracleError(label+" length")
    return raw
def enterprise_address(network_id,credential_kind,credential_hash_hex,expected_network=None):
    _strict(network_id,"network",15)
    if expected_network is not None and (_strict(expected_network,"expected network",15)!=network_id): raise OracleError("network mismatch")
    if type(credential_kind) is not str or credential_kind not in ("key","script"): raise OracleError("credential kind")
    return bytes([(0x60 if credential_kind=="key" else 0x70)|network_id])+_hex(credential_hash_hex,28,"credential")
def asset_preimage(kind,fields_hex):
    if type(kind) is not str or kind not in FIELD_WIDTHS or type(fields_hex) is not list or len(fields_hex)!=len(FIELD_WIDTHS[kind]): raise OracleError("asset fields")
    parts=[DOMAINS[kind]]
    for i,(value,width) in enumerate(zip(fields_hex,FIELD_WIDTHS[kind])): parts.append(_target_domain(value) if width==-1 else _hex(value,width,"field "+str(i)))
    preimage=b"".join(parts)
    return preimage,blake2b(preimage,digest_size=32).digest()

TOPOLOGY_RECORDS={
 "genesis":{"transition":"Genesis","governed":0,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":1,"outputs_with_change":2,"minted_assets":["authority_nft"],"burned_assets":[],"datums":["GovernanceConfigV1"],"redeemers":["Genesis"],"authority_members":0,"proposer":0,"voter":0,"distinct":0},
 "create":{"transition":"Create","governed":1,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":2,"outputs_with_change":3,"minted_assets":["proposal_nft"],"burned_assets":[],"datums":["AuthorityDatumV1","ProposalDatumV1"],"redeemers":["CreateProposal"],"authority_members":3,"proposer":1,"voter":0,"distinct":3},
 "vote":{"transition":"Vote","governed":1,"auxiliary_regular":1,"authority_reference":1,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":2,"outputs_with_change":3,"minted_assets":["receipt_nft"],"burned_assets":[],"datums":["AuthorityDatumV1","ProposalDatumV1"],"redeemers":["Vote"],"authority_members":0,"proposer":0,"voter":1,"distinct":1},
 "finalize-passed":{"transition":"Finalize-Passed","governed":1,"auxiliary_regular":1,"authority_reference":1,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":1,"outputs_with_change":2,"minted_assets":[],"burned_assets":[],"datums":["AuthorityDatumV1","ProposalDatumV1"],"redeemers":["FinalizePassed"],"authority_members":0,"proposer":0,"voter":0,"distinct":0},
 "finalize-rejected":{"transition":"Finalize-Rejected","governed":1,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":9,"outputs_with_change":10,"minted_assets":[],"burned_assets":["proposal_nft","all_receipts"],"datums":["ProposalDatumV1","VoteLockRecordV1"],"redeemers":["FinalizeRejected"],"authority_members":0,"proposer":0,"voter":0,"distinct":0},
 "cancel":{"transition":"Cancel","governed":1,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":9,"outputs_with_change":10,"minted_assets":[],"burned_assets":["proposal_nft","all_receipts"],"datums":["ProposalDatumV1","VoteLockRecordV1"],"redeemers":["Cancel"],"authority_members":0,"proposer":1,"voter":0,"distinct":1},
 "queue":{"transition":"Queue","governed":2,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":10,"outputs_with_change":11,"minted_assets":["intent_nft"],"burned_assets":["proposal_nft","all_receipts"],"datums":["AuthorityDatumV1","ProposalDatumV1","IntentDatumV1","VoteLockRecordV1"],"redeemers":["Queue"],"authority_members":3,"proposer":0,"voter":0,"distinct":3},
 "cancelintent":{"transition":"CancelIntent","governed":1,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":1,"outputs_with_change":2,"minted_assets":[],"burned_assets":["intent_nft"],"datums":["IntentDatumV1"],"redeemers":["CancelIntent"],"authority_members":3,"proposer":0,"voter":0,"distinct":3},
 "expireintent":{"transition":"ExpireIntent","governed":1,"auxiliary_regular":1,"authority_reference":0,"allowed_reference_scripts":0,"collateral":1,"outputs_without_change":1,"outputs_with_change":2,"minted_assets":[],"burned_assets":["intent_nft"],"datums":["IntentDatumV1"],"redeemers":["ExpireIntent"],"authority_members":0,"proposer":0,"voter":0,"distinct":0}}
_WITNESSES={"genesis":["authority_validator","authority_policy"],"create":["authority_validator","governor_validator","proposal_policy"],"vote":["governor_validator","receipt_policy"],"finalize-passed":["governor_validator"],"finalize-rejected":["governor_validator","proposal_policy","receipt_policy"],"cancel":["governor_validator","proposal_policy","receipt_policy"],"queue":["authority_validator","governor_validator","timelock_validator","intent_policy","receipt_policy"],"cancelintent":["timelock_validator","intent_policy"],"expireintent":["timelock_validator","intent_policy"]}
for _name,_record in TOPOLOGY_RECORDS.items():
    _record.update(enforcement="script_and_deployment_envelope",collateral_return={"without_change":0,"with_change":0},script_witnesses=_WITNESSES[_name],one_over_limit_mutations=["inputs","outputs","assets","datum_bytes","signers"])
TOPOLOGY_ORDER=tuple(TOPOLOGY_RECORDS)
FROZEN_TRANSITIONS=frozenset(TOPOLOGY_RECORDS)
def validate_topology_record(transition,record):
    if type(transition) is not str or transition not in TOPOLOGY_RECORDS or type(record) is not dict: raise OracleError("topology record")
    expected=TOPOLOGY_RECORDS[transition]
    if record==expected: return True
    nested={"id":transition,"transition":expected["transition"],"enforcement":expected["enforcement"],
            "inputs":{key:expected[key] for key in ("governed","auxiliary_regular","authority_reference","allowed_reference_scripts","collateral")},
            "collateral_return":expected["collateral_return"],
            "outputs":{"without_change":expected["outputs_without_change"],"with_change":expected["outputs_with_change"]},
            "minted_assets":expected["minted_assets"],"burned_assets":expected["burned_assets"],
            "datums":expected["datums"],"redeemers":expected["redeemers"],
            "signers":{"authority_members":expected["authority_members"],"proposer":expected["proposer"],"voter":expected["voter"],"distinct":expected["distinct"]},
            "script_witnesses":expected["script_witnesses"],"one_over_limit_mutations":expected["one_over_limit_mutations"]}
    if record!=nested: raise OracleError("topology semantic mismatch")
    return True
def validate_topology_counts(transition,counts):
    if type(transition) is not str or transition not in TOPOLOGY_RECORDS: raise OracleError("topology transition")
    keys={"inputs","outputs","change_outputs","mint","burn","authority_reference"}
    if type(counts) is not dict or set(counts)!=keys: raise OracleError("topology keys")
    for key,value in counts.items():
        strict_u32(value,"topology "+key)
        if value>MAX_INPUTS: raise OracleError("topology limit")
    expected=TOPOLOGY_RECORDS[transition]
    if counts["authority_reference"]!=expected["authority_reference"]: raise OracleError("authority reference")
    if (counts["inputs"]!=expected["governed"]+expected["auxiliary_regular"]+expected["authority_reference"]+expected["collateral"] or counts["outputs"]!=expected["outputs_without_change"] or counts["change_outputs"]!=expected["outputs_with_change"] or counts["mint"]!=len(expected["minted_assets"]) or counts["burn"]!=len(expected["burned_assets"])): raise OracleError("topology equation")
    if counts["inputs"]>MAX_INPUTS or counts["outputs"]>MAX_OUTPUTS or counts["mint"]+counts["burn"]>MAX_ASSETS: raise OracleError("topology limit")
    return True
def _asset_map(mapping,label):
    if type(mapping) is not dict: raise OracleError(label+" mapping")
    if len(mapping)>MAX_ASSETS: raise OracleError(label+" size")
    for asset,quantity in mapping.items():
        if type(asset) is not str or not asset or len(asset)>64: raise OracleError(label+" asset")
        strict_u64(quantity,label+" quantity")
    return mapping
def validate_value_flow(inputs,outputs,minted,burned,fee_lovelace,required_reserves=None,change=None,collateral=None):
    for mapping,label in zip((inputs,outputs,minted,burned),("inputs","outputs","minted","burned")): _asset_map(mapping,label)
    strict_u64(fee_lovelace,"fee")
    if required_reserves is not None: _asset_map(required_reserves,"reserve")
    for bucket,label in ((change,"change"),(collateral,"collateral")):
        if bucket is not None:
            _asset_map(bucket,label)
            if any(asset!="lovelace" and quantity!=0 for asset,quantity in bucket.items()): raise OracleError("governed asset in change collateral")
    for key in set(inputs)|set(outputs)|set(minted)|set(burned):
        total=checked_sub(checked_add(inputs.get(key,0),minted.get(key,0),"value"),burned.get(key,0),"value")
        expected=checked_add(outputs.get(key,0),fee_lovelace if key=="lovelace" else 0,"value")
        if total!=expected: raise OracleError("value equation")
    if "lovelace" in minted or "lovelace" in burned: raise OracleError("ADA mint burn")
    for asset,amount in (required_reserves or {}).items():
        if outputs.get(asset,0)!=amount: raise OracleError("reserve destination")
    return True
def floor_sqrt(value): return math.isqrt(strict_u64(value,"sqrt input"))
def weight_for_lock(locked_vams): return floor_sqrt(locked_vams)
def majority_result(yes_weight,no_weight,quorum,total_weight):
    strict_u64(yes_weight,"yes weight"); strict_u64(no_weight,"no weight"); strict_u32(quorum,"quorum"); strict_u64(total_weight,"total weight")
    if quorum==0: raise OracleError("quorum positive")
    total=checked_add(yes_weight,no_weight,"vote weight")
    if total>total_weight: raise OracleError("vote overflow")
    if total<quorum: return "quorum_not_attained"
    if yes_weight==no_weight: return "tie"
    return "passed" if yes_weight>no_weight else "rejected"
def validate_lifecycle(queue_time,execute_after,lifetime,now):
    strict_u64(queue_time,"queue time"); strict_u64(execute_after,"execute after"); strict_u64(lifetime,"lifetime"); strict_u64(now,"now")
    if execute_after!=checked_add(queue_time,lifetime,"execute-after"): raise OracleError("execute-after derivation")
    if now<queue_time: return "before"
    if now==queue_time: return "at"
    if now<execute_after: return "between"
    if now==execute_after: return "at_execute"
    return "after"

@dataclass(frozen=True)
class LedgerSnapshot:
    network_id:int; fetched_at_ms:int; max_age_ms:int; min_fee_a:int; min_fee_b:int; max_tx_size:int; max_value_size:int; max_tx_ex_units:int; max_block_ex_units:int; cost_models_digest:str
_SNAPSHOT_KEYS=frozenset({"schema_version","network_id","fetched_at_ms","max_age_ms","min_fee_a","min_fee_b","max_tx_size","max_value_size","max_tx_ex_units","max_block_ex_units","cost_models_digest"})
def require_ledger_snapshot(snapshot,expected_network,now_ms):
    if type(snapshot) is not LedgerSnapshot: raise OracleError("snapshot required")
    _strict(snapshot.network_id,"snapshot network",15); _strict(expected_network,"expected network",15)
    for value,label in ((snapshot.fetched_at_ms,"fetched at"),(snapshot.max_age_ms,"max age"),(snapshot.min_fee_a,"min fee a"),(snapshot.min_fee_b,"min fee b"),(snapshot.max_tx_size,"max tx size"),(snapshot.max_value_size,"max value size"),(snapshot.max_tx_ex_units,"max tx ex units"),(snapshot.max_block_ex_units,"max block ex units"),(now_ms,"now")): strict_u64(value,label)
    if snapshot.network_id!=expected_network or snapshot.max_age_ms==0 or now_ms<snapshot.fetched_at_ms or now_ms-snapshot.fetched_at_ms>snapshot.max_age_ms: raise OracleError("snapshot stale or mismatched")
    _hex(snapshot.cost_models_digest,32,"cost models")
    return True
def _reject_duplicate_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise OracleError("duplicate snapshot key")
        result[key]=value
    return result
def parse_snapshot_mapping(payload,expected_network,now_ms):
    if type(payload) is not dict or set(payload)!=_SNAPSHOT_KEYS or payload.get("schema_version")!=SNAPSHOT_SCHEMA_VERSION: raise OracleError("snapshot schema")
    snap=LedgerSnapshot(payload["network_id"],payload["fetched_at_ms"],payload["max_age_ms"],payload["min_fee_a"],payload["min_fee_b"],payload["max_tx_size"],payload["max_value_size"],payload["max_tx_ex_units"],payload["max_block_ex_units"],payload["cost_models_digest"])
    require_ledger_snapshot(snap,expected_network,now_ms); return snap
def _cli_failure(): print(json.dumps({"error":"oracle validation failed","ok":False},sort_keys=True)); return 1
def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False); parser.add_argument("--snapshot-json"); parser.add_argument("--expected-network"); parser.add_argument("--now-ms")
    try:
        with contextlib.redirect_stderr(io.StringIO()): args,unknown=parser.parse_known_args(sys.argv[1:] if argv is None else argv)
        if unknown or args.snapshot_json is None or args.expected_network is None or args.now_ms is None: return _cli_failure()
        expected_network=int(args.expected_network); now_ms=int(args.now_ms)
        payload=json.loads(args.snapshot_json,object_pairs_hook=_reject_duplicate_pairs,parse_constant=lambda token: (_ for _ in ()).throw(OracleError("snapshot number")))
        parse_snapshot_mapping(payload,expected_network,now_ms); print(json.dumps({"ok":True},sort_keys=True)); return 0
    except Exception: return _cli_failure()

@dataclass(frozen=True)
class OutputRecord:
    address_hex:str; credential_kind:str; network_id:int; lovelace:int; assets:dict; datum_form:str; transition_role:str
_OUTPUT_KEYS=frozenset({"address_hex","credential_kind","network_id","lovelace","assets","datum_form","transition_role"})
def validate_output_record(record):
    values=record.__dict__ if type(record) is OutputRecord else record
    if type(values) is not dict or set(values)!=_OUTPUT_KEYS: raise OracleError("output record")
    address=_hex(values["address_hex"],29,"output address")
    if type(values["credential_kind"]) is not str or values["credential_kind"] not in ("key","script"): raise OracleError("output credential")
    network=strict_u8(values["network_id"],"output network")
    if address!=enterprise_address(network,values["credential_kind"],values["address_hex"][2:]): raise OracleError("output address")
    strict_u64(values["lovelace"],"output lovelace"); _asset_map(values["assets"],"output assets")
    if type(values["datum_form"]) is not str or values["datum_form"] not in ("inline","none"): raise OracleError("output datum")
    if type(values["transition_role"]) is not str or not values["transition_role"]: raise OracleError("output role")
    return OutputRecord(**values)
def _frozen_topology():
    try:
        raw=(Path(__file__).resolve().parents[3]/"docs/remediation/m3_2a_r7/TRANSITION_TOPOLOGY.json").read_bytes()
        if sha256(raw).hexdigest()!=TOPOLOGY_SHA256: raise OracleError("topology hash")
        doc=json.loads(raw.decode("utf-8"),object_pairs_hook=_json_pairs)
        if type(doc) is not dict or type(doc.get("transitions")) is not list: raise OracleError("topology registry")
        rows={}
        for row in doc["transitions"]:
            if type(row) is not dict or type(row.get("id")) is not str or row["id"] in rows: raise OracleError("topology registry")
            rows[row["id"]]=row
        return rows
    except OracleError: raise
    except (OSError,UnicodeError,ValueError,TypeError,json.JSONDecodeError) as exc: raise OracleError("topology registry") from exc

def _require_transition(transition):
    if type(transition) is not str or transition not in FROZEN_TRANSITIONS:
        raise OracleError("topology transition")
    return transition

def _derive_authority_successor(pre_state,successor,transition,expected_network):
    _require_transition(transition)
    _strict(expected_network,"expected network",15)
    if type(pre_state) is not dict or type(successor) is not dict:
        raise OracleError("authority pre-state")
    required={"address_hex","credential_kind","network_id","lovelace","assets","datum_form","transition_role","datum"}
    if set(pre_state)!=required or set(successor)!=required:
        raise OracleError("authority pre-state")
    vector=_authority_vector()
    pre_core={key:pre_state[key] for key in required if key!="datum"}
    if pre_core["credential_kind"]!="script" or pre_core["network_id"]!=expected_network:
        raise OracleError("authority pre-state")
    if pre_core["address_hex"]!=enterprise_address(expected_network,"script",_AUTHORITY_SCRIPT_HASH).hex():
        raise OracleError("authority address")
    if pre_core["assets"]!={"authority_nft":1} or pre_core["lovelace"]!=vector["value"]["authority_state_lovelace"] or pre_core["datum_form"]!="inline" or pre_core["transition_role"]!="authority_continuation":
        raise OracleError("authority pre-state")
    _pre_values,expected_pre_values=_validate_authority_state(pre_state,expected_network,vector)
    expected_values=dict(expected_pre_values)
    counter="next_proposal_nonce" if transition=="create" else "next_intent_nonce" if transition=="queue" else None
    if counter is not None:
        expected_values[counter]=checked_add(expected_values[counter],1,"authority counter")
    expected_datum=_authority_datum(expected_values,vector)
    expected_core={"address_hex":enterprise_address(expected_network,"script",_AUTHORITY_SCRIPT_HASH).hex(),
                   "credential_kind":"script","network_id":expected_network,
                   "lovelace":vector["value"]["authority_state_lovelace"],
                   "assets":{"authority_nft":1},"datum_form":"inline",
                   "transition_role":"authority_continuation"}
    expected={"address_hex":expected_core["address_hex"],"credential_kind":"script",
              "network_id":expected_network,"lovelace":expected_core["lovelace"],
              "assets":{"authority_nft":1},"datum_form":"inline",
              "transition_role":"authority_continuation","datum":expected_datum}
    if successor!=expected:
        raise OracleError("authority successor")
    return expected

def validate_reserve_outputs(outputs,voter_refunds,proposer_refund=None,authority_output=None,expected_network=1,pre_state=None,transition=None,topology=None):
    _strict(expected_network,"expected network",15)
    transition=_require_transition(transition)
    if topology is not None:
        raise OracleError("topology input")
    rows=_frozen_topology()
    row=rows.get(transition)
    if row is None:
        raise OracleError("topology transition")
    if type(outputs) is not list or len(outputs)>MAX_OUTPUTS or type(voter_refunds) is not list or len(voter_refunds)>MAX_VOTERS:
        raise OracleError("output collection")
    parsed=[validate_output_record(item) for item in outputs]
    roles=[item.transition_role for item in parsed]
    if len(set(roles))!=len(roles):
        raise OracleError("duplicate output role")
    expected_roles=set(); voters=[]
    for entry in voter_refunds:
        if type(entry) is not dict or set(entry)!={"voter_vkh","locked_vams","reserve_lovelace"}:
            raise OracleError("voter entitlement")
        vkh=_hex(entry["voter_vkh"],28,"voter").hex()
        locked=strict_u64(entry["locked_vams"],"locked vams")
        reserve=strict_u64(entry["reserve_lovelace"],"reserve")
        voters.append((vkh,locked,reserve)); expected_roles.add("voter_refund:"+vkh)
    proposer=None
    if proposer_refund is not None:
        if type(proposer_refund) is not dict or set(proposer_refund)!={"proposer_vkh","lovelace"}:
            raise OracleError("proposer entitlement")
        proposer=_hex(proposer_refund["proposer_vkh"],28,"proposer").hex()
        proposer_lovelace=strict_u64(proposer_refund["lovelace"],"proposer reserve")
        expected_roles.add("proposer_refund")
    else:
        proposer_lovelace=None
    expected_authority=None
    if authority_output is not None:
        if pre_state is None:
            raise OracleError("authority expectation")
        expected_successor=_derive_authority_successor(pre_state,authority_output,transition,expected_network)
        expected_authority=validate_output_record({key:expected_successor[key] for key in _OUTPUT_KEYS})
        expected_roles.add("authority_continuation")
    if set(roles)!=expected_roles:
        raise OracleError("output cardinality")
    allowed={row["outputs"]["without_change"],row["outputs"]["with_change"]}
    if len(parsed) not in allowed:
        raise OracleError("topology output count")
    by_role={item.transition_role:item for item in parsed}
    for vkh,locked,reserve in voters:
        item=by_role["voter_refund:"+vkh]
        if item.network_id!=expected_network or item.credential_kind!="key" or item.address_hex!=enterprise_address(expected_network,"key",vkh).hex() or item.lovelace!=reserve or item.assets!={"locked_vams":locked} or item.datum_form!="none":
            raise OracleError("voter reserve destination")
    if proposer is not None:
        item=by_role["proposer_refund"]
        if item.network_id!=expected_network or item.credential_kind!="key" or item.address_hex!=enterprise_address(expected_network,"key",proposer).hex() or item.lovelace!=proposer_lovelace or item.assets or item.datum_form!="none":
            raise OracleError("proposer reserve destination")
    if authority_output is not None:
        item=by_role["authority_continuation"]
        if item!=expected_authority or item.credential_kind!="script" or item.network_id!=expected_network:
            raise OracleError("authority destination")
    return True

@dataclass(frozen=True)
class InlineDatum:
    kind:str; constructor_index:int; fields:tuple; cbor_hex:str

_DATUM_FIELDS={
 "AuthorityDatumV1":("version","network_id","authority_state_lovelace","proposal_base_lovelace","per_voter_refund_lovelace","policy_epoch","authority_policy_id","governor_script_hash","timelock_script_hash","seed_tx_id","seed_index","members","threshold","normal_delay_ms","emergency_disabled","next_proposal_nonce","next_intent_nonce","max_lock_vams","caps","target_domains"),
 "ProposalDatumV1":("version","status","proposal_asset","nonce","proposer_vkh","description_hash","action_hash","target_domain","policy_epoch","quorum","deadline","yes_weight","no_weight","locks"),
 "VoteLockRecordV1":("voter_vkh","locked_vams","support","weight","receipt_name"),
 "IntentDatumV1":("version","proposal_id","proposal_asset","action_hash","payload_hash","target_domain","policy_epoch","nonce","queue_time","execute_after","lifetime","proposer_vkh","consumed")}

def _json_pairs(pairs):
    out={}
    for key,value in pairs:
        if key in out: raise OracleError("duplicate registry key")
        out[key]=value
    return out

def _frozen_datums():
    try:
        raw=_open_fixed_registry()
        if sha256(raw).hexdigest()!=DATUM_VECTOR_SHA256: raise OracleError("datum registry hash")
        doc=json.loads(raw.decode("utf-8"),object_pairs_hook=_json_pairs)
        if type(doc) is not dict or set(doc)!={"schema_version","max_datum_bytes","vectors"} or doc["schema_version"]!="m3.2a-r7-datum-vectors-v1" or doc["max_datum_bytes"]!=MAX_DATUM_BYTES or type(doc["vectors"]) is not list: raise OracleError("datum registry schema")
        result={}
        for vector in doc["vectors"]:
            if type(vector) is not dict or set(vector)!={"id","kind","accepted","record_count","value","cbor_hex","byte_length"}: raise OracleError("datum registry vector")
            ident=vector["id"]
            if type(ident) is not str or not ident or ident in result: raise OracleError("datum registry id")
            if type(vector["kind"]) is not str or vector["kind"] not in {"authority","proposal","record","intent"} or type(vector["accepted"]) is not bool: raise OracleError("datum registry vector")
            count=vector["record_count"]
            if count is not None and (type(count) is not int or type(count) is bool or count<0): raise OracleError("datum registry vector")
            if type(vector["cbor_hex"]) is not str or _HEX.fullmatch(vector["cbor_hex"]) is None or len(vector["cbor_hex"])%2 or type(vector["byte_length"]) is not int or type(vector["byte_length"]) is bool or vector["byte_length"]!=len(bytes.fromhex(vector["cbor_hex"])) or vector["byte_length"]>MAX_DATUM_BYTES: raise OracleError("datum registry encoding")
            result[ident]=vector
        return result
    except OracleError: raise
    except (OSError,UnicodeError,ValueError,TypeError,json.JSONDecodeError) as exc: raise OracleError("datum registry") from exc

def _datum_value(name,value):
    if name=="network_id": strict_u8(value,name)
    elif name in {"version","policy_epoch","seed_index","threshold","quorum","weight"}: strict_u32(value,name)
    elif name in {"authority_state_lovelace","proposal_base_lovelace","per_voter_refund_lovelace","next_proposal_nonce","next_intent_nonce","max_lock_vams","nonce","deadline","yes_weight","no_weight","locked_vams","queue_time","execute_after","lifetime","normal_delay_ms"}: strict_u64(value,name)
    elif name in {"authority_policy_id","governor_script_hash","timelock_script_hash","proposer_vkh","voter_vkh"}: _hex(value,28,name)
    elif name in {"seed_tx_id","proposal_asset","description_hash","action_hash","payload_hash","receipt_name","proposal_id"}: _hex(value,32,name)
    elif name in {"support","emergency_disabled","consumed"}:
        if type(value) is not bool: raise OracleError(name+" boolean")
    elif name=="target_domain":
        if type(value) is not str or value not in TARGET_PAYLOAD_ALLOWLIST or _HEX.fullmatch(value) is None: raise OracleError("target domain encoding")
    elif name=="status":
        if type(value) is not str or value not in {"pending","passed","rejected","queued","cancelled","expired"}: raise OracleError("status")
    elif name=="members":
        if type(value) is not list or len(value)!=MAX_MEMBERS: raise OracleError("members")
        for item in value: _hex(item,28,"member")
    elif name=="caps":
        if type(value) is not list or len(value)!=5: raise OracleError("caps")
        for item in value: strict_u32(item,"cap")
    elif name=="target_domains":
        if type(value) is not list or len(value)==0 or len(value)>32: raise OracleError("target domains")
        for item in value:
            if type(item) is not str or item not in TARGET_PAYLOAD_ALLOWLIST: raise OracleError("target domain encoding")
    elif name=="locks":
        if type(value) is not list or len(value)>MAX_VOTERS: raise OracleError("locks")
        for item in value:
            if type(item) is not dict or set(item)!={"voter_vkh","locked_vams","support","weight","receipt_name"}: raise OracleError("lock")
            for key,val in item.items(): _datum_value(key,val)
    else: raise OracleError("datum field")

def _cbor_read(data,pos=0):
    if pos>=len(data): raise OracleError("datum cbor")
    initial=data[pos]; pos+=1; major=initial>>5; ai=initial&31
    if ai<24: arg=ai
    elif ai==24:
        if pos+1>len(data): raise OracleError("datum cbor")
        arg=data[pos]; pos+=1
        if arg<24: raise OracleError("datum noncanonical")
    elif ai==25:
        if pos+2>len(data): raise OracleError("datum cbor")
        arg=int.from_bytes(data[pos:pos+2],"big"); pos+=2
        if arg<256: raise OracleError("datum noncanonical")
    elif ai==26:
        if pos+4>len(data): raise OracleError("datum cbor")
        arg=int.from_bytes(data[pos:pos+4],"big"); pos+=4
        if arg<65536: raise OracleError("datum noncanonical")
    elif ai==27:
        if pos+8>len(data): raise OracleError("datum cbor")
        arg=int.from_bytes(data[pos:pos+8],"big"); pos+=8
        if arg<1<<32: raise OracleError("datum noncanonical")
    else: raise OracleError("datum indefinite")
    if major==0: return ("uint",arg),pos
    if major==1: return ("nint",-1-arg),pos
    if major in (2,3):
        if pos+arg>len(data): raise OracleError("datum cbor")
        raw=data[pos:pos+arg]; pos+=arg
        if major==2: return ("bytes",raw),pos
        try: return ("text",raw.decode("utf-8")),pos
        except UnicodeDecodeError as exc: raise OracleError("datum text") from exc
    if major==4:
        items=[]
        for _ in range(arg):
            item,pos=_cbor_read(data,pos); items.append(item)
        return ("array",tuple(items)),pos
    if major==5:
        items=[]
        for _ in range(arg):
            key,pos=_cbor_read(data,pos); value,pos=_cbor_read(data,pos); items.append((key,value))
        if len({repr(k) for k,_ in items})!=len(items): raise OracleError("datum map")
        return ("map",tuple(items)),pos
    if major==6:
        value,pos=_cbor_read(data,pos); return ("tag",arg,value),pos
    if major==7 and ai==20: return ("bool",False),pos
    if major==7 and ai==21: return ("bool",True),pos
    raise OracleError("datum type")

def _cbor_encode(node):
    kind=node[0]
    if kind=="uint": n=node[1]; head=0
    elif kind=="nint": n=-1-node[1]; head=32
    elif kind=="bytes":
        raw=node[1]
        if len(raw)<24: return bytes([len(raw)])+raw
        return _cbor_head(2,len(raw))+raw
    elif kind=="text": raw=node[1].encode(); return _cbor_head(3,len(raw))+raw
    elif kind=="array": return _cbor_head(4,len(node[1]))+b"".join(_cbor_encode(x) for x in node[1])
    elif kind=="map": return _cbor_head(5,len(node[1]))+b"".join(_cbor_encode(k)+_cbor_encode(v) for k,v in node[1])
    elif kind=="tag": return _cbor_head(6,node[1])+_cbor_encode(node[2])
    elif kind=="bool": return bytes([0xd8,0x7a if node[1] else 0x79,0x80])
    else: raise OracleError("datum type")
    return _cbor_head(head,n)

def _cbor_head(major,n):
    if n<24: return bytes([(major<<5)|n])
    if n<256: return bytes([(major<<5)|24,n])
    if n<65536: return bytes([(major<<5)|25])+n.to_bytes(2,"big")
    if n<1<<32: return bytes([(major<<5)|26])+n.to_bytes(4,"big")
    return bytes([(major<<5)|27])+n.to_bytes(8,"big")

def _typed_uint(data,pos):
    node,end=_cbor_read(data,pos)
    if node[0]!="uint":
        raise OracleError("datum integer")
    return node,end

def _typed_bytes(data,pos):
    if pos>=len(data):
        raise OracleError("datum bytes")
    first=data[pos]
    if first<24:
        length=first; pos+=1
    elif first==0x58:
        if pos+2>len(data): raise OracleError("datum bytes")
        length=data[pos+1]; pos+=2
        if length<24: raise OracleError("datum noncanonical")
    elif first==0x59:
        if pos+3>len(data): raise OracleError("datum bytes")
        length=int.from_bytes(data[pos+1:pos+3],"big"); pos+=3
        if length<256: raise OracleError("datum noncanonical")
    else:
        raise OracleError("datum bytes")
    if length>MAX_DATUM_BYTES or pos+length>len(data):
        raise OracleError("datum bytes")
    return ("bytes",data[pos:pos+length]),pos+length

def _typed_array(data,pos,item_reader):
    if pos>=len(data) or data[pos]>>5!=4:
        raise OracleError("datum array")
    count=data[pos]&31
    if count>=24: raise OracleError("datum array")
    pos+=1; items=[]
    for _ in range(count):
        item,pos=item_reader(data,pos); items.append(item)
    return ("array",tuple(items)),pos

def _typed_bool(data,pos):
    if pos+3>len(data) or data[pos]!=0xd8 or data[pos+1] not in (0x79,0x7a) or data[pos+2]!=0x80:
        raise OracleError("datum boolean")
    return ("bool",data[pos+1]==0x7a),pos+3

def _typed_constructor(data,pos,alt=0):
    if pos+2>len(data) or data[pos]!=0xd8 or data[pos+1]!=0x79+alt:
        raise OracleError("datum constructor")
    pos+=2
    node,pos=_typed_array(data,pos,lambda raw,index:_typed_value(raw,index))
    if len(node[1])!=0: raise OracleError("datum constructor")
    return ("tag",121+alt,("array",tuple())),pos

def _typed_value(data,pos):
    return _cbor_read(data,pos)

def _typed_record(data,pos):
    if pos+2>len(data) or data[pos]!=0xd8 or data[pos+1]!=0x79: raise OracleError("datum constructor")
    pos+=2
    if pos>=len(data) or data[pos]>>5!=4 or data[pos]&31!=5: raise OracleError("datum record")
    pos+=1; items=[]
    for reader in (_typed_bytes,_typed_uint,_typed_bool,_typed_uint,_typed_bytes):
        item,pos=reader(data,pos); items.append(item)
    return ("tag",121,("array",tuple(items))),pos

def _typed_datum(data,kind):
    if len(data)>MAX_DATUM_BYTES: raise OracleError("datum encoding")
    if len(data)<3 or data[0]!=0xd8 or data[1]!=0x79: raise OracleError("datum constructor")
    pos=2
    if pos>=len(data) or data[pos]>>5!=4: raise OracleError("datum array")
    count=data[pos]&31
    if count>=24: raise OracleError("datum array")
    pos+=1; readers={
      "AuthorityDatumV1":(_typed_uint,_typed_uint,_typed_uint,_typed_uint,_typed_uint,_typed_uint,_typed_bytes,_typed_bytes,_typed_bytes,_typed_bytes,_typed_uint,
                         lambda d,p:_typed_array(d,p,_typed_bytes),_typed_uint,_typed_uint,_typed_bool,_typed_uint,_typed_uint,_typed_uint,
                         lambda d,p:_typed_array(d,p,_typed_uint),lambda d,p:_typed_array(d,p,_typed_bytes)),
      "ProposalDatumV1":(_typed_uint,lambda d,p:_typed_constructor(d,p,0),_typed_bytes,_typed_uint,_typed_bytes,_typed_bytes,_typed_bytes,_typed_bytes,_typed_uint,_typed_uint,_typed_uint,_typed_uint,_typed_uint,
                         lambda d,p:_typed_array(d,p,_typed_record)),
      "VoteLockRecordV1":(_typed_bytes,_typed_uint,lambda d,p:_typed_constructor(d,p,1),_typed_uint,_typed_bytes),
      "IntentDatumV1":(_typed_uint,_typed_bytes,_typed_bytes,_typed_bytes,_typed_bytes,_typed_bytes,_typed_uint,_typed_uint,_typed_uint,_typed_uint,_typed_uint,_typed_bytes,_typed_bool),
    }
    expected=readers.get(kind)
    if expected is None or count!=len(expected): raise OracleError("datum fields")
    items=[]
    for reader in expected:
        item,pos=reader(data,pos); items.append(item)
    if pos!=len(data): raise OracleError("datum canonical")
    return ("tag",121,("array",tuple(items))),pos

def _parse_inline_fields(datum,expected_kind):
    if type(datum) is not dict or set(datum)!={"kind","constructor_index","fields","cbor_hex"}:
        raise OracleError("datum record")
    if datum["kind"]!=expected_kind or strict_u32(datum["constructor_index"],"constructor")!=0:
        raise OracleError("datum constructor")
    fields=datum["fields"]
    if type(fields) is not list or len(fields)!=len(_DATUM_FIELDS[expected_kind]):
        raise OracleError("datum fields")
    values={}
    for pair,expected in zip(fields,_DATUM_FIELDS[expected_kind]):
        if type(pair) not in (list,tuple) or len(pair)!=2 or pair[0]!=expected or pair[0] in values:
            raise OracleError("datum order")
        values[pair[0]]=pair[1]
        _datum_value(pair[0],pair[1])
    cbor=datum["cbor_hex"]
    if type(cbor) is not str or len(cbor)%2 or _HEX.fullmatch(cbor) is None:
        raise OracleError("datum encoding")
    encoded=bytes.fromhex(cbor)
    if not encoded or len(encoded)>MAX_DATUM_BYTES:
        raise OracleError("datum encoding")
    node,end=_typed_datum(encoded,expected_kind)
    if end!=len(encoded):
        raise OracleError("datum canonical")
    canonical=_cbor_encode(node)
    if encoded!=canonical:
        raise OracleError("datum canonical")
    return values,encoded,node

def validate_inline_datum(datum,vector_id=None):
    if type(vector_id) is not str or not vector_id:
        raise OracleError("datum vector id")
    registry=_frozen_datums()
    vector=registry.get(vector_id)
    if vector is None or not vector["accepted"]:
        raise OracleError("datum vector")
    expected_kind={"authority":"AuthorityDatumV1","proposal":"ProposalDatumV1","record":"VoteLockRecordV1","intent":"IntentDatumV1"}[vector["kind"]]
    values,encoded,node=_parse_inline_fields(datum,expected_kind)
    if values!=vector["value"]:
        raise OracleError("datum value")
    frozen=bytes.fromhex(vector["cbor_hex"])
    if encoded!=frozen or len(encoded)!=vector["byte_length"] or len(encoded)!=len(frozen) or not encoded.startswith(b"\xd8\x79"):
        raise OracleError("datum encoding")
    canonical=_cbor_encode(node)
    if len(encoded)!=len(canonical) or len(canonical)!=len(frozen) or canonical!=frozen:
        raise OracleError("datum canonical")
    return True

def _authority_vector():
    vector=next((item for item in _frozen_datums().values() if item["kind"]=="authority" and item["accepted"]),None)
    if vector is None:
        raise OracleError("authority vector")
    return vector

def _authority_node(field,value):
    if field in {"version","network_id","authority_state_lovelace","proposal_base_lovelace","per_voter_refund_lovelace","policy_epoch","seed_index","threshold","normal_delay_ms","next_proposal_nonce","next_intent_nonce","max_lock_vams"}:
        return ("uint",value)
    if field in {"authority_policy_id","governor_script_hash","timelock_script_hash","seed_tx_id"}:
        return ("bytes",bytes.fromhex(value))
    if field=="members":
        return ("array",tuple(("bytes",bytes.fromhex(item)) for item in value))
    if field=="caps":
        return ("array",tuple(("uint",item) for item in value))
    if field=="target_domains":
        return ("array",tuple(("bytes",bytes.fromhex(item)) for item in value))
    if field=="emergency_disabled":
        return ("bool",value)
    raise OracleError("authority datum field")

def _authority_datum(values,vector):
    base,end=_typed_datum(bytes.fromhex(vector["cbor_hex"]),"AuthorityDatumV1")
    if end!=len(bytes.fromhex(vector["cbor_hex"])) or base[0]!="tag" or base[1]!=121 or base[2][0]!="array":
        raise OracleError("authority datum encoding")
    items=list(base[2][1])
    names=_DATUM_FIELDS["AuthorityDatumV1"]
    if len(items)!=len(names):
        raise OracleError("authority datum fields")
    for index,name in enumerate(names):
        items[index]=_authority_node(name,values[name])
    encoded=_cbor_encode(("tag",121,("array",tuple(items))))
    return {"kind":"AuthorityDatumV1","constructor_index":0,
            "fields":[[name,values[name]] for name in names],
            "cbor_hex":encoded.hex()}

def _validate_authority_state(pre_state,expected_network,vector):
    datum=pre_state["datum"]
    values,encoded,_node=_parse_inline_fields(datum,"AuthorityDatumV1")
    if values["network_id"]!=expected_network:
        raise OracleError("authority network")
    for name,expected in vector["value"].items():
        if name=="network_id":
            continue
        if name in {"next_proposal_nonce","next_intent_nonce"}:
            strict_u64(values[name],"authority counter")
        elif values[name]!=expected:
            raise OracleError("authority immutable field")
    expected_values=dict(vector["value"])
    expected_values["network_id"]=expected_network
    expected_values["next_proposal_nonce"]=values["next_proposal_nonce"]
    expected_values["next_intent_nonce"]=values["next_intent_nonce"]
    expected_datum=_authority_datum(expected_values,vector)
    if datum!=expected_datum:
        raise OracleError("authority datum binding")
    return values,expected_values

def check_datum_size(cbor_hex,declared_size,accepted):
    if type(cbor_hex) is not str or len(cbor_hex)%2 or _HEX.fullmatch(cbor_hex) is None: raise OracleError("datum encoding")
    strict_u32(declared_size,"datum size")
    if type(accepted) is not bool: raise OracleError("datum accepted")
    if len(bytes.fromhex(cbor_hex))!=declared_size: raise OracleError("datum declaration")
    if accepted and declared_size>MAX_DATUM_BYTES: raise OracleError("datum cap")
    return declared_size

if __name__ == "__main__":
    raise SystemExit(main())
