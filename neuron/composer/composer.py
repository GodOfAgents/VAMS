"""
VAMS Resource Composer — Top-Level Orchestrator
=================================================
The main entry point for the Resource Composition Engine.

Orchestrates the full lifecycle:
    1. Blueprint → Candidate Discovery (HardwareRegistry)
    2. Scoring (CandidateScorer)
    3. Allocation (ResourceAllocator)
    4. Escrow Locking (x402 integration point)
    5. Instance Management (provision / deprovision / list)

Architecture Reference:
    - ICN Gap #3: Resource Composition Engine
    - VAMS Phase 3, Sprint 6
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Dict, List, Optional

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


class VAMSResourceComposer:
    """
    Top-level Resource Composition Engine.

    Connects the CandidateScorer and ResourceAllocator with the live
    HardwareRegistry to provide blueprint-driven infrastructure provisioning.

    Usage:
        composer = VAMSResourceComposer()

        # Option 1: Provision a pre-defined blueprint
        instance = composer.provision_blueprint("AI_INFERENCE_STANDARD")

        # Option 2: Provision a custom blueprint
        bp = InstanceBlueprint(name="custom", compute=ComputeSpec(...))
        instance = composer.provision(bp)

        # Manage
        composer.list_active_instances()
        composer.deprovision(instance.instance_id)
    """

    def __init__(
        self,
        scorer: Optional[CandidateScorer] = None,
        allocator: Optional[ResourceAllocator] = None,
        registry_client=None,  # Optional HardwareRegistryClient
        service_client: Optional[ServiceBlockClient] = None,
    ):
        self.scorer = scorer or CandidateScorer()
        self.allocator = allocator or ResourceAllocator()
        self._registry_client = registry_client
        self._service_client = service_client or ServiceBlockClient()

        # Active instance tracking
        self._instances: Dict[str, ProvisionedInstance] = {}

        # Statistics
        self._stats = {
            "total_provisions": 0,
            "total_deprovisions": 0,
            "failed_provisions": 0,
            "active_instances": 0,
        }

    # ──────────────────────────────────────────────────
    # Public API — Provisioning
    # ──────────────────────────────────────────────────

    def provision(
        self,
        blueprint: InstanceBlueprint,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> ProvisionedInstance:
        """
        Provision resources for a blueprint.

        Args:
            blueprint: The resource requirements
            node_data: Optional pre-fetched node data (for testing).
                       If None, queries HardwareRegistryClient.

        Returns:
            ProvisionedInstance with allocation details

        Raises:
            ComposerError: If provisioning fails
        """
        logger.info(f"Provisioning blueprint: {blueprint.name}")

        try:
            # Step 1: Get candidate nodes
            if node_data is None:
                node_data = self._fetch_candidate_nodes(blueprint)

            if not node_data:
                raise ComposerError(
                    f"No hardware nodes available for blueprint '{blueprint.name}'"
                )

            # Step 2: Score candidates
            scored = self.scorer.score(blueprint, node_data)
            if not scored:
                raise ComposerError(
                    f"No candidates passed quality filters for '{blueprint.name}'"
                )

            # Step 3: Allocate
            plan = self.allocator.allocate(blueprint, scored)

            # Step 4: Create provisioned instance
            instance_id = self._generate_instance_id(blueprint)
            instance = ProvisionedInstance(
                instance_id=instance_id,
                blueprint=blueprint,
                allocation=plan,
                status=AllocationStatus.ACTIVE,
                expires_at=time.time() + blueprint.max_duration_seconds,
            )

            # Step 5: Track instance
            self._instances[instance_id] = instance
            self._stats["total_provisions"] += 1
            self._stats["active_instances"] = len(self._instances)

            logger.info(
                f"Provisioned instance {instance_id}: "
                f"{plan.total_nodes} nodes, "
                f"${plan.total_hourly_cost:.2f}/hr"
            )
            return instance

        except (AllocationError, ComposerError) as e:
            self._stats["failed_provisions"] += 1
            logger.error(f"Provisioning failed for '{blueprint.name}': {e}")
            raise ComposerError(str(e)) from e

    def provision_blueprint(
        self,
        blueprint_name: str,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> ProvisionedInstance:
        """Provision a pre-defined blueprint by name."""
        bp = get_blueprint(blueprint_name)
        return self.provision(bp, node_data)

    def provision_service_block(
        self,
        block_name: str,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> ProvisionedInstance:
        """Provision a registered Service Block."""
        bp = self._service_client.resolve_blueprint(block_name)
        return self.provision(bp, node_data)

    def provision_macro_block(
        self,
        macro_name: str,
        node_data: Optional[List[RawNodeData]] = None,
    ) -> List[ProvisionedInstance]:
        """Provision a composite Macro Service Block."""
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
        Deprovision an active instance.
        Releases resources and settles payments.
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.warning(f"Instance {instance_id} not found")
            return False

        instance.status = AllocationStatus.TERMINATED
        del self._instances[instance_id]

        self._stats["total_deprovisions"] += 1
        self._stats["active_instances"] = len(self._instances)

        logger.info(f"Deprovisioned instance {instance_id}")
        return True

    def get_instance(self, instance_id: str) -> Optional[ProvisionedInstance]:
        """Get a specific instance by ID."""
        return self._instances.get(instance_id)

    def list_active_instances(self) -> List[ProvisionedInstance]:
        """List all active provisioned instances."""
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
        if not plan.nodes or plan.total_nodes == 0:
            return []

        total_capacity = sum(n.capacity_units for n in plan.nodes)
        if total_capacity == 0:
            return []

        max_hourly = getattr(blueprint, "max_cost_per_hour", plan.total_hourly_cost)
        if max_hourly == 0.0:
            max_hourly = plan.total_hourly_cost

        splits = []
        calculator = GasAbstractionPremiumCalculator()

        for node in plan.nodes:
            share = node.capacity_units / total_capacity
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
                "capacity_units": node.capacity_units,
            })

        return splits

    def get_escrow_params(
        self,
        plan: AllocationPlan,
        blueprint: InstanceBlueprint,
        duration_seconds: int = 3600,
        builder_rev_share_bps: int = 0,
        builder_address: str = "",
    ) -> Dict:
        """
        Produce the parameters needed for a ComposedSettlement.createComposedEscrow() call.

        Args:
            plan: The allocation plan.
            blueprint: The originating blueprint.
            duration_seconds: Escrow validity window.
            builder_rev_share_bps: Builder revenue share (BPS).
            builder_address: Builder's address.

        Returns:
            Dict with providers, amounts, validForSeconds, blueprintHash, etc.
        """
        splits = self.calculate_payment_splits(plan, blueprint)
        if not splits:
            raise ComposerError("No payment splits available for plan")

        providers = [s["provider"] for s in splits]
        amounts = [s["amount"] for s in splits]

        blueprint_hash = hashlib.sha256(
            f"{blueprint.name}:{blueprint.compute.gpu_type.value}".encode()
        ).hexdigest()

        service_block_id = ""
        # Check if the blueprint name corresponds to a registered service block
        from neuron.services.registry_client import _SERVICE_BLOCK_BLUEPRINTS
        if blueprint.name in _SERVICE_BLOCK_BLUEPRINTS:
            # Generate deterministic block ID using name
            service_block_id = f"0x{hashlib.sha256(blueprint.name.encode()).hexdigest()}"

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
            "amounts": amounts,
            "validForSeconds": duration_seconds,
            "blueprintHash": f"0x{blueprint_hash}",
            "serviceBlockId": service_block_id,
            "builderRevShareBps": builder_rev_share_bps,
            "builderAddress": builder_address,
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

