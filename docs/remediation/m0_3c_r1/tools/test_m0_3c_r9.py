"""R9 lifecycle snapshot and semantic-independence regressions."""
from __future__ import annotations
import copy,hashlib,importlib.util,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS))
import m0_3c_adjudicator as A
import m0_3c_context as C
import m0_3c_filesystem as F
import m0_3c_r7_validate as V
import m0_3c_semantic_oracle as O
REPO=Path("/home/GodOfAgents/code/VAMS-testnet")
R7=Path("/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r7-20260920T164522Z-829ab544571f")
SCANNER=Path("/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks")
def enc(v):return (json.dumps(v,sort_keys=True,indent=2)+"\n").encode()
def rebuild(root):
 (root/"SHA256SUMS").write_text("".join(hashlib.sha256((root/n).read_bytes()).hexdigest()+"  "+n+"\n" for n in sorted(V.ART)))
def prepare(root):
 shutil.copytree(R7,root)
 env=json.loads((root/"environment.json").read_text());env["evidence_output"]=str(root);(root/"environment.json").write_bytes(enc(env))
 att=root/"semantic-attestation.json";att.unlink()
 result=O.run(REPO,SCANNER,REPO/"docs/remediation/m0_3c_r1/decisions.json",att)
 result["attestation"]=str(att);(root/"semantic-oracle-result.json").write_bytes(enc(result))
 reviewed=json.loads((root/"reviewed-hashes.json").read_text())
 for name in list(reviewed["files"]):reviewed["files"][name]=hashlib.sha256(Path(name).read_bytes()).hexdigest()
 (root/"reviewed-hashes.json").write_bytes(enc(reviewed));rebuild(root)
 return root
class R9LifecycleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.hold=tempfile.TemporaryDirectory(prefix="m03c-r9-valid-");cls.base=prepare(Path(cls.hold.name)/"evidence")
 @classmethod
 def tearDownClass(cls):cls.hold.cleanup()
 def package(self):
  td=tempfile.TemporaryDirectory(prefix="m03c-r9-case-");root=Path(td.name)/"evidence";shutil.copytree(self.base,root);env=json.loads((root/"environment.json").read_text());env["evidence_output"]=str(root);(root/"environment.json").write_bytes(enc(env));oracle=json.loads((root/"semantic-oracle-result.json").read_text());oracle["attestation"]=str(root/"semantic-attestation.json");(root/"semantic-oracle-result.json").write_bytes(enc(oracle));rebuild(root);return td,root
 def attack_after_snapshot(self,name,mutate):
  td,root=self.package();original=F.ArtifactSnapshot.get_bytes;done=False
  def wrapped(snapshot,item):
   nonlocal done
   value=original(snapshot,item)
   if not done:
    done=True;mutate(root)
   return value
  try:
   with mock.patch.object(F.ArtifactSnapshot,"get_bytes",wrapped),self.assertRaises(V.Error) as caught:V.validate(REPO,root)
   self.assertIn(str(caught.exception),{"filesystem.race","filesystem.topology","filesystem.file","filesystem.directory"})
  finally:td.cleanup()
 def test_unchanged_control(self):
  td,root=self.package()
  try:self.assertEqual(V.validate(REPO,root)["status"],"pass")
  finally:td.cleanup()
 def test_atomic_inode_replacement(self):
  def change(root):
   p=root/"REVIEW.md";q=root/".replacement";q.write_bytes(p.read_bytes());os.replace(q,p)
  self.attack_after_snapshot("atomic_inode",change)
 def test_json_artifact_replacement(self):
  def change(root):
   p=root/"commands.json";doc=json.loads(p.read_text());doc[0]["stdout_size"]+=1;q=root/".json-replacement";q.write_bytes(enc(doc));os.replace(q,p)
  self.attack_after_snapshot("json_artifact",change)
 def test_same_inode_write(self):
  self.attack_after_snapshot("inplace",lambda r:(r/"commands.json").write_bytes((r/"commands.json").read_bytes()))
 def test_truncate_extend_restore(self):
  def change(root):
   p=root/"commands.json";raw=p.read_bytes()
   with p.open("r+b") as f:f.truncate(max(1,len(raw)//2));f.write(b"x"*64);f.truncate(len(raw))
   p.write_bytes(raw)
  self.attack_after_snapshot("restore",change)
 def test_manifest_replacement(self):
  def change(root):
   p=root/"SHA256SUMS";q=root/".manifest";q.write_bytes(p.read_bytes());os.replace(q,p)
  self.attack_after_snapshot("manifest",change)
 def test_directory_entry_replacement(self):
  def change(root):
   old=root/"gate.old";os.rename(root/"gate",old);shutil.copytree(old,root/"gate")
  self.attack_after_snapshot("directory",change)
 def test_mutation_after_parse_before_acceptance(self):
  td,root=self.package();original=V._validate_snapshot
  def wrapped(repo,e,snapshot):
   result=original(repo,e,snapshot);p=root/"summary.json";p.write_bytes(p.read_bytes());return result
  try:
   with mock.patch.object(V,"_validate_snapshot",wrapped),self.assertRaises(V.Error) as caught:V.validate(REPO,root)
   self.assertEqual(str(caught.exception),"filesystem.race")
  finally:td.cleanup()
 def test_no_post_snapshot_evidence_path_read(self):
  td,root=self.package();rt=Path.read_text;rb=Path.read_bytes
  def deny_text(path,*a,**k):
   if path==root or root in path.parents:raise AssertionError("evidence pathname reopen")
   return rt(path,*a,**k)
  def deny_bytes(path,*a,**k):
   if path==root or root in path.parents:raise AssertionError("evidence pathname reopen")
   return rb(path,*a,**k)
  try:
   with mock.patch.object(Path,"read_text",deny_text),mock.patch.object(Path,"read_bytes",deny_bytes):
    self.assertEqual(V.validate(REPO,root)["status"],"pass")
  finally:td.cleanup()
class R9SemanticIndependenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.decisions=json.loads((REPO/"docs/remediation/m0_3c_r1/decisions.json").read_text())["records"];cls.blobs,_=A.direct_tree(REPO);target=REPO/A.PREFIX;cls.pinned={p:(target/p).read_bytes() for p in cls.blobs};cls.graph=O.oracle_graph(cls.pinned)
  cls.decision=next(x for x in cls.decisions if x["source_review"]=="expected_custom_error_assertion");cls.rel=cls.decision["relative_path"][len(A.PREFIX)+1:]
 def test_oracle_has_no_semantic_catalogs(self):
  self.assertFalse(hasattr(O,"ORACLE_ERROR_POLICY"));self.assertFalse(hasattr(O,"ORACLE_TARGETS"))
 def test_production_catalog_corruption_does_not_change_oracle(self):
  baseline=O.oracle_context(self.rel,self.pinned[self.rel],self.decision["line_start"],self.pinned,self.blobs,self.graph)
  with mock.patch.object(C,"ERROR_POLICY",{}),mock.patch.object(C,"TARGETS",{}):
   observed=O.oracle_context(self.rel,self.pinned[self.rel],self.decision["line_start"],self.pinned,self.blobs,self.graph)
  self.assertEqual(observed,baseline)
 def test_oracle_corruption_does_not_change_production(self):
  report=[{"File":self.decision["relative_path"],"RuleID":self.decision["rule_id"],"StartLine":self.decision["line_start"],"EndLine":self.decision["line_end"]}]
  before=A.production_semantics(REPO,report,A.PIN,self.blobs)
  with mock.patch.object(O,"_derive_targets",side_effect=O.OracleError("corrupt")):
   after=A.production_semantics(REPO,report,A.PIN,self.blobs)
  self.assertEqual(before,after)
 def test_disagreement_fails_public_gate(self):
  report=[{"File":self.decision["relative_path"],"RuleID":self.decision["rule_id"],"StartLine":self.decision["line_start"],"EndLine":self.decision["line_end"]}]
  state=A.provenance(REPO);manifest=A.base.digest(A.base.encoded(A.base.source_manifest(REPO)));context=O.oracle_context(self.rel,self.pinned[self.rel],self.decision["line_start"],self.pinned,self.blobs,self.graph)
  semantic={"finding_id":self.decision["finding_id"],"relative_path":self.decision["relative_path"],"rule_id":self.decision["rule_id"],"line_start":self.decision["line_start"],"line_end":self.decision["line_end"],"file_sha256":self.decision["file_sha256"],"source_object_id":self.blobs[self.rel]["object_id"],"classification":self.decision["source_review"],"verdict":"confirmed_noncredential_fixture","context":context}
  semantic["context"]["error_selector"]="00000000"
  records=A.build_records(report,head=state["head"],commit=state["submodule_commit"],decisions=[self.decision],repo=REPO,state=state,manifest_sha256=manifest,owned_blobs=self.blobs,semantic_records={self.decision["finding_id"]:semantic})
  self.assertEqual(records[0]["disposition"],"unresolved");self.assertFalse(A.approved_gate(records,[self.decision],{self.decision["finding_id"]:semantic}))
if __name__=="__main__":unittest.main()
