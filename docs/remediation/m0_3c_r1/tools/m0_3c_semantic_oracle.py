#!/usr/bin/env python3
"""Independent content-addressed semantic attestation for M0.3c findings.

This verifier deliberately does not import the adjudicator or its classifiers.
It starts from a fresh scanner report over blobs from the pinned Git tree, uses
a bounded JavaScript token parser plus comment/string-aware Solidity declaration
parsing, and uses cryptography for DER public-key parsing.
"""
from __future__ import annotations
import argparse
from collections import Counter,deque
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tempfile
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import cryptography
from eth_hash.auto import keccak as independent_keccak

HEAD="829ab544571f12efe50ecb5740f129c8acb3e16f"
PARENT_PREFIX="contracts/lib/openzeppelin-contracts-upgradeable"
PARENT_PIN="aa677e9d28ed78fc427ec47ba2baef2030c58e7c"
PREFIX=PARENT_PREFIX+"/lib/openzeppelin-contracts"
PIN="fcbae5394ae8ad52d8e580a3477db99814b9d565"
SCANNER_SHA256="88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"
CHILD_GITLINKS={"lib/erc4626-tests":"232ff9ba8194e406967f52ecc5cb52ed764209e9",
"lib/forge-std":"3b20d60d14b343ee4f908cb8079495c07f5e8981",
"lib/halmos-cheatcodes":"7328abe100445fc53885c21d0e713b95293cf14c"}
class OracleError(RuntimeError):pass

def sha(data):return hashlib.sha256(data).hexdigest()
def encoded(v):return (json.dumps(v,sort_keys=True,indent=2)+"\n").encode()
def unique(items):
 out={}
 for k,v in items:
  if k in out:raise OracleError("duplicate JSON key")
  out[k]=v
 return out
def load(path):return json.loads(Path(path).read_text(encoding="utf-8"),object_pairs_hook=unique)
def git(cwd,*args):return subprocess.run(["git",*args],cwd=cwd,capture_output=True,check=True).stdout
def safe_path(v):
 if not isinstance(v,str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,220}",v):raise OracleError("unsafe path")
 p=PurePosixPath(v)
 if p.is_absolute() or any(x in {"",".",".."} for x in v.split("/")):raise OracleError("noncanonical path")
 return v
def stable_id(head,commit,path,rule,start,end):return sha("|".join((head,commit,path,rule,str(start),str(end))).encode())

def state(repo):
 head=git(repo,"rev-parse","HEAD").decode().strip()
 parent=git(repo,"ls-tree","HEAD","--",PARENT_PREFIX).decode().split()
 pindex=git(repo,"ls-files","--stage","--",PARENT_PREFIX).decode().split()
 if head!=HEAD or len(parent)!=4 or parent[:2]!=["160000","commit"] or parent[2]!=PARENT_PIN or len(pindex)!=4 or pindex[0]!="160000" or pindex[1]!=PARENT_PIN:raise OracleError("parent provenance")
 parent_dir=repo/PARENT_PREFIX
 if git(parent_dir,"rev-parse","HEAD").decode().strip()!=PARENT_PIN or git(parent_dir,"status","--porcelain","--untracked-files=all","--ignored"):raise OracleError("parent not clean")
 target=git(parent_dir,"ls-tree",PARENT_PIN,"--","lib/openzeppelin-contracts").decode().split()
 tindex=git(parent_dir,"ls-files","--stage","--","lib/openzeppelin-contracts").decode().split()
 if len(target)!=4 or target[:2]!=["160000","commit"] or target[2]!=PIN or len(tindex)!=4 or tindex[0]!="160000" or tindex[1]!=PIN:raise OracleError("target provenance")
 target_dir=repo/PREFIX
 if git(target_dir,"rev-parse","HEAD").decode().strip()!=PIN or git(target_dir,"status","--porcelain","--untracked-files=all","--ignored"):raise OracleError("target not clean")
 return head

def tree(repo):
 raw=git(repo/PREFIX,"ls-tree","-r","-z",PIN);blobs={};links={}
 for entry in raw.split(b"\0"):
  if not entry:continue
  meta,name=entry.split(b"\t",1);mode,kind,oid=meta.decode().split();name=safe_path(name.decode())
  if mode=="160000" and kind=="commit":links[name]=oid
  elif kind=="blob" and mode in {"100644","100755"}:blobs[name]={"object_id":oid,"mode":mode}
  else:raise OracleError("unsupported tree entry")
 if links!=CHILD_GITLINKS:raise OracleError("child gitlinks")
 return blobs

def source_manifest(repo):
 names=git(repo,"ls-files","-z","--cached","--others","--exclude-standard").decode().split("\0");result={}
 for name in sorted(set(names)-{""}):
  if name.startswith(("docs/","codex-skills/",".codex/","contracts/lib/")) or name.endswith(".md"):continue
  p=repo/name
  if p.is_dir():continue
  result[name]=sha(p.read_bytes())
 return result

def strip_solidity(data):
 text=data.decode("utf-8");out=[];i=0;state="code";quote=""
 while i<len(text):
  c=text[i];n=text[i+1] if i+1<len(text) else ""
  if state=="code":
   if c=="/" and n=="/":state="line";out.extend("  ");i+=2;continue
   if c=="/" and n=="*":state="block";out.extend("  ");i+=2;continue
   if c in ("'",chr(34)):state="string";quote=c;out.append(" ");i+=1;continue
   out.append(c);i+=1
  elif state=="line":
   out.append("\n" if c=="\n" else " ")
   if c=="\n":state="code"
   i+=1
  elif state=="block":
   if c=="*" and n=="/":state="code";out.extend("  ");i+=2
   else:out.append("\n" if c=="\n" else " ");i+=1
  else:
   if c=="\\":out.extend("  ");i+=2
   elif c==quote:state="code";out.append(" ");i+=1
   else:out.append("\n" if c=="\n" else " ");i+=1
 if state in {"block","string"}:raise OracleError("unterminated Solidity token")
 return "".join(out)

def declarations(blobs):
 pattern=re.compile(r"\berror\s+(ERC([0-9]+)[A-Za-z][A-Za-z0-9]*)\s*\(");found={}
 for path,data in blobs.items():
  if not path.startswith("contracts/") or not path.endswith(".sol"):continue
  for name,standard in pattern.findall(strip_solidity(data)):
   found.setdefault(name,[]).append((path,standard))
 return found

def oracle_graph(blobs):
 out={};head=re.compile(r"\b(?:abstract\s+)?(contract|interface|library)\s+([A-Za-z_]\w*)(?:\s+is\s+([^\{]+))?\s*\{")
 for path,data in blobs.items():
  if not path.startswith("contracts/") or not path.endswith(".sol"):continue
  code=strip_solidity(data)
  for found in head.finditer(code):
   depth=1;i=found.end()
   while i<len(code) and depth:
    depth+=(code[i]=="{")-(code[i]=="}");i+=1
   if depth:raise OracleError("unbalanced Solidity container")
   name=found.group(2)
   if name in out:raise OracleError("duplicate Solidity container")
   parents=[]
   for item in (found.group(3) or "").split(","):
    match=re.match(r"\s*([A-Za-z_]\w*)",item)
    if match:parents.append(match.group(1))
   out[name]={"path":path,"kind":found.group(1),"parents":parents,"body":code[found.end():i-1]}
 for name,node in out.items():
  used=[candidate for candidate,value in out.items() if value["kind"]=="library" and re.search(rf"\b{re.escape(candidate)}\s*[.]",node["body"])]
  node["next"]=list(dict.fromkeys(node["parents"]+sorted(used)))
 return out

def oracle_signature(body,error):
 match=re.search(rf"\berror\s+{re.escape(error)}\s*\(([^)]*)\)\s*;",body)
 if not match:return None
 types=[]
 for argument in match.group(1).split(","):
  argument=argument.strip()
  if not argument:continue
  words=[word for word in argument.split() if word not in {"memory","calldata","storage","payable"}]
  if not words:return None
  types.append(words[0])
 return f"{error}({','.join(types)})"

def oracle_invocation(data,line_number):
 lines=data.decode("utf-8").splitlines()
 if not 1<=line_number<=len(lines):raise OracleError("assertion line")
 try:tokens=js_tokens(lines[line_number-1])
 except OracleError as exc:raise OracleError("assertion syntax") from exc
 kinds=[x[0] for x in tokens]
 if kinds!=[".","id",".","id",".","id","(","id",".","id",",","str",")"] or [tokens[i][1] for i in (1,3,5,7)]!=["to","be","revertedWithCustomError","this"]:raise OracleError("assertion syntax")
 assertion_target="this."+tokens[9][1];error=tokens[11][1]
 joined=" ".join(lines[max(0,line_number-16):line_number]);prefix=joined.rsplit(".to.be.revertedWithCustomError",1)[0]
 parts=prefix.rsplit("await expect(",1)
 if len(parts)!=2:raise OracleError("missing invocation")
 expression=parts[1];dot=r"\s*[.]\s*"
 direct=re.search(rf"this{dot}([A-Za-z_]\w*)(?:{dot}connect\s*\([^)]*\))?(?:{dot}getFunction\s*\((['\"])([^'\"]+)\2\)|{dot}([$A-Za-z_]\w*)\s*\()",expression)
 alias=re.search(r"this\s*[.]\s*([A-Za-z_]\w*)\s*\(",expression)
 if direct:call_target="this."+direct.group(1);operation=direct.group(3) or direct.group(4)
 elif re.search(r"ethers\s*[.]\s*deployContract\s*\(",expression):call_target="ethers";operation="deployContract"
 elif alias and alias.group(1) in {"transfer","approve"}:call_target="this.token";operation=alias.group(1)
 else:raise OracleError("unresolved invocation")
 return assertion_target,error,call_target,operation

def oracle_route(graph,start,owner,error):
 pending=deque([(start,[start])]);visited=set();routes=[];declared=[]
 while pending:
  current,route=pending.popleft()
  if current in visited:continue
  visited.add(current);node=graph.get(current)
  if node and oracle_signature(node["body"],error) is not None:declared.append(current)
  if current==owner:routes.append(route);continue
  if node:
   for nxt in node["next"]:pending.append((nxt,route+[nxt]))
 if len(routes)!=1 or declared!=[owner]:raise OracleError("unreachable or ambiguous owner")
 return routes[0]

def _reachable_declarations(graph,start,error):
 pending=deque([(start,[start])]);visited=set();found=[]
 while pending:
  current,route=pending.popleft()
  if current in visited:continue
  visited.add(current);node=graph.get(current)
  if node is None:continue
  sig=oracle_signature(node["body"],error)
  if sig is not None:found.append((current,sig,route))
  for nxt in node["next"]:pending.append((nxt,route+[nxt]))
 return found

def _deployments(text):
 mapping={}
 for name,artifact in re.findall(r"\bconst\s+([A-Za-z_]\w*)\s*=\s*await\s+ethers\.deployContract\(\s*['\"](\$[A-Za-z_]\w*)['\"]",text):
  mapping.setdefault(name,set()).add(artifact)
 for name,artifact in re.findall(r"\b([A-Za-z_]\w*)\s*:\s*await\s+ethers\.deployContract\(\s*['\"](\$[A-Za-z_]\w*)['\"]",text):
  mapping.setdefault(name,set()).add(artifact)
 for variable,body in re.findall(r"for\s*\(\s*const\s+([A-Za-z_]\w*)\s+of\s*\[([^]]+)\]",text,re.S):
  mapping.setdefault(variable,set()).update(re.findall(r"['\"](\$[A-Za-z_]\w*)['\"]",body))
 for variable,artifact in re.findall(r"\{\s*([A-Za-z_]\w*)\s*:\s*['\"](\$[A-Za-z_]\w*)['\"]",text):
  mapping.setdefault(variable,set()).add(artifact)
 return mapping

def _behavior_name(data,line):
 prefix="\n".join(data.decode("utf-8").splitlines()[:line])
 names=re.findall(r"function\s+(shouldBehaveLike[A-Za-z0-9_]*)\s*\(",prefix)
 if not names:raise OracleError("behavior scope")
 return names[-1]

def _derive_targets(path,data,line,pinned,graph,error,assertion_target,call_target):
 behavior=path.endswith(".behavior.js")
 callers=[]
 if behavior:
  stem=PurePosixPath(path).stem
  for candidate,raw in pinned.items():
   if not candidate.startswith("test/") or not candidate.endswith(".js") or candidate==path:continue
   text=raw.decode("utf-8")
   if (stem in text or PurePosixPath(path).name in text) and re.search(r"\bshouldBehaveLike[A-Za-z0-9_]*\s*\(",text):callers.append(candidate)
 else:callers=[path]
 targets=[]
 for caller_path in callers:
  text=pinned[caller_path].decode("utf-8");mapping=_deployments(text);artifacts=set()
  if behavior:
   artifacts.update(mapping.get("token",set()))
   if re.search(r"ethers\.deployContract\(\s*Token\b",text):artifacts.update(mapping.get("Token",set()))
  else:
   lines=text.splitlines();before="\n".join(lines[:line])
   for target in (assertion_target,call_target):
    if target.startswith("this."):
     prop=target.split(".",1)[1]
     assigned=re.findall(r"this\."+re.escape(prop)+r"\s*=\s*this\.([A-Za-z_]\w*)",before)
     key=assigned[-1] if assigned else prop
     artifacts.update(mapping.get(key,set()))
   window="\n".join(lines[max(0,line-18):line+1])
   artifacts.update(re.findall(r"ethers\.deployContract\(\s*['\"](\$[A-Za-z_]\w*)['\"]",window))
   if not artifacts and assertion_target=="this.token" and re.search(r"ethers\.deployContract\(\s*Token\b",text):
    artifacts.update(mapping.get("Token",set()))
   if not artifacts:
    for key in ("token","mock","ownable"):artifacts.update(mapping.get(key,set()))
  for artifact in artifacts:
   declarations=_reachable_declarations(graph,artifact.removeprefix("$"),error)
   if len(declarations)==1:targets.append((caller_path,artifact,declarations[0]))
 unique={(c,a):(c,a,d) for c,a,d in targets}
 if not unique:raise OracleError("execution target derivation")
 return [unique[k] for k in sorted(unique)]

def oracle_context(path,data,line,pinned,owned,graph):
 assertion_target,error,call_target,operation=oracle_invocation(data,line)
 targets=_derive_targets(path,data,line,pinned,graph,error,assertion_target,call_target)
 owners={(d[0],d[1]) for _,_,d in targets}
 if len(owners)!=1:raise OracleError("ambiguous declaration owner")
 owner_name,expected=next(iter(owners));owner=graph[owner_name];owner_path=owner["path"];owner_kind=owner["kind"]
 execution=[];chains=[]
 for caller_path,artifact,declaration in targets:
  route=declaration[2];caller=pinned[caller_path]
  execution.append({"artifact":artifact,"caller_path":caller_path,"caller_sha256":sha(caller),"caller_object_id":owned[caller_path]["object_id"]})
  chains.append({"artifact":artifact,"containers":[{"name":name,"kind":graph[name]["kind"],"path":graph[name]["path"]} for name in route]})
 owner_data=pinned[owner_path]
 if hashlib.sha1(b"blob "+str(len(owner_data)).encode("ascii")+b"\0"+owner_data).hexdigest()!=owned[owner_path]["object_id"]:raise OracleError("owner blob drift")
 for item in execution:
  caller=pinned[item["caller_path"]]
  if hashlib.sha1(b"blob "+str(len(caller)).encode("ascii")+b"\0"+caller).hexdigest()!=item["caller_object_id"]:raise OracleError("caller blob drift")
 return {"kind":"custom_error_execution","assertion_target":assertion_target,"call_target":call_target,"invoked_operation":operation,
  "error_name":error,"error_signature":expected,"error_selector":independent_keccak(expected.encode("ascii")).hex()[:8],
  "declaration_owner":{"name":owner_name,"kind":owner_kind,"path":owner_path,"source_sha256":sha(owner_data),"source_object_id":owned[owner_path]["object_id"]},
  "execution_targets":sorted(execution,key=lambda x:(x["caller_path"],x["artifact"])),"reachability_chains":sorted(chains,key=lambda x:x["artifact"])}

def js_tokens(line):
 tokens=[];i=0
 while i<len(line):
  c=line[i]
  if c.isspace():i+=1;continue
  if c in ".(),":tokens.append((c,c));i+=1;continue
  if c.isalpha() or c in "_$":
   j=i+1
   while j<len(line) and (line[j].isalnum() or line[j] in "_$"):j+=1
   tokens.append(("id",line[i:j]));i=j;continue
  if c in ("'",chr(34),chr(96)):
   q=c;j=i+1;value=[]
   while j<len(line):
    if line[j]=="\\":
     if j+1>=len(line):raise OracleError("invalid escape")
     value.append(line[j+1]);j+=2
    elif line[j]==q:tokens.append(("str","".join(value)));i=j+1;break
    else:value.append(line[j]);j+=1
   else:raise OracleError("unterminated JavaScript string")
   continue
  raise OracleError("unsupported JavaScript token")
 return tokens

def assertion_semantics(data,line_number,declared,path):
 lines=data.decode("utf-8").splitlines()
 if not 1<=line_number<=len(lines):return False
 try:tokens=js_tokens(lines[line_number-1])
 except OracleError:return False
 kinds=[x[0] for x in tokens]
 if kinds!=[".","id",".","id",".","id","(","id",".","id",",","str",")"]:return False
 if [tokens[i][1] for i in (1,3,5,7)]!=["to","be","revertedWithCustomError","this"]:return False
 error=tokens[11][1];match=re.fullmatch(r"ERC([0-9]+)[A-Za-z][A-Za-z0-9]*",error)
 if not match or error not in declared or len(declared[error])!=1:return False
 standard=match.group(1)
 return f"/token/ERC{standard}/" in path or (standard=="20" and "/governance/" in path)

def der_semantics(data,line_number):
 lines=data.decode("utf-8").splitlines()
 if not 1<=line_number<=len(lines):return False
 fragment=lines[line_number-1].strip()
 if fragment.endswith(","):fragment=fragment[:-1]
 try:item=json.loads("{"+fragment+"}",object_pairs_hook=unique);document=json.loads(data,object_pairs_hook=unique)
 except (json.JSONDecodeError,OracleError):return False
 if set(item)!={"keyDer"} or not isinstance(item["keyDer"],str):return False
 groups=[g for g in document.get("testGroups",[]) if isinstance(g,dict) and g.get("keyDer")==item["keyDer"]]
 if document.get("algorithm")!="ECDSA" or not groups:return False
 if any(g.get("type")!="EcdsaP1363Verify" or not isinstance(g.get("key"),dict) or g["key"].get("type")!="EcPublicKey" for g in groups):return False
 try:key=serialization.load_der_public_key(bytes.fromhex(item["keyDer"]))
 except (ValueError,TypeError):return False
 return isinstance(key,ec.EllipticCurvePublicKey)

def classify(data,path,line,declared):
 if path.startswith(PREFIX+"/test/") and path.endswith((".test.js",".behavior.js")) and assertion_semantics(data,line,declared,path):return "expected_custom_error_assertion"
 if path.startswith(PREFIX+"/test/") and path.endswith(".json") and der_semantics(data,line):return "ecdsa_public_key_der"
 return "not_proven"

def run(repo,scanner,decisions_path,output):
 repo=Path(repo).resolve();scanner=Path(scanner).resolve();decisions_path=Path(decisions_path).resolve();output=Path(output).absolute()
 if output.exists() or output.is_symlink() or not output.parent.is_dir():raise OracleError("invalid output")
 head=state(repo)
 if sha(scanner.read_bytes())!=SCANNER_SHA256:raise OracleError("scanner digest")
 scanner_version=subprocess.run([str(scanner),"version"],capture_output=True,check=True).stdout.decode().strip()
 if scanner_version!="8.30.1":raise OracleError("scanner version")
 owned=tree(repo);pinned={p:git(repo/PREFIX,"show",f"{PIN}:{p}") for p in owned};declared=declarations(pinned);graph=oracle_graph(pinned)
 decision_bytes=decisions_path.read_bytes();document=json.loads(decision_bytes,object_pairs_hook=unique)
 if not isinstance(document,dict) or set(document)!={"schema","records"} or document["schema"]!="m0_3c_r1_decisions" or not isinstance(document["records"],list):raise OracleError("decisions schema")
 decisions={d.get("finding_id"):d for d in document["records"] if isinstance(d,dict)}
 if len(decisions)!=158:raise OracleError("decision count")
 manifest_sha=sha(encoded(source_manifest(repo)));records=[];counts=Counter();raw_parent=None
 with tempfile.TemporaryDirectory(prefix="m03c-r5-semantic-") as temporary:
  os.chmod(temporary,0o700);raw_parent=temporary;source=Path(temporary)/"source";source.mkdir(mode=0o700)
  for path,meta in owned.items():
   target=source/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(pinned[path]);target.chmod(0o755 if meta["mode"]=="100755" else 0o644)
  report=Path(temporary)/"report.json"
  scanner_command=[str(scanner),"dir",".","--config",str(repo/".gitleaks.toml"),"--redact=100","--report-format","json","--report-path",str(report),"--exit-code","1","--no-banner"]
  process=subprocess.run(scanner_command,cwd=source,capture_output=True)
  if process.returncode!=1:raise OracleError("scanner exit")
  findings=load(report)
  seen=set()
  for finding in findings:
   relative=finding.get("File")
   if isinstance(relative,str) and relative.startswith("./"):relative=relative[2:]
   safe_path(relative)
   rule=finding.get("RuleID");start=finding.get("StartLine");end=finding.get("EndLine")
   if relative not in owned or rule!="generic-api-key" or type(start) is not int or type(end) is not int or start!=end:raise OracleError("finding identity")
   canonical=PREFIX+"/"+relative;identifier=stable_id(head,PIN,canonical,rule,start,end)
   if identifier in seen or identifier not in decisions:raise OracleError("finding set")
   seen.add(identifier);decision=decisions[identifier];context=None
   if relative.startswith("test/") and relative.endswith((".test.js",".behavior.js")):
    try:context=oracle_context(relative,pinned[relative],start,pinned,owned,graph);classification="expected_custom_error_assertion"
    except OracleError:classification="not_proven"
   elif relative.startswith("test/") and relative.endswith(".json") and der_semantics(pinned[relative],start):
    classification="ecdsa_public_key_der";context={"kind":"public_ec_der"}
   else:classification="not_proven"
   expected={"head":head,"parent_submodule_commit":PARENT_PIN,"submodule_commit":PIN,"relative_path":canonical,
    "rule_id":rule,"line_start":start,"line_end":end,"file_sha256":sha(pinned[relative]),"source_manifest_sha256":manifest_sha}
   if any(decision.get(k)!=v for k,v in expected.items()) or decision.get("source_review")!=classification or classification=="not_proven":raise OracleError("semantic disagreement")
   if (repo/canonical).read_bytes()!=pinned[relative]:raise OracleError("working source drift")
   records.append({"finding_id":identifier,"relative_path":canonical,"rule_id":rule,"line_start":start,"line_end":end,
    "file_sha256":sha(pinned[relative]),"source_object_id":owned[relative]["object_id"],
    "classification":classification,"verdict":"confirmed_noncredential_fixture","context":context})
   counts[classification]+=1
  del findings
 if raw_parent is None or Path(raw_parent).exists():raise OracleError("raw report retained")
 if len(records)!=158 or set(decisions)!=seen or counts!=Counter({"expected_custom_error_assertion":83,"ecdsa_public_key_der":75}):raise OracleError("unexpected tranche")
 oracle_path=Path(__file__).resolve();python_path=Path(sys.executable).resolve();crypto_path=Path(cryptography.__file__).resolve()
 attestation={"schema":"m0_3c_r9_semantic_attestation","head":head,"parent_submodule_commit":PARENT_PIN,
  "submodule_commit":PIN,"decisions_sha256":sha(decision_bytes),"source_manifest_sha256":manifest_sha,
  "scanner_sha256":SCANNER_SHA256,"scanner_version":scanner_version,
  "verifier":{"name":"m0_3c_semantic_oracle_v3","path":str(oracle_path.relative_to(repo)),"sha256":sha(oracle_path.read_bytes()),
   "python_path":str(python_path),"python_sha256":sha(python_path.read_bytes()),"python_version":"Python "+platform.python_version(),
   "cryptography_version":cryptography.__version__,"cryptography_module_path":str(crypto_path),
   "cryptography_module_sha256":sha(crypto_path.read_bytes())},
  "records":sorted(records,key=lambda x:x["finding_id"])}
 descriptor,temp=tempfile.mkstemp(prefix="."+output.name+".",dir=output.parent)
 try:
  with os.fdopen(descriptor,"wb") as stream:stream.write(encoded(attestation));stream.flush();os.fsync(stream.fileno())
  os.replace(temp,output)
 finally:
  if os.path.exists(temp):os.unlink(temp)
 return {"schema":"m0_3c_r9_semantic_attestation_result","attestation":str(output),"attestation_sha256":sha(output.read_bytes()),
  "finding_count":158,"path_count":len({r["relative_path"] for r in records}),"proof_counts":dict(sorted(counts.items())),
  "raw_removed":True,"scanner_exit":1,"scanner_command":scanner_command,"scanner_cwd":str(source)}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ("repo","scanner","decisions","output"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 try:result=run(a.repo,a.scanner,a.decisions,a.output)
 except Exception as exc:
  print(json.dumps({"schema":"m0_3c_r9_semantic_attestation_result","status":"failure","type":type(exc).__name__},sort_keys=True));return 1
 print(json.dumps(result,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
