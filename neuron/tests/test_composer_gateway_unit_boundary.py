"""Actual handler-body units, not ASGI/authentication or live-provider evidence.

FastAPI is not replaced or imported here. Extracted functions retain their real
bodies; request/HTTPException fixtures exercise only their local SDK calls and
response semantics. Full Gateway startup/middleware/HTTP checks remain required.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from neuron.composer import composer as module
from neuron.composer.composer import VAMSResourceComposer
from neuron.composer.models import (
    AllocationPlan, AllocationStatus, ComputeSpec, InstanceBlueprint, ResourceAssignment,
)
from neuron.composer.scorer import RawNodeData
from neuron.runtime_safety import LiveModeSafetyError, load_runtime_policy
from neuron.services.registry_client import ServiceBlockClient


def blueprint():
    return InstanceBlueprint(name="unit-simulation", compute=ComputeSpec(),
                             max_cost_per_hour=10.0, min_sla_score_bps=0)


def nodes():
    return [RawNodeData("local-node", "local-provider", "CPU_SIMULATED", "local",
                        4, 1.0, 0.0, benchmark_score_bps=9000, latency_ms=1)]


class ExistingComposerDefectTests(unittest.TestCase):
    """These three cases also run against original source without new APIs."""
    def test_default_composer_cannot_report_activation_without_provider(self):
        with self.assertRaises(LiveModeSafetyError):
            VAMSResourceComposer().provision(blueprint(), nodes())

    def test_default_catalogue_cannot_impersonate_registry_read(self):
        with self.assertRaises(LiveModeSafetyError):
            ServiceBlockClient().list_blocks()

    def test_quote_accepts_actual_allocator_plan_shape(self):
        plan = AllocationPlan("local-only", [
            ResourceAssignment("n1", "p1", "CPU", "local", 1, 1.0, 1.0),
            ResourceAssignment("n2", "p2", "CPU", "local", 3, 1.0, 1.0),
        ], total_hourly_cost=2.0, total_nodes=2)
        quote = VAMSResourceComposer().get_payment_quote(plan, blueprint())
        self.assertEqual([s["amount"] for s in quote["splits"]], [2.5, 7.5])
        self.assertFalse(quote["transactionReady"])
        self.assertFalse(quote["authoritative"])


class HTTPFixtureError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


def finish(coro):
    """These handlers perform no awaits; fail if future code needs an event loop."""
    try:
        coro.send(None)
    except StopIteration as stop:
        return stop.value
    finally:
        coro.close()
    raise AssertionError("Handler yielded; this unit harness cannot exercise async I/O")


def handlers():
    source = Path(__file__).resolve().parents[2] / "gateway/server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {"_bind_resource_composer", "_require_composer_simulation", "compose_resources",
             "deprovision_resources", "list_composed_instances", "list_available_blueprints",
             "list_service_blocks", "list_macro_blocks"}
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in names]
    assert {n.name for n in selected} == names
    for node in selected:
        node.decorator_list = []  # Routing/middleware is outside this unit scope.
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    extracted = ast.fix_missing_locations(ast.Module(body=body + selected, type_ignores=[]))
    namespace = {"COMPOSER_AVAILABLE": True, "HTTPException": HTTPFixtureError,
                 "VAMSResourceComposer": VAMSResourceComposer, "ServiceBlockClient": ServiceBlockClient,
                 "LiveModeSafetyError": LiveModeSafetyError, "ComposerError": module.ComposerError}
    from neuron.composer import blueprints, models
    namespace.update({name: getattr(models, name) for name in (
        "InstanceBlueprint", "ComputeSpec", "GPUType", "MemorySpec", "StorageSpec", "NetworkSpec")})
    namespace["list_blueprints"] = blueprints.list_blueprints
    exec(compile(extracted, str(source), "exec"), namespace)  # nosec B102 # test-only exec of AST-extracted repository source
    return namespace


def request(**fields):
    return SimpleNamespace(**{**dict(blueprint_name=None, service_block_name=None, macro_block_name=None,
        name="unit-simulation", gpu_type=None, gpu_count=1, vcpu=1, ram_gb=1, storage_gb=1,
        region="", max_cost_per_hour=10.0, elastic=False, min_replicas=1, max_replicas=1,
        required_service_blocks=[]), **fields})


class ComposerHandlerBodyTests(unittest.TestCase):
    def setUp(self):
        self.h = handlers()

    def bind(self, mode):
        env = patch.dict("os.environ", {"VAMS_ENV": mode}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.h["_bind_resource_composer"](load_runtime_policy())

    def test_live_process_cannot_be_overridden_by_supplied_demo_environment(self):
        with patch.dict("os.environ", {"VAMS_ENV": "production"}, clear=True):
            for component in (VAMSResourceComposer, ServiceBlockClient):
                with self.subTest(component=component.__name__):
                    with self.assertRaises((TypeError, LiveModeSafetyError)):
                        component(simulation=True, environ={"VAMS_ENV": "demo"})

    def test_non_demo_startup_binds_disabled_composer_without_disabling_gateway(self):
        for mode in ("test", "local", "staging", "testnet", "production"):
            with self.subTest(mode=mode), patch.dict("os.environ", {"VAMS_ENV": mode}, clear=True):
                self.h["_bind_resource_composer"](load_runtime_policy())
                self.assertFalse(self.h["composer"].simulation)
                self.assertTrue(self.h["COMPOSER_AVAILABLE"])
                with self.assertRaises(HTTPFixtureError) as error:
                    finish(self.h["compose_resources"](request()))
                self.assertEqual(error.exception.status_code, 503)
                for route in ("list_service_blocks", "list_macro_blocks"):
                    with self.assertRaises(HTTPFixtureError) as error:
                        finish(self.h[route]())
                    self.assertEqual(error.exception.status_code, 503)

    def test_demo_handler_uses_real_scoring_allocation_and_reports_simulation(self):
        self.bind("demo")
        with patch.object(self.h["composer"], "_fetch_candidate_nodes", return_value=nodes()):
            result = finish(self.h["compose_resources"](request()))
        self.assertEqual(result["status"], "simulated")
        self.assertTrue(result["simulation"])
        self.assertEqual(result["evidence_classification"], "non-authoritative")
        self.assertEqual(result["instance"]["status"], "simulated")
        self.assertIsNone(result["instance"]["escrow_tx_hash"])
        self.assertEqual(self.h["composer"].get_stats()["total_provisions"], 0)

    def test_all_compose_response_branches_label_simulation(self):
        self.bind("demo")
        composer = self.h["composer"]
        instance = composer.provision(blueprint(), nodes())
        # The branch stubs return a real local SDK record; they establish only
        # response shape, not complete blueprint/catalogue/provider execution.
        for field, method in (("blueprint_name", "provision_blueprint"),
                              ("service_block_name", "provision_service_block"),
                              ("macro_block_name", "provision_macro_block")):
            with self.subTest(branch=field), patch.object(composer, method,
                    return_value=[instance] if field == "macro_block_name" else instance):
                response = finish(self.h["compose_resources"](request(**{field: "fixture"})))
                self.assertEqual(response["status"], "simulated")
                self.assertTrue(response["simulation"])
                self.assertEqual(response["evidence_classification"], "non-authoritative")

    def test_demo_catalogue_macros_and_static_templates_are_not_registry_evidence(self):
        self.bind("demo")
        for route in ("list_service_blocks", "list_macro_blocks", "list_available_blueprints"):
            with self.subTest(route=route):
                response = finish(self.h[route]())
                self.assertFalse(response["registry_verified"])
                self.assertEqual(response["evidence_classification"], "non-authoritative")

    def test_drift_prevents_new_requests_but_allows_inspection_and_local_cleanup(self):
        self.bind("demo")
        composer = self.h["composer"]
        record = composer.provision(blueprint(), nodes())
        with patch.dict("os.environ", {"VAMS_ENV": "testnet"}, clear=True):
            for route in ("list_service_blocks", "list_macro_blocks"):
                with self.assertRaises(HTTPFixtureError) as error:
                    finish(self.h[route]())
                self.assertEqual(error.exception.status_code, 503)
            with self.assertRaises(HTTPFixtureError):
                finish(self.h["compose_resources"](request()))
            response = finish(self.h["list_composed_instances"]())
            self.assertEqual(response["total"], 1)
            self.assertEqual(response["instances"][0]["status"], "simulated")
            response = finish(self.h["deprovision_resources"](record.instance_id))
            self.assertEqual(response["status"], "simulation_removed")
            self.assertIs(record.status, AllocationStatus.SIMULATION_REMOVED)
            self.assertEqual(composer.get_stats()["total_deprovisions"], 0)

    def test_unavailable_composer_and_unknown_cleanup_have_correct_errors(self):
        self.bind("demo")
        with self.assertRaises(HTTPFixtureError) as error:
            finish(self.h["deprovision_resources"]("absent"))
        self.assertEqual(error.exception.status_code, 404)
        self.h["COMPOSER_AVAILABLE"] = False
        with self.assertRaises(HTTPFixtureError) as error:
            finish(self.h["compose_resources"](request()))
        self.assertEqual(error.exception.status_code, 503)

    def test_collaborator_policy_change_prevents_record_and_success_counters(self):
        runtime = patch.dict("os.environ", {"VAMS_ENV": "test"}, clear=True)
        runtime.start()
        self.addCleanup(runtime.stop)
        import os
        env = os.environ
        composer = VAMSResourceComposer(simulation=True)
        allocate = composer.allocator.allocate
        def drifting_allocator(*args):
            plan = allocate(*args)
            env["NEURON_MOCK_MODE"] = "true"
            return plan
        before = composer.get_stats()
        with patch.object(composer.allocator, "allocate", side_effect=drifting_allocator), \
             patch.object(composer, "_generate_instance_id") as make_id:
            with self.assertRaises(LiveModeSafetyError):
                composer.provision(blueprint(), nodes())
        make_id.assert_not_called()
        self.assertEqual(composer.list_instances(), [])
        self.assertEqual(composer.get_stats(), before)

    def test_legacy_quote_shape_is_still_estimate_and_retired_setter_rejects(self):
        composer = VAMSResourceComposer()
        plan = SimpleNamespace(nodes=[SimpleNamespace(node_id="legacy-local", provider="local",
                  capacity_units=1)], total_nodes=1, total_hourly_cost=1.0)
        result = composer.get_payment_quote(plan, blueprint())
        self.assertEqual(result["quotedAmounts"], [10.0])
        self.assertFalse(result["authoritative"])
        self.assertFalse(result["transactionReady"])
        with self.assertRaises(module.ComposerError):
            composer.get_escrow_params(plan=plan, blueprint=blueprint())
        with self.assertRaises(module.ComposerError):
            composer.build_escrow_request(SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
