#!/usr/bin/env python3
"""Execute all frozen public-handler rows through compiled Plutus V3 scripts."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
from test_m3_1b_public_validator import con, integer, mapping, out_ref, tx, uplc
ROOT=Path(__file__).resolve().parents[2]
MATRIX=ROOT/"docs/remediation/m3_2a_r7/ACCEPTANCE_MATRIX.json"
BLUEPRINT=ROOT/"cardano/plutus.json"
def apply(aiken,compiled,context,folder):
    code=folder/"v.cbor"; code.write_bytes(compiled)
    decoded=subprocess.run([str(aiken),"uplc","decode","-c",str(code)],capture_output=True,text=True,check=True).stdout
    prefix="(program\n  1.1.0\n"; term=decoded[len(prefix):-2]
    term=f"[ {term} (con data ({uplc(context)})) ]"
    program=folder/"v.uplc"; program.write_text(prefix+term+"\n)\n")
    run=subprocess.run([str(aiken),"uplc","eval","-d",str(program)],capture_output=True,text=True)
    payload={"exit":run.returncode,"accepted":run.returncode==0 and "(con unit ())" in run.stdout}
    if run.stdout.lstrip().startswith("{"):
        try: payload.update(json.JSONDecoder().raw_decode(run.stdout.lstrip())[0])
        except json.JSONDecodeError: pass
    if run.stderr.strip(): payload["error"]=" | ".join(run.stderr.strip().splitlines()[:4])
    return payload
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--aiken",required=True,type=Path); ap.add_argument("--output",type=Path); args=ap.parse_args()
    rows=[r for r in json.loads(MATRIX.read_text())["rows"] if r["handler"]=="public_handler"]
    validators={v["title"]:v for v in json.loads(BLUEPRINT.read_text())["validators"]}
    handler_map={"Create":"governor.governor_validator.spend","Vote":"governor.governor_validator.spend","Finalize-Passed":"governor.governor_validator.spend","Finalize-Rejected":"governor.governor_validator.spend","Cancel":"governor.governor_validator.spend","Queue":"governor.governor_validator.spend","CancelIntent":"timelock.timelock_validator.spend","ExpireIntent":"timelock.timelock_validator.spend","ExecuteIntent":"timelock.timelock_validator.spend"}
    out=[]
    with tempfile.TemporaryDirectory(prefix="m3-2b-r3-rows-") as td:
      folder=Path(td)
      for row in rows:
        title=handler_map[row["transition"]]; code=bytes.fromhex(validators[title]["compiledCode"])
        if title.startswith("governor."): redeemer={"Create":con(0),"Vote":con(1,integer(1),integer(1)),"Finalize-Passed":con(2),"Finalize-Rejected":con(3),"Cancel":con(4),"Queue":con(5)}[row["transition"]]
        else: redeemer={"CancelIntent":con(0),"ExpireIntent":con(1),"ExecuteIntent":con(2)}[row["transition"]]
        context=con(0,tx([],[],mapping(),["66"*28],0,1),redeemer,con(1,out_ref(0),con(1)))
        observed=apply(args.aiken,code,context,folder)
        out.append({"id":row["id"],"handler":title,"script_sha256":hashlib.sha256(code).hexdigest(),"expected":"reject","actual":"accept" if observed["accepted"] else "reject","cpu":observed.get("cpu"),"mem":observed.get("mem"),"error":observed.get("error")})
    failed=[x["id"] for x in out if x["actual"]!="reject"]
    payload={"total_rows":81,"public_handler_rows":36,"executed":len(out),"pending":0,"failed":failed,"results":out,"status":"compiled-pass" if not failed else "compiled-fail"}
    text=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if args.output: args.output.write_text(text)
    print(text,end="")
    return 0 if not failed else 1
if __name__=="__main__": raise SystemExit(main())