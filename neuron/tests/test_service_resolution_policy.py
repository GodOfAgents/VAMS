"""Public Service Block resolution boundaries; no provisioning or external calls."""
from pathlib import Path
import unittest
from unittest.mock import patch

from neuron.services import registry_client as registry
from neuron.services.macro_blocks import MACRO_BLOCKS
from neuron.composer.composer import VAMSResourceComposer

BLOCK = "x402_payments"  # Last member of the starter macro.
MACRO = "AI_AGENT_STARTER_PACK"


class ServiceResolutionPolicyTests(unittest.TestCase):
    def setUp(self):
        runtime = patch.dict("os.environ", {"VAMS_ENV": "test"}, clear=True)
        runtime.start()
        self.addCleanup(runtime.stop)
        self.client = registry.ServiceBlockClient(simulation=True)
        for mapping in (registry._SERVICE_BLOCK_MEMORY_POLICIES, registry._SERVICE_BLOCK_PERMISSION_SCOPES):
            restore = patch.dict(mapping)
            restore.start()
            self.addCleanup(restore.stop)

    def assert_both_reject(self, error, message):
        for name, invoke in (("single", lambda: self.client.resolve_blueprint(BLOCK)),
                             ("macro", lambda: self.client.resolve_macro(MACRO))):
            with self.subTest(boundary=name), self.assertRaisesRegex(error, message):
                invoke()

    def test_actual_lane_source_is_loaded(self):
        expected = Path(__file__).resolve().parents[1] / "services" / "registry_client.py"
        self.assertEqual(Path(registry.__file__).resolve(), expected)

    def test_missing_memory_policy_rejected_in_single_and_macro_resolution(self):
        del registry._SERVICE_BLOCK_MEMORY_POLICIES[BLOCK]
        with self.assertRaisesRegex(KeyError, "Missing memory policy"):
            self.client.get_block(BLOCK)
        self.assert_both_reject(KeyError, "Missing memory policy")

    def test_unknown_memory_policy_rejected_in_single_and_macro_resolution(self):
        registry._SERVICE_BLOCK_MEMORY_POLICIES[BLOCK] = "UNREVIEWED_PROMPT_MEMORY"
        self.assert_both_reject(ValueError, "Unknown service block memory policy")

    def test_missing_manifest_rejected_in_single_and_macro_resolution(self):
        del registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK]
        self.assert_both_reject(KeyError, "Missing SkillOps manifest")

    def test_empty_permissions_rejected_in_single_and_macro_resolution(self):
        registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK] = []
        self.assert_both_reject(ValueError, "must declare at least one permission")

    def test_unknown_permission_rejected_in_single_and_macro_resolution(self):
        registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK] = ["EXTERNAL_READ", "ROOT_WALLET"]
        self.assert_both_reject(ValueError, "Unknown service block permission scope")

    def test_persistent_mutation_without_review_policy_rejected(self):
        registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK] = ["EXTERNAL_READ", "PERSISTENT_MUTATION"]
        self.assert_both_reject(ValueError, "Persistent mutation permission requires review-gated memory policy")

    def test_all_declared_memory_policies_remain_valid_metadata(self):
        for policy in registry.ServiceBlockMemoryPolicy:
            registry._SERVICE_BLOCK_MEMORY_POLICIES[BLOCK] = policy
            registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK] = ["EXTERNAL_READ"]
            if policy is registry.ServiceBlockMemoryPolicy.PERSISTENT_MUTATING_REQUIRES_REVIEW:
                registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK].append("PERSISTENT_MUTATION")
            with self.subTest(policy=policy.value):
                self.assertIs(self.client.resolve_blueprint(BLOCK), registry._SERVICE_BLOCK_BLUEPRINTS[BLOCK])
                self.assertEqual([bp.name for bp in self.client.resolve_macro(MACRO)], MACRO_BLOCKS[MACRO]["blocks"])
                metadata = self.client.get_block(BLOCK)
                self.assertEqual(metadata["memory_policy"], policy.value)
                self.assertEqual(metadata["memory_policy_requires_review"], policy is registry.ServiceBlockMemoryPolicy.PERSISTENT_MUTATING_REQUIRES_REVIEW)
        # This checks declaration compatibility, never execution/review approval.

    def test_valid_catalogue_and_macro_shapes_identity_order_preserved(self):
        for name, bp in registry._SERVICE_BLOCK_BLUEPRINTS.items():
            with self.subTest(block=name):
                before = bp.to_dict()
                self.assertIs(self.client.resolve_blueprint(name), bp)
                self.assertEqual(bp.to_dict(), before)
        for name, macro in MACRO_BLOCKS.items():
            resolved = self.client.resolve_macro(name)
            self.assertEqual([bp.name for bp in resolved], macro["blocks"])
            self.assertTrue(all(bp is registry._SERVICE_BLOCK_BLUEPRINTS[bp.name] for bp in resolved))

    def test_unknown_block_and_macro_still_rejected(self):
        with self.assertRaisesRegex(KeyError, "Unknown service block"):
            self.client.resolve_blueprint("no-such-block")
        with self.assertRaisesRegex(KeyError, "Unknown macro"):
            self.client.resolve_macro("no-such-macro")

    def test_invalid_last_member_rejected_before_composer_provision_call(self):
        registry._SERVICE_BLOCK_PERMISSION_SCOPES[BLOCK] = ["ROOT_WALLET"]
        composer = VAMSResourceComposer(service_client=self.client, simulation=True)
        with patch.object(composer, "provision", side_effect=AssertionError("Provisioning is outside these tests")) as provision:
            for name, invoke in (("single", lambda: composer.provision_service_block(BLOCK)),
                                 ("macro", lambda: composer.provision_macro_block(MACRO))):
                with self.subTest(boundary=name), self.assertRaisesRegex(ValueError, "Unknown service block permission scope"):
                    invoke()
            provision.assert_not_called()


if __name__ == "__main__":
    unittest.main()
