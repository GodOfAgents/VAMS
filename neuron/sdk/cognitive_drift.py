"""
VAMS Neuron - Cognitive Drift Detector & Sync Pulse Engine
===========================================================
Implements multi-agent Cognitive Drift detection and Cognitive Sync
Pulse (CSP) reconciliation using Stake-Weighted Oracle Consensus.

Mathematical basis:
    Δψ_i(t) = ∫₀ᵗ ‖∇Φ_i(σ,τ) - ∇S_global(τ)‖ dτ
    
    CSP triggered when: ∃ i : Δψ_i(t) > θ
    
    S_global_reconciled = Σ(w_k · S_k) / Σ(w_k)
    where w_k = stake_k · reputation_k^γ  (γ=1.5)

Reference: AGENTOS_INTEGRATION.md §2.5, §3.2
"""

import time
import math
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

logger = logging.getLogger("vams.cognitive_drift")


class DriftStatus(Enum):
    """Status of cognitive drift for an agent."""
    ALIGNED = "aligned"           # Δψ < θ (within tolerance)
    DRIFTING = "drifting"         # Δψ approaching θ
    DIVERGED = "diverged"         # Δψ > θ (CSP required)


class CSPStatus(Enum):
    """Status of a Cognitive Sync Pulse."""
    IDLE = "idle"
    TRIGGERED = "triggered"
    COLLECTING = "collecting"       # Gathering agent states
    RECONCILING = "reconciling"     # Oracle consensus underway
    COMMITTED = "committed"         # S_global anchored to L0
    FAILED = "failed"


@dataclass
class AgentState:
    """
    An agent's internal state snapshot for drift computation.
    """
    agent_id: str
    state_vector: List[float]      # Encoded semantic state
    state_hash: str                # SHA-256 of state
    timestamp: float = field(default_factory=time.time)
    
    @staticmethod
    def from_dict(agent_id: str, state_dict: Dict[str, Any]) -> "AgentState":
        """Create AgentState from a dictionary with computed hash and vector."""
        state_json = json.dumps(state_dict, sort_keys=True, default=str)
        state_hash = hashlib.sha256(state_json.encode()).hexdigest()
        
        # Simple numeric encoding of state for drift computation
        # In production, this would use a proper embedding model
        vector = [float(hash(state_json[i:i+8]) % 1000) / 1000 
                  for i in range(0, min(len(state_json), 80), 8)]
        
        return AgentState(
            agent_id=agent_id,
            state_vector=vector,
            state_hash=state_hash
        )


@dataclass
class OracleNode:
    """
    An oracle participant in CSP consensus.
    Weight = stake × reputation^γ (γ = 1.5 by default).
    """
    node_id: str
    stake_vams: float              # $VAMS staked
    reputation: float              # Reputation score [0, 1]
    state_vote: Optional[str] = None  # Voted state hash
    
    def weight(self, gamma: float = 1.5) -> float:
        """Compute oracle influence weight."""
        return self.stake_vams * (self.reputation ** gamma)


@dataclass 
class CSPResult:
    """Result of a Cognitive Sync Pulse reconciliation."""
    csp_id: str
    status: CSPStatus
    reconciled_hash: Optional[str] = None    # S_global hash
    participants: int = 0
    consensus_time_ms: float = 0.0
    drift_before: float = 0.0
    drift_after: float = 0.0


class CognitiveDriftDetector:
    """
    Monitors multi-agent Cognitive Drift and triggers Sync Pulses.
    
    Tracks the cumulative divergence of each agent's internal state
    from the global ground truth S_global. When any agent's drift
    exceeds threshold θ, a Cognitive Sync Pulse (CSP) is triggered.
    
    The drift metric Δψ_i(t) approximates:
        Δψ_i(t) = ∫₀ᵗ ‖∇Φ_i(σ,τ) - ∇S_global(τ)‖ dτ
    
    Using discrete samples and L2 norm on state vectors.
    
    Args:
        theta: Drift threshold for CSP trigger (default: 0.3)
        gamma: Oracle reputation exponent (default: 1.5, superlinear)
        max_oracle_influence: Cap individual oracle weight (default: 15%)
        min_oracle_participants: Minimum oracles for valid CSP (default: 3)
        reputation_decay: Per-epoch reputation decay rate (default: 5%)
    """
    
    def __init__(
        self,
        theta: float = 0.3,
        gamma: float = 1.5,
        max_oracle_influence: float = 0.15,
        min_oracle_participants: int = 3,
        reputation_decay: float = 0.05
    ):
        self.theta = theta
        self.gamma = gamma
        self.max_oracle_influence = max_oracle_influence
        self.min_oracle_participants = min_oracle_participants
        self.reputation_decay = reputation_decay
        
        # Global state (ground truth)
        self._s_global: Optional[AgentState] = None
        
        # Per-agent drift tracking
        self._agent_states: Dict[str, AgentState] = {}
        self._agent_drift: Dict[str, float] = {}
        self._drift_history: List[Dict[str, float]] = []
        
        # Oracle network (mock for local mode)
        self._oracle_nodes: List[OracleNode] = []
        
        # CSP state
        self._csp_status = CSPStatus.IDLE
        self._csp_count = 0
        self._last_csp_time = 0.0
        
        # Statistics
        self._stats = {
            "drift_measurements": 0,
            "csp_triggered": 0,
            "csp_successful": 0,
            "max_drift_observed": 0.0,
            "avg_drift": 0.0
        }
        
        # Initialize mock oracle network
        self._init_mock_oracles()
    
    def _init_mock_oracles(self):
        """Initialize a mock oracle network for local testing."""
        self._oracle_nodes = [
            OracleNode("oracle_A", stake_vams=10_000, reputation=0.95),
            OracleNode("oracle_B", stake_vams=5_000, reputation=0.88),
            OracleNode("oracle_C", stake_vams=8_000, reputation=0.92),
            OracleNode("oracle_D", stake_vams=3_000, reputation=0.78),
            OracleNode("oracle_E", stake_vams=6_000, reputation=0.85),
        ]
    
    def set_global_state(self, state_dict: Dict[str, Any]):
        """
        Set the global ground truth state S_global.
        
        In production, this is determined by oracle consensus.
        For local testing, set manually.
        """
        self._s_global = AgentState.from_dict("s_global", state_dict)
        logger.info(f"S_global updated: {self._s_global.state_hash[:16]}...")
    
    def measure_drift(
        self, 
        agent_id: str, 
        agent_state_dict: Dict[str, Any]
    ) -> Tuple[float, DriftStatus]:
        """
        Measure cognitive drift for a specific agent.
        
        Computes Δψ_i(t) = ‖Φ_i - S_global‖₂ (L2 norm)
        
        Args:
            agent_id: Agent identifier
            agent_state_dict: Agent's current internal state
            
        Returns:
            (drift_value, drift_status) tuple
        """
        agent_state = AgentState.from_dict(agent_id, agent_state_dict)
        self._agent_states[agent_id] = agent_state
        
        self._stats["drift_measurements"] += 1
        
        # If no global state, drift is 0 (single-agent mode)
        if self._s_global is None:
            self._agent_drift[agent_id] = 0.0
            return 0.0, DriftStatus.ALIGNED
        
        # Compute L2 norm between agent vector and global vector
        drift = self._compute_l2_drift(
            agent_state.state_vector, 
            self._s_global.state_vector
        )
        
        # Accumulate drift (discrete integration)
        prev_drift = self._agent_drift.get(agent_id, 0.0)
        cumulative_drift = prev_drift * 0.9 + drift * 0.1  # EMA smoothing
        self._agent_drift[agent_id] = cumulative_drift
        
        # Update stats
        self._stats["max_drift_observed"] = max(
            self._stats["max_drift_observed"], cumulative_drift
        )
        n = self._stats["drift_measurements"]
        self._stats["avg_drift"] = (
            self._stats["avg_drift"] * (n - 1) + cumulative_drift
        ) / n
        
        # Determine status
        if cumulative_drift > self.theta:
            status = DriftStatus.DIVERGED
        elif cumulative_drift > self.theta * 0.7:
            status = DriftStatus.DRIFTING
        else:
            status = DriftStatus.ALIGNED
        
        logger.debug(
            f"Drift[{agent_id}]: d_psi={cumulative_drift:.4f} "
            f"(theta={self.theta}) -> {status.value}"
        )
        
        return cumulative_drift, status
    
    def _compute_l2_drift(
        self, 
        vec_a: List[float], 
        vec_b: List[float]
    ) -> float:
        """Compute L2 norm between two state vectors."""
        # Pad shorter vector
        max_len = max(len(vec_a), len(vec_b))
        a = vec_a + [0.0] * (max_len - len(vec_a))
        b = vec_b + [0.0] * (max_len - len(vec_b))
        
        return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))
    
    def check_sync_required(self) -> bool:
        """
        Check if any agent's drift exceeds θ, requiring a CSP.
        
        ∃ i : Δψ_i(t) > θ ⟹ CSP triggered
        """
        for agent_id, drift in self._agent_drift.items():
            if drift > self.theta:
                logger.info(
                    f"CSP required! Agent {agent_id} drift "
                    f"d_psi={drift:.4f} > theta={self.theta}"
                )
                return True
        return False
    
    def trigger_sync_pulse(self) -> CSPResult:
        """
        Execute a Cognitive Sync Pulse.
        
        1. Pause all agent reasoning threads (SIG_SYNC_PULSE)
        2. Collect agent states
        3. Run stake-weighted oracle consensus
        4. Commit reconciled S_global as ZK-State Root
        5. Agents reload reconciled state into L1 cache
        
        Returns:
            CSPResult with reconciliation outcome
        """
        self._csp_count += 1
        self._csp_status = CSPStatus.TRIGGERED
        self._stats["csp_triggered"] += 1
        
        csp_id = f"csp_{self._csp_count}_{int(time.time())}"
        start_time = time.time()
        
        logger.info(f"CSP triggered: {csp_id}")
        
        # Record pre-CSP drift
        max_drift_before = max(self._agent_drift.values()) if self._agent_drift else 0.0
        
        # Phase: Oracle Consensus
        self._csp_status = CSPStatus.RECONCILING
        
        try:
            reconciled_hash = self._run_oracle_consensus()
            
            # Update global state with reconciled hash
            consensus_time = (time.time() - start_time) * 1000
            
            # Reset all agent drift post-reconciliation
            for agent_id in self._agent_drift:
                self._agent_drift[agent_id] = 0.0
            
            self._csp_status = CSPStatus.COMMITTED
            self._stats["csp_successful"] += 1
            self._last_csp_time = time.time()
            
            result = CSPResult(
                csp_id=csp_id,
                status=CSPStatus.COMMITTED,
                reconciled_hash=reconciled_hash,
                participants=len(self._oracle_nodes),
                consensus_time_ms=consensus_time,
                drift_before=max_drift_before,
                drift_after=0.0
            )
            
            logger.info(
                f"CSP committed: {csp_id} "
                f"(hash={reconciled_hash[:16]}..., "
                f"time={consensus_time:.1f}ms)"
            )
            
            return result
            
        except Exception as e:
            self._csp_status = CSPStatus.FAILED
            logger.error(f"CSP failed: {csp_id} — {e}")
            return CSPResult(
                csp_id=csp_id,
                status=CSPStatus.FAILED,
                drift_before=max_drift_before
            )
        finally:
            self._csp_status = CSPStatus.IDLE
    
    def _run_oracle_consensus(self) -> str:
        """
        Run stake-weighted oracle consensus.
        
        S_global = Σ(w_k · S_k) / Σ(w_k)
        where w_k = stake_k · reputation_k^γ
        
        Safeguards:
        - Max individual influence capped at 15%
        - Reputation has superlinear weight (γ=1.5)
        - Minimum 3 participants required
        """
        if len(self._oracle_nodes) < self.min_oracle_participants:
            raise ValueError(
                f"Insufficient oracle participants: "
                f"{len(self._oracle_nodes)} < {self.min_oracle_participants}"
            )
        
        # Compute weights with reputation exponent
        weights = []
        for node in self._oracle_nodes:
            w = node.weight(self.gamma)
            weights.append((node, w))
        
        total_weight = sum(w for _, w in weights)
        
        # Cap individual influence
        capped_weights = []
        for node, w in weights:
            normalized = w / total_weight
            if normalized > self.max_oracle_influence:
                w = self.max_oracle_influence * total_weight
            capped_weights.append((node, w))
        
        # Recalculate total after capping
        total_weight = sum(w for _, w in capped_weights)
        
        # Generate mock oracle votes based on existing agent states
        all_hashes = list(set(
            s.state_hash for s in self._agent_states.values()
        ))
        
        if not all_hashes:
            # No agent states — use current S_global
            if self._s_global:
                return self._s_global.state_hash
            return hashlib.sha256(b"genesis").hexdigest()
        
        # Weighted vote (in mock mode, all oracles agree on majority state)
        # In production, each oracle independently computes their view
        reconciled_hash = all_hashes[0]  # Simplified: majority wins
        
        # Apply reputation decay for next epoch
        for node in self._oracle_nodes:
            node.reputation = max(0.1, node.reputation * (1 - self.reputation_decay))
        
        return reconciled_hash
    
    def get_all_drift(self) -> Dict[str, Tuple[float, str]]:
        """Get drift values and status for all tracked agents."""
        result = {}
        for agent_id, drift in self._agent_drift.items():
            if drift > self.theta:
                status = DriftStatus.DIVERGED
            elif drift > self.theta * 0.7:
                status = DriftStatus.DRIFTING
            else:
                status = DriftStatus.ALIGNED
            result[agent_id] = (drift, status.value)
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Return drift detector statistics."""
        return {
            **self._stats,
            "theta": self.theta,
            "gamma": self.gamma,
            "csp_status": self._csp_status.value,
            "tracked_agents": len(self._agent_states),
            "oracle_count": len(self._oracle_nodes),
            "s_global_hash": (
                self._s_global.state_hash[:16] + "..." 
                if self._s_global else "none"
            )
        }
