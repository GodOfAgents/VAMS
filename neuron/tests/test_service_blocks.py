"""
VAMS Service Block Registry — Unit Tests
==========================================
Tests the Python-side service block client, blueprint resolution,
and macro block expansion.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from neuron.services.registry_client import (
    ServiceBlockClient,
    ServiceBlockManifest,
    ServiceBlockMemoryPolicy,
    ServiceBlockPermission,
    _SERVICE_BLOCK_BLUEPRINTS,
    _SERVICE_BLOCK_MEMORY_POLICIES,
    _SERVICE_BLOCK_PERMISSION_SCOPES,
)
from neuron.services.macro_blocks import (
    MACRO_BLOCKS,
    get_macro,
    list_macros,
)
from neuron.composer.models import InstanceBlueprint


# ═══════════════════════════════════════════════════════════════
# Tests: Service Block Client
# ═══════════════════════════════════════════════════════════════

class TestServiceBlockClient:

    def test_list_all_blocks(self):
        client = ServiceBlockClient()
        blocks = client.list_blocks()
        assert len(blocks) == len(_SERVICE_BLOCK_BLUEPRINTS)

    def test_list_blocks_by_category(self):
        client = ServiceBlockClient()
        ai_blocks = client.list_blocks(category="AI")
        assert len(ai_blocks) > 0
        for b in ai_blocks:
            assert b["category"] == "AI"

    def test_get_block_metadata(self):
        client = ServiceBlockClient()
        block = client.get_block("llama_inference")
        assert block is not None
        assert block["name"] == "llama_inference"
        assert block["category"] == "AI"
        assert block["memory_policy"] == ServiceBlockMemoryPolicy.STATELESS.value
        assert block["memory_policy_requires_review"] is False
        assert "blueprint" in block

    def test_get_unknown_block(self):
        client = ServiceBlockClient()
        assert client.get_block("nonexistent") is None

    def test_resolve_blueprint(self):
        client = ServiceBlockClient()
        bp = client.resolve_blueprint("llama_inference")
        assert isinstance(bp, InstanceBlueprint)
        assert bp.name == "llama_inference"
        assert bp.compute.gpu_count == 2

    def test_resolve_unknown_raises(self):
        client = ServiceBlockClient()
        with pytest.raises(KeyError, match="Unknown service block"):
            client.resolve_blueprint("nonexistent")

    def test_all_blocks_expose_memory_policy(self):
        client = ServiceBlockClient()
        blocks = client.list_blocks()
        valid_policies = {p.value for p in ServiceBlockMemoryPolicy}

        assert set(_SERVICE_BLOCK_MEMORY_POLICIES) == set(_SERVICE_BLOCK_BLUEPRINTS)
        for block in blocks:
            assert block["memory_policy"] in valid_policies
            assert "memory_policy_requires_review" in block

    def test_external_readonly_blocks_are_explicit(self):
        client = ServiceBlockClient()

        vector_block = client.get_block("vector_db")
        storage_block = client.get_block("storage_cluster_block")

        assert vector_block["memory_policy"] == ServiceBlockMemoryPolicy.EXTERNAL_READONLY.value
        assert storage_block["memory_policy"] == ServiceBlockMemoryPolicy.EXTERNAL_READONLY.value

    def test_unknown_memory_policy_fails_closed(self, monkeypatch):
        client = ServiceBlockClient()
        monkeypatch.setitem(
            _SERVICE_BLOCK_MEMORY_POLICIES,
            "llama_inference",
            "UNREVIEWED_PROMPT_MEMORY",
        )

        with pytest.raises(ValueError, match="Unknown service block memory policy"):
            client.get_block("llama_inference")

    def test_missing_memory_policy_fails_closed(self, monkeypatch):
        client = ServiceBlockClient()
        monkeypatch.delitem(_SERVICE_BLOCK_MEMORY_POLICIES, "llama_inference")

        with pytest.raises(KeyError, match="Missing memory policy"):
            client.get_block("llama_inference")

    def test_all_blocks_expose_skillops_manifest(self):
        client = ServiceBlockClient()
        blocks = client.list_blocks()

        assert set(_SERVICE_BLOCK_PERMISSION_SCOPES) == set(_SERVICE_BLOCK_BLUEPRINTS)
        for block in blocks:
            manifest = block["skillops_manifest"]
            assert manifest["manifest_hash"].startswith("0x")
            assert manifest["capability_root"].startswith("0x")
            assert manifest["manifest_version"] == 1
            assert manifest["permissions_bitmap"] > 0

    def test_unknown_permission_scope_fails_closed(self):
        client = ServiceBlockClient()
        manifest = ServiceBlockManifest(
            block_name="llama_inference",
            permission_scopes=["EXTERNAL_READ", "ROOT_WALLET"],
        )

        with pytest.raises(ValueError, match="Unknown service block permission scope"):
            client.validate_skillops_manifest(manifest)

    def test_missing_skillops_manifest_fails_closed(self, monkeypatch):
        client = ServiceBlockClient()
        monkeypatch.delitem(_SERVICE_BLOCK_PERMISSION_SCOPES, "llama_inference")

        with pytest.raises(KeyError, match="Missing SkillOps manifest"):
            client.get_block("llama_inference")

    def test_persistent_mutation_requires_review_policy(self):
        client = ServiceBlockClient()
        manifest = ServiceBlockManifest(
            block_name="llama_inference",
            permission_scopes=[
                ServiceBlockPermission.EXTERNAL_READ.value,
                ServiceBlockPermission.PERSISTENT_MUTATION.value,
            ],
        )

        with pytest.raises(ValueError, match="Persistent mutation permission"):
            client.validate_skillops_manifest(manifest)


# ═══════════════════════════════════════════════════════════════
# Tests: Macro Blocks
# ═══════════════════════════════════════════════════════════════

class TestMacroBlocks:

    def test_macro_definitions_valid(self):
        for name, macro in MACRO_BLOCKS.items():
            assert "name" in macro
            assert "blocks" in macro
            assert len(macro["blocks"]) > 0

            # All constituent blocks must exist
            for block_name in macro["blocks"]:
                assert block_name in _SERVICE_BLOCK_BLUEPRINTS, (
                    f"Macro '{name}' references unknown block '{block_name}'"
                )

    def test_get_macro(self):
        macro = get_macro("AI_AGENT_STARTER_PACK")
        assert macro["name"] == "AI_AGENT_STARTER_PACK"
        assert "llama_inference" in macro["blocks"]
        assert "vector_db" in macro["blocks"]

    def test_get_unknown_macro_raises(self):
        with pytest.raises(KeyError, match="Unknown macro"):
            get_macro("NONEXISTENT_PACK")

    def test_list_macros(self):
        macros = list_macros()
        assert len(macros) == len(MACRO_BLOCKS)
        for m in macros:
            assert "name" in m
            assert "block_count" in m
            assert m["block_count"] > 0


# ═══════════════════════════════════════════════════════════════
# Tests: Macro Resolution
# ═══════════════════════════════════════════════════════════════

class TestMacroResolution:

    def test_resolve_ai_starter_pack(self):
        client = ServiceBlockClient()
        blueprints = client.resolve_macro("AI_AGENT_STARTER_PACK")
        assert len(blueprints) == 5
        names = [bp.name for bp in blueprints]
        assert "llama_inference" in names
        assert "vector_db" in names
        assert "tee_wrapper" in names
        assert "celestia_audit" in names
        assert "x402_payments" in names

    def test_resolve_defi_suite(self):
        client = ServiceBlockClient()
        blueprints = client.resolve_macro("DEFI_ARBITRAGE_SUITE")
        assert len(blueprints) == 3

    def test_all_resolved_are_blueprints(self):
        client = ServiceBlockClient()
        for macro_name in MACRO_BLOCKS:
            blueprints = client.resolve_macro(macro_name)
            for bp in blueprints:
                assert isinstance(bp, InstanceBlueprint)


# ═══════════════════════════════════════════════════════════════
# Tests: Category Inference
# ═══════════════════════════════════════════════════════════════

class TestCategoryInference:

    def test_ai_blocks_categorized(self):
        client = ServiceBlockClient()
        assert client._infer_category("llama_inference") == "AI"
        assert client._infer_category("vector_db") == "AI"
        assert client._infer_category("high_speed_compute") == "AI"

    def test_security_blocks_categorized(self):
        client = ServiceBlockClient()
        assert client._infer_category("tee_wrapper") == "SECURITY"
        assert client._infer_category("mev_protection") == "SECURITY"

    def test_network_blocks_categorized(self):
        client = ServiceBlockClient()
        assert client._infer_category("multi_chain_bridge") == "NETWORK"
        assert client._infer_category("x402_payments") == "NETWORK"
        assert client._infer_category("ServiceBlock_OMS_v1") == "NETWORK"


# ═══════════════════════════════════════════════════════════════
# Tests: OMS Service Block & Required Service Blocks (Phase 2)
# ═══════════════════════════════════════════════════════════════

class TestOMSIntegrationPhase2:

    def test_oms_service_block_exists(self):
        client = ServiceBlockClient()
        block = client.get_block("ServiceBlock_OMS_v1")
        assert block is not None
        assert block["name"] == "ServiceBlock_OMS_v1"
        assert block["category"] == "NETWORK"
        
        bp = client.resolve_blueprint("ServiceBlock_OMS_v1")
        assert bp.min_trust_tier == "silver"


    def test_blueprint_required_service_blocks(self):
        # Create blueprints that only differ in required service blocks
        bp1 = InstanceBlueprint(name="test_bp", required_service_blocks=[])
        bp2 = InstanceBlueprint(name="test_bp", required_service_blocks=["ServiceBlock_OMS_v1"])
        
        # Hashing should be different
        assert bp1.blueprint_hash() != bp2.blueprint_hash()
        
        # to_dict should serialize the field
        d1 = bp1.to_dict()
        d2 = bp2.to_dict()
        assert "required_service_blocks" in d1
        assert d1["required_service_blocks"] == []
        assert d2["required_service_blocks"] == ["ServiceBlock_OMS_v1"]

    def test_get_escrow_params_service_block_id(self):
        from neuron.composer.composer import VAMSResourceComposer
        from neuron.composer.allocator import AllocationPlan
        
        composer = VAMSResourceComposer()
        
        # Create a mock allocation plan
        class MockNode:
            def __init__(self, node_id, provider, capacity_units):
                self.node_id = node_id
                self.provider = provider
                self.capacity_units = capacity_units
                self.reservation_price = 1.0

        class MockAllocationPlan:
            def __init__(self, nodes):
                self.nodes = nodes
                self.total_nodes = len(nodes)
                self.total_hourly_cost = sum(n.reservation_price for n in nodes)

        nodes = [MockNode("n1", "0xPROVIDER", 100)]
        plan = MockAllocationPlan(nodes)
        
        # Test with a regular blueprint
        bp_regular = InstanceBlueprint(name="regular_bp")
        params_regular = composer.get_escrow_params(plan, bp_regular)
        assert params_regular["serviceBlockId"] == ""
        
        # Test with a service block blueprint
        bp_service = InstanceBlueprint(name="ServiceBlock_OMS_v1")
        params_service = composer.get_escrow_params(plan, bp_service)
        assert params_service["serviceBlockId"] != ""
        assert params_service["serviceBlockId"].startswith("0x")
        
        # Determinism check
        import hashlib
        expected_id = f"0x{hashlib.sha256(b'ServiceBlock_OMS_v1').hexdigest()}"
        assert params_service["serviceBlockId"] == expected_id



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
