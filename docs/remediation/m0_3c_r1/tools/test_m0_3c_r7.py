"""R7 regressions for execution context and physical evidence boundaries."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS))
import m0_3c_adjudicator as A
import m0_3c_context as C
import m0_3c_filesystem as F
import m0_3c_semantic_oracle as O

ROOT=Path("/home/GodOfAgents/code/VAMS-testnet")

class R7Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.decisions=json.loads((ROOT/"docs/remediation/m0_3c_r1/decisions.json").read_text())["records"]
  cls.blobs,_=A.direct_tree(ROOT)
  cls.report=[{"File":d["relative_path"],"RuleID":d["rule_id"],"StartLine":d["line_start"],"EndLine":d["line_end"]} for d in cls.decisions]
  cls.production=A.production_semantics(ROOT,cls.report,A.PIN,cls.blobs)
  target=ROOT/A.PREFIX
  cls.pinned={p:(target/p).read_bytes() for p in cls.blobs}
  cls.oracle_graph=O.oracle_graph(cls.pinned)

 def test_all_real_contexts_agree_without_shared_parser(self):
  counts={"expected_custom_error_assertion":0,"ecdsa_public_key_der":0}
  for d in self.decisions:
   rel=d["relative_path"][len(A.PREFIX)+1:]
   proof,_,context=self.production[(d["relative_path"],d["line_start"],d["line_end"])]
   if proof=="expected_custom_error_assertion":
    independent=O.oracle_context(rel,self.pinned[rel],d["line_start"],self.pinned,self.blobs,self.oracle_graph)
    self.assertEqual(context,independent)
   else:self.assertEqual(context,{"kind":"public_ec_der"})
   counts[proof]+=1
  self.assertEqual(counts,{"expected_custom_error_assertion":83,"ecdsa_public_key_der":75})

 def test_real_exact_target_transitive_and_used_library_routes_exist(self):
  contexts=[value[2] for value in self.production.values() if value[0]=="expected_custom_error_assertion"]
  self.assertTrue(any(c["reachability_chains"][0]["containers"][0]["name"]==c["declaration_owner"]["name"] for c in contexts))
  self.assertTrue(any(len(chain["containers"])>1 and chain["containers"][-1]["kind"]=="interface" for c in contexts for chain in c["reachability_chains"]))
  self.assertTrue(any(chain["containers"][-1]["kind"]=="library" for c in contexts for chain in c["reachability_chains"]))

 def test_wrong_signature_renamed_comment_string_and_ambiguous_declarations_reject(self):
  decision=next(d for d in self.decisions if d["source_review"]=="expected_custom_error_assertion" and self.production[(d["relative_path"],d["line_start"],d["line_end"])][2]["error_name"]=="ERC20InvalidReceiver")
  rel=decision["relative_path"][len(A.PREFIX)+1:];owner="contracts/interfaces/draft-IERC6093.sol"
  variants={
   "wrong_signature":lambda b:b.replace(b"error ERC20InvalidReceiver(address receiver);",b"error ERC20InvalidReceiver(uint256 receiver);",1),
   "renamed":lambda b:b.replace(b"ERC20InvalidReceiver",b"ERC20InvalidRecipient",1),
   "comment_only":lambda b:b.replace(b"error ERC20InvalidReceiver(address receiver);",b"// error ERC20InvalidReceiver(address receiver);",1),
   "string_only":lambda b:b.replace(b"error ERC20InvalidReceiver(address receiver);",b'string constant probe = "error ERC20InvalidReceiver(address receiver);";',1),
   "undeclared":lambda b:b.replace(b"error ERC20InvalidReceiver(address receiver);",b"",1),
  }
  for name,mutate in variants.items():
   pinned=dict(self.pinned);pinned[owner]=mutate(pinned[owner]);self.assertNotEqual(pinned[owner],self.pinned[owner])
   with self.subTest(name=name):
    with self.assertRaises(C.ContextError):C.resolve_context(rel,pinned[rel],decision["line_start"],pinned,self.blobs,C.build_index(pinned))
    with self.assertRaises(O.OracleError):O.oracle_context(rel,pinned[rel],decision["line_start"],pinned,self.blobs,O.oracle_graph(pinned))

 def test_repository_wide_name_match_cannot_classify(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);path=A.PREFIX+"/test/token/ERC20/Fake.test.js";p=root/path;p.parent.mkdir(parents=True)
   fixture="".join([
    ".to.be.revertedWithCustom",
    "Error(this.token, '",
    "ERC20InvalidReceiver",
    "')\n",
   ])
   p.write_text(fixture)
   self.assertEqual(A.source_proof(root,path,1,1,{"ERC20InvalidReceiver":[("contracts/unrelated.sol","20")]}),("not_proven","unreviewed"))

 def test_reachability_rejects_sibling_unrelated_import_only_and_ambiguity(self):
  base={
   "Target":{"path":"contracts/Target.sol","kind":"contract","bases":[],"body":"","edges":["Base"]},
   "Base":{"path":"contracts/Base.sol","kind":"contract","bases":[],"body":"","edges":["Owner"]},
   "Owner":{"path":"contracts/Owner.sol","kind":"interface","bases":[],"body":"error ERC20InvalidReceiver(address receiver);","edges":[]},
   "Sibling":{"path":"contracts/Sibling.sol","kind":"contract","bases":[],"body":"error ERC20InvalidReceiver(address receiver);","edges":[]},
  }
  self.assertEqual(C._chain(base,"Target","Owner","ERC20InvalidReceiver"),["Target","Base","Owner"])
  for mutate in ("unrelated","import_only","sibling","ambiguous"):
   graph=copy.deepcopy(base)
   if mutate in {"unrelated","import_only"}:graph["Target"]["edges"]=[]
   elif mutate=="sibling":graph["Target"]["body"]="error ERC20InvalidReceiver(address receiver);"
   else:graph["Base"]["body"]="error ERC20InvalidReceiver(address receiver);"
   with self.subTest(mutate=mutate),self.assertRaises(C.ContextError):C._chain(graph,"Target","Owner","ERC20InvalidReceiver")
  oracle={k:{"path":v["path"],"kind":v["kind"],"parents":[],"body":v["body"],"next":list(v["edges"])} for k,v in base.items()}
  self.assertEqual(O.oracle_route(oracle,"Target","Owner","ERC20InvalidReceiver"),["Target","Base","Owner"])
  oracle["Base"]["body"]="error ERC20InvalidReceiver(address receiver);"
  with self.assertRaises(O.OracleError):O.oracle_route(oracle,"Target","Owner","ERC20InvalidReceiver")

 def test_used_library_route_is_explicit(self):
  graph={
   "Target":{"path":"contracts/Target.sol","kind":"contract","bases":[],"body":"Lib.check();","edges":["Lib"]},
   "Lib":{"path":"contracts/Lib.sol","kind":"library","bases":[],"body":"error ERC1363InvalidReceiver(address receiver);","edges":[]},
  }
  self.assertEqual(C._chain(graph,"Target","Lib","ERC1363InvalidReceiver"),["Target","Lib"])

 def test_public_gate_rejects_every_context_rebinding(self):
  decision=next(d for d in self.decisions if d["source_review"]=="expected_custom_error_assertion")
  key=(decision["relative_path"],decision["line_start"],decision["line_end"]);context=self.production[key][2]
  semantic={"finding_id":decision["finding_id"],"relative_path":decision["relative_path"],"rule_id":decision["rule_id"],
   "line_start":decision["line_start"],"line_end":decision["line_end"],"file_sha256":decision["file_sha256"],
   "source_object_id":self.blobs[decision["relative_path"][len(A.PREFIX)+1:]]["object_id"],
   "classification":decision["source_review"],"verdict":"confirmed_noncredential_fixture","context":context}
  state=A.provenance(ROOT);manifest=A.base.digest(A.base.encoded(A.base.source_manifest(ROOT)))
  kwargs={"head":state["head"],"commit":state["submodule_commit"],"repo":ROOT,"state":state,"manifest_sha256":manifest,"owned_blobs":self.blobs}
  report=[{"File":decision["relative_path"],"RuleID":decision["rule_id"],"StartLine":decision["line_start"],"EndLine":decision["line_end"]}]
  records=A.build_records(report,decisions=[decision],semantic_records={decision["finding_id"]:semantic},**kwargs)
  self.assertTrue(A.approved_gate(records,[decision],{decision["finding_id"]:semantic}))
  mutations=[("missing",lambda x:x.pop("context")),("selector",lambda x:x["context"].__setitem__("error_selector","00000000")),
   ("target",lambda x:x["context"].__setitem__("call_target","this.other")),
   ("owner",lambda x:x["context"]["declaration_owner"].__setitem__("path","contracts/Other.sol")),
   ("chain",lambda x:x["context"]["reachability_chains"][0]["containers"].pop())]
  for name,change in mutations:
   altered=copy.deepcopy(semantic);change(altered)
   with self.subTest(name=name):
    changed=A.build_records(report,decisions=[decision],semantic_records={decision["finding_id"]:altered},**kwargs)
    self.assertEqual(changed[0]["disposition"],"unresolved")
    self.assertFalse(A.approved_gate(changed,[decision],{decision["finding_id"]:altered}))

 def test_filesystem_rejects_links_specials_unknown_and_empty_directories(self):
  cases=("symlink","hardlink","fifo","empty","unknown")
  for case in cases:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/"a.json").write_text("{}\n");(root/"SHA256SUMS").write_text("0"*64+"  a.json\n")
    if case=="symlink":os.symlink("a.json",root/"x")
    elif case=="hardlink":os.link(root/"a.json",root/"x")
    elif case=="fifo":os.mkfifo(root/"x")
    elif case=="empty":(root/"x").mkdir()
    else:(root/"x").write_text("x")
    with self.assertRaises(F.EvidenceTreeError):F.inspect_exact_tree(root,{"a.json"})

if __name__=="__main__":unittest.main()
