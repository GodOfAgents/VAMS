"""Real Git regressions for clean, byte-bound historical source evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.audit import audit_program


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_PATHS = (
    "scripts/remediation/build_f05_2a_proof_other_network_mutant_r1.py",
    "scripts/remediation/build_f05_2a_proof_other_validator_hash_r1.py",
    "scripts/remediation/test_f05_2a_proof_other_network_mutant_r1.py",
    "scripts/remediation/test_f05_2a_proof_other_validator_hash_r1.py",
)
REFRESH_PATHS = (
    "contracts/script/DeployTestnet.s.sol",  # CRLF
    "gateway/heartbeat_consent_signatures_v2.py",  # Mixed LF/CRLF
)


class SourceByteIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory(prefix="vams Git byte evidence ")
        self.addCleanup(holder.cleanup)
        self.folder = Path(holder.name)
        self.repo = self.folder/"source"
        self.repo.mkdir()
        empty = self.folder/"empty-config"
        empty.write_text("")
        hooks = self.folder/"empty-hooks"
        hooks.mkdir()
        self.environment = {name:os.environ[name] for name in ("HOME","PATH","LANG","LC_ALL","SYSTEMROOT","TEMP","TMP","TMPDIR") if name in os.environ}
        self.environment.update(GIT_CONFIG_NOSYSTEM="1",GIT_CONFIG_GLOBAL=str(empty),GIT_ATTR_NOSYSTEM="1")
        binary = shutil.which("git")
        self.assertIsNotNone(binary,"These Git integrity regressions require Git")
        self.command = [binary,"-c","user.name=VAMS synthetic fixture","-c","user.email=fixture@example.invalid","-c","core.hooksPath="+str(hooks)]
        self.git("init","-q")
        self.git("config","core.autocrlf","false")
        self.git("config","core.attributesFile",str(empty))
        self.originals = {name:(ROOT/name).read_bytes() for name in (*HISTORICAL_PATHS, *REFRESH_PATHS)}

    def git(self, *arguments: str, root: Path | None = None, data: bytes | None = None) -> bytes:
        result = subprocess.run(self.command+list(arguments),cwd=root or self.repo,
                                env=self.environment,input=data,capture_output=True,
                                check=False,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors="replace"))
        return result.stdout

    def prepare(self, *, old_policy: bool = False) -> None:
        attributes = (ROOT/".gitattributes").read_text()
        if old_policy:
            attributes = "\n".join(line for line in attributes.splitlines()
                                   if not any(line.lstrip("/").startswith(name+" ") for name in self.originals))+"\n"
        (self.repo/".gitattributes").write_text(attributes)
        self.git("add","--",".gitattributes")
        for name,data in self.originals.items():
            self.assertIn(b"\r\n", data, "Expected retained CRLF bytes")
            path = self.repo/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            # Preserve the known committed blob, bypassing conversion only
            # while constructing this private regression repository.
            blob = self.git("hash-object","-w","--no-filters","--stdin",data=data).decode().strip()
            self.git("update-index","--add","--cacheinfo","100644",blob,name)
        self.git("commit","-q","-m","test fixture with retained source bytes")

    def manifest_dirty(self, root: Path | None = None) -> bool:
        source = root or self.repo
        output = self.folder/"synthetic-unit-manifest.json"
        # Run the real manifest generator and real Git status. Only the private
        # repository/evidence location changes; job statuses are synthetic unit
        # inputs, never release evidence or promotion approvals.
        with (mock.patch.object(audit_program,"ROOT",source),
              mock.patch.object(audit_program,"EVIDENCE_DIR",source/"absent-unit-evidence"),
              mock.patch.dict(os.environ,{"GITHUB_ACTIONS":"false"})):
            audit_program.generate_manifest(output,[name+"=success" for name in audit_program.REQUIRED_EVIDENCE_RESULTS])
        result = json.loads(output.read_text())
        self.assertEqual(result["environment"],"local")
        return result["dirty"]

    def test_fresh_checkout_preserves_evidence_bytes_and_clean_manifest(self) -> None:
        self.prepare()
        clone = self.folder/"fresh clone"
        self.git("clone","-q","--no-local",str(self.repo),str(clone))
        self.assertEqual(self.git("status","--porcelain",root=clone),b"")
        self.assertFalse(self.manifest_dirty(clone))
        for name,data in self.originals.items():
            with self.subTest(path=name):
                self.assertEqual((clone/name).read_bytes(),data)
                self.assertEqual(self.git("show","HEAD:"+name,root=clone),data)
                attributes = self.git("check-attr","text","diff","--",name,root=clone).decode()
                self.assertIn(": text: unset",attributes)
                self.assertIn(": diff: set",attributes)

    def test_previous_policy_reports_dirty_even_when_raw_bytes_match(self) -> None:
        self.prepare(old_policy=True)
        for name,data in self.originals.items():
            self.assertEqual((self.repo/name).read_bytes(),data)
            self.assertEqual(self.git("show","HEAD:"+name),data)
        self.assertTrue(self.git("status","--porcelain"))
        self.assertTrue(self.manifest_dirty())

    def test_stat_revalidation_preserves_clean_status_for_legacy_blobs(self) -> None:
        self.prepare()
        clone = self.folder / "refresh checkout"
        self.git("clone", "-q", "--no-local", str(self.repo), str(clone))
        self.assertEqual(self.git("status", "--porcelain", root=clone), b"")
        for name in REFRESH_PATHS:
            path = clone / name
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns - 120_000_000_000))
            self.assertEqual(path.read_bytes(), self.originals[name])
        self.assertEqual(self.git("status", "--porcelain", root=clone), b"")
        self.assertFalse(self.manifest_dirty(clone))

    def test_byte_and_lineending_changes_still_fail_cleanliness_and_show_text_diffs(self) -> None:
        self.prepare()
        for name,data in self.originals.items():
            variants = (
                ("byte change", data + b"# byte_change_marker\n"),
                ("line ending change", data.replace(b"\r\n", b"\n")),
            )
            for change, changed in variants:
                with self.subTest(path=name, change=change):
                    (self.repo/name).write_bytes(changed)
                    self.assertTrue(self.manifest_dirty())
                    diff = self.git("diff","--no-ext-diff","--",name)
                    self.assertIn(b"@@",diff)
                    self.assertNotIn(b"Binary files",diff)
                    (self.repo/name).write_bytes(data)
                    self.assertFalse(self.manifest_dirty())

    def test_untracked_sources_remain_dirty_and_other_python_files_keep_lf_policy(self) -> None:
        self.prepare()
        path = self.repo/"new_source.py"
        path.write_bytes(b"value = 1\r\n")
        self.assertTrue(self.manifest_dirty())
        self.git("add","--","new_source.py")
        self.assertEqual(self.git("show",":new_source.py"),b"value = 1\n")
        self.assertTrue(self.manifest_dirty())

    def test_external_generated_evidence_keeps_source_checks_strict(self) -> None:
        self.prepare()
        external = self.folder/"runner temporary evidence"
        external.mkdir()
        data = b'{"classification":"synthetic unit artifact, no signature acceptance"}\n'
        (external/"audit-evidence.json").write_bytes(data)
        self.assertFalse(self.manifest_dirty())
        inside = self.repo/"docs/audit/evidence/audit-evidence.json"
        inside.parent.mkdir(parents=True)
        inside.write_bytes(data)
        self.assertTrue(self.manifest_dirty(),"downloaded evidence inside checkout must remain visible")
        inside.unlink()
        self.assertFalse(self.manifest_dirty())
        path = self.repo/HISTORICAL_PATHS[0]
        path.write_bytes(path.read_bytes()+b"# actual source change\n")
        self.assertTrue(self.manifest_dirty(),"external artifacts cannot hide source changes")


if __name__ == "__main__":
    unittest.main()
