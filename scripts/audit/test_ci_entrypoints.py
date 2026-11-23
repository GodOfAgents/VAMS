"""Exercise clean-process imports and relocated source bindings used by CI."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CIEntryPointTests(unittest.TestCase):
    def test_audit_direct_script_imports_packages_with_only_the_ci_root(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [
            sys.executable, "scripts/audit/test_audit_program.py",
            "CardanoPackageConsistencyTests.test_consistent_synthetic_package_checks_bytes_only",
            "AuditProgramTests.test_deployment_manifests_require_both_networks_and_stage",
        ]
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                text=True, check=False, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ran 2 tests", result.stderr)

    def test_provenance_test_import_uses_its_relocated_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vams relocated imports ") as directory:
            root = Path(directory)
            for relative in ("scripts/remediation/test_m3_1b_r9_provenance.py",
                             "scripts/remediation/verify_m3_1b_r9.py"):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            code = (
                "import importlib.util, pathlib, sys; "
                "root=pathlib.Path(sys.argv[1]).resolve(); "
                "path=root/'scripts/remediation/test_m3_1b_r9_provenance.py'; "
                "spec=importlib.util.spec_from_file_location('relocated_provenance',path); "
                "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
                "assert module.ROOT == root, module.ROOT; "
                "assert module.MODULE_PATH == root/'scripts/remediation/verify_m3_1b_r9.py'; "
                "assert pathlib.Path(module.R11.__file__).resolve() == module.MODULE_PATH; "
                "print('relocated import verified')"
            )
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run([sys.executable, "-I", "-c", code, str(root)],
                                    cwd=root, env=environment, capture_output=True,
                                    text=True, check=False, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("relocated import verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
