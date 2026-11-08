"""Source-unit boundary tests: real R3 scorer/models + extracted M76 provision body.

This deliberately bypasses unrelated package initialization and runtime policy
for the local fixture. The real M76 ResourceAllocator runs; no provider, gateway,
ASGI, or settlement path is invoked.
"""
import ast
import importlib
import logging
import math
import sys
import time
import types
import unittest
from pathlib import Path
from typing import List, Optional

CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
NEURON_ROOT = CANDIDATE_ROOT / "neuron"
COMPOSER_ROOT = NEURON_ROOT / "composer"

# Avoid unrelated package __init__ imports; scorer, models, and allocator below
# are actual source modules from this isolated candidate tree.
for package_name, package_path in (
    ("neuron", NEURON_ROOT),
    ("neuron.composer", COMPOSER_ROOT),
):
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        sys.modules[package_name] = package
    elif not hasattr(package, "__path__"):
        package.__path__ = [str(package_path)]
    if "." in package_name:
        parent_name, child_name = package_name.rsplit(".", 1)
        setattr(sys.modules[parent_name], child_name, package)

models = importlib.import_module("neuron.composer.models")
scorer_module = importlib.import_module("neuron.composer.scorer")
allocator_module = importlib.import_module("neuron.composer.allocator")


def load_actual_provision_method():
    """Compile the provision method and ComposerError class from source bytes."""
    source_path = COMPOSER_ROOT / "composer.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    composer_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "VAMSResourceComposer"
    )
    error_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ComposerError"
    )
    provision = next(
        node for node in composer_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "provision"
    )
    namespace = {
        "__name__": "isolated_composer_provision_fixture",
        "AllocationError": allocator_module.AllocationError,
        "AllocationPlan": models.AllocationPlan,
        "AllocationStatus": models.AllocationStatus,
        "InstanceBlueprint": models.InstanceBlueprint,
        "ProvisionedInstance": models.ProvisionedInstance,
        "RawNodeData": scorer_module.RawNodeData,
        "List": List,
        "Optional": Optional,
        "logger": logging.getLogger("composer-error-boundary-test"),
        "time": time,
    }
    extracted = ast.Module(body=[error_class, provision], type_ignores=[])
    ast.fix_missing_locations(extracted)
    exec(compile(extracted, str(source_path), "exec"), namespace)
    return namespace["ComposerError"], namespace["provision"]


ComposerError, actual_provision = load_actual_provision_method()


def blueprint(gpu_count=1):
    return models.InstanceBlueprint(
        name="composer-error-boundary",
        compute=models.ComputeSpec(gpu_count=gpu_count),
        min_sla_score_bps=0,
    )


def nodes():
    return [scorer_module.RawNodeData(
        node_id="local-node",
        provider="fixture-provider",
        hw_class="GPU_A100",
        region="fixture-region",
        capacity_units=1,
        reservation_price=1.0,
        collateral_staked=0.0,
        benchmark_score_bps=9000,
        latency_ms=5.0,
    )]


class RecordingAllocator(allocator_module.ResourceAllocator):
    """Observe calls while preserving the actual allocator implementation."""
    def __init__(self):
        super().__init__()
        self.calls = 0

    def allocate(self, blueprint, scored):
        self.calls += 1
        return super().allocate(blueprint, scored)


class ComposerHarness:
    """Minimal local harness; only the effective runtime guard is stubbed."""
    provision = actual_provision

    def __init__(self, scorer, allocator):
        self.scorer = scorer
        self.allocator = allocator
        self._registry_client = None
        self._instances = {}
        self._stats = {
            "failed_simulations": 0,
            "total_simulations": 0,
            "simulated_instances": 0,
        }
        self.policy_checks = 0

    def assert_simulation_available(self):
        self.policy_checks += 1

    def _generate_instance_id(self, _blueprint):
        return "vams-local-fixture"


class ComposerProvisionErrorBoundaryTests(unittest.TestCase):
    def invalid_weights_case(self, kind):
        if kind == "negative_sum_preserved":
            weights = scorer_module.ScorerWeights(0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
            scorer = scorer_module.CandidateScorer(weights)
            scorer.weights.price = -0.01
            scorer.weights.sla = 1.01
        elif kind == "nan_mutation":
            scorer = scorer_module.CandidateScorer()
            scorer.weights.sla = math.nan
        else:
            raise AssertionError("unknown invalid-weight case")

        allocator = RecordingAllocator()
        composer = ComposerHarness(scorer, allocator)
        with self.assertRaises(ComposerError) as caught:
            composer.provision(blueprint(), nodes())

        self.assertEqual(str(caught.exception), "Invalid scoring input or configuration")
        self.assertNotIn("price", str(caught.exception))
        self.assertNotIn("nan", str(caught.exception).lower())
        self.assertIsInstance(caught.exception.__cause__, ComposerError)
        self.assertIsInstance(caught.exception.__cause__.__cause__, ValueError)
        self.assertEqual(allocator.calls, 0)
        self.assertEqual(composer._instances, {})
        self.assertEqual(composer._stats["failed_simulations"], 1)
        self.assertEqual(composer._stats["total_simulations"], 0)
        self.assertEqual(composer._stats["simulated_instances"], 0)

    def test_negative_weight_with_sum_preserved_is_domain_error_before_allocation(self):
        self.invalid_weights_case("negative_sum_preserved")

    def test_nan_mutated_weight_is_domain_error_before_allocation(self):
        self.invalid_weights_case("nan_mutation")

    def test_existing_allocator_error_mapping_and_counter_remain(self):
        allocator = RecordingAllocator()
        composer = ComposerHarness(scorer_module.CandidateScorer(), allocator)
        with self.assertRaises(ComposerError) as caught:
            composer.provision(blueprint(gpu_count=2), nodes())
        self.assertIn("Insufficient capacity", str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, allocator_module.AllocationError)
        self.assertEqual(allocator.calls, 1)
        self.assertEqual(composer._instances, {})
        self.assertEqual(composer._stats["failed_simulations"], 1)

    def test_valid_local_scoring_still_allocates_simulated_instance(self):
        allocator = RecordingAllocator()
        composer = ComposerHarness(scorer_module.CandidateScorer(), allocator)
        instance = composer.provision(blueprint(), nodes())
        self.assertIsInstance(instance, models.ProvisionedInstance)
        self.assertIs(instance.status, models.AllocationStatus.SIMULATED)
        self.assertIs(composer._instances[instance.instance_id], instance)
        self.assertEqual(allocator.calls, 1)
        self.assertEqual(composer._stats["failed_simulations"], 0)
        self.assertEqual(composer._stats["total_simulations"], 1)
        self.assertEqual(composer._stats["simulated_instances"], 1)
        self.assertEqual(composer.policy_checks, 2)

    def test_empty_node_list_keeps_existing_early_domain_error(self):
        scorer = scorer_module.CandidateScorer()
        scorer.weights.sla = math.nan
        allocator = RecordingAllocator()
        composer = ComposerHarness(scorer, allocator)
        with self.assertRaises(ComposerError) as caught:
            composer.provision(blueprint(), [])
        self.assertIn("No hardware nodes available", str(caught.exception))
        self.assertEqual(allocator.calls, 0)
        self.assertEqual(composer._instances, {})
        self.assertEqual(composer._stats["failed_simulations"], 1)


if __name__ == "__main__":
    unittest.main()
