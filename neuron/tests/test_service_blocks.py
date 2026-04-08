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

from neuron.services.registry_client import ServiceBlockClient, _SERVICE_BLOCK_BLUEPRINTS
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
