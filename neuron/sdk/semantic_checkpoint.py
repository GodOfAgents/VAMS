"""
VAMS Neuron - Semantic Checkpoint Manager (AgentOS Integration)
================================================================
Implements CID-based (Contextual Information Density) semantic boundary
detection from the AgentOS preprint. Replaces fixed-interval DBOS
checkpoints with attention entropy derivatives that detect natural
cognitive boundaries.

Mathematical basis:
    D(t) = 1 - [-1/H * Σ_i Σ_j α_{i,j} * log(α_{i,j})]
    Boundary at t* ⟺ |dD/dt|_{t=t*} > ε

Reference: AGENTOS_INTEGRATION.md §2.3, §3.1
"""

import math
import time
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger("vams.semantic_checkpoint")


class CheckpointTrigger(Enum):
    """Why a checkpoint was triggered."""
    FIXED_STEP = "fixed_step"          # Traditional @step boundary
    SEMANTIC_BOUNDARY = "semantic"     # CID entropy derivative > ε
    INTERRUPT_RETURN = "interrupt"     # Post-tool-call (SIG_TOOL_INVOKE return)
    SYNC_PULSE = "sync_pulse"          # Cognitive Sync Pulse reconciliation
    FORCED = "forced"                  # Manual / crash-safety


@dataclass
class SemanticPage:
    """
    A semantically coherent unit of agent state.
    Content-addressed for verifiable memory access.
    """
    page_id: str
    content: Dict[str, Any]
    content_hash: str              # SHA-256 of serialized content
    cid_score: float               # CID at boundary detection
    trigger: CheckpointTrigger     # What triggered this checkpoint
    timestamp: float = field(default_factory=time.time)
    tier: str = "L2_RAM"           # Storage tier (L1_CACHE, L2_RAM, L3_STORAGE, L0_ANCHOR)
    anchor_tx: Optional[str] = None  # L0 anchor reference (Polygon CDK state root)
    
    def verify(self) -> bool:
        """Verify content integrity via hash."""
        computed = hashlib.sha256(
            json.dumps(self.content, sort_keys=True, default=str).encode()
        ).hexdigest()
        return computed == self.content_hash


@dataclass
class CIDMeasurement:
    """A single CID measurement at token position t."""
    position: int
    cid_value: float
    derivative: float
    is_boundary: bool
    timestamp: float = field(default_factory=time.time)


class SemanticCheckpointManager:
    """
    Replaces fixed-interval DBOS checkpoints with CID-based semantic
    boundary detection from the AgentOS preprint.
    
    The Contextual Information Density (CID) measures how "focused" the
    model's attention is at position t:
    
        D(t) = 1 - [-1/H * Σ_i Σ_j α_{i,j} * log(α_{i,j})]
    
    A semantic boundary is detected when |dD/dt| > ε.
    
    This produces semantically coherent checkpoints — each one captures
    a complete reasoning unit rather than an arbitrary byte boundary.
    
    Args:
        epsilon: Boundary detection threshold (default: 0.15)
        min_interval: Minimum steps between checkpoints to prevent thrashing
        max_interval: Maximum steps between checkpoints (safety fallback)
        enable_anchoring: Whether to anchor semantic hashes to L0 (Polygon CDK)
    """
    
    def __init__(
        self,
        epsilon: float = 0.15,
        min_interval: int = 3,
        max_interval: int = 50,
        enable_anchoring: bool = False
    ):
        self.epsilon = epsilon
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.enable_anchoring = enable_anchoring
        
        # CID history for derivative computation
        self._cid_history: List[CIDMeasurement] = []
        self._steps_since_checkpoint = 0
        self._total_checkpoints = 0
        self._total_steps = 0
        self._semantic_pages: List[SemanticPage] = []
        
        # Statistics for monitoring
        self._stats = {
            "semantic_boundaries": 0,
            "fixed_fallbacks": 0,
            "forced_checkpoints": 0,
            "avg_cid": 0.0,
            "pages_committed": 0
        }
    
    def compute_cid(
        self, 
        attention_weights: List[List[float]], 
        num_heads: int, 
        position: int
    ) -> float:
        """
        Compute Contextual Information Density from attention weights.
        
        D(t) = 1 - [-1/H * Σ_i Σ_j α_{i,j} * log(α_{i,j})]
        
        Args:
            attention_weights: [H x t] attention weight matrix
            num_heads: Number of attention heads (H)
            position: Current token position (t)
        
        Returns:
            CID value D(t) in range [0, 1]
            Higher = more focused attention (concentrated reasoning)
            Lower = distributed attention (exploratory/transitional)
        """
        if not attention_weights or num_heads == 0:
            return 0.5  # Neutral default
        
        entropy_sum = 0.0
        valid_entries = 0
        
        for head_idx in range(min(num_heads, len(attention_weights))):
            head_weights = attention_weights[head_idx]
            for pos in range(min(position, len(head_weights))):
                alpha = head_weights[pos]
                if alpha > 1e-10:  # Avoid log(0)
                    entropy_sum += alpha * math.log(alpha)
                    valid_entries += 1
        
        if valid_entries == 0:
            return 0.5
        
        # Normalize by number of heads
        normalized_entropy = -entropy_sum / num_heads
        
        # CID = 1 - normalized_entropy (clamped to [0, 1])
        cid = max(0.0, min(1.0, 1.0 - normalized_entropy))
        return cid
    
    def compute_cid_from_logits(self, logits: List[float]) -> float:
        """
        Simplified CID computation from output logits when attention
        weights are not directly available. Uses softmax entropy as proxy.
        
        This is the practical fallback for most inference providers
        (io.net, Bittensor) that don't expose raw attention matrices.
        
        Args:
            logits: Model output logits for current step
            
        Returns:
            CID value D(t) approximation
        """
        if not logits:
            return 0.5
        
        # Softmax
        max_logit = max(logits)
        exp_logits = [math.exp(l - max_logit) for l in logits]
        sum_exp = sum(exp_logits)
        probs = [e / sum_exp for e in exp_logits]
        
        # Shannon entropy
        entropy = 0.0
        for p in probs:
            if p > 1e-10:
                entropy -= p * math.log(p)
        
        # Normalize to [0, 1] (max entropy = log(vocab_size))
        max_entropy = math.log(len(logits)) if len(logits) > 1 else 1.0
        normalized_entropy = entropy / max_entropy
        
        return max(0.0, min(1.0, 1.0 - normalized_entropy))
    
    def detect_boundary(self, current_cid: float) -> Tuple[bool, float]:
        """
        Detect semantic boundary when dD/dt exceeds threshold ε.
        
        Also enforces min/max interval constraints to prevent:
        - Thrashing (too many checkpoints)
        - Clock drift (too few checkpoints)
        
        Args:
            current_cid: Current CID measurement
            
        Returns:
            (is_boundary, derivative) tuple
        """
        self._total_steps += 1
        self._steps_since_checkpoint += 1
        
        # Compute derivative
        derivative = 0.0
        if self._cid_history:
            derivative = abs(current_cid - self._cid_history[-1].cid_value)
        
        # Record measurement
        measurement = CIDMeasurement(
            position=self._total_steps,
            cid_value=current_cid,
            derivative=derivative,
            is_boundary=False
        )
        
        # Update rolling average
        n = len(self._cid_history) + 1
        self._stats["avg_cid"] = (
            self._stats["avg_cid"] * (n - 1) + current_cid
        ) / n
        
        is_boundary = False
        
        # Check max interval (safety fallback — must checkpoint)
        if self._steps_since_checkpoint >= self.max_interval:
            is_boundary = True
            self._stats["fixed_fallbacks"] += 1
            logger.debug(
                f"Max interval checkpoint at step {self._total_steps} "
                f"(max_interval={self.max_interval})"
            )
        
        # Check semantic boundary (CID derivative exceeds ε)
        elif (derivative > self.epsilon and 
              self._steps_since_checkpoint >= self.min_interval):
            is_boundary = True
            self._stats["semantic_boundaries"] += 1
            logger.debug(
                f"Semantic boundary at step {self._total_steps}: "
                f"dD/dt={derivative:.4f} > eps={self.epsilon}"
            )
        
        measurement.is_boundary = is_boundary
        self._cid_history.append(measurement)
        
        # Trim history (keep last 200 measurements)
        if len(self._cid_history) > 200:
            self._cid_history = self._cid_history[-100:]
        
        if is_boundary:
            self._steps_since_checkpoint = 0
            self._total_checkpoints += 1
        
        return is_boundary, derivative
    
    def create_semantic_page(
        self,
        agent_state: Dict[str, Any],
        trigger: CheckpointTrigger = CheckpointTrigger.SEMANTIC_BOUNDARY,
        cid_score: Optional[float] = None
    ) -> SemanticPage:
        """
        Create a semantically coherent checkpoint page.
        
        Content-addressed (SHA-256) for verifiable memory access.
        
        Args:
            agent_state: Current agent state to checkpoint
            trigger: What triggered this checkpoint
            cid_score: CID value at boundary (auto-detected if None)
            
        Returns:
            SemanticPage with content hash for verification
        """
        # Compute content hash
        content_json = json.dumps(agent_state, sort_keys=True, default=str)
        content_hash = hashlib.sha256(content_json.encode()).hexdigest()
        
        # Generate page ID
        page_id = f"sp_{self._total_checkpoints}_{content_hash[:12]}"
        
        # Use last CID if not provided
        if cid_score is None and self._cid_history:
            cid_score = self._cid_history[-1].cid_value
        
        page = SemanticPage(
            page_id=page_id,
            content=agent_state,
            content_hash=content_hash,
            cid_score=cid_score or 0.5,
            trigger=trigger
        )
        
        self._semantic_pages.append(page)
        self._stats["pages_committed"] += 1
        
        logger.info(
            f"Semantic page committed: {page_id} "
            f"(trigger={trigger.value}, CID={cid_score:.3f})"
        )
        
        return page
    
    def get_semantic_hash(self) -> str:
        """
        Get the unified semantic hash of all committed pages.
        This is the value anchored to L0 (Polygon CDK Validium).
        """
        if not self._semantic_pages:
            return hashlib.sha256(b"empty").hexdigest()
        
        combined = "|".join(p.content_hash for p in self._semantic_pages)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """Return checkpoint statistics for monitoring."""
        return {
            **self._stats,
            "total_steps": self._total_steps,
            "total_checkpoints": self._total_checkpoints,
            "epsilon": self.epsilon,
            "semantic_hash": self.get_semantic_hash()[:16] + "...",
            "efficiency": (
                f"{self._stats['semantic_boundaries']}/{self._total_checkpoints} "
                f"semantic ({self._stats['semantic_boundaries'] / max(1, self._total_checkpoints) * 100:.0f}%)"
            ) if self._total_checkpoints > 0 else "0/0"
        }
    
    def reset(self):
        """Reset all state (for new workflow)."""
        self._cid_history.clear()
        self._semantic_pages.clear()
        self._steps_since_checkpoint = 0
        self._total_checkpoints = 0
        self._total_steps = 0
        self._stats = {
            "semantic_boundaries": 0,
            "fixed_fallbacks": 0,
            "forced_checkpoints": 0,
            "avg_cid": 0.0,
            "pages_committed": 0
        }
