"""
VAMS Neuron - Cognitive Layer Unit Tests
========================================
Tests for SIRA, HORMA, HIPIF, ProPlay, EvoMem, and V(m) memory value consolidation.
"""

import sys
import os
import pytest
import shutil
import json
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.semantic_mmu import SemanticMMU, MemoryTier, MemoryPage
from sdk.sira_engine import SiraEngine
from intelligence.world_model import ProPlayWorldModel, SimpleTextEmbedding


@pytest.fixture(autouse=True)
def cleanup_data_dirs():
    """Ensure a clean state for test run directories."""
    dirs_to_clean = [".data/memory", ".data/index"]
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)
    yield
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d)


# ============================================================================
# HORMA File System & Semantic MMU Tests
# ============================================================================

class TestHormaFileSystem:
    """Tests for HORMA filesystem layout and S-MMU integration."""
    
    def test_store_and_fetch_l3_fs(self):
        """Test that storing to L3 writes to the HORMA filesystem and fetch reads it back."""
        mmu = SemanticMMU()
        address = "workflows/bridge/test_page"
        content = {"status": "success", "tx_hash": "0x123abc"}
        
        # Store page in L3 (Glacier / local filesystem)
        page = mmu.store(address, content, tier=MemoryTier.L3_STORAGE)
        assert page.value_score >= 0.7  # Contains "success"

        
        # Verify file existence on disk (.data/memory/workflows/bridge/test_page.json)
        disk_path = os.path.join(".data", "memory", "workflows", "bridge", "test_page.json")
        assert os.path.exists(disk_path)
        
        # Clear the internal cache dictionaries to force filesystem read
        mmu._l1_cache.clear()
        mmu._l2_store.clear()
        mmu._l3_store.clear()
        
        # Fetch should trigger page fault handling and promote from filesystem
        fetched_page = mmu.fetch(address)
        assert fetched_page is not None
        assert fetched_page.address == address
        assert fetched_page.content["tx_hash"] == "0x123abc"
        assert fetched_page.tier == MemoryTier.L1_CACHE  # Promoted to L1

    def test_invalidate_deletes_file(self):
        """Test that invalidating a page deletes it from the filesystem."""
        mmu = SemanticMMU()
        address = "workflows/bridge/test_delete"
        mmu.store(address, "content", tier=MemoryTier.L3_STORAGE)
        
        disk_path = os.path.join(".data", "memory", "workflows", "bridge", "test_delete.json")
        assert os.path.exists(disk_path)
        
        mmu.invalidate(address)
        assert not os.path.exists(disk_path)


# ============================================================================
# HIPIF Folding Tests
# ============================================================================

class TestHipifFolding:
    """Tests for HIPIF subtask information folding."""
    
    def test_fold_completed_subtask(self):
        """Test folding noisy traces into single macro summaries."""
        mmu = SemanticMMU()
        raw_trace_path = ".data/memory/test_trace.log"
        os.makedirs(os.path.dirname(raw_trace_path), exist_ok=True)
        
        # Write noisy execution trace
        trace_data = (
            "Step 1: Init HTLC bridge request\n"
            "Step 2: Sign transaction 0x789def\n"
            "Step 3: Call contract deposit()\n"
            "ERROR: RPC connection timed out, retrying...\n"
            "Step 4: Retry deposit() success\n"
            "Step 5: Event SettleTx receipt received\n"
            "Workflow status: success done"
        )
        with open(raw_trace_path, "w") as f:
            f.write(trace_data)
            
        assert os.path.exists(raw_trace_path)
        
        # Fold completed subtask
        folded_summary = mmu.fold_completed_subtask("bridge_workflow_01", raw_trace_path)
        
        # Check raw trace is cleaned up
        assert not os.path.exists(raw_trace_path)
        
        # Verify folded document exists in L3
        folded_page = mmu.fetch("workflows/bridge_workflow_01/folded_summary")
        assert folded_page is not None
        assert "Folded Subtask Summary: bridge_workflow_01" in folded_page.content
        assert "Status: SUCCESS" in folded_page.content
        assert "0x789def" in folded_page.content
        assert "RPC connection timed out" in folded_page.content


# ============================================================================
# SIRA Retrieval Engine Tests
# ============================================================================

class TestSiraEngine:
    """Tests for SIRA lexical BM25 engine & dual scoring."""
    
    def test_sira_pruning_and_scoring(self):
        """Test that SIRA correctly scores and ranks documents using dual-scoring."""
        sira = SiraEngine()
        
        # Index three documents
        sira.add_document("doc1", "VAMS cross chain DePIN bridge matching module polygon")
        sira.add_document("doc2", "Glacier Vector Database memory management unit indexing")
        sira.add_document("doc3", "GCA Conscience Anchor token economics audit staking polygon")
        
        # SIRA dual scoring test:
        # Original query: "polygon"
        # Expansion sketch keywords: ["depin", "bridge", "polygon"]
        # In this corpus, "polygon" is in doc1 and doc3 (high document frequency, low uniqueness).
        # "depin" and "bridge" are only in doc1 (rare keywords, highly specific).
        # SIRA should prioritize doc1 over doc3 because of dual-expansion keywords.
        
        results = sira.retrieve(
            query_orig="polygon",
            q_exp_terms=["depin", "bridge", "polygon"],
            w=1.5,
            tau=0.8
        )
        
        assert len(results) > 0
        best_doc, best_score = results[0]
        assert best_doc == "doc1"  # doc1 contains polygon + rare terms: depin, bridge
        
        # Assert doc3 is lower score but retrieved
        retrieved_ids = [doc_id for doc_id, _ in results]
        assert "doc3" in retrieved_ids
        assert "doc2" not in retrieved_ids  # doc2 contains none of the keywords


# ============================================================================
# ProPlay World Model Tests
# ============================================================================

class TestProPlayWorldModel:
    """Tests for ProPlay procedural graph planning."""
    
    def test_proplay_guidance(self):
        """Test that recording transitions creates a planning path for soft guidance."""
        model = ProPlayWorldModel(filepath=".data/memory/test_graph.json")
        
        # Record successful and failed transitions
        model.add_procedure("init_swap", "Initiate swap transaction")
        model.add_procedure("verify_rate", "Verify exchange rate balance")
        model.add_procedure("execute_bridge", "Execute decentralized bridge route")
        model.add_procedure("confirm_l2", "Confirm Layer 2 block signature")
        
        # Success path: init_swap -> verify_rate -> execute_bridge
        model.record_transition("init_swap", "verify_rate", reward=1.0, task_description="DeFi routing cross-chain swap")
        model.record_transition("verify_rate", "execute_bridge", reward=1.0, task_description="DeFi routing cross-chain swap")
        
        # Failed path (avoid rate verification)
        model.record_transition("init_swap", "execute_bridge", reward=0.0, task_description="DeFi routing cross-chain swap")
        
        # Request soft guidance for a matching task intent
        guidance = model.get_soft_guidance("DeFi cross-chain token swap execution")
        
        assert "init_swap" in guidance
        assert "verify_rate" in guidance
        assert "execute_bridge" in guidance
        # Should recommend verified path: init_swap -> verify_rate -> execute_bridge
        assert "init_swap -> verify_rate -> execute_bridge" in guidance


# ============================================================================
# EvoMem and V(m) Consolidation Tests
# ============================================================================

class TestEvoMemAndVm:
    """Tests for EvoMem patches and V(m) memory value consolidation."""
    
    def test_evomem_patch_tracking(self):
        """Test append-only 4-tuple patch logging."""
        mmu = SemanticMMU(
            review_authorizer=lambda action, reviewer: (
                action == "evomem_patch" and reviewer == "test-reviewer"
            )
        )
        address = "config/bridge_endpoints"
        
        patch_info = {
            "previous_state": "http://polygon-amoy.rpc.com/v1",
            "new_state": "http://polygon-amoy.rpc.com/v2",
            "rationale_for_change": "v1 deprecated",
            "supporting_evidence": "404 responses observed"
        }
        
        success = mmu.apply_memory_patch(
            address,
            patch_info,
            review_approved=True,
            reviewed_by="test-reviewer",
        )
        assert success
        
        # Verify patch file exists in patches directory
        patch_file = os.path.join(".data", "memory", "patches", "config_bridge_endpoints.jsonl")
        assert os.path.exists(patch_file)
        
        with open(patch_file, 'r') as f:
            stored_patch = json.loads(f.readline().strip())
        assert stored_patch["new_state"] == "http://polygon-amoy.rpc.com/v2"
        assert stored_patch["reviewed_by"] == "test-reviewer"

    def test_evomem_patch_rejects_unreviewed_persistence(self):
        mmu = SemanticMMU()
        patch_info = {
            "previous_state": "old",
            "new_state": "new",
            "rationale_for_change": "test",
            "supporting_evidence": "evidence",
        }

        assert mmu.apply_memory_patch("config/value", patch_info) is False
        assert (
            mmu.apply_memory_patch(
                "config/value",
                patch_info,
                review_approved=True,
                reviewed_by="self-asserted-reviewer",
            )
            is False
        )

    def test_hard_reset_clears_session_memory_only(self):
        mmu = SemanticMMU(session_id="session-a")
        mmu.store("session/private", {"prompt": "sensitive"}, MemoryTier.L1_CACHE)
        mmu.store("session/checkpoint", {"nonce": 1}, MemoryTier.L2_RAM)
        mmu.store("workflows/persistent/summary", "approved", MemoryTier.L3_STORAGE)

        result = mmu.hard_reset_session()

        assert result["l1_pages"] == 1
        assert result["l2_pages"] == 1
        assert mmu.fetch("session/private") is None
        assert mmu.fetch("workflows/persistent/summary") is not None
        assert mmu.session_id != "session-a"

    def test_memory_paths_reject_traversal(self):
        mmu = SemanticMMU()

        with pytest.raises(ValueError, match="unsafe path"):
            mmu.store("../../outside", "blocked", MemoryTier.L3_STORAGE)

    def test_hipif_rejects_trace_outside_memory_root(self, tmp_path):
        trace = tmp_path / "trace.log"
        trace.write_text("secret", encoding="utf-8")

        with pytest.raises(ValueError, match="contained under"):
            SemanticMMU().fold_completed_subtask("workflow", str(trace))

    def test_vm_valuation(self):
        """Test memory value consolidation scoring V(m)."""
        mmu = SemanticMMU()
        
        # High value: Contains success and aligns with safety rules
        high_value = mmu.evaluate_memory_value("Subtask bridge execution success. Tx confirmed on chain.")
        # Low value: Violates safety rules (Alignment drops to 0)
        low_value = mmu.evaluate_memory_value("Malicious exploit script triggered against RPC endpoint.")
        
        assert high_value > low_value
        assert low_value < 0.5
