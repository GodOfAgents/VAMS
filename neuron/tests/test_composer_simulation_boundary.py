"""Regression coverage for the Composer's local-simulation boundary.

These tests use only stdlib unittest and synthetic in-memory inputs. They do not
qualify a provider, registry, escrow, runtime, or deployment path.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from neuron.composer.composer import VAMSResourceComposer
from neuron.composer.models import (
    AllocationPlan,
    AllocationStatus,
    ComputeSpec,
    GPUType,
    InstanceBlueprint,
    ProvisionedInstance,
    ResourceAssignment,
)
from neuron.composer.scorer import RawNodeData
from neuron.runtime_safety import (
    LiveModeSafetyError,
    RuntimeConfigurationError,
    load_runtime_policy,
)
from neuron.services.registry_client import ServiceBlockClient


def _env(mode: str = "test", **flags: str) -> dict[str, str]:
    return {"VAMS_ENV": mode, **flags}


def _blueprint(
    name: str = "simulation-boundary", *, gpu_type=GPUType.ANY, gpu_count: int = 1
):
    return InstanceBlueprint(
        name=name,
        compute=ComputeSpec(gpu_type=gpu_type, gpu_count=gpu_count),
        max_cost_per_hour=10.0,
        min_sla_score_bps=0,
    )


def _nodes():
    return [
        RawNodeData(
            node_id="synthetic-node-1",
            provider="synthetic-provider",
            hw_class="CPU_SIMULATED",
            region="local",
            capacity_units=1,
            reservation_price=1.0,
            collateral_staked=0.0,
            benchmark_score_bps=9000,
            latency_ms=1.0,
        )
    ]


class ComposerSimulationBoundaryTests(unittest.TestCase):
    def setUp(self):
        restore = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        restore.start()
        self.addCleanup(restore.stop)

    def use_environment(self, mode="test", **flags):
        os.environ.clear()
        os.environ.update(_env(mode, **flags))
        return os.environ

    def test_default_false_is_import_safe_and_rejects_before_any_candidate_work(self):
        # Default-false construction does not need to parse ambient runtime
        # state. The first candidate-only operation fails closed.
        malformed = self.use_environment("not-a-runtime-mode")
        composer = VAMSResourceComposer()
        composer.scorer = Mock()
        composer.allocator = Mock()
        composer._registry_client = Mock()
        before = composer.get_stats()

        with self.assertRaises(LiveModeSafetyError):
            composer.provision(_blueprint(), _nodes())

        composer.scorer.score.assert_not_called()
        composer.allocator.allocate.assert_not_called()
        composer._registry_client.find_active_nodes.assert_not_called()
        self.assertEqual(composer.get_stats(), before)
        self.assertEqual(composer._instances, {})

    def test_default_false_rejects_every_synthetic_provision_wrapper_before_lookup(self):
        env = self.use_environment()
        fake_contract = Mock()
        client = ServiceBlockClient(contract_client=fake_contract)
        composer = VAMSResourceComposer(service_client=client)
        with patch("neuron.composer.composer.get_blueprint") as lookup:
            with self.assertRaises(LiveModeSafetyError):
                composer.provision_blueprint("AI_INFERENCE_STANDARD", _nodes())
            lookup.assert_not_called()

        client.resolve_blueprint = Mock(side_effect=AssertionError("lookup reached"))
        client.resolve_macro = Mock(side_effect=AssertionError("lookup reached"))
        with self.assertRaises(LiveModeSafetyError):
            composer.provision_service_block("llama_inference", _nodes())
        with self.assertRaises(LiveModeSafetyError):
            composer.provision_macro_block("DATA_PIPELINE_STANDARD", _nodes())
        client.resolve_blueprint.assert_not_called()
        client.resolve_macro.assert_not_called()
        self.assertEqual(composer.get_stats()["total_provisions"], 0)
        self.assertEqual(composer.get_stats()["failed_provisions"], 0)
        fake_contract.assert_not_called()

    def test_invalid_selector_live_mode_and_malformed_policy_are_rejected(self):
        for bad_selector in (1, "true", None):
            with self.subTest(selector=bad_selector):
                with self.assertRaises((RuntimeConfigurationError, LiveModeSafetyError)):
                    VAMSResourceComposer(simulation=bad_selector)
                with self.assertRaises((RuntimeConfigurationError, LiveModeSafetyError)):
                    ServiceBlockClient(simulation=bad_selector)

        for live_mode in ("staging", "testnet", "production"):
            with self.subTest(mode=live_mode):
                self.use_environment(live_mode)
                with self.assertRaises(LiveModeSafetyError):
                    VAMSResourceComposer(simulation=True)
                with self.assertRaises(LiveModeSafetyError):
                    ServiceBlockClient(simulation=True)

        self.use_environment("TEST")
        with self.assertRaises(RuntimeConfigurationError):
            VAMSResourceComposer(simulation=True)
        self.use_environment("local")

        with self.assertRaises(RuntimeConfigurationError):
            VAMSResourceComposer(
                simulation=True,
                policy=load_runtime_policy(_env("test")),

            )

    def test_explicit_simulation_is_available_only_for_non_live_modes(self):
        for mode in ("test", "local", "demo"):
            with self.subTest(mode=mode):
                env = self.use_environment(mode)
                composer = VAMSResourceComposer(simulation=True)
                client = ServiceBlockClient(simulation=True)
                self.assertTrue(composer.simulation)
                self.assertTrue(client.simulation)
                self.assertEqual(composer.runtime_policy, load_runtime_policy(env))
                self.assertEqual(client.runtime_policy, load_runtime_policy(env))

    def test_runtime_configuration_is_immutable(self):
        env = self.use_environment()
        composer = VAMSResourceComposer(simulation=True)
        client = ServiceBlockClient(simulation=True)
        for target, field, value in (
            (composer, "simulation", False),
            (composer, "runtime_policy", None),
            (composer, "_runtime_environ", {}),
            (client, "simulation", False),
            (client, "runtime_policy", None),
            (client, "_runtime_environ", {}),
        ):
            with self.subTest(target=type(target).__name__, field=field):
                with self.assertRaises((AttributeError, RuntimeConfigurationError)):
                    setattr(target, field, value)

    def test_supplied_service_client_selection_or_policy_mismatch_fails_at_construction(self):
        env = self.use_environment()
        default_client = ServiceBlockClient()
        with self.assertRaises((LiveModeSafetyError, RuntimeConfigurationError)):
            VAMSResourceComposer(
                service_client=default_client,
                simulation=True,

            )

        client_env = self.use_environment("test", NEURON_MOCK_MODE="true")
        client = ServiceBlockClient(simulation=True)
        composer_env = self.use_environment("test")
        with self.assertRaises((LiveModeSafetyError, RuntimeConfigurationError)):
            VAMSResourceComposer(
                service_client=client,
                simulation=True,

            )

    def test_policy_drift_rejects_new_synthetic_provision_before_work_and_counters(self):
        for change in (
            {"VAMS_ENV": "staging"},
            {"NEURON_MOCK_MODE": "true"},
            {"NEURON_MOCK_MODE": "yes"},
        ):
            with self.subTest(change=change):
                env = self.use_environment()
                composer = VAMSResourceComposer(simulation=True)
                composer.scorer = Mock()
                composer.allocator = Mock()
                composer._registry_client = Mock()
                before = composer.get_stats()
                env.update(change)
                with self.assertRaises((LiveModeSafetyError, RuntimeConfigurationError)):
                    composer.provision(_blueprint(), _nodes())
                composer.scorer.score.assert_not_called()
                composer.allocator.allocate.assert_not_called()
                composer._registry_client.find_active_nodes.assert_not_called()
                self.assertEqual(composer.get_stats(), before)
                self.assertEqual(composer._instances, {})

    def test_service_catalogue_apis_all_recheck_policy_before_returning_synthetic_data(self):
        env = self.use_environment()
        client = ServiceBlockClient(simulation=True)
        manifest = client.get_skillops_manifest("llama_inference")
        env["NEURON_MOCK_MODE"] = "true"

        guarded_calls = (
            lambda: client.list_blocks(),
            lambda: client.get_block("llama_inference"),
            lambda: client.get_memory_policy("llama_inference"),
            lambda: client.get_skillops_manifest("llama_inference"),
            lambda: client.validate_skillops_manifest(manifest),
            lambda: client.resolve_blueprint("llama_inference"),
            lambda: client.resolve_macro("DATA_PIPELINE_STANDARD"),
            lambda: client.list_macros(),
        )
        for call in guarded_calls:
            with self.subTest(call=call):
                with self.assertRaises(RuntimeConfigurationError):
                    call()

    def test_default_false_service_client_rejects_each_synthetic_catalogue_api(self):
        env = self.use_environment()
        qualified = ServiceBlockClient(simulation=True)
        manifest = qualified.get_skillops_manifest("llama_inference")
        fake_contract = Mock()
        client = ServiceBlockClient(contract_client=fake_contract)
        guarded_calls = (
            lambda: client.list_blocks(),
            lambda: client.get_block("llama_inference"),
            lambda: client.get_memory_policy("llama_inference"),
            lambda: client.get_skillops_manifest("llama_inference"),
            lambda: client.validate_skillops_manifest(manifest),
            lambda: client.resolve_blueprint("llama_inference"),
            lambda: client.resolve_macro("DATA_PIPELINE_STANDARD"),
            lambda: client.list_macros(),
        )
        for call in guarded_calls:
            with self.subTest(call=call):
                with self.assertRaises(LiveModeSafetyError):
                    call()
        fake_contract.assert_not_called()

    def test_explicit_simulation_service_catalogue_still_supports_local_inspection(self):
        client = ServiceBlockClient(simulation=True)
        blocks = client.list_blocks()
        self.assertTrue(blocks)
        self.assertTrue(all(item["simulation"] for item in blocks))
        self.assertTrue(all(item["registry_verified"] is False for item in blocks))
        self.assertTrue(
            all(item["evidence_classification"] == "non-authoritative" for item in blocks)
        )
        block = client.get_block("llama_inference")
        self.assertTrue(block["simulation"])
        self.assertFalse(block["registry_verified"])
        self.assertEqual(client.get_memory_policy("llama_inference").value, "STATELESS")
        manifest = client.get_skillops_manifest("llama_inference")
        self.assertIs(client.validate_skillops_manifest(manifest), manifest)
        self.assertEqual(client.resolve_blueprint("llama_inference").name, "llama_inference")
        self.assertTrue(client.resolve_macro("DATA_PIPELINE_STANDARD"))
        self.assertTrue(client.list_macros())

    def test_positive_simulation_uses_real_scorer_allocator_and_has_separate_lifecycle(self):
        env = self.use_environment("demo")
        composer = VAMSResourceComposer(simulation=True)
        instance = composer.provision(_blueprint(), _nodes())

        self.assertIs(instance.status, AllocationStatus.SIMULATED)
        serialized = instance.to_dict()
        self.assertTrue(serialized["simulation"])
        self.assertEqual(serialized["evidence_classification"], "non-authoritative")
        self.assertIsNone(instance.escrow_tx_hash)
        self.assertEqual(composer.list_active_instances(), [])
        self.assertEqual(composer.list_instances(), [instance])
        stats = composer.get_stats()
        self.assertEqual(stats["total_provisions"], 0)
        self.assertEqual(stats["total_deprovisions"], 0)
        self.assertEqual(stats["active_instances"], 0)
        self.assertEqual(stats["total_simulations"], 1)
        self.assertEqual(stats["simulated_instances"], 1)
        self.assertEqual(stats["failed_provisions"], 0)
        self.assertEqual(stats["failed_simulations"], 0)

        # Local inspection and cleanup remain safe after the captured policy
        # drifts because neither operation creates external authority/effects.
        env["VAMS_ENV"] = "staging"
        self.assertIs(composer.get_instance(instance.instance_id), instance)
        self.assertEqual(composer.list_instances(), [instance])
        self.assertTrue(composer.deprovision(instance.instance_id))
        self.assertIs(instance.status, AllocationStatus.SIMULATION_REMOVED)
        self.assertEqual(composer.list_instances(), [])
        stats = composer.get_stats()
        self.assertEqual(stats["total_provisions"], 0)
        self.assertEqual(stats["total_deprovisions"], 0)
        self.assertEqual(stats["removed_simulations"], 1)
        self.assertEqual(stats["active_instances"], 0)

    def test_forged_active_record_cannot_be_locally_removed_as_simulation(self):
        env = self.use_environment()
        composer = VAMSResourceComposer(simulation=True)
        blueprint = _blueprint()
        assignment = ResourceAssignment(
            node_id="forged-node",
            provider="forged-provider",
            hw_class="CPU_SIMULATED",
            region="local",
            allocated_units=1,
            hourly_cost=1.0,
            score=1.0,
        )
        forged = ProvisionedInstance(
            instance_id="forged-active",
            blueprint=blueprint,
            allocation=AllocationPlan(
                blueprint_hash=blueprint.blueprint_hash(),
                assignments=[assignment],
                total_hourly_cost=1.0,
                total_nodes=1,
            ),
            status=AllocationStatus.ACTIVE,
        )
        composer._instances[forged.instance_id] = forged
        before = composer.get_stats()
        env["VAMS_ENV"] = "staging"
        with self.assertRaises(LiveModeSafetyError):
            composer.deprovision(forged.instance_id)
        self.assertIs(composer.get_instance(forged.instance_id), forged)
        self.assertEqual(composer.get_stats(), before)

    def test_default_false_composer_keeps_pure_split_and_quote_arithmetic(self):
        blueprint = _blueprint("quote-multiprovider", gpu_count=3)
        blueprint.max_cost_per_hour = 12.0
        simulated = VAMSResourceComposer(simulation=True)
        plan = simulated.provision(
            blueprint,
            [
                RawNodeData(
                    node_id="quote-node-1", provider="quote-provider-1",
                    hw_class="CPU_SIMULATED", region="local", capacity_units=1,
                    reservation_price=1.0, collateral_staked=0.0,
                    benchmark_score_bps=9000, latency_ms=1.0,
                ),
                RawNodeData(
                    node_id="quote-node-2", provider="quote-provider-2",
                    hw_class="CPU_SIMULATED", region="local", capacity_units=2,
                    reservation_price=1.0, collateral_staked=0.0,
                    benchmark_score_bps=9000, latency_ms=2.0,
                ),
            ],
        ).allocation
        self.assertEqual(
            sorted(assignment.allocated_units for assignment in plan.assignments), [1, 2]
        )
        composer = VAMSResourceComposer()
        self.assertEqual(len(composer.calculate_payment_splits(plan, blueprint)), 2)
        quote = composer.get_payment_quote(plan, blueprint)
        self.assertFalse(quote["authoritative"])
        self.assertFalse(quote["transactionReady"])
        self.assertEqual(set(quote["providers"]), {"quote-provider-1", "quote-provider-2"})
        self.assertEqual(
            round(sum(split["amount"] for split in quote["splits"]), 6), 12.0
        )
        self.assertEqual(composer.get_stats()["total_provisions"], 0)


if __name__ == "__main__":
    unittest.main()
