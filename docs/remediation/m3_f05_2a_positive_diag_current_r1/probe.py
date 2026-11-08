from __future__ import annotations
import importlib.util, json, pathlib, sys
script=pathlib.Path("scripts/remediation/test_f05_2a_authority_bootstrap_public.py").resolve()
spec=importlib.util.spec_from_file_location("vams_f05_diag",script)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)
original=mod._evaluate
observed={}
def capture(aiken,code,context,work,label):
 result=original(aiken,code,context,work,label)
 observed["label"]=label
 observed["evaluation"]={k:result.get(k) for k in ("accepted","exit","cpu","mem","diagnostic")}
 return result
mod._evaluate=capture
try:
 mod._run_suite(pathlib.Path(sys.argv[1]).resolve())
 observed["harness_result"]="unexpectedly_completed"
except AssertionError as exc:
 observed["harness_error"]=str(exc)
pathlib.Path(sys.argv[2]).write_text(json.dumps(observed,indent=2)+"
")
print(json.dumps(observed,sort_keys=True))
