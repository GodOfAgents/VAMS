import time
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum

from neuron.sdk.interrupt_handler import InterruptRequest, InterruptResult, InterruptSignal, InterruptStatus
from neuron.sdk.semantic_mmu import MemoryTier
from neuron.sdk.nonce_manager import NonceManager

logger = logging.getLogger("vams.x402_recovery")

class EscrowState(Enum):
    """Maps on-chain IX402EscrowManager.EscrowStatus plus NOT_FOUND."""
    LOCKED = 0
    CLAIMED = 1
    REFUNDED = 2
    DISPUTED = 3
    RESOLVED = 4
    NOT_FOUND = 5

@dataclass
class EscrowRecord:
    """Local mirror of on-chain escrow state."""
    escrow_id: bytes
    state: EscrowState
    amount_wei: int
    expires_at: float
    provider: str
    nonce: int
    result: Optional[Any] = None
    proof: Optional[Dict[str, Any]] = None

def compute_escrow_id(agent: str, provider: str, nonce: int, timestamp: int) -> bytes:
    """Calculate unique escrow ID mimicking on-chain keccak256."""
    data = f"{agent}:{provider}:{nonce}:{timestamp}".encode()
    return hashlib.sha256(data).digest()

class EscrowStateClient:
    """Abstraction over on-chain escrow queries."""
    def __init__(self):
        self._escrows: Dict[bytes, EscrowRecord] = {}

    def register_mock_escrow(self, escrow: EscrowRecord):
        """Register an escrow record (used in testing and mocks)."""
        self._escrows[escrow.escrow_id] = escrow

    def get_escrow_status(self, agent: str, provider: str, nonce: int) -> EscrowRecord:
        """Queries on-chain escrow state (mock implementation)."""
        for record in self._escrows.values():
            if record.provider == provider and record.nonce == nonce:
                return record
        
        return EscrowRecord(
            escrow_id=b"",
            state=EscrowState.NOT_FOUND,
            amount_wei=0,
            expires_at=0.0,
            provider=provider,
            nonce=nonce
        )

    def is_claimable(self, escrow_id: bytes) -> bool:
        """Check if escrow is in LOCKED state and not expired."""
        record = self._escrows.get(escrow_id)
        if not record:
            return False
        return record.state == EscrowState.LOCKED and time.time() < record.expires_at

    def is_refundable(self, escrow_id: bytes) -> bool:
        """Check if escrow is in LOCKED state and expired."""
        record = self._escrows.get(escrow_id)
        if not record:
            return False
        return record.state == EscrowState.LOCKED and time.time() >= record.expires_at


class X402InterruptHandler:
    """Core recovery interrupt handler managing x402 SIG_TOOL_INVOKE lifecycle."""
    def __init__(
        self,
        agent_id: str,
        escrow_client: EscrowStateClient,
        payment_client: Any,
        mmu: Any,
        nonce_manager: NonceManager,
        max_retries: int = 2,
        grace_period_seconds: float = 5.0
    ):
        self.agent_id = agent_id
        self.escrow_client = escrow_client
        self.payment_client = payment_client
        self.mmu = mmu
        self.nonce_manager = nonce_manager
        self.max_retries = max_retries
        self.grace_period_seconds = grace_period_seconds
        self.recovery_attempts = 0


    def handle_tool_invoke(self, request: InterruptRequest) -> InterruptResult:
        """Main entry point for SIG_TOOL_INVOKE interrupts."""
        # Try to restore checkpoint from MMU
        checkpoint = self.mmu.restore_interrupt_state(request.interrupt_id)
        
        recovered_nonce = None
        recovered_provider = None
        
        if checkpoint:
            self.recovery_attempts += 1
            logger.info(f"Crash recovery initiated for interrupt {request.interrupt_id}")
            nonce = checkpoint.get("nonce")
            provider = checkpoint.get("provider")
            
            result = self._recover_from_crash(request, nonce, provider)
            if result and result.status == InterruptStatus.VERIFIED:
                return result
            
            escrow = self.escrow_client.get_escrow_status(self.agent_id, provider, nonce)
            if escrow.state == EscrowState.NOT_FOUND:
                recovered_nonce = nonce
                recovered_provider = provider
                logger.info(f"Recovery found escrow NOT_FOUND. Reusing nonce {nonce} for provider {provider}")

        # Execute fresh with failover support
        providers = [request.target_provider]
        if recovered_provider and recovered_provider not in providers:
            providers.insert(0, recovered_provider)
            
        default_providers = ["io.net", "phala", "bittensor"]
        for dp in default_providers:
            if dp not in providers:
                providers.append(dp)

        last_error = None
        for attempt in range(self.max_retries + 1):
            provider = providers[attempt % len(providers)]
            logger.info(f"Attempting tool invoke with provider {provider} (attempt {attempt})")
            
            if attempt == 0 and recovered_nonce is not None and provider == recovered_provider:
                nonce = recovered_nonce
            else:
                nonce = self.nonce_manager.next_nonce("global")
            
            req_copy = InterruptRequest(
                interrupt_id=request.interrupt_id,
                signal=request.signal,
                source=request.source,
                target_provider=provider,
                payload=request.payload,
                max_cost_vams=request.max_cost_vams,
                timeout_ms=request.timeout_ms,
                require_proof=request.require_proof,
                created_at=request.created_at
            )
            
            try:
                # 1. Lock escrow
                escrow = self._lock_escrow(req_copy, nonce)
                
                # 2. Checkpoint state in MMU
                self.mmu.checkpoint_interrupt_state(request.interrupt_id, escrow, request.payload)
                
                # 3. Await delivery
                result = self._await_delivery(escrow, req_copy)
                
                if result.status == InterruptStatus.VERIFIED:
                    self._inject_result_to_mmu(request, result)
                    return result
                else:
                    last_error = result.error or "Execution failed"
            except Exception as e:
                logger.error(f"Provider {provider} failed with exception: {e}")
                last_error = str(e)

        return InterruptResult(
            interrupt_id=request.interrupt_id,
            signal=request.signal,
            status=InterruptStatus.FAILED,
            error=f"All attempts exhausted. Last error: {last_error}",
            provider=request.target_provider
        )


    def _recover_from_crash(self, request: InterruptRequest, nonce: int, provider: str) -> Optional[InterruptResult]:
        """Checks on-chain state to recover a crashed invocation."""
        escrow = self.escrow_client.get_escrow_status(self.agent_id, provider, nonce)
        
        if escrow.state == EscrowState.CLAIMED:
            logger.info(f"Escrow {escrow.escrow_id.hex()[:12]} already claimed. Reconstructing result.")
            result = InterruptResult(
                interrupt_id=request.interrupt_id,
                signal=request.signal,
                status=InterruptStatus.VERIFIED,
                result=escrow.result or {
                    "tool_output": f"Reconstructed result for {request.payload.get('tool', 'unknown')}",
                    "provider": provider,
                    "reconstructed": True
                },
                proof=escrow.proof or {
                    "type": "reconstructed_attestation",
                    "hash": hashlib.sha256(str(request.payload).encode()).hexdigest()[:16]
                },
                provider=provider,
                cost_vams=float(escrow.amount_wei) / 10**18
            )
            self._inject_result_to_mmu(request, result)
            return result
            
        elif escrow.state == EscrowState.LOCKED:
            if time.time() < escrow.expires_at:
                logger.info(f"Escrow {escrow.escrow_id.hex()[:12]} still locked. Resuming wait.")
                return self._await_delivery(escrow, request)
            else:
                logger.info(f"Escrow {escrow.escrow_id.hex()[:12]} expired. Reclaiming funds.")
                self._reclaim_expired(escrow)
                return None
                
        elif escrow.state == EscrowState.REFUNDED:
            logger.info(f"Escrow {escrow.escrow_id.hex()[:12]} already refunded.")
            return None
            
        elif escrow.state == EscrowState.NOT_FOUND:
            logger.info("No escrow found on-chain for this nonce.")
            return None
            
        return None

    def _lock_escrow(self, request: InterruptRequest, nonce: int) -> EscrowRecord:
        """Lock funds on-chain (simulated)."""
        amount_wei = int(request.max_cost_vams * 10**18)
        expires_at = time.time() + (request.timeout_ms / 1000.0)
        
        escrow_id = compute_escrow_id(self.agent_id, request.target_provider, nonce, int(time.time()))
        
        record = EscrowRecord(
            escrow_id=escrow_id,
            state=EscrowState.LOCKED,
            amount_wei=amount_wei,
            expires_at=expires_at,
            provider=request.target_provider,
            nonce=nonce
        )
        
        self.escrow_client.register_mock_escrow(record)
        return record

    def _await_delivery(self, escrow: EscrowRecord, request: InterruptRequest) -> InterruptResult:
        """Wait for delivery from provider."""
        if time.time() >= escrow.expires_at - self.grace_period_seconds:  # Configurable grace period
            logger.warning("Too close to expiry, failing fast")
            return InterruptResult(
                interrupt_id=request.interrupt_id,
                signal=request.signal,
                status=InterruptStatus.TIMEOUT,
                error="Escrow expired or too close to expiry",
                provider=escrow.provider
            )

        # Simulate execution delay
        time.sleep(0.05)

        if request.payload.get("simulate_invalid_preimage", False):
            escrow.state = EscrowState.DISPUTED
            return InterruptResult(
                interrupt_id=request.interrupt_id,
                signal=request.signal,
                status=InterruptStatus.FAILED,
                error="Disputed: HTLC preimage mismatch",
                provider=escrow.provider
            )

        # Provider claims escrow
        escrow.state = EscrowState.CLAIMED
        escrow.result = {
            "tool_output": f"Mock result for {request.payload.get('tool', 'unknown')}",
            "provider": escrow.provider,
            "mock": True
        }
        escrow.proof = {
            "type": "mock_attestation",
            "hash": hashlib.sha256(str(request.payload).encode()).hexdigest()[:16]
        }

        return InterruptResult(
            interrupt_id=request.interrupt_id,
            signal=request.signal,
            status=InterruptStatus.VERIFIED,
            result=escrow.result,
            proof=escrow.proof,
            provider=escrow.provider,
            cost_vams=float(escrow.amount_wei) / 10**18
        )

    def _reclaim_expired(self, escrow: EscrowRecord) -> InterruptResult:
        """Reclaim funds from expired escrow."""
        escrow.state = EscrowState.REFUNDED
        logger.info(f"Reclaiming funds for escrow {escrow.escrow_id.hex()[:12]}")
        return InterruptResult(
            interrupt_id=f"refund_{escrow.nonce}",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            status=InterruptStatus.INJECTED,
            result={"refunded": True},
            provider=escrow.provider
        )

    def _inject_result_to_mmu(self, request: InterruptRequest, result: InterruptResult):
        """Inject verified result to L1 cache."""
        address = f"workflows/tool_results/{request.interrupt_id}"
        self.mmu.store(address, result.result, tier=MemoryTier.L1_CACHE)
        logger.info(f"Injected result into MMU L1 cache at {address}")
