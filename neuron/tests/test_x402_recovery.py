"""
Tests for x402 SIG_TOOL_INVOKE Interrupt Recovery and Cognitive Memory Integration.
Validates the persistent nonce generation, on-chain escrow state machine recovery,
provider failover, and Semantic MMU checkpointing.
"""

import sys
import os
import time
import pytest
import shutil
from typing import Generator

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neuron.sdk.nonce_manager import NonceManager
from neuron.sdk.x402_recovery import (
    X402InterruptHandler,
    EscrowStateClient,
    EscrowState,
    EscrowRecord,
    compute_escrow_id
)
from neuron.sdk.semantic_mmu import SemanticMMU, MemoryTier


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def cleanup_temp_dirs() -> Generator[None, None, None]:
    """Clean up any files created in .data during testing."""
    dirs = [".data/nonces", ".data/memory"]
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
    yield
    for d in dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
            except Exception:
                pass


@pytest.fixture
def nonce_manager(tmp_path) -> NonceManager:
    path = str(tmp_path / "test_nonces.json")
    return NonceManager(agent_id="test_agent", persistence_path=path)


@pytest.fixture
def mock_escrow_client() -> EscrowStateClient:
    return EscrowStateClient()


@pytest.fixture
def mock_mmu() -> SemanticMMU:
    return SemanticMMU()


@pytest.fixture
def recovery_handler(nonce_manager, mock_escrow_client, mock_mmu) -> X402InterruptHandler:
    return X402InterruptHandler(
        agent_id="test_agent",
        escrow_client=mock_escrow_client,
        payment_client=None,
        mmu=mock_mmu,
        nonce_manager=nonce_manager,
        max_retries=2
    )


# ═══════════════════════════════════════════════════════════════
# Test Class 1: TestNonceManager
# ═══════════════════════════════════════════════════════════════

class TestNonceManager:
    def test_nonce_starts_at_zero(self, nonce_manager):
        assert nonce_manager.current_nonce("global") == 0
        assert nonce_manager.current_nonce("provider1") == 0

    def test_nonce_increments_monotonically(self, nonce_manager):
        n1 = nonce_manager.next_nonce("provider1")
        n2 = nonce_manager.next_nonce("provider1")
        assert n1 == 1
        assert n2 == 2
        assert nonce_manager.current_nonce("provider1") == 2

    def test_nonce_persists_across_instances(self, tmp_path):
        path = str(tmp_path / "nonces.json")
        nm1 = NonceManager("test_agent", persistence_path=path)
        nm1.next_nonce("p1")
        nm1.next_nonce("p1")
        
        nm2 = NonceManager("test_agent", persistence_path=path)
        assert nm2.current_nonce("p1") == 2
        assert nm2.next_nonce("p1") == 3

    def test_concurrent_nonce_generation(self, nonce_manager):
        import threading
        threads = []
        nonces = []
        lock = threading.Lock()
        
        def gen():
            n = nonce_manager.next_nonce("p1")
            with lock:
                nonces.append(n)
                
        for _ in range(20):
            t = threading.Thread(target=gen)
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        assert len(nonces) == 20
        assert sorted(nonces) == list(range(1, 21))

    def test_nonce_file_corruption_recovery(self, tmp_path):
        path = str(tmp_path / "corrupt_nonces.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{invalid_json_corruption_here}")
            
        nm = NonceManager("test_agent", persistence_path=path)
        assert nm.current_nonce("p1") == 0
        assert nm.next_nonce("p1") == 1


# ═══════════════════════════════════════════════════════════════
# Test Class 2: TestEscrowStateClient
# ═══════════════════════════════════════════════════════════════

class TestEscrowStateClient:
    def test_mock_client_returns_not_found_for_unknown_nonce(self, mock_escrow_client):
        rec = mock_escrow_client.get_escrow_status("test_agent", "p1", 999)
        assert rec.state == EscrowState.NOT_FOUND

    def test_mock_client_returns_locked_for_registered_escrow(self, mock_escrow_client):
        rec = EscrowRecord(b"id", EscrowState.LOCKED, 100, time.time() + 10, "p1", 1)
        mock_escrow_client.register_mock_escrow(rec)
        status = mock_escrow_client.get_escrow_status("test_agent", "p1", 1)
        assert status.state == EscrowState.LOCKED

    def test_mock_client_returns_claimed_after_claim(self, mock_escrow_client):
        rec = EscrowRecord(b"id", EscrowState.LOCKED, 100, time.time() + 10, "p1", 1)
        mock_escrow_client.register_mock_escrow(rec)
        rec.state = EscrowState.CLAIMED
        status = mock_escrow_client.get_escrow_status("test_agent", "p1", 1)
        assert status.state == EscrowState.CLAIMED

    def test_mock_client_returns_refunded_after_refund(self, mock_escrow_client):
        rec = EscrowRecord(b"id", EscrowState.LOCKED, 100, time.time() + 10, "p1", 1)
        mock_escrow_client.register_mock_escrow(rec)
        rec.state = EscrowState.REFUNDED
        status = mock_escrow_client.get_escrow_status("test_agent", "p1", 1)
        assert status.state == EscrowState.REFUNDED

    def test_mock_client_is_claimable(self, mock_escrow_client):
        rec = EscrowRecord(b"id", EscrowState.LOCKED, 100, time.time() + 10, "p1", 1)
        mock_escrow_client.register_mock_escrow(rec)
        assert mock_escrow_client.is_claimable(b"id")
        assert not mock_escrow_client.is_refundable(b"id")

    def test_mock_client_is_refundable_after_expiry(self, mock_escrow_client):
        rec = EscrowRecord(b"id", EscrowState.LOCKED, 100, time.time() - 1, "p1", 1)
        mock_escrow_client.register_mock_escrow(rec)
        assert not mock_escrow_client.is_claimable(b"id")
        assert mock_escrow_client.is_refundable(b"id")


# ═══════════════════════════════════════════════════════════════
# Test Class 3: TestX402RecoveryFreshExecution
# ═══════════════════════════════════════════════════════════════

class TestX402RecoveryFreshExecution:
    def test_fresh_execution_locks_escrow_and_returns_verified(self, recovery_handler, mock_escrow_client):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        req = InterruptRequest(
            interrupt_id="irq_fresh_1",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        assert res.result["tool_output"] == "Mock result for calculator"
        
        escrow = mock_escrow_client.get_escrow_status("test_agent", "p1", 1)
        assert escrow.state == EscrowState.CLAIMED

    def test_fresh_execution_stores_checkpoint_in_mmu(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_fresh_2",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        recovery_handler.handle_tool_invoke(req)
        
        checkpoint = mock_mmu.restore_interrupt_state("irq_fresh_2")
        assert checkpoint is not None
        assert checkpoint["nonce"] == 1
        assert checkpoint["provider"] == "p1"
        assert checkpoint["request_payload"] == {"tool": "calculator"}

    def test_fresh_execution_injects_result_to_l1_cache(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_fresh_3",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        recovery_handler.handle_tool_invoke(req)
        
        cached = mock_mmu.fetch("workflows/tool_results/irq_fresh_3")
        assert cached is not None
        assert cached.content["tool_output"] == "Mock result for calculator"

    def test_fresh_execution_increments_nonce(self, recovery_handler, nonce_manager):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_fresh_4",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        assert nonce_manager.current_nonce("global") == 0
        recovery_handler.handle_tool_invoke(req)
        assert nonce_manager.current_nonce("global") == 1



# ═══════════════════════════════════════════════════════════════
# Test Class 4: TestX402RecoveryCrashScenarios
# ═══════════════════════════════════════════════════════════════

class TestX402RecoveryCrashScenarios:
    def test_recovery_from_crash_escrow_already_claimed(self, recovery_handler, mock_escrow_client, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        escrow_id = compute_escrow_id("test_agent", "p1", 5, int(time.time()))
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.CLAIMED,
            amount_wei=1000000,
            expires_at=time.time() + 10,
            provider="p1",
            nonce=5,
            result={"tool_output": "cached_claimed_result"},
            proof={"type": "proof"}
        )
        mock_escrow_client.register_mock_escrow(record)
        
        checkpoint = {
            "nonce": 5,
            "provider": "p1",
            "escrow_id": escrow_id.hex(),
            "amount_wei": 1000000,
            "expires_at": time.time() + 10,
            "request_payload": {"tool": "search"}
        }
        mock_mmu.store("_irq_checkpoint/irq_crash_1", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_crash_1",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        res = recovery_handler.handle_tool_invoke(req)
        
        assert res.status == InterruptStatus.VERIFIED
        assert res.result["tool_output"] == "cached_claimed_result"
        assert recovery_handler.recovery_attempts == 1

    def test_recovery_from_crash_escrow_still_locked_not_expired(self, recovery_handler, mock_escrow_client, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        escrow_id = compute_escrow_id("test_agent", "p1", 5, int(time.time()))
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.LOCKED,
            amount_wei=1000000,
            expires_at=time.time() + 10,
            provider="p1",
            nonce=5
        )
        mock_escrow_client.register_mock_escrow(record)
        
        checkpoint = {
            "nonce": 5,
            "provider": "p1",
            "escrow_id": escrow_id.hex(),
            "amount_wei": 1000000,
            "expires_at": time.time() + 10,
            "request_payload": {"tool": "search"}
        }
        mock_mmu.store("_irq_checkpoint/irq_crash_2", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_crash_2",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        res = recovery_handler.handle_tool_invoke(req)
        
        assert res.status == InterruptStatus.VERIFIED
        assert record.state == EscrowState.CLAIMED
        assert recovery_handler.recovery_attempts == 1

    def test_recovery_from_crash_escrow_locked_but_expired(self, recovery_handler, mock_escrow_client, mock_mmu, nonce_manager):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        escrow_id = compute_escrow_id("test_agent", "p1", 5, int(time.time()))
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.LOCKED,
            amount_wei=1000000,
            expires_at=time.time() - 1,
            provider="p1",
            nonce=5
        )
        mock_escrow_client.register_mock_escrow(record)
        
        checkpoint = {
            "nonce": 5,
            "provider": "p1",
            "escrow_id": escrow_id.hex(),
            "amount_wei": 1000000,
            "expires_at": time.time() - 1,
            "request_payload": {"tool": "search"}
        }
        mock_mmu.store("_irq_checkpoint/irq_crash_3", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_crash_3",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        
        # Advance the nonces so that next nonce is 6 (which is fresh)
        nonce_manager.next_nonce("global") # 1
        nonce_manager.next_nonce("global") # 2
        nonce_manager.next_nonce("global") # 3
        nonce_manager.next_nonce("global") # 4
        nonce_manager.next_nonce("global") # 5
        
        res = recovery_handler.handle_tool_invoke(req)
        
        assert res.status == InterruptStatus.VERIFIED
        assert record.state == EscrowState.REFUNDED
        new_escrow = mock_escrow_client.get_escrow_status("test_agent", "p1", 6)
        assert new_escrow.state == EscrowState.CLAIMED
        assert recovery_handler.recovery_attempts == 1

    def test_recovery_from_crash_escrow_already_refunded(self, recovery_handler, mock_escrow_client, mock_mmu, nonce_manager):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        escrow_id = compute_escrow_id("test_agent", "p1", 5, int(time.time()))
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.REFUNDED,
            amount_wei=1000000,
            expires_at=time.time() - 1,
            provider="p1",
            nonce=5
        )
        mock_escrow_client.register_mock_escrow(record)
        
        checkpoint = {
            "nonce": 5,
            "provider": "p1",
            "escrow_id": escrow_id.hex(),
            "amount_wei": 1000000,
            "expires_at": time.time() - 1,
            "request_payload": {"tool": "search"}
        }
        mock_mmu.store("_irq_checkpoint/irq_crash_4", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_crash_4",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        new_escrow = mock_escrow_client.get_escrow_status("test_agent", "p1", 1)
        assert new_escrow.state == EscrowState.CLAIMED

    def test_recovery_from_crash_escrow_not_found(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        checkpoint = {
            "nonce": 5,
            "provider": "p1",
            "escrow_id": "0x00",
            "amount_wei": 1000000,
            "expires_at": time.time() + 10,
            "request_payload": {"tool": "search"}
        }
        mock_mmu.store("_irq_checkpoint/irq_crash_5", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_crash_5",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        new_escrow = recovery_handler.escrow_client.get_escrow_status("test_agent", "p1", 5)
        assert new_escrow.state == EscrowState.CLAIMED

    def test_recovery_does_not_double_spend(self, recovery_handler, mock_escrow_client, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        escrow_id = compute_escrow_id("test_agent", "p1", 10, int(time.time()))
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.LOCKED,
            amount_wei=1000000,
            expires_at=time.time() + 10,
            provider="p1",
            nonce=10
        )
        mock_escrow_client.register_mock_escrow(record)
        
        checkpoint = {
            "nonce": 10,
            "provider": "p1",
            "escrow_id": escrow_id.hex(),
            "amount_wei": 1000000,
            "expires_at": time.time() + 10,
            "request_payload": {"tool": "search"}
        }
        mock_mmu.store("_irq_checkpoint/irq_double_spend", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_double_spend",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        
        all_escrows = [e for e in mock_escrow_client._escrows.values() if e.nonce == 10]
        assert len(all_escrows) == 1

    def test_recovery_with_htlc_preimage_mismatch(self, recovery_handler, mock_escrow_client, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        escrow_id = compute_escrow_id("test_agent", "p1", 12, int(time.time()))
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.LOCKED,
            amount_wei=1000000,
            expires_at=time.time() + 10,
            provider="p1",
            nonce=12
        )
        mock_escrow_client.register_mock_escrow(record)
        
        checkpoint = {
            "nonce": 12,
            "provider": "p1",
            "escrow_id": escrow_id.hex(),
            "amount_wei": 1000000,
            "expires_at": time.time() + 10,
            "request_payload": {"tool": "search", "simulate_invalid_preimage": True}
        }
        mock_mmu.store("_irq_checkpoint/irq_preimage_fail", checkpoint, tier=MemoryTier.L2_RAM)
        
        req = InterruptRequest(
            interrupt_id="irq_preimage_fail",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search", "simulate_invalid_preimage": True}
        )
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.FAILED
        assert "HTLC preimage mismatch" in res.error
        assert record.state == EscrowState.DISPUTED

    def test_configurable_grace_period(self, recovery_handler):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        from neuron.sdk.x402_recovery import EscrowRecord, EscrowState
        
        recovery_handler.grace_period_seconds = 10.0
        
        escrow = EscrowRecord(
            escrow_id=b"id_grace",
            state=EscrowState.LOCKED,
            amount_wei=1000000,
            expires_at=time.time() + 8.0,
            provider="p1",
            nonce=1
        )
        
        req = InterruptRequest(
            interrupt_id="irq_grace",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "search"}
        )
        
        res = recovery_handler._await_delivery(escrow, req)
        assert res.status == InterruptStatus.TIMEOUT
        assert "expired" in res.error.lower() or "expiry" in res.error.lower()



# ═══════════════════════════════════════════════════════════════
# Test Class 5: TestX402ProviderFailover
# ═══════════════════════════════════════════════════════════════

class TestX402ProviderFailover:
    def test_provider_timeout_triggers_failover(self, recovery_handler):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        original_await = recovery_handler._await_delivery
        
        def mock_await_delivery(escrow, req):
            if req.target_provider == "phala":
                raise Exception("Phala provider offline")
            return original_await(escrow, req)
            
        recovery_handler._await_delivery = mock_await_delivery
        
        req = InterruptRequest(
            interrupt_id="irq_failover_1",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="phala",
            payload={"tool": "calculator"}
        )
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        assert res.provider in ["io.net", "bittensor"]

    def test_max_retries_exhausted_returns_failed(self, recovery_handler):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        def mock_await_delivery(escrow, req):
            raise Exception("Provider offline")
            
        recovery_handler._await_delivery = mock_await_delivery
        recovery_handler.max_retries = 2
        
        req = InterruptRequest(
            interrupt_id="irq_failover_2",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.FAILED
        assert "All attempts exhausted" in res.error

    def test_failover_uses_fresh_nonce_per_provider(self, recovery_handler):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        
        locked_nonces = []
        original_lock = recovery_handler._lock_escrow
        
        def mock_lock_escrow(req, nonce):
            locked_nonces.append((req.target_provider, nonce))
            if req.target_provider == "phala":
                raise Exception("fail")
            return original_lock(req, nonce)
            
        recovery_handler._lock_escrow = mock_lock_escrow
        
        req = InterruptRequest(
            interrupt_id="irq_failover_3",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="phala",
            payload={"tool": "calculator"}
        )
        
        recovery_handler.handle_tool_invoke(req)
        assert len(locked_nonces) == 2
        assert locked_nonces[0][0] == "phala"
        assert locked_nonces[1][0] == "io.net"
        assert locked_nonces[0][1] != locked_nonces[1][1]


# ═══════════════════════════════════════════════════════════════
# Test Class 6: TestX402MMUIntegration
# ═══════════════════════════════════════════════════════════════

class TestX402MMUIntegration:
    def test_interrupt_checkpoint_stored_in_l2(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_mmu_1",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        recovery_handler.handle_tool_invoke(req)
        
        address = "_irq_checkpoint/irq_mmu_1"
        assert address in mock_mmu._l2_store
        assert mock_mmu._l2_store[address].tier == MemoryTier.L2_RAM

    def test_interrupt_checkpoint_survives_l1_eviction(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_mmu_2",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        recovery_handler.handle_tool_invoke(req)
        
        mock_mmu.l1_capacity = 4
        for i in range(10):
            mock_mmu.store(f"dummy_{i}", "content")
            
        address = "_irq_checkpoint/irq_mmu_2"
        assert address not in mock_mmu._l1_cache
        
        checkpoint = mock_mmu.restore_interrupt_state("irq_mmu_2")
        assert checkpoint is not None
        assert checkpoint["nonce"] == 1

    def test_restore_interrupt_state_returns_correct_nonce(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_mmu_3",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        recovery_handler.handle_tool_invoke(req)
        
        checkpoint = mock_mmu.restore_interrupt_state("irq_mmu_3")
        assert checkpoint["nonce"] == 1

    def test_verified_result_injected_into_l1_cache(self, recovery_handler, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal
        req = InterruptRequest(
            interrupt_id="irq_mmu_4",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        recovery_handler.handle_tool_invoke(req)
        
        cached = mock_mmu._l1_cache.get("workflows/tool_results/irq_mmu_4")
        assert cached is not None
        assert cached.content["tool_output"] == "Mock result for calculator"


# ═══════════════════════════════════════════════════════════════
# Test Class 7: TestX402EscrowLifecycleIntegration
# ═══════════════════════════════════════════════════════════════

class TestX402EscrowLifecycleIntegration:
    def test_full_lifecycle_lock_deliver_claim_inject(self, recovery_handler, mock_escrow_client, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        req = InterruptRequest(
            interrupt_id="irq_lifecycle_1",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        
        cached = mock_mmu.fetch("workflows/tool_results/irq_lifecycle_1")
        assert cached is not None
        
        escrow = mock_escrow_client.get_escrow_status("test_agent", "p1", 1)
        assert escrow.state == EscrowState.CLAIMED

    def test_full_lifecycle_with_crash_and_recovery(self, recovery_handler, mock_escrow_client, mock_mmu):
        from neuron.sdk.interrupt_handler import InterruptRequest, InterruptSignal, InterruptStatus
        
        req = InterruptRequest(
            interrupt_id="irq_lifecycle_2",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            source="test_agent",
            target_provider="p1",
            payload={"tool": "calculator"}
        )
        
        escrow = recovery_handler._lock_escrow(req, 100)
        mock_mmu.checkpoint_interrupt_state(req.interrupt_id, escrow, req.payload)
        mock_mmu._l1_cache.clear()
        
        res = recovery_handler.handle_tool_invoke(req)
        assert res.status == InterruptStatus.VERIFIED
        assert res.provider == "p1"
        assert recovery_handler.recovery_attempts == 1

    def test_full_lifecycle_with_proplay_guidance(self, recovery_handler):
        from intelligence.world_model import ProPlayWorldModel
        
        wm = ProPlayWorldModel(filepath=".data/memory/test_lifecycle_graph.json")
        wm.add_procedure("lock_escrow", "Lock VAMS escrow")
        wm.add_procedure("deliver_service", "Deliver DePIN service")
        wm.add_procedure("claim_escrow", "Claim locked escrow")
        
        wm.record_transition("lock_escrow", "deliver_service", reward=1.0, task_description="x402 tool invoke")
        wm.record_transition("deliver_service", "claim_escrow", reward=1.0, task_description="x402 tool invoke")
        
        guidance = wm.get_soft_guidance("x402 tool invoke")
        assert "lock_escrow -> deliver_service -> claim_escrow" in guidance
