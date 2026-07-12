from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("validate_docs.py")
SPEC = importlib.util.spec_from_file_location("validate_docs", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class DocumentationValidatorTests(unittest.TestCase):
    def test_current_documents_require_verification_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            document = root / "README.md"
            document.write_text("# Test\n", encoding="utf-8")
            (docs / "documentation-manifest.json").write_text(
                json.dumps(
                    {
                        "current_architecture_version": "0.8.0",
                        "documents": [
                            {"path": "README.md", "lifecycle": "current"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(module, "ROOT", root), mock.patch.object(
                module, "MANIFEST_PATH", docs / "documentation-manifest.json"
            ):
                self.assertIn("README.md lacks Last verified metadata", module.validate())

    def test_local_file_uri_is_rejected(self) -> None:
        errors: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_text("# Test\n", encoding="utf-8")
            with mock.patch.object(module, "ROOT", root):
                module._validate_relative_links(path, "[bad](file:///C:/private)", errors)
        self.assertEqual(errors, ["README.md contains a local file URI"])


if __name__ == "__main__":
    unittest.main()
