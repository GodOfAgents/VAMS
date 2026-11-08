#!/usr/bin/env python3
import argparse, copy, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path

def enc(v):
    return (json.dumps(v, indent=2, sort_keys=True) + "\n").encode()

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rebuild(root):
    core=["decisions.json","excluded-gitlinks.json","findings.json","ledger.json","owned-blobs.json","reachability.json","record.json","source-manifest.json","summary.json"]
    (root/"source-checksums.sha256").write_text("".join(f"{digest(root/n)}  {n}\n" for n in sorted(core)))
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (root / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.relative_to(root).as_posix()}\n" for p in files))

def verify_layers(root):
    core={"decisions.json","excluded-gitlinks.json","findings.json","ledger.json",
          "owned-blobs.json","reachability.json","record.json",
          "source-manifest.json","summary.json"}
    inner={}
    for line in (root/"source-checksums.sha256").read_text().splitlines():
        value,name=line.split("  ")
        if name in inner or digest(root/name)!=value:
            return False
        inner[name]=value
    if set(inner)!=core:
        return False
    outer={}
    for line in (root/"SHA256SUMS").read_text().splitlines():
        value,name=line.split("  ")
        if name in outer or digest(root/name)!=value:
            return False
        outer[name]=value
    actual={x.relative_to(root).as_posix() for x in root.rglob("*")
            if x.is_file() and x.name!="SHA256SUMS"}
    return set(outer)==actual

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--evidence", required=True)
    ap.add_argument("--python", required=True); ap.add_argument("--validator", required=True)
    a=ap.parse_args(); repo=Path(a.repo); evidence=Path(a.evidence)
    results=[]
    def run_case(name, expected_accept, mutate):
        with tempfile.TemporaryDirectory(prefix="m03c-r4-validator-") as td:
            root=Path(td)/"evidence"; shutil.copytree(evidence,root)
            environment=json.loads((root/"environment.json").read_text())
            environment["evidence_output"]=str(root)
            (root/"environment.json").write_bytes(enc(environment))
            mutate(root); rebuild(root)
            checksums_passed=verify_layers(root)
            p=subprocess.run([a.python,a.validator,"--repo",str(repo),"--evidence",str(root)],cwd=repo,
                env=os.environ|{"PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":str(repo/"scripts/security")},
                capture_output=True,text=True)
            accepted=p.returncode==0
            try: response=json.loads(p.stdout)
            except json.JSONDecodeError: response={}
            code=response.get("code")
            schema_reason=(accepted and expected_accept) or (
                not expected_accept and isinstance(code,str)
                and 1 <= len(code) <= 128
            )
            unsafe_echo=any(token in p.stdout or token in p.stderr for token in ("R4_PROBE_MARKER","apiSecretMaterial","private.key","credential material"))
            results.append({"name":name,"expected_accept":expected_accept,"accepted":accepted,
                            "expectation_met":accepted==expected_accept and checksums_passed and schema_reason,
                            "checksums_passed":checksums_passed,"schema_code":code,
                            "unsafe_echo":unsafe_echo,"exit":p.returncode,
                            "stdout_sha256":hashlib.sha256(p.stdout.encode()).hexdigest(),
                            "stderr_sha256":hashlib.sha256(p.stderr.encode()).hexdigest()})
    def noop(root): pass
    run_case("baseline_current_artifacts",True,noop)
    def raw_true(root):
        p=root/"record.json"; v=json.loads(p.read_text()); v["raw_removed"]=True; p.write_bytes(enc(v))
    run_case("required_raw_removed_true",True,raw_true)
    variants=["apiSecretMaterial","api_secret_material","api-secret-material","api secret material","api.secret.material","Api_SeCrEt-Material",
              "secretValue","raw_match","private.key","credential material","tokenDigest","fingerprintMetadata"]
    for variant in variants:
        def mut(root,key=variant):
            p=root/"record.json"; v=json.loads(p.read_text()); v["independent_probe"]={"level1":[{"level2":{key:"R4_PROBE_MARKER"}}]}; p.write_bytes(enc(v))
        run_case("sensitive_variant_"+str(variants.index(variant)),False,mut)
    root_artifacts=["findings.json","decisions.json","ledger.json","summary.json","record.json","reachability.json","owned-blobs.json","excluded-gitlinks.json","environment.json","changed-files.json","reviewed-hashes.json"]
    for name in root_artifacts:
        def mut(root,n=name):
            p=root/n; v=json.loads(p.read_text()); v["unexpected"]="R4_PROBE_MARKER"; p.write_bytes(enc(v))
        run_case("unknown_root_"+name,False,mut)
    def unknown_record(root):
        for n in ("findings.json","decisions.json","ledger.json"):
            p=root/n; v=json.loads(p.read_text()); v["records"][0]["unexpected"]="R4_PROBE_MARKER"; p.write_bytes(enc(v))
    run_case("unknown_record_field",False,unknown_record)
    def unknown_command(root):
        p=root/"commands.json"; v=json.loads(p.read_text()); v[0]["unexpected"]="R4_PROBE_MARKER"; p.write_bytes(enc(v))
    run_case("unknown_command_field",False,unknown_command)
    def unknown_command_result(root):
        p=root/"commands.json"; v=json.loads(p.read_text())
        for item in v:
            if isinstance(item.get("result"),dict):
                item["result"]["unexpected"]="R4_PROBE_MARKER"; break
        p.write_bytes(enc(v))
    run_case("unknown_command_result_field",False,unknown_command_result)
    def duplicate(root):
        p=root/"record.json"; text=p.read_text(); p.write_text(text.replace("{\n",'{\n  "schema": "m0_3c_r1_run",\n',1))
    run_case("duplicate_json_key",False,duplicate)
    for length,expected in ((239,True),(240,True),(241,False)):
        def mut(root,n=length):
            p=root/"commands.json"; v=json.loads(p.read_text()); v[0]["command"][0]="a"*n; p.write_bytes(enc(v))
        run_case("command_string_length_"+str(length),expected,mut)
    def huge_list(root):
        p=root/"environment.json"; v=json.loads(p.read_text()); v["dirty_status"]=["safe"]*2049; p.write_bytes(enc(v))
    run_case("excessive_list",False,huge_list)
    def huge_map(root):
        p=root/"reviewed-hashes.json"; v=json.loads(p.read_text()); v["files"]={f"safe{i}":"0"*64 for i in range(2049)}; p.write_bytes(enc(v))
    run_case("excessive_map",False,huge_map)
    def deep(root):
        x="leaf"
        for i in range(12): x={f"level{i}":x}
        p=root/"record.json"; v=json.loads(p.read_text()); v["independent_probe"]=x; p.write_bytes(enc(v))
    run_case("excessive_depth",False,deep)
    def huge_serialized(root):
        p=root/"record.json"; p.write_text(p.read_text()+" "*(1048577-p.stat().st_size))
    run_case("excessive_serialized_size",False,huge_serialized)
    record_mutations=[
      ("malformed_hash","file_sha256","0"*63),("malformed_path","relative_path","../escape"),
      ("malformed_enum","disposition","approved"),("malformed_identity","finding_id","0"*64),
      ("malformed_line_zero","line_start",0),("malformed_line_reverse","line_start",999999),
      ("bool_as_line", "line_start", True),("null_line","line_start",None),("unexpected_scalar_line","line_start",1.5)]
    for name,field,value in record_mutations:
        def mut(root,f=field,x=value):
            for n in ("findings.json","decisions.json","ledger.json"):
                p=root/n; v=json.loads(p.read_text()); v["records"][0][f]=x; p.write_bytes(enc(v))
        run_case(name,False,mut)
    def bool_record(root):
        p=root/"record.json"; v=json.loads(p.read_text()); v["raw_removed"]=1; p.write_bytes(enc(v))
    run_case("bool_as_integer_raw_removed",False,bool_record)
    def bool_scan(root):
        p=root/"record.json"; v=json.loads(p.read_text()); v["scanner_exit"]=True; p.write_bytes(enc(v))
    run_case("bool_as_integer_scanner_exit",False,bool_scan)
    def bool_total(root):
        p=root/"summary.json"; v=json.loads(p.read_text()); v["disposition_totals"]["potential_credential"]=False; p.write_bytes(enc(v))
    run_case("bool_as_integer_disposition_total",False,bool_total)
    def null_unvalidated(root):
        p=root/"record.json"; v=json.loads(p.read_text()); v["promotion_gates"]=None; p.write_bytes(enc(v))
    run_case("null_unvalidated_record_field",False,null_unvalidated)
    def scalar_unvalidated(root):
        p=root/"environment.json"; v=json.loads(p.read_text()); v["branch"]=1; p.write_bytes(enc(v))
    run_case("unexpected_scalar_environment_branch",False,scalar_unvalidated)
    def dynamic_files(root):
        p=root/"reviewed-hashes.json"; v=json.loads(p.read_text()); v["files"]["apiSecretMaterial"]="0"*64; p.write_bytes(enc(v))
    run_case("sensitive_dynamic_reviewed_files_key",False,dynamic_files)
    def dynamic_binary(root):
        p=root/"reviewed-hashes.json"; v=json.loads(p.read_text()); v["pinned_binaries"]["credential material"]="0"*64; p.write_bytes(enc(v))
    run_case("sensitive_dynamic_pinned_binary_key",False,dynamic_binary)
    def changed_substitution(root):
        p=root/"changed-files.json"; v=json.loads(p.read_text()); v["paths"][0]="safe/replacement.txt"; p.write_bytes(enc(v))
    run_case("changed_files_wrong_exact_set",False,changed_substitution)
    failures=[r["name"] for r in results if not r["expectation_met"] or r["unsafe_echo"]]
    print(json.dumps({"schema":"m0_3c_r5_validator_adversarial","case_count":len(results),
                      "expectation_failure_count":len(failures),"expectation_failures":failures,
                      "temporary_copies_removed":True,"results":results},sort_keys=True))
if __name__=="__main__": main()