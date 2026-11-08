"""SkillOps version shape checks against actual local SDK source; no external effects."""
from pathlib import Path
import unittest
from unittest.mock import patch

from neuron.services import registry_client as registry


BLOCK = "llama_inference"
CAPABILITY_ROOT = "0xc1f99dc0f6f4b462b8618dad045917bf522ee16ada153989a626a2152860dc66"
# Fixed canonical-JSON/SHA-256 compatibility vectors, independent of the validator.
VALID_VERSION_HASHES = {
    1: "0xc2a8e6ff5cc45b95b9c6f381b357f98710b18a8334aa5b0d53b9afc431fcae0b",
    2: "0xb73170c6e544a01f7214cb4387c729d140454ab30a972916ca9f6cecc0cc0561",
    256: "0xaff5af8d500b88c7384c923c9cb2df59a309f5c562e742753bbe814bcc10f0a1",
    2**64: "0x047b2cfaa9e0dde209fafef37921d0fe0d1d775965190a3f44eb9310c8504664",
    2**128: "0xd744274749523db7e7c9c87fc5c75e49fe9f19288d1694184b3ac258feed3ab7",
}


class ServiceManifestVersionTypeTests(unittest.TestCase):
    def setUp(self):
        runtime = patch.dict("os.environ", {"VAMS_ENV": "test"}, clear=True)
        runtime.start()
        self.addCleanup(runtime.stop)
        self.client = registry.ServiceBlockClient(simulation=True)

    def manifest(self, version=1, **metadata):
        return registry.ServiceBlockManifest(
            block_name=BLOCK,
            permission_scopes=["EXTERNAL_READ"],
            manifest_version=version,
            **metadata,
        )

    def assert_versions_rejected(self, versions, **metadata):
        for version in versions:
            with self.subTest(version=repr(version), metadata=metadata):
                with self.assertRaises(ValueError):
                    self.client.validate_skillops_manifest(self.manifest(version, **metadata))

    def test_actual_lane_source_is_loaded(self):
        expected = Path(__file__).resolve().parents[1] / "services" / "registry_client.py"
        self.assertEqual(Path(registry.__file__).resolve(), expected)

    def test_boolean_versions_rejected(self):
        self.assert_versions_rejected((True, False))

    def test_float_versions_rejected_including_integral_and_nonfinite(self):
        self.assert_versions_rejected((1.0, 1.5, float("nan"), float("inf"),
                                       float("-inf"), 0.0, -1.0))

    def test_none_strings_bytes_and_containers_rejected(self):
        self.assert_versions_rejected((None, "1", "", b"1", [], {}, (), set()))

    def test_zero_and_negative_integers_rejected(self):
        self.assert_versions_rejected((0, -1, -(2**128)))

    def test_invalid_version_rejected_before_hashing(self):
        for version in (True, 1.0, 1.5, float("nan"), float("inf"), None, "1", []):
            with self.subTest(version=repr(version)):
                with patch.object(registry.ServiceBlockManifest, "computed_manifest_hash") as hashed:
                    with self.assertRaises(ValueError):
                        self.client.validate_skillops_manifest(self.manifest(version))
                    hashed.assert_not_called()

    def test_default_version_serialization_and_hash_preserved(self):
        manifest = registry.ServiceBlockManifest(block_name=BLOCK, permission_scopes=["EXTERNAL_READ"])
        self.assertIs(self.client.validate_skillops_manifest(manifest), manifest)
        self.assertEqual(manifest.to_dict(), {
            "block_name": BLOCK,
            "manifest_hash": VALID_VERSION_HASHES[1],
            "capability_root": CAPABILITY_ROOT,
            "manifest_version": 1,
            "permission_scopes": ["EXTERNAL_READ"],
            "permissions_bitmap": 1,
        })

    def test_positive_integer_versions_keep_identity_serialization_and_hashes(self):
        for version, expected_hash in VALID_VERSION_HASHES.items():
            with self.subTest(version=version):
                manifest = self.manifest(version)
                self.assertIs(self.client.validate_skillops_manifest(manifest), manifest)
                self.assertEqual(manifest.to_dict()["manifest_version"], version)
                self.assertIs(type(manifest.to_dict()["manifest_version"]), int)
                self.assertEqual(manifest.computed_manifest_hash(), expected_hash)
                self.assertEqual(manifest.computed_capability_root(), CAPABILITY_ROOT)

    def test_existing_explicit_metadata_treatment_preserved(self):
        # Existing overrides are metadata, not signature or authenticity evidence.
        expected_root = "0x" + "a" * 64
        expected_hash = "0x" + "b" * 64
        manifest = self.manifest(2, capability_root=expected_root, manifest_hash=expected_hash)
        self.assertIs(self.client.validate_skillops_manifest(manifest), manifest)
        self.assertEqual(manifest.to_dict()["capability_root"], expected_root)
        self.assertEqual(manifest.to_dict()["manifest_hash"], expected_hash)
        self.assertEqual(manifest.to_dict()["manifest_version"], 2)

    def test_explicit_metadata_cannot_bypass_invalid_version_guard(self):
        self.assert_versions_rejected((True, 1.5, float("nan"), float("inf")),
                                      capability_root="0x" + "a" * 64,
                                      manifest_hash="0x" + "b" * 64)

    def test_empty_optional_metadata_retains_existing_hash_fallback(self):
        manifest = self.manifest(capability_root="", manifest_hash="")
        self.assertIs(self.client.validate_skillops_manifest(manifest), manifest)
        self.assertEqual(manifest.computed_capability_root(), CAPABILITY_ROOT)
        self.assertEqual(manifest.computed_manifest_hash(), VALID_VERSION_HASHES[1])


if __name__ == "__main__":
    unittest.main()
