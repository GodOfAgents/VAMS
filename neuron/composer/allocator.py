"""
VAMS Resource Allocator — Multi-Provider Bin-Packing
=====================================================
Takes scored candidates and an InstanceBlueprint to produce
an AllocationPlan describing how resources are distributed
across one or more providers.

Allocation Strategies:
    1. Single-Provider: One node satisfies entire blueprint
    2. Multi-Provider:  Bin-packing across multiple nodes
    3. Elastic:         Minimum viable + scaling triggers

Architecture Reference:
    - ICN Gap #3: Resource Composition Engine
    - VAMS Phase 3, Sprint 6
"""

from __future__ import annotations

import logging
from typing import List, Optional

from neuron.composer.models import (
    AllocationPlan,
    InstanceBlueprint,
    ResourceAssignment,
    ScoredCandidate,
)

logger = logging.getLogger("VAMS-Allocator")


class AllocationError(Exception):
    """Raised when allocation cannot be satisfied."""
    pass


class ResourceAllocator:
    """
    Multi-provider resource allocator.

    Takes a sorted list of ScoredCandidates (best-first from CandidateScorer)
    and produces an AllocationPlan satisfying the blueprint's requirements.

    Usage:
        allocator = ResourceAllocator()
        plan = allocator.allocate(blueprint, scored_candidates)
    """

    def allocate(
        self,
        blueprint: InstanceBlueprint,
        candidates: List[ScoredCandidate],
    ) -> AllocationPlan:
        """
        Allocate resources to satisfy a blueprint.

        Strategy selection:
            - If elastic=True → elastic allocation (min_replicas)
            - If a single node can satisfy → single-provider
            - Otherwise → multi-provider bin-packing

        Args:
            blueprint: The resource requirements
            candidates: Scored candidates sorted best-first

        Returns:
            AllocationPlan with one or more ResourceAssignments

        Raises:
            AllocationError: If no valid allocation exists
        """
        if not candidates:
            raise AllocationError(
                f"No candidates available for blueprint '{blueprint.name}'"
            )

        required_units = blueprint.compute.gpu_count or 1

        if blueprint.elastic:
            return self._allocate_elastic(blueprint, candidates, required_units)

        # Try single-provider first (preferred — simpler, lower latency)
        single = self._try_single_provider(blueprint, candidates, required_units)
        if single:
            return single

        # Fall back to multi-provider bin-packing
        return self._allocate_multi_provider(blueprint, candidates, required_units)

    # ──────────────────────────────────────────────────
    # Single-Provider Allocation
    # ──────────────────────────────────────────────────

    def _try_single_provider(
        self,
        blueprint: InstanceBlueprint,
        candidates: List[ScoredCandidate],
        required_units: int,
    ) -> Optional[AllocationPlan]:
        """Find a single node that can satisfy the entire blueprint."""
        for candidate in candidates:
            if candidate.capacity_units >= required_units:
                hourly_cost = candidate.reservation_price * required_units

                # Budget check
                if blueprint.max_cost_per_hour > 0:
                    if hourly_cost > blueprint.max_cost_per_hour:
                        continue

                plan = AllocationPlan(
                    blueprint_hash=blueprint.blueprint_hash(),
                    assignments=[
                        ResourceAssignment(
                            node_id=candidate.node_id,
                            provider=candidate.provider,
                            hw_class=candidate.hw_class,
                            region=candidate.region,
                            allocated_units=required_units,
                            hourly_cost=hourly_cost,
                            score=candidate.total_score,
                        )
                    ],
                    total_hourly_cost=hourly_cost,
                    total_nodes=1,
                    is_multi_provider=False,
                )
                logger.info(
                    f"Single-provider allocation: {candidate.node_id} "
                    f"({required_units} units, ${hourly_cost:.2f}/hr)"
                )
                return plan

        return None

    # ──────────────────────────────────────────────────
    # Multi-Provider Bin-Packing
    # ──────────────────────────────────────────────────

    def _allocate_multi_provider(
        self,
        blueprint: InstanceBlueprint,
        candidates: List[ScoredCandidate],
        required_units: int,
    ) -> AllocationPlan:
        """
        Greedy bin-packing: allocate from best candidates until
        required capacity is met.

        This is a first-fit-decreasing approach — candidates are
        already sorted by score (best first).
        """
        assignments: List[ResourceAssignment] = []
        remaining = required_units
        total_cost = 0.0
        providers_used = set()

        for candidate in candidates:
            if remaining <= 0:
                break

            allocatable = min(candidate.capacity_units, remaining)
            hourly_cost = candidate.reservation_price * allocatable

            # Budget check (incremental)
            if blueprint.max_cost_per_hour > 0:
                if total_cost + hourly_cost > blueprint.max_cost_per_hour:
                    continue

            assignments.append(ResourceAssignment(
                node_id=candidate.node_id,
                provider=candidate.provider,
                hw_class=candidate.hw_class,
                region=candidate.region,
                allocated_units=allocatable,
                hourly_cost=hourly_cost,
                score=candidate.total_score,
            ))

            remaining -= allocatable
            total_cost += hourly_cost
            providers_used.add(candidate.provider)

        if remaining > 0:
            raise AllocationError(
                f"Insufficient capacity for blueprint '{blueprint.name}'. "
                f"Need {required_units} units, could allocate "
                f"{required_units - remaining}. "
                f"Tried {len(candidates)} candidates."
            )

        plan = AllocationPlan(
            blueprint_hash=blueprint.blueprint_hash(),
            assignments=assignments,
            total_hourly_cost=total_cost,
            total_nodes=len(assignments),
            is_multi_provider=len(providers_used) > 1,
        )

        logger.info(
            f"Multi-provider allocation: {len(assignments)} nodes "
            f"across {len(providers_used)} providers "
            f"(${total_cost:.2f}/hr)"
        )
        return plan

    # ──────────────────────────────────────────────────
    # Elastic Allocation
    # ──────────────────────────────────────────────────

    def _allocate_elastic(
        self,
        blueprint: InstanceBlueprint,
        candidates: List[ScoredCandidate],
        required_units: int,
    ) -> AllocationPlan:
        """
        Elastic allocation: provision min_replicas initially,
        with capacity to scale up to max_replicas.

        The AllocationPlan contains only the initial assignment.
        Scaling is handled by the Composer via poll-based monitoring.
        """
        min_units = blueprint.min_replicas
        if min_units < 1:
            min_units = 1

        # Allocate minimum viable — use first N candidates
        assignments: List[ResourceAssignment] = []
        total_cost = 0.0

        for candidate in candidates[:min_units]:
            units_per = max(1, required_units // min_units)
            hourly_cost = candidate.reservation_price * units_per

            assignments.append(ResourceAssignment(
                node_id=candidate.node_id,
                provider=candidate.provider,
                hw_class=candidate.hw_class,
                region=candidate.region,
                allocated_units=units_per,
                hourly_cost=hourly_cost,
                score=candidate.total_score,
            ))
            total_cost += hourly_cost

        if not assignments:
            raise AllocationError(
                f"No candidates for elastic allocation of '{blueprint.name}'"
            )

        plan = AllocationPlan(
            blueprint_hash=blueprint.blueprint_hash(),
            assignments=assignments,
            total_hourly_cost=total_cost,
            total_nodes=len(assignments),
            is_multi_provider=len(set(a.provider for a in assignments)) > 1,
        )

        logger.info(
            f"Elastic allocation: {len(assignments)}/{blueprint.max_replicas} "
            f"nodes provisioned (${total_cost:.2f}/hr)"
        )
        return plan
