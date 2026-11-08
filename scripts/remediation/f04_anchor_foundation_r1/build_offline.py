#!/usr/bin/env python3
"""Fail-closed F04 offline snapshot builder; invocation requires independent review."""
import argparse, hashlib, json, os, re, shutil, signal, stat, subprocess, sys, time
from pathlib import Path, PurePosixPath

REPO=Path("/home/GodOfAgents/code/VAMS-testnet"); CARDANO=REPO/"cardano"
EVROOT=Path("/home/GodOfAgents/vams-evidence")
MANIFEST=CARDANO/"aiken-dependency-manifest.json"
AIKEN=Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
BWRAP=Path("/usr/bin/bwrap")
PYTHON=Path("/home/GodOfAgents/vams-evidence/m7-python-depsec-r2-20261006/venv/bin/python")
H={
"manifest":"d4bbe77962932359f2d2d8598f7758b84868c9377aba23f96c103baefac7ec93",
"toml":"0520b42b48f051b1850f8143cdb9d2a7e7532d88ebac3c1b2ae7073332bac23a",
"lock":"7c69f0a484d3b42862dc0ab0773cf6b3edf72709c921b2ad3648a0753af8cafc",
"index":"9e051ca506a016c3553f334cefcd0e65efa505dcbb73ff20b0b807dc7b5e360e",
"aiken":"07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79",
"bwrap":"0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0",
"python":"aa01d96348989f33ed998b42c83e98593b41dba83914d9899730b90c36f2e5c9",
"sources":{
"lib/vams/f04_anchor_types.ak":"2f3f038ce17ad59dc2e1bac237093ed21306e58e89098e3e518463de6bf8526b",
"validators/f04_anchor_lock.ak":"006550eeb3b8be847962066ba141845793bc0db29fea32f20e7f37aff5410085",
"validators/f04_anchor_policy.ak":"7f9e088bd7d5955455f82ffb6df341d9c79031d33a7c90560df7eb3a537d5c29"},
"packages":{
"aiken-lang/fuzz":("06874926ec70747f3fc4e2b9364ee9e1393441cc","665295bf2c1f7a8a894056b070374700b4bdf7a788b8bff0be06b832a952eafe",16),
"aiken-lang/stdlib":("33376da0c274e41f52e69e4769a0e7878a24efba","575c264e524946034aae098e8724e42b2de6d592c94c72ae850b1ec54c9e4c97",38)}
}
ACQUIRE=re.compile(rb"(?i)(download(?:ing|ed)?\s+\d+\s+packages?|\bfrom network\b)")
class Blocked(RuntimeError): pass
def sha(b): return hashlib.sha256(b).hexdigest()
def fh(p):
 s=p.lstat()
 if not stat.S_ISREG(s.st_mode): raise Blocked(f"not regular: {p}")
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1048576),b""): h.update(x)
 return h.hexdigest()
def rel(s):
 p=PurePosixPath(s)
 if not s or p.is_absolute() or "\\" in s or "\x00" in s or any(x in ("",".","..") for x in p.parts): raise Blocked(f"unsafe path: {s!r}")
 return p.as_posix()
def files(root):
 if root.is_symlink() or not root.is_dir(): raise Blocked(f"missing/symlink dir: {root}")
 out=[]
 for base,ds,ns in os.walk(root,followlinks=False):
  b=Path(base)
  for n in ds:
   p=b/n
   if p.is_symlink() or not p.is_dir(): raise Blocked(f"special dir: {p}")
  for n in ns:
   p=b/n
   if p.is_symlink() or not p.is_file(): raise Blocked(f"special file: {p}")
   out.append(p)
 return sorted(out,key=lambda p:p.relative_to(root).as_posix())
def tree(root):
 rows=[f"{p.relative_to(root).as_posix()}\0{p.stat().st_size}\0{fh(p)}\n" for p in files(root)]
 return sha("".join(rows).encode()),len(rows)
def load():
 raw=MANIFEST.read_bytes()
 if sha(raw)!=H["manifest"]: raise Blocked("dependency manifest hash drift")
 m=json.loads(raw)
 fixed={"aiken.toml":H["toml"],"aiken.lock":H["lock"],"build/packages/packages.toml":H["index"]}
 for r,d in fixed.items():
  if fh(CARDANO/r)!=d: raise Blocked(f"project input drift: {r}")
 if m["compiler"]["binary_sha256"]!=H["aiken"]: raise Blocked("manifest compiler hash mismatch")
 for x in m["project_inputs"]:
  r=rel(x["path"])
  if fh(CARDANO/r)!=x["sha256"]: raise Blocked(f"project input drift: {r}")
 declared={}
 for x in m["compilation_sources"]:
  r=rel(x["path"])
  if fh(CARDANO/r)!=x["sha256"]: raise Blocked(f"source drift: {r}")
  declared[r]=x["sha256"]
 for r,d in H["sources"].items():
  if r in declared or fh(CARDANO/r)!=d: raise Blocked(f"F04 source drift: {r}")
  declared[r]=d
 actual={p.relative_to(CARDANO).as_posix() for root in (CARDANO/"lib",CARDANO/"validators") for p in root.rglob("*.ak")}
 if actual!=set(declared): raise Blocked(f"source inventory mismatch unbound={sorted(actual-set(declared))}")
 bp=m["blueprint"]
 if fh(CARDANO/rel(bp["path"]))!=bp["sha256"]: raise Blocked("blueprint input drift")
 cache=CARDANO/m["package_cache"]["root"]
 if {p.name for p in cache.iterdir() if p.name!="packages.toml"}!=set(m["package_cache"]["directories"]): raise Blocked("cache topology drift")
 names=set()
 for d in m["dependencies"]:
  n=d["name"]
  if n not in H["packages"]: raise Blocked(f"unexpected package: {n}")
  rev,th,count=H["packages"][n]
  if (d["revision"],d["package_tree_sha256"],d["package_file_count"])!=(rev,th,count): raise Blocked(f"package pin mismatch: {n}")
  root=cache/rel(d["package_dir"]); exp={rel(x["path"]):x for x in d["files"]}
  actual={p.relative_to(root).as_posix() for p in files(root)}
  if actual!=set(exp): raise Blocked(f"package file set mismatch: {n}")
  for r,x in exp.items():
   p=root/r
   if p.stat().st_size!=x["size"] or fh(p)!=x["sha256"]: raise Blocked(f"package file mismatch: {n}/{r}")
  if tree(root)!=(th,count): raise Blocked(f"package tree mismatch: {n}")
  names.add(n)
 if names!=set(H["packages"]): raise Blocked("package set mismatch")
 return m
def binary(p,h,label):
 p=p.resolve(strict=True)
 if fh(p)!=h or not os.access(p,os.X_OK): raise Blocked(f"{label} binary mismatch")
 return p
def python():
 p=Path(sys.executable).resolve(strict=True)
 if p!=PYTHON.resolve(strict=True) or fh(p)!=H["python"]: raise Blocked("unapproved Python")
 return p
def evidence_path(s):
 p=Path(s)
 if not p.is_absolute() or ".." in p.parts: raise Blocked("evidence path must be absolute")
 root=EVROOT.resolve(strict=True); q=p.resolve(strict=False)
 if q==root or root not in q.parents: raise Blocked("evidence path outside vams-evidence")
 c=root
 for part in q.relative_to(root).parts[:-1]:
  c/=part
  if c.exists() and c.is_symlink(): raise Blocked("symlink evidence parent")
 if q.exists() or q.is_symlink(): raise Blocked("evidence directory already exists")
 return q
def copycheck(src,dst,h):
 if fh(src)!=h: raise Blocked(f"input drift during copy: {src}")
 dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst)
 if fh(dst)!=h: raise Blocked(f"copy hash mismatch: {dst}")
def snapshot(ev,m):
 ws=ev/"workspace/cardano"; ws.mkdir(parents=True)
 rec={}
 for x in m["compilation_sources"]: rec[rel(x["path"])]=x["sha256"]
 rec.update(H["sources"])
 for x in m["project_inputs"]: rec[rel(x["path"])]=x["sha256"]
 rec["aiken-dependency-manifest.json"]=H["manifest"]
 rec[rel(m["blueprint"]["path"])]=m["blueprint"]["sha256"]
 for d in m["dependencies"]:
  for x in d["files"]: rec[f'{m["package_cache"]["root"]}/{d["package_dir"]}/{rel(x["path"])}']=x["sha256"]
 for r,h in sorted(rec.items()): copycheck(CARDANO/r,ws/r,h)
 for r in ("runtime/home","runtime/cache","runtime/config","outputs"): (ev/r).mkdir(parents=True,exist_ok=True)
 return {"inputs":rec,"input_count":len(rec),"sources":len(m["compilation_sources"])+len(H["sources"]),
         "runner_sha256":fh(Path(__file__).resolve())}
def pkgmap(m,root):
 z={}
 for d in m["dependencies"]:
  t,n=tree(root/m["package_cache"]["root"]/d["package_dir"])
  z[d["name"]]={"revision":d["revision"],"tree_sha256":t,"files":n}
 return dict(sorted(z.items()))
def mount(path,text):
 target=str(path.resolve()); hits=[]
 for line in text.splitlines():
  f=line.split()
  if len(f)<7: continue
  mp=f[4].replace("\\040"," ").replace("\\011","\t").replace("\\134","\\")
  if target==mp or target.startswith(mp.rstrip("/")+"/"): hits.append((len(mp),mp,set(f[5].split(","))))
 if not hits: raise Blocked(f"mount missing: {target}")
 _,p,o=max(hits); return p,o
def kill_group(p):
 try: os.killpg(p.pid,signal.SIGKILL)
 except ProcessLookupError: pass
 return p.wait()
def run(argv,cwd,env,ev,name,timeout):
 out=ev/f"{name}.stdout"; err=ev/f"{name}.stderr"; start=time.monotonic()
 timed=False; code=None; launcher_error=None; capture_error=None; capture_complete=False
 try:
  with out.open("xb") as so,err.open("xb") as se:
   try: p=subprocess.Popen(argv,cwd=str(cwd),env=env,stdout=so,stderr=se,start_new_session=True)
   except OSError as e: launcher_error=type(e).__name__
   else:
    try: code=p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
     timed=True; code=kill_group(p)
  capture_complete=(out.is_file() and err.is_file() and not out.is_symlink() and not err.is_symlink())
  out_hash=fh(out) if capture_complete else None
  err_hash=fh(err) if capture_complete else None
 except OSError as e:
  capture_error=type(e).__name__; capture_complete=False; out_hash=None; err_hash=None
 except Blocked:
  capture_error="BlockedCapture"; capture_complete=False; out_hash=None; err_hash=None
 if launcher_error is not None: outcome="LAUNCH_ERROR"
 elif capture_error is not None or not capture_complete: outcome="CAPTURE_ERROR"
 elif timed: outcome="TIMED_OUT"
 elif code is None: outcome="NO_CHILD_EXIT"
 elif code<0: outcome="SIGNAL_TERMINATED"
 elif code==0: outcome="EXITED_ZERO"
 else: outcome="EXITED_NONZERO"
 return {"argv":argv,"cwd":str(cwd),"child_exit":code,"child_signal":-code if code is not None and code<0 else None,
         "terminal_outcome":outcome,"launcher_error_class":launcher_error,"capture_error_class":capture_error,
         "started":launcher_error is None and capture_error is None,"timed_out":timed,"capture_complete":capture_complete,
         "elapsed_seconds":round(time.monotonic()-start,3),"stdout":out.name,"stderr":err.name,
         "stdout_sha256":out_hash,"stderr_sha256":err_hash}
def command_plan(a,ws,out,mode):
 if mode not in ("check-only","build"): raise Blocked("invalid mode")
 plan={"version":[str(a),"--version"],"check":[str(a),"check"]}
 if mode=="build": plan["build"]=[str(a),"build",str(ws),"--out",str(out),"--uplc","--trace-level","verbose"]
 validate_plan(mode,plan)
 return plan
def validate_plan(mode,plan):
 expected={"version","check"} | ({"build"} if mode=="build" else set())
 if mode not in ("check-only","build") or set(plan)!=expected: raise Blocked("command plan does not match explicit mode")
 return True
def command_ok(r):
 return (r.get("started") is True and r.get("launcher_error_class") is None and
         r.get("capture_complete") is True and r.get("child_exit")==0 and
         r.get("timed_out") is False and r.get("stdout_sha256") is not None and
         r.get("stderr_sha256") is not None)
def check_then_optional_build(plan,mode,invoke,validate_check,validate_build,records):
 if mode not in ("check-only","build"): raise Blocked("invalid mode")
 check=invoke("check",plan["check"]); records["check"]=check
 if not command_ok(check): raise Blocked("check command failed")
 validate_check(check)
 if mode=="build":
  build=invoke("build",plan["build"]); records["build"]=build
  if not command_ok(build): raise Blocked("build command failed")
  validate_build(build)
 return records
def outer_accepted(mode,wrapper_exit,inner,capture_complete,wrapper_timeout,launcher_error,capture_error):
 expected="PASS_CHECK_ONLY" if mode=="check-only" else "PASS_BUILD_ONLY"
 if mode not in ("check-only","build") or wrapper_exit!=0 or not capture_complete or wrapper_timeout:
  return False
 if launcher_error is not None or capture_error is not None or not isinstance(inner,dict): return False
 if inner.get("mode")!=mode or inner.get("wrapper_exit")!=0 or inner.get("status")!=expected: return False
 commands=inner.get("commands",{})
 if not command_ok(commands.get("check",{})): return False
 if mode=="build" and not command_ok(commands.get("build",{})): return False
 return True
def acquisition(r,ev): return any(ACQUIRE.search((ev/r[k]).read_bytes()) for k in ("stdout","stderr"))
def check_snapshot(ws,snap):
 for r,h in snap["inputs"].items():
  if fh(ws/r)!=h: raise Blocked(f"snapshot drift: {r}")
def inside(ev,timeout,mode):
 result={"mode":mode,"commands":{}}; code=2
 try:
  host=os.environ["F04_HOST_NETNS"]; rh=os.environ["F04_RUNNER_SHA256"]
  if mode not in ("check-only","build"): raise Blocked("invalid mode")
  if os.environ.get("F04_EVIDENCE_DIR")!=str(ev) or fh(Path(__file__).resolve())!=rh: raise Blocked("runner/evidence binding mismatch")
  if fh(Path(sys.executable).resolve(strict=True))!=H["python"]: raise Blocked("isolated Python binary drift")
  ns=os.readlink("/proc/self/ns/net")
  if ns==host: raise Blocked("network namespace not isolated")
  mi=Path("/proc/self/mountinfo").read_text()
  (ev/"inside-netns.txt").write_text(ns+"\n"); (ev/"inside-pidns.txt").write_text(os.readlink("/proc/self/ns/pid")+"\n"); (ev/"inside-mountinfo.txt").write_text(mi)
  (ev/"inside-ipv4-routes.txt").write_text(Path("/proc/net/route").read_text())
  (ev/"inside-ipv6-routes.txt").write_text(Path("/proc/net/ipv6_route").read_text())
  cm,co=mount(REPO,mi); em,eo=mount(ev,mi); wm,wo=mount(ev/"workspace/cardano",mi)
  if "ro" not in co or "rw" in co or "rw" not in eo or wm!=em or "rw" not in wo: raise Blocked("mount protections failed")
  result["isolation"]={"host_netns":host,"inside_netns":ns,"network_isolated":True,"canonical_mount":cm,
    "canonical_options":sorted(co),"evidence_mount":em,"evidence_options":sorted(eo),"workspace_mount":wm,"workspace_options":sorted(wo)}
  m=load(); ws=ev/"workspace/cardano"; snap=json.loads((ev/"snapshot-inputs.json").read_text())
  check_snapshot(ws,snap)
  base=pkgmap(m,CARDANO)
  if pkgmap(m,ws)!=base: raise Blocked("workspace cache differs from trusted canonical cache")
  a=binary(AIKEN,H["aiken"],"Aiken"); tmp=Path(os.environ.get("TMPDIR",""))
  if not tmp.is_absolute() or not tmp.is_dir() or not os.access(tmp,os.W_OK): raise Blocked("isolated TMPDIR missing or not writable")
  env={"PATH":str(a.parent),"HOME":str(ev/"runtime/home"),"TMPDIR":str(tmp),
       "XDG_CACHE_HOME":str(ev/"runtime/cache"),"XDG_CONFIG_HOME":str(ev/"runtime/config"),
       "AIKEN_NO_NETWORK":"1","LC_ALL":"C","LANG":"C"}
  out=ev/"outputs/f04-anchor-foundation-r1-plutus.json"
  if out.exists(): raise Blocked("build output exists")
  plan=command_plan(a,ws,out,mode)
  v=run(plan["version"],ws,env,ev,"aiken-version",timeout); result["commands"]["version"]=v
  if not command_ok(v) or not (ev/v["stdout"]).read_bytes().startswith(b"aiken v1.1.21"): raise Blocked("Aiken version check failed")
  def validate_check(c):
   if acquisition(c,ev): raise Blocked("check reported acquisition")
   if fh(ws/"aiken.lock")!=H["lock"] or pkgmap(m,ws)!=base: raise Blocked("check changed lock/cache")
   check_snapshot(ws,snap)
  def validate_build(b):
   if acquisition(b,ev): raise Blocked("build reported acquisition")
   if fh(ws/"aiken.lock")!=H["lock"] or pkgmap(m,ws)!=base: raise Blocked("build changed lock/cache")
   check_snapshot(ws,snap)
   if not out.is_file() or out.is_symlink(): raise Blocked("external blueprint missing")
  invoke=lambda name,argv: run(argv,ws,env,ev,f"aiken-{name}",timeout)
  check_then_optional_build(plan,mode,invoke,validate_check,validate_build,result["commands"])
  if mode=="build":
   result["output"]={"path":str(out),"size":out.stat().st_size,"sha256":fh(out)}
   result["status"]="PASS_BUILD_ONLY"
  else: result["status"]="PASS_CHECK_ONLY"
  code=0
 except Exception as e:
  result.update(status="BLOCKED",error_class=type(e).__name__)
 result["wrapper_exit"]=code
 try: (ev/"run-summary.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
 except OSError: return 2
 return code
def writej(p,x): p.write_text(json.dumps(x,sort_keys=True,indent=2)+"\n")
def host(raw,timeout,mode):
 ev=evidence_path(raw); ev.mkdir(mode=0o700,parents=True)
 try:
  py=python(); a=binary(AIKEN,H["aiken"],"Aiken"); bw=binary(BWRAP,H["bwrap"],"bwrap"); m=load()
  snap=snapshot(ev,m); snap.update(python_sha256=fh(py),aiken_sha256=fh(a),bwrap_sha256=fh(bw),python_version=sys.version)
  writej(ev/"snapshot-inputs.json",snap)
  before=os.readlink("/proc/self/ns/net"); (ev/"host-netns-before.txt").write_text(before+"\n")
  tmp=f"/tmp/f04-anchor-{os.getpid()}"
  argv=[str(bw),"--unshare-net","--unshare-pid","--as-pid-1","--die-with-parent","--ro-bind","/","/","--dev-bind","/dev","/dev","--proc","/proc",
   "--tmpfs","/tmp","--dir",tmp,"--bind",str(ev),str(ev),"--clearenv",
   "--setenv","PATH",str(AIKEN.parent),"--setenv","HOME",str(ev/"runtime/home"),"--setenv","TMPDIR",tmp,
   "--setenv","XDG_CACHE_HOME",str(ev/"runtime/cache"),"--setenv","XDG_CONFIG_HOME",str(ev/"runtime/config"),
   "--setenv","AIKEN_NO_NETWORK","1","--setenv","LC_ALL","C","--setenv","LANG","C",
   "--setenv","PYTHONDONTWRITEBYTECODE","1","--setenv","F04_EVIDENCE_DIR",str(ev),
   "--setenv","F04_HOST_NETNS",before,"--setenv","F04_RUNNER_SHA256",snap["runner_sha256"],
   "--chdir",str(REPO),str(py),"-B",str(Path(__file__).resolve()),"--inside","--mode",mode,"--evidence-dir",str(ev),"--timeout-seconds",str(timeout)]
  (ev/"bwrap-argv.json").write_text(json.dumps(argv,indent=2)+"\n")
  wrapper_exit=None; launcher_error=None; capture_error=None; wrapper_timeout=False
  try:
   with (ev/"bwrap.stdout").open("xb") as so,(ev/"bwrap.stderr").open("xb") as se:
    try: p=subprocess.Popen(argv,stdout=so,stderr=se,start_new_session=True)
    except OSError as e: launcher_error=type(e).__name__
    else:
     try: wrapper_exit=p.wait(timeout=timeout*3+60)
     except subprocess.TimeoutExpired:
      wrapper_timeout=True; wrapper_exit=kill_group(p)
  except OSError as e: capture_error=type(e).__name__
  capture_complete=False; out_hash=None; err_hash=None
  try:
   capture_complete=not (ev/"bwrap.stdout").is_symlink() and not (ev/"bwrap.stderr").is_symlink()
   out_hash=fh(ev/"bwrap.stdout") if capture_complete else None
   err_hash=fh(ev/"bwrap.stderr") if capture_complete else None
  except OSError as e: capture_error=capture_error or type(e).__name__; capture_complete=False
  except Blocked: capture_error=capture_error or "BlockedCapture"; capture_complete=False
  after=os.readlink("/proc/self/ns/net"); (ev/"host-netns-after.txt").write_text(after+"\n")
  if after!=before: raise Blocked("host network namespace changed")
  ip=ev/"run-summary.json"; inner=None
  if ip.is_file() and not ip.is_symlink(): inner=json.loads(ip.read_text())
  check_record=(inner or {}).get("commands",{}).get("check",{})
  inner_bound=(isinstance(inner,dict) and inner.get("mode")==mode and inner.get("wrapper_exit")==wrapper_exit)
  complete=launcher_error is None and capture_error is None and capture_complete and inner_bound and not wrapper_timeout
  writej(ev/"outer-summary.json",{"mode":mode,"bwrap_launcher_error_class":launcher_error,
   "wrapper_exit":wrapper_exit,"wrapper_timed_out":wrapper_timeout,"capture_error_class":capture_error,"capture_complete":capture_complete,
   "aiken_check_child_exit":check_record.get("child_exit"),"aiken_check_launcher_error_class":check_record.get("launcher_error_class"),
   "aiken_check_timed_out":check_record.get("timed_out"),"bwrap_stdout_sha256":out_hash,"bwrap_stderr_sha256":err_hash,
   "inner_summary_present":inner is not None,"inner_summary_bound":inner_bound,
   "complete":complete,"runner_sha256":snap["runner_sha256"],"python_sha256":fh(py),
   "aiken_sha256":fh(a),"bwrap_sha256":fh(bw),"host_netns_before":before,"host_netns_after":after})
  return wrapper_exit if outer_accepted(mode,wrapper_exit,inner,capture_complete,wrapper_timeout,launcher_error,capture_error) else 2
 except Exception as e:
  writej(ev/"preflight-error.json",{"status":"BLOCKED_BEFORE_AIKEN","error_class":type(e).__name__})
  return 2
def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--evidence-dir",required=True)
 p.add_argument("--timeout-seconds",type=int,default=300); p.add_argument("--mode",choices=("check-only","build"),required=True); p.add_argument("--inside",action="store_true",help=argparse.SUPPRESS)
 a=p.parse_args()
 if not 1<=a.timeout_seconds<=600: p.error("timeout must be in [1,600]")
 if a.inside: return inside(Path(a.evidence_dir).resolve(strict=True),a.timeout_seconds,a.mode)
 return host(a.evidence_dir,a.timeout_seconds,a.mode)
if __name__=="__main__": raise SystemExit(main())
