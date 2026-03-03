"""
Tests for AgentOS Cognitive Runtime SDK Modules
=================================================
Covers: SemanticCheckpointManager, SemanticMMU, InterruptVectorTable,
        CognitiveDriftDetector
"""

import sys
import os
import io
import math
import time
import logging

# Fix Windows console encoding for Unicode in log output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Suppress debug logging during tests (avoid console encoding issues)
logging.basicConfig(level=logging.WARNING)

# Ensure neuron directory is on path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# ─────────────────────────────────────────────────────────────────────
# 1. Semantic Checkpoint Manager
# ─────────────────────────────────────────────────────────────────────

def test_cid_computation():
    """Test CID computation from attention weights."""
    from sdk.semantic_checkpoint import SemanticCheckpointManager
    
    mgr = SemanticCheckpointManager(epsilon=0.15)
    
    # Uniform attention → low CID (high entropy → unfocused)
    uniform = [[0.25, 0.25, 0.25, 0.25]]
    cid = mgr.compute_cid(uniform, num_heads=1, position=4)
    assert 0.0 <= cid <= 1.0, f"CID out of range: {cid}"
    
    # Focused attention → high CID (low entropy → concentrated)
    focused = [[0.97, 0.01, 0.01, 0.01]]
    cid_focused = mgr.compute_cid(focused, num_heads=1, position=4)
    assert cid_focused > cid, f"Focused CID ({cid_focused}) should be higher than uniform ({cid})"
    
    print(f"  [PASS] CID computation: uniform={cid:.4f}, focused={cid_focused:.4f}")


def test_boundary_detection():
    """Test semantic boundary detection via CID derivatives."""
    from sdk.semantic_checkpoint import SemanticCheckpointManager
    
    mgr = SemanticCheckpointManager(epsilon=0.15, min_interval=1, max_interval=100)
    
    # Stable CID → no boundary
    for _ in range(5):
        is_boundary, _ = mgr.detect_boundary(0.5)
    assert not is_boundary, "Should not detect boundary with stable CID"
    
    # Sharp CID change → boundary
    is_boundary, derivative = mgr.detect_boundary(0.9)  # Jump of 0.4
    assert is_boundary, f"Should detect boundary (derivative={derivative:.4f})"
    
    print(f"  [PASS] Boundary detection: derivative={derivative:.4f} > ε=0.15")


def test_semantic_page_creation():
    """Test semantic page creation and verification."""
    from sdk.semantic_checkpoint import SemanticCheckpointManager, CheckpointTrigger
    
    mgr = SemanticCheckpointManager()
    state = {"agent_id": "test", "step": 3, "data": [1, 2, 3]}
    
    page = mgr.create_semantic_page(state, CheckpointTrigger.SEMANTIC_BOUNDARY, cid_score=0.8)
    assert page.verify(), "Page integrity verification failed"
    assert page.cid_score == 0.8
    assert "sp_" in page.page_id
    
    print(f"  [PASS] Semantic page: {page.page_id} (hash={page.content_hash[:12]}...)")


def test_cid_from_logits():
    """Test CID approximation from logits (fallback mode)."""
    from sdk.semantic_checkpoint import SemanticCheckpointManager
    
    mgr = SemanticCheckpointManager()
    
    # High confidence logits → high CID
    confident = [10.0, 0.1, 0.1, 0.1]
    cid_high = mgr.compute_cid_from_logits(confident)
    
    # Uniform logits → low CID
    uniform = [1.0, 1.0, 1.0, 1.0]
    cid_low = mgr.compute_cid_from_logits(uniform)
    
    assert cid_high > cid_low, f"Confident CID ({cid_high}) should > uniform ({cid_low})"
    
    print(f"  [PASS] CID from logits: confident={cid_high:.4f}, uniform={cid_low:.4f}")


# ─────────────────────────────────────────────────────────────────────
# 2. Semantic MMU
# ─────────────────────────────────────────────────────────────────────

def test_mmu_store_and_fetch():
    """Test basic store/fetch in L1 cache."""
    from sdk.semantic_mmu import SemanticMMU, MemoryTier
    
    mmu = SemanticMMU(l1_capacity=4)
    
    mmu.store("market_data", {"BTC": 60000}, MemoryTier.L1_CACHE)
    page = mmu.fetch("market_data")
    
    assert page is not None, "Fetch returned None"
    assert page.content["BTC"] == 60000
    assert page.verify(), "Integrity check failed"
    
    print(f"  [PASS] S-MMU store/fetch: {page.address} (verified)")


def test_mmu_lru_eviction():
    """Test LRU eviction when L1 is full."""
    from sdk.semantic_mmu import SemanticMMU, MemoryTier
    
    mmu = SemanticMMU(l1_capacity=3)
    
    mmu.store("a", {"v": 1}, MemoryTier.L1_CACHE)
    mmu.store("b", {"v": 2}, MemoryTier.L1_CACHE)
    mmu.store("c", {"v": 3}, MemoryTier.L1_CACHE)
    mmu.store("d", {"v": 4}, MemoryTier.L1_CACHE)  # Evicts "a"
    
    stats = mmu.get_stats()
    assert stats["evictions"] == 1, f"Expected 1 eviction, got {stats['evictions']}"
    assert stats["l1_pages"] == 3
    
    # "a" should still be in L2 (demoted)
    page_a = mmu.fetch("a")
    assert page_a is not None, "Evicted page should be in L2"
    assert stats["l2_pages"] >= 1
    
    print(f"  [PASS] LRU eviction: {stats['evictions']} evictions, demoted to L2")


def test_mmu_page_fault():
    """Test page fault for non-existent address."""
    from sdk.semantic_mmu import SemanticMMU
    
    mmu = SemanticMMU()
    page = mmu.fetch("nonexistent")
    
    assert page is None, "Should return None for missing address"
    stats = mmu.get_stats()
    assert stats["page_faults"] >= 1
    
    print(f"  [PASS] Page fault: {stats['page_faults']} faults detected")


# ─────────────────────────────────────────────────────────────────────
# 3. Interrupt Vector Table
# ─────────────────────────────────────────────────────────────────────

def test_ivt_tool_invoke():
    """Test SIG_TOOL_INVOKE interrupt (mock mode)."""
    from sdk.interrupt_handler import InterruptVectorTable, InterruptSignal, InterruptStatus
    
    ivt = InterruptVectorTable(agent_id="test_agent", mock_mode=True)
    
    result = ivt.raise_interrupt(
        InterruptSignal.SIG_TOOL_INVOKE,
        payload={"tool": "market_query", "params": {"symbol": "BTC"}},
        target_provider="io.net"
    )
    
    assert result.status == InterruptStatus.VERIFIED, f"Expected VERIFIED, got {result.status}"
    assert result.cost_vams > 0, "Cost should be > 0"
    assert result.result is not None
    
    stats = ivt.get_stats()
    assert stats["successful"] == 1
    
    print(f"  [PASS] SIG_TOOL_INVOKE: cost={result.cost_vams:.3f} VAMS, latency={result.latency_ms:.1f}ms")


def test_ivt_all_signals():
    """Test all interrupt signal types."""
    from sdk.interrupt_handler import InterruptVectorTable, InterruptSignal, InterruptStatus
    
    ivt = InterruptVectorTable(agent_id="test_agent", mock_mode=True)
    
    signals = [
        (InterruptSignal.SIG_TOOL_INVOKE, {"tool": "test"}),
        (InterruptSignal.SIG_MEM_FAULT, {"address": "market_data"}),
        (InterruptSignal.SIG_SYNC_PULSE, {"agents": ["a1", "a2"]}),
        (InterruptSignal.SIG_CHECKPOINT, {"state": {"step": 1}}),
        (InterruptSignal.SIG_MIGRATE, {"target": "akash"}),
    ]
    
    for sig, payload in signals:
        result = ivt.raise_interrupt(sig, payload)
        assert result.status == InterruptStatus.VERIFIED, f"{sig.value} failed: {result.status}"
    
    stats = ivt.get_stats()
    assert stats["total_interrupts"] == 5
    assert stats["successful"] == 5
    
    print(f"  [PASS] All 5 signals verified, total cost={stats['total_cost_vams']:.3f} VAMS")


# ─────────────────────────────────────────────────────────────────────
# 4. Cognitive Drift Detector
# ─────────────────────────────────────────────────────────────────────

def test_drift_aligned():
    """Test drift measurement when agent is aligned."""
    from sdk.cognitive_drift import CognitiveDriftDetector, DriftStatus
    
    detector = CognitiveDriftDetector(theta=0.3)
    
    # Set global state
    detector.set_global_state({"goal": "trade BTC", "mode": "active"})
    
    # Measure drift with similar state
    drift, status = detector.measure_drift("agent_1", {"goal": "trade BTC", "mode": "active"})
    
    # Same state → should be aligned (drift ≈ 0)
    assert status == DriftStatus.ALIGNED, f"Expected ALIGNED, got {status}"
    
    print(f"  [PASS] Drift aligned: Δψ={drift:.4f}, status={status.value}")


def test_drift_diverged():
    """Test drift detection with divergent state."""
    from sdk.cognitive_drift import CognitiveDriftDetector, DriftStatus
    
    detector = CognitiveDriftDetector(theta=0.01)  # Very low threshold
    
    detector.set_global_state({"goal": "trade BTC"})
    
    # Repeatedly inject divergent states to accumulate drift
    for i in range(20):
        drift, status = detector.measure_drift("agent_1", {"goal": f"state_{i}", "noise": i * 100})
    
    assert detector.check_sync_required(), "Should require sync after divergent states"
    
    print(f"  [PASS] Drift diverged: Δψ={drift:.4f}, sync_required=True")


def test_csp_reconciliation():
    """Test Cognitive Sync Pulse reconciliation."""
    from sdk.cognitive_drift import CognitiveDriftDetector, CSPStatus
    
    detector = CognitiveDriftDetector(theta=0.01, min_oracle_participants=3)
    
    detector.set_global_state({"epoch": 1})
    detector.measure_drift("agent_1", {"epoch": 1, "data": "different"})
    
    result = detector.trigger_sync_pulse()
    
    assert result.status == CSPStatus.COMMITTED, f"Expected COMMITTED, got {result.status}"
    assert result.participants >= 3
    assert result.reconciled_hash is not None
    
    stats = detector.get_stats()
    assert stats["csp_successful"] == 1
    
    print(f"  [PASS] CSP reconciliation: {result.csp_id} ({result.consensus_time_ms:.1f}ms, {result.participants} oracles)")


# ─────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  VAMS AgentOS Cognitive Runtime - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Semantic Checkpoint Manager", [
            test_cid_computation,
            test_boundary_detection,
            test_semantic_page_creation,
            test_cid_from_logits,
        ]),
        ("Semantic MMU (S-MMU)", [
            test_mmu_store_and_fetch,
            test_mmu_lru_eviction,
            test_mmu_page_fault,
        ]),
        ("Interrupt Vector Table (IVT)", [
            test_ivt_tool_invoke,
            test_ivt_all_signals,
        ]),
        ("Cognitive Drift Detector", [
            test_drift_aligned,
            test_drift_diverged,
            test_csp_reconciliation,
        ]),
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    for section, test_fns in tests:
        print(f"\n[{section}]")
        for fn in test_fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  [FAIL] {fn.__name__}: {e}")
    
    print()
    print("-" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print("-" * 60)
    print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
