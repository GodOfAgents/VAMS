"""
Tests for multi-provider composed settlement payment splitting.
Validates payment split calculation, escrow parameter generation,
and edge cases for the composer's payment split functionality.
"""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import List

from neuron.composer.composer import VAMSResourceComposer, ComposerError


# ═══════════════════════════════════════════════════════════════
# Minimal Data Models for Testing
# ═══════════════════════════════════════════════════════════════

@dataclass
class MockNode:
    """Mock allocated node for testing."""
    node_id: str
    provider: str
    capacity_units: int
    hourly_cost: float = 0.0


@dataclass
class MockAllocationPlan:
    """Mock allocation plan."""
    nodes: List[MockNode]
    total_nodes: int
    total_hourly_cost: float


@dataclass
class MockComputeSpec:
    """Mock compute spec."""
    class GpuType:
        value = "A100"
    gpu_type = GpuType()


@dataclass
class MockBlueprint:
    """Mock blueprint for testing."""
    name: str = "test-blueprint"
    max_cost_per_hour: float = 100.0
    compute: MockComputeSpec = None

    def __post_init__(self):
        if self.compute is None:
            self.compute = MockComputeSpec()


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def composer():
    return VAMSResourceComposer()


@pytest.fixture
def two_provider_plan():
    """Plan with 2 providers of equal capacity."""
    nodes = [
        MockNode(node_id="n1", provider="0xP1", capacity_units=50),
        MockNode(node_id="n2", provider="0xP2", capacity_units=50),
    ]
    return MockAllocationPlan(nodes=nodes, total_nodes=2, total_hourly_cost=80.0)


@pytest.fixture
def three_provider_plan():
    """Plan with 3 providers of varying capacity."""
    nodes = [
        MockNode(node_id="n1", provider="0xP1", capacity_units=60),
        MockNode(node_id="n2", provider="0xP2", capacity_units=30),
        MockNode(node_id="n3", provider="0xP3", capacity_units=10),
    ]
    return MockAllocationPlan(nodes=nodes, total_nodes=3, total_hourly_cost=120.0)


@pytest.fixture
def blueprint():
    return MockBlueprint(name="test-bp", max_cost_per_hour=100.0)


# ═══════════════════════════════════════════════════════════════
# Payment Split Calculation Tests
# ═══════════════════════════════════════════════════════════════

class TestPaymentSplits:
    def test_even_split_two_providers(self, composer, two_provider_plan, blueprint):
        """Two providers with equal capacity get equal payments."""
        splits = composer.calculate_payment_splits(two_provider_plan, blueprint)

        assert len(splits) == 2
        assert splits[0]["amount"] == 50.0  # 100 × 50%
        assert splits[1]["amount"] == 50.0
        assert splits[0]["share_pct"] == 50.0
        assert splits[1]["share_pct"] == 50.0

    def test_proportional_split_three_providers(self, composer, three_provider_plan, blueprint):
        """Three providers get proportional to capacity."""
        splits = composer.calculate_payment_splits(three_provider_plan, blueprint)

        assert len(splits) == 3
        # 60/100 = 60%, 30/100 = 30%, 10/100 = 10%
        assert splits[0]["amount"] == 60.0
        assert splits[1]["amount"] == 30.0
        assert splits[2]["amount"] == 10.0
        assert splits[0]["share_pct"] == 60.0
        assert splits[1]["share_pct"] == 30.0
        assert splits[2]["share_pct"] == 10.0

    def test_splits_sum_to_max_cost(self, composer, three_provider_plan, blueprint):
        """All splits should sum to the blueprint's max cost."""
        splits = composer.calculate_payment_splits(three_provider_plan, blueprint)
        total = sum(s["amount"] for s in splits)
        assert abs(total - blueprint.max_cost_per_hour) < 0.01

    def test_empty_plan(self, composer, blueprint):
        """Empty plan returns empty splits."""
        empty_plan = MockAllocationPlan(nodes=[], total_nodes=0, total_hourly_cost=0)
        splits = composer.calculate_payment_splits(empty_plan, blueprint)
        assert splits == []

    def test_single_provider(self, composer, blueprint):
        """Single provider gets 100% of the payment."""
        plan = MockAllocationPlan(
            nodes=[MockNode(node_id="n1", provider="0xP1", capacity_units=100)],
            total_nodes=1,
            total_hourly_cost=50.0,
        )
        splits = composer.calculate_payment_splits(plan, blueprint)

        assert len(splits) == 1
        assert splits[0]["amount"] == 100.0
        assert splits[0]["share_pct"] == 100.0

    def test_unequal_five_providers(self, composer, blueprint):
        """Five providers with varied capacity."""
        nodes = [
            MockNode(node_id=f"n{i}", provider=f"0xP{i}", capacity_units=cap)
            for i, cap in enumerate([40, 30, 15, 10, 5])
        ]
        plan = MockAllocationPlan(nodes=nodes, total_nodes=5, total_hourly_cost=200.0)
        splits = composer.calculate_payment_splits(plan, blueprint)

        assert len(splits) == 5
        total = sum(s["amount"] for s in splits)
        assert abs(total - 100.0) < 0.01  # Uses max_cost_per_hour from blueprint


# ═══════════════════════════════════════════════════════════════
# Escrow Parameter Tests
# ═══════════════════════════════════════════════════════════════

class TestEscrowParams:
    def test_get_escrow_params_structure(self, composer, two_provider_plan, blueprint):
        """Escrow params should have all required fields."""
        params = composer.get_escrow_params(two_provider_plan, blueprint)

        assert "providers" in params
        assert "amounts" in params
        assert "validForSeconds" in params
        assert "blueprintHash" in params
        assert "builderRevShareBps" in params
        assert "builderAddress" in params
        assert "splits" in params

        assert len(params["providers"]) == 2
        assert len(params["amounts"]) == 2
        assert params["validForSeconds"] == 3600

    def test_escrow_params_with_builder(self, composer, two_provider_plan, blueprint):
        """Builder share and address should be included."""
        params = composer.get_escrow_params(
            two_provider_plan,
            blueprint,
            builder_rev_share_bps=500,
            builder_address="0xBUILDER",
        )

        assert params["builderRevShareBps"] == 500
        assert params["builderAddress"] == "0xBUILDER"

    def test_escrow_params_custom_duration(self, composer, two_provider_plan, blueprint):
        """Custom duration should be reflected."""
        params = composer.get_escrow_params(
            two_provider_plan,
            blueprint,
            duration_seconds=7200,
        )
        assert params["validForSeconds"] == 7200

    def test_escrow_params_blueprint_hash(self, composer, two_provider_plan, blueprint):
        """Blueprint hash should be deterministic."""
        params1 = composer.get_escrow_params(two_provider_plan, blueprint)
        params2 = composer.get_escrow_params(two_provider_plan, blueprint)

        assert params1["blueprintHash"] == params2["blueprintHash"]
        assert params1["blueprintHash"].startswith("0x")

    def test_escrow_params_empty_plan_raises(self, composer, blueprint):
        """Empty plan should raise ComposerError."""
        empty_plan = MockAllocationPlan(nodes=[], total_nodes=0, total_hourly_cost=0)

        with pytest.raises(ComposerError, match="No payment splits"):
            composer.get_escrow_params(empty_plan, blueprint)

    def test_escrow_params_with_premium(self, composer, two_provider_plan):
        """Escrow params should include gas premium fields when service block is present."""
        class MockComputeSpecWithBlock:
            class GpuType:
                value = "A100"
            gpu_type = GpuType()

        class MockBlueprintWithBlock:
            name = "ServiceBlock_OMS_v1"
            max_cost_per_hour = 80.0
            compute = MockComputeSpecWithBlock()
            required_service_blocks = ["ServiceBlock_OMS_v1"]

        bp = MockBlueprintWithBlock()
        params = composer.get_escrow_params(two_provider_plan, bp)

        # Base premium (2%) + OMS premium (5%) = 7% premium rate = 700 BPS
        assert params["gasPremiumBps"] == 700
        # totalCostWithPremium should be: (80.0 * 1.07) * (3600 / 3600) = 85.6
        assert params["totalCostWithPremium"] == 85.6

        # Check splits have correct fields
        for split in params["splits"]:
            assert "base_cost" in split
            assert "premium_surcharge" in split
            assert "total_cost" in split
            assert split["amount"] == split["base_cost"]
            assert round(split["base_cost"] + split["premium_surcharge"], 6) == split["total_cost"]
