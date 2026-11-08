"""Source-level mutant regressions for the source54 TEE promotion scan."""

from pathlib import Path
import unittest

from mock_mode_promotion_scan import check_tee_sources


OVERLAY_ROOT = Path(__file__).resolve().parents[2]
PHALA_PATH = OVERLAY_ROOT / "neuron" / "sdk" / "phala_tee.py"
PLUGIN_PATH = OVERLAY_ROOT / "neuron" / "trust_plugins" / "tee_plugin.py"


class TeePromotionScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phala = PHALA_PATH.read_text(encoding="utf-8")
        cls.plugin = PLUGIN_PATH.read_text(encoding="utf-8")

    def assert_rejected(self, phala=None, plugin=None):
        errors = check_tee_sources(
            self.phala if phala is None else phala,
            self.plugin if plugin is None else plugin,
        )
        self.assertTrue(errors, "unsafe source mutation passed the TEE scanner")

    def test_candidate_tee_source_passes(self):
        self.assertEqual(check_tee_sources(self.phala, self.plugin), [])

    def test_unsafe_provider_json_claim_promotion_is_rejected(self):
        mutant = self.phala.replace(
            "valid=False,\n                provider_claim_valid=result[\"valid\"],",
            "valid=result[\"valid\"],\n                provider_claim_valid=result[\"valid\"],",
            1,
        )
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_caller_mapping_cannot_replace_ambient_policy(self):
        mutant = self.phala.replace(
            "ambient = load_runtime_policy(os.environ)",
            "ambient = load_runtime_policy(source)",
            1,
        )
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_missing_direct_live_dispatch_guard_is_rejected_even_with_comment(self):
        old = (
            'if self.runtime_policy.is_live:\n'
            '            raise LiveModeSafetyError(\n'
            '                "PhalaTEE contract calls require unavailable authenticated action admission"\n'
            '            )'
        )
        mutant = self.phala.replace(old, "if False:\n            pass", 1)
        self.assertNotEqual(mutant, self.phala)
        mutant += "\n# if self.runtime_policy.is_live: raise LiveModeSafetyError\n"
        self.assert_rejected(phala=mutant)

    def test_real_proof_return_is_rejected(self):
        old = (
            "if not self.mock_mode:\n"
            "            return ProofResult(\n"
            "                valid=False,"
        )
        mutant = self.plugin.replace(old, old.replace("valid=False", "valid=True"), 1)
        self.assertNotEqual(mutant, self.plugin)
        self.assert_rejected(plugin=mutant)

    def test_lowered_quorum_is_rejected(self):
        mutant = self.phala.replace("required != 2", "required != 1", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_quorum_condition_without_rejection_is_rejected(self):
        old = (
            'if type(required) is not int or required != 2:\n'
            '            raise ValueError("multi-TEE verification requires exactly two attestations")'
        )
        mutant = self.phala.replace(old, "if type(required) is not int or required != 2:\n            pass", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_final_quorum_cannot_be_lowered(self):
        mutant = self.phala.replace("return (valid_count >= 2, reports)", "return (valid_count >= 1, reports)", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_early_true_report_property_cannot_be_hidden_by_later_false(self):
        old = """    def usable_as_live_evidence(self) -> bool:
        # The legacy Phala/Marlin response protocol is not authenticated.
        return False"""
        mutant = self.phala.replace(
            old,
            """    def usable_as_live_evidence(self) -> bool:
        return self.is_valid
        return False""",
            1,
        )
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_ambient_mismatch_branch_must_reject(self):
        old = """    if configured != ambient or (supplied is not None and supplied != ambient):
        raise RuntimeConfigurationError(
            f"Conflicting runtime policy for {component}; ambient runtime configuration is authoritative"
        )"""
        mutant = self.phala.replace(
            old,
            "    if configured != ambient or (supplied is not None and supplied != ambient):\n        pass",
            1,
        )
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_reversed_ambient_comparison_is_rejected(self):
        mutant = self.phala.replace("configured != ambient", "configured == ambient", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_ambient_helper_must_return_ambient_policy(self):
        mutant = self.phala.replace("    return ambient\n\n\nclass TEEProvider", "    return configured\n\n\nclass TEEProvider", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_runtime_mismatch_branch_must_reject_not_pass(self):
        old = """            if current != self.runtime_policy:
                raise _PhalaRuntimeDriftError(
                    "PhalaTEE runtime configuration changed during the operation"
                )"""
        mutant = self.phala.replace(old, "            if current != self.runtime_policy:\n                pass", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_runtime_mismatch_comparison_cannot_be_reversed(self):
        mutant = self.phala.replace("if current != self.runtime_policy:", "if current == self.runtime_policy:", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_runtime_mismatch_raise_cannot_be_made_conditional_dead_code(self):
        old = "if current != self.runtime_policy:"
        mutant = self.phala.replace(old, "if current != self.runtime_policy and False:", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_freeze_method_must_be_called(self):
        mutant = self.phala.replace("        self._freeze_runtime_configuration()\n", "        pass\n", 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)

    def test_provider_callback_cannot_precede_real_proof_rejection(self):
        old = """        self._assert_current_runtime()
        if not self.mock_mode:
            return ProofResult("""
        mutant = self.plugin.replace(
            old,
            """        self._assert_current_runtime()
        self.phala_client.verify_sgx_quote(kwargs.get("sgx_quote"))
        if not self.mock_mode:
            return ProofResult(""",
            1,
        )
        self.assertNotEqual(mutant, self.plugin)
        self.assert_rejected(plugin=mutant)

    def test_mock_dispatch_callback_cannot_precede_its_rejection(self):
        old = '''        if self.mock_mode:
            raise LiveModeSafetyError(
                "PhalaTEE contract calls are unavailable in mock mode"
            )
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "PhalaTEE contract calls require unavailable authenticated action admission"
            )'''
        new = '''        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "PhalaTEE contract calls require unavailable authenticated action admission"
            )
        if self.mock_mode:
            self._session.post("https://provider.invalid")
            raise LiveModeSafetyError(
                "PhalaTEE contract calls are unavailable in mock mode"
            )'''
        mutant = self.phala.replace(old, new, 1)
        self.assertNotEqual(mutant, self.phala)
        self.assert_rejected(phala=mutant)


if __name__ == "__main__":
    unittest.main()
