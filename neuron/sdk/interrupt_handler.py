"""
VAMS Neuron - Interrupt Vector Table & x402 Interrupt Handler
==============================================================
Maps AgentOS Interrupt Vector Table (IVT) onto the VAMS x402
micropayment flow. Every tool call is an OS-level interrupt that
triggers HTLC escrow → DePIN execution → verified result injection.

Interrupt Types:
    SIG_TOOL_INVOKE  → x402 HTLC Escrow (per-call micropayment)
    SIG_MEM_FAULT    → S-MMU Page Fault (storage retrieval fee)
    SIG_SYNC_PULSE   → CSP Oracle Query (oracle query fee)
    SIG_CHECKPOINT   → DBOS State Commit (DA posting fee)
    SIG_MIGRATE      → Agent Migration (compute re-provisioning)

Reference: AGENTOS_INTEGRATION.md §2.4
"""

import time
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from enum import Enum

logger = logging.getLogger("vams.interrupt_handler")


class InterruptSignal(Enum):
    """AgentOS interrupt signals mapped to VAMS economic events."""
    SIG_TOOL_INVOKE = "tool_invoke"       # External tool call
    SIG_MEM_FAULT = "mem_fault"           # S-MMU page fault
    SIG_SYNC_PULSE = "sync_pulse"         # Cognitive Sync Pulse
    SIG_CHECKPOINT = "checkpoint"          # DBOS state commit
    SIG_MIGRATE = "migrate"                # Agent migration


class InterruptStatus(Enum):
    """Status of an interrupt in the pipeline."""
    PENDING = "pending"
    ESCROW_LOCKED = "escrow_locked"
    EXECUTING = "executing"
    RESULT_READY = "result_ready"
    VERIFIED = "verified"
    INJECTED = "injected"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class InterruptRequest:
    """
    An interrupt request from the Reasoning Kernel.
    
    Created when the RK determines a tool call / external action is needed.
    Routes through the VAMS x402 pipeline for economic settlement.
    """
    interrupt_id: str
    signal: InterruptSignal
    source: str                     # Agent ID
    target_provider: str            # DePIN provider (io.net, Phala, etc.)
    payload: Dict[str, Any]         # Tool call parameters
    max_cost_vams: float = 1.0      # Maximum VAMS to escrow
    timeout_ms: int = 30_000        # HTLC timelock (ms)
    require_proof: bool = True      # Require TEE attestation / ZK proof
    created_at: float = field(default_factory=time.time)


@dataclass
class InterruptResult:
    """
    Result of an interrupt execution.
    
    Contains the tool result + verification proof for injection
    back into the agent's L1 cache (S-MMU).
    """
    interrupt_id: str
    signal: InterruptSignal
    status: InterruptStatus
    result: Optional[Any] = None
    proof: Optional[Dict[str, Any]] = None   # TEE attestation or ZK proof
    provider: Optional[str] = None
    cost_vams: float = 0.0
    latency_ms: float = 0.0
    error: Optional[str] = None
    completed_at: float = field(default_factory=time.time)


# Default provider routing per signal type
DEFAULT_PROVIDER_ROUTING = {
    InterruptSignal.SIG_TOOL_INVOKE: ["io.net", "phala", "bittensor"],
    InterruptSignal.SIG_MEM_FAULT: ["near", "glacier", "arweave"],
    InterruptSignal.SIG_SYNC_PULSE: ["vams_oracle"],
    InterruptSignal.SIG_CHECKPOINT: ["celestia", "polygon_da"],
    InterruptSignal.SIG_MIGRATE: ["akash", "io.net"],
}

# Default cost table (VAMS) per signal type
DEFAULT_COST_TABLE = {
    InterruptSignal.SIG_TOOL_INVOKE: 1.0,
    InterruptSignal.SIG_MEM_FAULT: 0.01,
    InterruptSignal.SIG_SYNC_PULSE: 0.5,
    InterruptSignal.SIG_CHECKPOINT: 0.005,
    InterruptSignal.SIG_MIGRATE: 5.0,
}


class InterruptVectorTable:
    """
    VAMS implementation of the AgentOS Interrupt Vector Table.
    
    Routes tool calls through the x402 micropayment pipeline:
    
    1. RK Decision  → SIG_TOOL_INVOKE interrupt
    2. IVT pauses   → Reasoning thread suspended
    3. HTLC Lock    → $VAMS escrowed for DePIN provider
    4. Execution    → Provider processes + returns proof
    5. Verification → Proof validated (TEE attestation / ZK)
    6. Injection    → Result injected into L1 cache, thread resumes
    
    In local/mock mode, steps 3-5 are simulated. When connected to
    real VAMS infrastructure, uses the x402 payment channel.
    
    Args:
        agent_id: Unique agent identifier
        mock_mode: Simulate x402 payments (for local dev)
        timeout_ms: Default HTLC timelock in milliseconds
        max_retries: Number of provider failover attempts
    """
    
    def __init__(
        self,
        agent_id: str = "local_agent",
        mock_mode: bool = True,
        timeout_ms: int = 30_000,
        max_retries: int = 2,
        x402_handler: Optional[Any] = None
    ):
        self.agent_id = agent_id
        self.mock_mode = mock_mode
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self._x402_handler = x402_handler
        
        # Registered interrupt handlers (signal → callback)
        self._handlers: Dict[InterruptSignal, Callable] = {}
        
        # Interrupt history
        self._history: List[InterruptResult] = []
        self._active_interrupt: Optional[InterruptRequest] = None
        
        # Payment tracking
        self._total_spent_vams = 0.0
        self._interrupt_count = 0
        
        # Statistics
        self._stats = {
            "total_interrupts": 0,
            "successful": 0,
            "failed": 0,
            "timeouts": 0,
            "total_cost_vams": 0.0,
            "avg_latency_ms": 0.0,
            "by_signal": {sig.value: 0 for sig in InterruptSignal}
        }
        
        # Register default handlers
        self._register_default_handlers()
        
        # Wire custom x402 handler if provided and not mock_mode
        if not self.mock_mode and self._x402_handler is not None:
            self.register_x402_handler(self._x402_handler)

    
    def _register_default_handlers(self):
        """Register mock handlers for all interrupt signals."""
        self._handlers[InterruptSignal.SIG_TOOL_INVOKE] = self._handle_tool_invoke
        self._handlers[InterruptSignal.SIG_MEM_FAULT] = self._handle_mem_fault
        self._handlers[InterruptSignal.SIG_SYNC_PULSE] = self._handle_sync_pulse
        self._handlers[InterruptSignal.SIG_CHECKPOINT] = self._handle_checkpoint
        self._handlers[InterruptSignal.SIG_MIGRATE] = self._handle_migrate
    
    def register_handler(
        self, 
        signal: InterruptSignal, 
        handler: Callable[[InterruptRequest], InterruptResult]
    ):
        """
        Register a custom interrupt handler.
        
        Used to wire real x402 payment channels when connected
        to VAMS infrastructure.
        """
        self._handlers[signal] = handler
        logger.info(f"Custom handler registered for {signal.value}")

    def register_x402_handler(self, handler: Any):
        """Convenience method to register a custom x402 recovery interrupt handler."""
        self._x402_handler = handler
        self.register_handler(InterruptSignal.SIG_TOOL_INVOKE, handler.handle_tool_invoke)

    
    def raise_interrupt(
        self,
        signal: InterruptSignal,
        payload: Dict[str, Any],
        target_provider: Optional[str] = None,
        max_cost: Optional[float] = None,
        timeout_ms: Optional[int] = None
    ) -> InterruptResult:
        """
        Raise an interrupt — the core IVT operation.
        
        This suspends the reasoning thread, routes through x402,
        and returns the verified result for L1 cache injection.
        
        Args:
            signal: Interrupt signal type
            payload: Tool call parameters / request data
            target_provider: Override default provider routing
            max_cost: Override default cost limit (VAMS)
            timeout_ms: Override default HTLC timelock
            
        Returns:
            InterruptResult with verified result or error
        """
        self._interrupt_count += 1
        self._stats["total_interrupts"] += 1
        self._stats["by_signal"][signal.value] += 1
        
        # Resolve provider
        if not target_provider:
            providers = DEFAULT_PROVIDER_ROUTING.get(signal, ["default"])
            target_provider = providers[0]
        
        # Resolve cost
        if max_cost is None:
            max_cost = DEFAULT_COST_TABLE.get(signal, 1.0)
        
        # Create interrupt request
        request = InterruptRequest(
            interrupt_id=f"irq_{self._interrupt_count}_{signal.value}",
            signal=signal,
            source=self.agent_id,
            target_provider=target_provider,
            payload=payload,
            max_cost_vams=max_cost,
            timeout_ms=timeout_ms or self.timeout_ms
        )
        
        self._active_interrupt = request
        start_time = time.time()
        
        logger.info(
            f"IRQ raised: {request.interrupt_id} "
            f"[{signal.value}] → {target_provider} "
            f"(max: {max_cost} VAMS, timeout: {request.timeout_ms}ms)"
        )
        
        # Execute through handler
        try:
            handler = self._handlers.get(signal)
            if not handler:
                raise ValueError(f"No handler for signal {signal.value}")
            
            result = handler(request)
            result.latency_ms = (time.time() - start_time) * 1000
            
            # Update stats
            if result.status in (InterruptStatus.VERIFIED, InterruptStatus.INJECTED):
                self._stats["successful"] += 1
                self._total_spent_vams += result.cost_vams
                self._stats["total_cost_vams"] = self._total_spent_vams
            elif result.status == InterruptStatus.TIMEOUT:
                self._stats["timeouts"] += 1
            else:
                self._stats["failed"] += 1
            
            # Update average latency
            n = self._stats["successful"] + self._stats["failed"] + self._stats["timeouts"]
            self._stats["avg_latency_ms"] = (
                self._stats["avg_latency_ms"] * (n - 1) + result.latency_ms
            ) / n
            
        except Exception as e:
            result = InterruptResult(
                interrupt_id=request.interrupt_id,
                signal=signal,
                status=InterruptStatus.FAILED,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )
            self._stats["failed"] += 1
            logger.error(f"IRQ failed: {request.interrupt_id} — {e}")
        
        self._history.append(result)
        self._active_interrupt = None
        
        # Keep last 100 results
        if len(self._history) > 100:
            self._history = self._history[-50:]
        
        return result
    
    # ─────────────────────────────────────────────────────────────────
    # Default Handlers (Mock Mode)
    # ─────────────────────────────────────────────────────────────────
    
    def _handle_tool_invoke(self, req: InterruptRequest) -> InterruptResult:
        """Handle SIG_TOOL_INVOKE — external tool call via x402."""
        if self.mock_mode:
            # Simulate: HTLC lock → execution → result
            time.sleep(0.05)  # Simulate 50ms network
            return InterruptResult(
                interrupt_id=req.interrupt_id,
                signal=req.signal,
                status=InterruptStatus.VERIFIED,
                result={
                    "tool_output": f"Mock result for {req.payload.get('tool', 'unknown')}",
                    "provider": req.target_provider,
                    "mock": True
                },
                proof={
                    "type": "mock_attestation",
                    "hash": hashlib.sha256(str(req.payload).encode()).hexdigest()[:16]
                },
                provider=req.target_provider,
                cost_vams=req.max_cost_vams * 0.8  # 80% of max
            )
        
        # TODO: Real x402 HTLC flow when connected to VAMS infra
        raise NotImplementedError("Real x402 interrupt handler not yet implemented")
    
    def _handle_mem_fault(self, req: InterruptRequest) -> InterruptResult:
        """Handle SIG_MEM_FAULT — S-MMU page fault retrieval."""
        if self.mock_mode:
            time.sleep(0.02)
            return InterruptResult(
                interrupt_id=req.interrupt_id,
                signal=req.signal,
                status=InterruptStatus.VERIFIED,
                result={"page_data": None, "from_tier": "L3_STORAGE", "mock": True},
                provider=req.target_provider,
                cost_vams=0.01
            )
        raise NotImplementedError("Real memory fault handler not yet implemented")
    
    def _handle_sync_pulse(self, req: InterruptRequest) -> InterruptResult:
        """Handle SIG_SYNC_PULSE — Cognitive Sync Pulse via oracle."""
        if self.mock_mode:
            time.sleep(0.1)
            return InterruptResult(
                interrupt_id=req.interrupt_id,
                signal=req.signal,
                status=InterruptStatus.VERIFIED,
                result={
                    "reconciled_state": "mock_s_global",
                    "participants": 1,
                    "mock": True
                },
                provider="vams_oracle",
                cost_vams=0.5
            )
        raise NotImplementedError("Real sync pulse handler not yet implemented")
    
    def _handle_checkpoint(self, req: InterruptRequest) -> InterruptResult:
        """Handle SIG_CHECKPOINT — DA posting for state commit."""
        if self.mock_mode:
            time.sleep(0.01)
            return InterruptResult(
                interrupt_id=req.interrupt_id,
                signal=req.signal,
                status=InterruptStatus.VERIFIED,
                result={
                    "da_commitment": hashlib.sha256(
                        str(req.payload).encode()
                    ).hexdigest()[:16],
                    "mock": True
                },
                provider=req.target_provider,
                cost_vams=0.005
            )
        raise NotImplementedError("Real checkpoint handler not yet implemented")
    
    def _handle_migrate(self, req: InterruptRequest) -> InterruptResult:
        """Handle SIG_MIGRATE — agent migration to new provider."""
        if self.mock_mode:
            time.sleep(0.2)
            return InterruptResult(
                interrupt_id=req.interrupt_id,
                signal=req.signal,
                status=InterruptStatus.VERIFIED,
                result={
                    "new_provider": req.target_provider,
                    "migration_time_ms": 200,
                    "mock": True
                },
                provider=req.target_provider,
                cost_vams=5.0
            )
        raise NotImplementedError("Real migration handler not yet implemented")
    
    def get_stats(self) -> Dict[str, Any]:
        """Return IVT statistics."""
        return {
            **self._stats,
            "mock_mode": self.mock_mode,
            "agent_id": self.agent_id,
            "active_interrupt": (
                self._active_interrupt.interrupt_id 
                if self._active_interrupt else None
            )
        }
