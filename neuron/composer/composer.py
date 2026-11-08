"""
VAMS Resource Composer — Top-Level Orchestrator
=================================================
The main entry point for the Resource Composition Engine.

Scores and allocates local simulations only. Provider execution, authenticated
registry reads and execution receipts are not implemented by this orchestrator.

Architecture Reference:
    - ICN Gap #3: Resource Composition Engine
    - VAMS Phase 3, Sprint 6
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Dict, List, Optional

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration, LiveModeSafetyError, RuntimeConfigurationError,
    RuntimePolicy, load_runtime_policy,
)

from neuron.composer.allocator import AllocationError, ResourceAllocator
from neuron.composer.blueprints import BLUEPRINT_REGISTRY, get_blueprint, list_blueprints
from neuron.composer.models import (
    AllocationPlan,
    AllocationStatus,
    InstanceBlueprint,
    ProvisionedInstance,
    ScoredCandidate,
)
from neuron.composer.scorer import CandidateScorer, RawNodeData, ScorerWeights
from neuron.services.registry_client import ServiceBlockClient
from neuron.economics.gas_premium import GasAbstractionPremiumCalculator

logger = logging.getLogger("VAMS-Composer")


class ComposerError(Exception):
    """Top-level composer error."""
    pass


class VAMSResourceComposer(ImmutableRuntimeConfiguration):
    """
    Top-level Resource Composition Engine.

    Explicit non-live simulation connecting scoring and allocation. Returned
    plans create no provider resource, execution receipt, escrow or payment.

    Usage:
        composer = VAMSResourceComposer(simulation=True)  # VAMS_ENV=test/local/demo

        # Option 1: Provision a pre-defined blueprint
        instance = composer.provision_blueprint("AI_INFERENCE_STANDARD")

        # Option 2: Provision a custom blueprint
        bp = InstanceBlueprint(name="custom", compute=ComputeSpec(...))
        instance = composer.provision(bp)

        # Manage
        composer.list_instances()
        composer.deprovision(instance.instance_id)
    """

    _immutable_runtime_fields = frozenset({"simulation", "runtime_policy", "_runtime_environ", "_service_client"})

    def __init__(
        self,
        scorer: Optional[CandidateScorer] = None,
        allocator: Optional[ResourceAllocator] = None,
        registry_client=None,  # Optional HardwareRegistryClient
        service_client: Optional[ServiceBlockClient] = None,
        *,
        simulation: bool = False,
        policy: Optional[RuntimePolicy] = None,
    ):
        if type(simulation) is not bool:
            raise RuntimeConfigurationError("Composer simulation must be a boolean")
        if policy is not None and type(policy) is not RuntimePolicy:
            raise RuntimeConfigurationError("Composer requires a RuntimePolicy")
        self._runtime_environ = os.environ
        self.runtime_policy = None
        if simulation or policy is not None:
            observed = load_runtime_policy(self._runtime_environ)
            if policy is not None and policy != observed:
                raise RuntimeConfigurationError("Conflicting Composer runtime policy")
            observed.authorize_component_mock("Composer simulation", simulation)
            self.runtime_policy = observed
        self.simulation = simulation
        if service_client is not None:
            if (not isinstance(service_client, ServiceBlockClient)
                    or service_client.simulation != simulation
                    or service_client.runtime_policy != self.runtime_policy):
                raise RuntimeConfigurationError("Composer and ServiceBlockClient configuration differs")
        self._service_client = service_client if service_client is not None else ServiceBlockClient(
            simulation=simulation, policy=policy,
        )
        self.scorer = scorer or CandidateScorer()
        self.allocator = allocator or ResourceAllocator()
        self._registry_client = registry_client

        # Active instance tracking
        self._instances: Dict[str, ProvisionedInstance] = {}

        # Statistics
        self._stats = {
            "total_provisions": 0,
            "total_deprovisions": 0,
            "failed_provisions": 0,
            "active_instances": 0,
            "total_simulations": 0,
            "failed_simulations": 0,
            "simulated_instances": 0,
            "removed_simulations": 0,
        }
        self._freeze_runtime_configuration()

    def assert_simulation_available(self) -> None:
        if not self.simulation or self.runtime_policy is None:
            raise LiveModeSafetyError("Authenticated Composer provider execution unavailable")
        observed = load_runtime_policy(self._runtime_environ)
        if observed != self.runtime_policy:
            raise RuntimeConfigurationError("Composer runtime policy changed")
        observed.authorize_component_mock("Composer simulation", True)
        self._service_client.assert_simulation_available()

    # ──────────────────────────────────────────────────
    # Public API — Provisioning
    # ──────────────────────────────────────────────────

    def provision(
        self,
        blueprint: InstanceBlueprint,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> ProvisionedInstance:
        """
        Simulate a local allocation; creates no external resource or receipt.

        Args:
            blueprint: The resource requirements
            node_data: Optional pre-fetched node data (for testing).
                       If None, queries HardwareRegistryClient.

        Returns:
            ProvisionedInstance with allocation details

        Raises:
            ComposerError: If provisioning fails
        """
        self.assert_simulation_available()
        logger.info(f"Simulating blueprint: {blueprint.name}")

        try:
            # Step 1: Get candidate nodes
            if node_data is None:
                node_data = self._fetch_candidate_nodes(blueprint)

            if not node_data:
                raise ComposerError(
                    f"No hardware nodes available for blueprint '{blueprint.name}'"
                )

            # Step 2: Score candidates
            try:
                scored = self.scorer.score(blueprint, node_data)
            except ValueError as exc:
                raise ComposerError("Invalid scoring input or configuration") from exc
            if not scored:
                raise ComposerError(
                    f"No candidates passed quality filters for '{blueprint.name}'"
                )

            # Step 3: Allocate
            plan = self.allocator.allocate(blueprint, scored)

            # Collaborator callbacks must not publish a result after policy drift.
            self.assert_simulation_available()

            # Step 4: Create provisioned instance
            instance_id = self._generate_instance_id(blueprint)
            instance = ProvisionedInstance(
                instance_id=instance_id,
                blueprint=blueprint,
                allocation=plan,
                status=AllocationStatus.SIMULATED,
                expires_at=time.time() + blueprint.max_duration_seconds,
            )

            # Step 5: Track instance
            self._instances[instance_id] = instance
            self._stats["total_simulations"] += 1
            self._stats["simulated_instances"] += 1

            logger.info(
                f"Simulated allocation {instance_id}: "
                f"{plan.total_nodes} nodes, "
                f"${plan.total_hourly_cost:.2f}/hr"
            )
            return instance

        except (AllocationError, ComposerError) as e:
            self._stats["failed_simulations"] += 1
            logger.error(f"Simulation failed for '{blueprint.name}': {e}")
            raise ComposerError(str(e)) from e

    def provision_blueprint(
        self,
        blueprint_name: str,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> ProvisionedInstance:
        """Provision a pre-defined blueprint by name."""
        self.assert_simulation_available()
        bp = get_blueprint(blueprint_name)
        return self.provision(bp, node_data)

    def provision_service_block(
        self,
        block_name: str,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> ProvisionedInstance:
        """Simulate a Service Block declaration; not a registry read."""
        self.assert_simulation_available()
        bp = self._service_client.resolve_blueprint(block_name)
        return self.provision(bp, node_data)

    def provision_macro_block(
        self,
        macro_name: str,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> List[ProvisionedInstance]:
        """Simulate a composite Macro Service Block."""
        self.assert_simulation_available()
        blueprints = self._service_client.resolve_macro(macro_name)
        instances = []
        for bp in blueprints:
            instances.append(self.provision(bp, node_data))
        return instances

    # ──────────────────────────────────────────────────
    # Public API — Lifecycle Management
    # ──────────────────────────────────────────────────

    def deprovision(self, instance_id: str) -> bool:
        """
        Remove a simulated local record, even after runtime drift.
        No provider resource is released and no payment is made or earned.
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.warning(f"Instance {instance_id} not found")
            return False

        if instance.status is not AllocationStatus.SIMULATED:
            raise LiveModeSafetyError("Authenticated provider deprovisioning unavailable")
        instance.status = AllocationStatus.SIMULATION_REMOVED
        del self._instances[instance_id]

        self._stats["removed_simulations"] += 1
        self._stats["simulated_instances"] -= 1

        logger.info(f"Removed local simulation {instance_id}")
        return True

    def get_instance(self, instance_id: str) -> Optional[ProvisionedInstance]:
        """Get a specific instance by ID."""
        return self._instances.get(instance_id)

    def list_active_instances(self) -> List[ProvisionedInstance]:
        """List all active provisioned instances."""
        return [i for i in self._instances.values() if i.status is AllocationStatus.ACTIVE]

    def list_instances(self) -> List[ProvisionedInstance]:
        """Inspect local records without issuing new authority, including after drift."""
        return list(self._instances.values())

    def get_stats(self) -> dict:
        """Get composer statistics."""
        return {**self._stats}

    # ──────────────────────────────────────────────────
    # Public API — Payment Splitting (Phase 4)
    # ──────────────────────────────────────────────────

    def calculate_payment_splits(
        self,
        plan: AllocationPlan,
        blueprint: InstanceBlueprint,
    ) -> List[Dict]:
        """
        Calculate per-provider payment splits for a composed allocation.

        Distributes the blueprint's max_cost_per_hour proportionally across
        allocated nodes based on their capacity contribution.

        Args:
            plan: The allocation plan from the Resource Allocator.
            blueprint: The originating blueprint (for cost limits).

        Returns:
            List of dicts: [{provider, node_id, amount, share_pct}, ...]
        """
        # The allocator produces assignments/allocated_units. The older nodes
        # shape remains quote-only compatibility and never creates calldata.
        nodes = ([(n, n.allocated_units) for n in plan.assignments]
                 if isinstance(plan, AllocationPlan)
                 else [(n, n.capacity_units) for n in plan.nodes])
        if not nodes or plan.total_nodes == 0:
            return []

        total_capacity = sum(capacity for _, capacity in nodes)
        if total_capacity == 0:
            return []

        max_hourly = getattr(blueprint, "max_cost_per_hour", plan.total_hourly_cost)
        if max_hourly == 0.0:
            max_hourly = plan.total_hourly_cost

        splits = []
        calculator = GasAbstractionPremiumCalculator()

        for node, capacity in nodes:
            share = capacity / total_capacity
            amount = max_hourly * share

            required_blocks = getattr(blueprint, "required_service_blocks", [])
            premium_surcharge = calculator.calculate_premium_cost(amount, required_blocks)
            total_cost = calculator.calculate_total_cost(amount, required_blocks)

            splits.append({
                "provider": node.provider,
                "node_id": node.node_id,
                "amount": round(amount, 6),
                "base_cost": round(amount, 6),
                "premium_surcharge": round(premium_surcharge, 6),
                "total_cost": round(total_cost, 6),
                "share_pct": round(share * 100, 2),
                "capacity_units": capacity,
            })

        return splits

    def get_escrow_params(self, *args, **kwargs):
        raise ComposerError("Unbound escrow parameters retired; use build_escrow_request with integer token units")

    def build_escrow_request(self, transaction_builder, **request):
        from neuron.composer.settlement import SettlementTransactionBuilder
        if type(transaction_builder) is not SettlementTransactionBuilder:
            raise ComposerError("Typed bound settlement builder required")
        return transaction_builder.build(**request)

    def get_payment_quote(
        self,
        plan: AllocationPlan,
        blueprint: InstanceBlueprint,
        duration_seconds: int = 3600,
    ) -> Dict:
        """Return a non-authoritative price quote; never transaction calldata."""
        splits = self.calculate_payment_splits(plan, blueprint)
        if not splits:
            raise ComposerError("No payment splits available for plan")

        providers = [s["provider"] for s in splits]
        amounts = [s["amount"] for s in splits]

        calculator = GasAbstractionPremiumCalculator()
        required_blocks = getattr(blueprint, "required_service_blocks", [])
        premium_rate = calculator.calculate_premium_rate(required_blocks)
        gas_premium_bps = int(premium_rate * 10000)

        # Scale hourly base cost by duration
        total_base_hourly = sum(s["base_cost"] for s in splits)
        total_hourly_with_premium = calculator.calculate_total_cost(total_base_hourly, required_blocks)
        total_cost_with_premium = total_hourly_with_premium * (duration_seconds / 3600.0)

        return {
            "providers": providers,
            "quotedAmounts": amounts,
            "durationSeconds": duration_seconds,
            "blueprintName": blueprint.name,
            "authoritative": False,
            "transactionReady": False,
            "splits": splits,
            "gasPremiumBps": gas_premium_bps,
            "totalCostWithPremium": round(total_cost_with_premium, 6),
        }

    # ──────────────────────────────────────────────────
    # Internal Helpers
    # ──────────────────────────────────────────────────

    def _fetch_candidate_nodes(self, blueprint: InstanceBlueprint) -> List[RawNodeData]:
        """
        Query the HardwareRegistryClient for nodes matching the blueprint.
        Falls back to empty list if no registry client is configured.
        """
        if self._registry_client is None:
            logger.warning("No HardwareRegistryClient configured — using empty node list")
            return []

        try:
            # Use SDK to find nodes matching the compute spec
            hw_class = blueprint.compute.gpu_type.value
            region = blueprint.networking.region or None

            nodes = self._registry_client.find_active_nodes(
                hw_class=hw_class,
                region=region,
            )

            # Convert SDK response to RawNodeData
            result = []
            for node in nodes:
                result.append(RawNodeData(
                    node_id=node.get("node_id", ""),
                    provider=node.get("provider", ""),
                    hw_class=node.get("hw_class", hw_class),
                    region=node.get("region", ""),
                    capacity_units=node.get("capacity_units", 1),
                    reservation_price=node.get("reservation_price", 0.0),
                    collateral_staked=node.get("collateral_staked", 0.0),
                    benchmark_score_bps=node.get("benchmark_score_bps", 0),
                    latency_ms=node.get("latency_ms", 0.0),
                    is_active=node.get("is_active", True),
                ))
            return result

        except Exception as e:
            logger.error(f"Failed to fetch nodes from registry: {e}")
            return []

    @staticmethod
    def _generate_instance_id(blueprint: InstanceBlueprint) -> str:
        """Generate a unique instance identifier."""
        payload = f"{blueprint.name}:{time.time()}:{id(blueprint)}"
        return f"vams-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


