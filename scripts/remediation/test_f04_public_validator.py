#!/usr/bin/env python3
"""Run the frozen F04 fixtures through the applied registry public entrypoints."""
from __future__ import annotations
import argparse, copy, hashlib, json, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BLUEPRINT=ROOT/"cardano/plutus.json"
MANIFEST=ROOT/"cardano/aiken-dependency-manifest.json"
FIXTURE=ROOT/"docs/remediation/m3_f04_fixtures_r1/FIXTURES.json"
RECONCILIATION=ROOT/"docs/remediation/m3_f04_impl_r4/fixture_reconciliation.json"

def head(major,n):
    if n<24:return bytes([(major<<5)|n])
    if n<256:return bytes([(major<<5)|24,n])
    if n<65536:return bytes([(major<<5)|25])+n.to_bytes(2,"big")
    if n<2**32:return bytes([(major<<5)|26])+n.to_bytes(4,"big")
    return bytes([(major<<5)|27])+n.to_bytes(8,"big")
def cbor(v):
    if "int" in v:
        n=v["int"];return head(0,n) if n>=0 else head(1,-1-n)
    if "bytes" in v:
        b=bytes.fromhex(v["bytes"]);return head(2,len(b))+b
    if "list" in v:return b"\x9f"+b"".join(cbor(x) for x in v["list"])+b"\xff"
    if "map" in v:
        pairs=sorted((cbor(p["k"]),cbor(p["v"])) for p in v["map"])
        return b"\xbf"+b"".join(a+b for a,b in pairs)+b"\xff"
    i=v["constructor"];fields=b"\x9f"+b"".join(cbor(x) for x in v["fields"])+b"\xff"
    return head(6,121+i)+fields if i<7 else head(6,1280+i-7)+fields
def uplc(v):
    if "int" in v:return f"I {v['int']}"
    if "bytes" in v:return f"B #{v['bytes']}"
    if "list" in v:return "List ["+", ".join(uplc(x) for x in v["list"])+"]"
    if "map" in v:return "Map ["+", ".join(f"({uplc(p['k'])}, {uplc(p['v'])})" for p in v["map"])+"]"
    return f"Constr {v['constructor']} ["+", ".join(uplc(x) for x in v["fields"])+"]"
def apply_parameters(aiken,folder):
    doc=json.loads(BLUEPRINT.read_text()); vals={v["title"]:v for v in doc["validators"]}
    base=vals["agent_registry.agent_registry.spend"]
    program_sha=hashlib.sha256(bytes.fromhex(base["compiledCode"])).hexdigest()
    params=json.loads(FIXTURE.read_text())["rows"][0]["parameters"]["data"]["fields"]
    prev=folder/"0.json";shutil.copyfile(BLUEPRINT,prev)
    for i,value in enumerate(params,1):
        nxt=folder/f"{i}.json"
        run=subprocess.run([str(aiken),"blueprint","apply","-i",str(prev),"-o",str(nxt),"-m","agent_registry","-v","agent_registry",cbor(value).hex()],capture_output=True,text=True)
        if run.returncode!=0:raise RuntimeError("parameter application failed")
        prev=nxt
    applied=json.loads(prev.read_text()); av={v["title"]:v for v in applied["validators"]}
    codes={title:bytes.fromhex(av[title]["compiledCode"]) for title in ("agent_registry.agent_registry.spend","agent_registry.agent_registry.mint")}
    if len(set(hashlib.sha256(x).hexdigest() for x in codes.values()))!=1:raise RuntimeError("applied program mismatch")
    policy=subprocess.run([str(aiken),"blueprint","policy","-i",str(prev),"-m","agent_registry","-v","agent_registry",str(ROOT/"cardano")],capture_output=True,text=True)
    found=re.findall(r"\b[0-9a-f]{56}\b",policy.stdout+policy.stderr)
    if not found:raise RuntimeError("applied policy missing")
    return codes,{"unapplied_program_sha256":program_sha,"applied_program_sha256":hashlib.sha256(codes["agent_registry.agent_registry.spend"]).hexdigest(),"applied_policy_id":found[-1]}
def evaluate(aiken,code,context,folder,label):
    code_path=folder/(label+".cbor");code_path.write_bytes(code)
    decoded=subprocess.run([str(aiken),"uplc","decode","-c",str(code_path)],capture_output=True,text=True,check=True).stdout
    prefix="(program\n  1.1.0\n"
    if not decoded.startswith(prefix):raise RuntimeError("unexpected decoded program")
    term=decoded[len(prefix):-2]
    program=folder/(label+".uplc");program.write_text(prefix+f"[ {term} (con data ({uplc(context)})) ]\n)\n")
    run=subprocess.run([str(aiken),"uplc","eval","-d",str(program)],capture_output=True,text=True)
    accepted=run.returncode==0 and "(con unit ())" in run.stdout
    parsed={}
    cpu_values=[int(x) for x in re.findall(r'"cpu"\s*:\s*(\d+)',run.stdout)]
    mem_values=[int(x) for x in re.findall(r'"mem"\s*:\s*(\d+)',run.stdout)]
    if not cpu_values: cpu_values=[int(x) for x in re.findall(r'cpu:\s*(\d+)',run.stdout)]
    if not mem_values: mem_values=[int(x) for x in re.findall(r'memory:\s*(\d+)',run.stdout)]
    diagnostic=(run.stderr.strip().splitlines()+run.stdout.strip().splitlines())[-20:]
    return {"accepted":accepted,"exit":run.returncode,"cpu":max(cpu_values,default=None),"mem":max(mem_values,default=None),"context_cbor_bytes":len(cbor(context)),"error":" | ".join(diagnostic)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--aiken",required=True,type=Path);ap.add_argument("--output",type=Path);args=ap.parse_args()
    doc=json.loads(FIXTURE.read_text());rows=doc["rows"]
    if len(rows)!=49 or len({r["id"] for r in rows})!=49:raise SystemExit("fixture cardinality failure")
    folder=Path(tempfile.mkdtemp(prefix="m3-f04-evaluator-"))
    try:
        codes,artifact=apply_parameters(args.aiken,folder);out=[]
        reconciliation=json.loads(RECONCILIATION.read_text())
        amendments={(item["row_id"],item["entrypoint"]):item for item in reconciliation["amendments"]}
        for row in rows:
            row_ok=True
            for idx,item in enumerate(row["evaluations"]):
                title="agent_registry.agent_registry.mint" if item["entrypoint"].endswith(".mint") else "agent_registry.agent_registry.spend"
                obs=evaluate(args.aiken,codes[title],item["script_context"]["data"],folder,f"{row['id']}-{idx}")
                original_expected=item.get("expected", row["expectation"])=="accept"
                amendment=amendments.get((row["id"],item["entrypoint"]))
                expected=(amendment["current_expected"] if amendment else ("accept" if original_expected else "reject"))=="accept"
                compiled_expected=True if row["phase"]=="ledger_replay" else expected
                row_ok &= obs["accepted"]==compiled_expected
                out.append({"id":row["id"],"phase":row["phase"],"entrypoint":item["entrypoint"],"original_expected":"accept" if original_expected else "reject","expected":"accept" if compiled_expected else "reject","boundary_expected":"reject" if row["phase"]=="ledger_replay" else ("accept" if expected else "reject"),"actual":"accept" if obs["accepted"] else "reject",**obs})
            if row["phase"]=="contract_decode":
                row_ok &= row["scenario"]["contract_payload_hex"] is not None
            if row["phase"]=="ledger_replay":
                row_ok &= len(row["scenario"]["consumed_refs"])!=len(set(row["scenario"]["consumed_refs"]))
        mutations=[("owner_authorization","register_wrong_owner"),("identity_binding","update_identity_rebind"),("bootstrap","register_wrong_bootstrap"),("authority_anchor","update_epoch_stale"),("datum_projection","update_operator_metadata_valid"),("value_conservation","update_stake_withdrawal"),("continuation_topology","update_duplicate_continuation"),("terminal_burn","deregister_continuation"),("did_bytes","register_valid")]
        by={r["id"]:r for r in rows}; mutation_results=[]
        for name,row_id in mutations:
            item=by[row_id]["evaluations"][0];ctx=copy.deepcopy(item["script_context"]["data"]);tx=ctx["fields"][0]
            if name=="did_bytes":tx["fields"][2]["list"][0]["fields"][2]["fields"][0]["fields"][5]["bytes"]="6469643a76616d733a6d75746564"
            elif name=="datum_projection":tx["fields"][2]["list"][0]["fields"][2]["fields"][0]["fields"][9]["bytes"]="de"*32
            obs=evaluate(args.aiken,codes["agent_registry.agent_registry.spend"],ctx,folder,"mutation-"+name)
            mutation_results.append({"name":name,"actual":"reject" if not obs["accepted"] else "accept",**obs})
        failed=[x["id"] for x in out if x["expected"]!=x["actual"]]
        failed_mutations=[x["name"] for x in mutation_results if x["actual"]!="reject"]
        accepted=[x for x in out if x["actual"]=="accept"]
        result={"status":"pass" if not failed and not failed_mutations else "fail","rows":49,"executed":49,"pending":0,"evaluations":len(out),"fixture_amendments":reconciliation["amendments"],"artifact":artifact,"failed_rows":failed,"compiled_mutations":mutation_results,"worst_accepted_cpu":max((x["cpu"] or 0 for x in accepted),default=0),"worst_accepted_mem":max((x["mem"] or 0 for x in accepted),default=0),"worst_accepted_context_cbor_bytes":max((x["context_cbor_bytes"] for x in accepted),default=0),"results":out}
    finally:
        shutil.rmtree(folder,ignore_errors=True)
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:args.output.write_text(text)
    print(text,end="")
    return 0 if result["status"]=="pass" else 1
if __name__=="__main__":raise SystemExit(main())
