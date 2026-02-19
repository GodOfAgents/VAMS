"""
VAMS Neuron - Conditional L1 Router (CLR)
=========================================
Production implementation of the neuro-symbolic router.
Routes agent transactions to optimal chains based on:
1. Hard Constraints (Security, Privacy, Sovereignty)
2. Trust Constraints (Agent Tier vs Transaction Value)
3. Soft Optimization (Latency, Cost, Decentralization)

Integrates with:
- Chain Oracle (Live Data)
- Trust Aggregator (Access Control)
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import IntEnum


try:
    from neuron.chain_oracle import OracleManager, ChainMetrics
except ImportError:
    from chain_oracle import OracleManager, ChainMetrics


logger = logging.getLogger("VAMS-CLR")

# =============================================================================
# DATA MODELS
# =============================================================================

class TrustTier(IntEnum):
    """
    Agent Trust Tiers (Matches IVAMSTrustAggregator.sol)
    """
    UNVERIFIED = 0
    BRONZE = 1     # Basic Identity (Sandboxed)
    SILVER = 2     # Verified Execution (Standard DeFi)
    GOLD = 3       # Full Sovereignty (High Leverage)
    PLATINUM = 4   # Corporate/Gov Compliant

@dataclass
class TransactionIntent:
    """Agent's transaction requirements."""
    value_usd: float
    max_latency_ms: int
    requires_privacy: bool
    requires_sovereignty: bool = False
    requires_compliance_privacy: bool = False  # Midnight (ZK-SD)
    requires_formal_verification: bool = False # Cardano
    min_security: float = 0.5                  # 0.0 - 1.0 score

@dataclass
class RoutingDecision:
    """Final routing decision."""
    chain: str
    target_bridge: str
    reason: str
    metrics: ChainMetrics
    fee_estimate_usd: float

# =============================================================================
# CHAIN CONFIGURATION (Static Properties)
# =============================================================================

@dataclass
class ChainConfig:
    name: str
    privacy_type: str        # Public, TEE, ZK, ZK-SD
    sovereignty: str         # Shared, Sovereign
    security_score: float    # 0.0 - 1.0 (Liveness/Reorg resistance)
    formally_verified: bool  # True for Cardano/Midnight
    bridge_contract: str     # Address on VAMS L3

# Combined with Oracle Data at runtime
STATIC_CHAINS = {
    "Ethereum": ChainConfig("Ethereum", "Public", "Shared", 0.99, False, "0x..."),
    "Avalanche": ChainConfig("Avalanche", "Public", "Sovereign", 0.95, False, "0x..."),
    "Solana": ChainConfig("Solana", "Public", "Shared", 0.85, False, "0x..."),
    "Polygon": ChainConfig("Polygon", "Public", "Shared", 0.92, False, "0x..."),
    "Arbitrum": ChainConfig("Arbitrum", "Public", "Shared", 0.94, False, "0x..."),
    "Base": ChainConfig("Base", "Public", "Shared", 0.91, False, "0x..."),
    "Phala": ChainConfig("Phala", "TEE", "Shared", 0.90, False, "0x..."),
    "Oasis": ChainConfig("Oasis", "ZK", "Sovereign", 0.88, False, "0x..."),
    "Cardano": ChainConfig("Cardano", "Public", "Sovereign", 0.97, True, "0x..."),
    "Midnight": ChainConfig("Midnight", "ZK-SD", "Sovereign", 0.93, True, "0x..."),
}

# =============================================================================
# ROUTER IMPLEMENTATION
# =============================================================================

class CLRouter:
    """
    Conditional L1 Router.
    """
    def __init__(self, oracle: Optional[OracleManager] = None):
        self.oracle = oracle or OracleManager()
        self.eth_price = 3000.0 # Fallback USD price if oracle fails

    def route(self, intent: TransactionIntent, agent_tier: TrustTier) -> RoutingDecision:
        """
        Main routing function.
        Returns optimal chain or raises ValueError if unroutable.
        """
        # 1. ACCESS CONTROL (Trust Tier Check)
        self._check_permissions(intent, agent_tier)

        # 2. DATA COLLECTION
        metrics = self.oracle.get_all_metrics()
        
        # 3. HARD FILTER (Symbolic Guardrail)
        feasible = []
        for name, config in STATIC_CHAINS.items():
            chain_metrics = metrics.get(name)
            if not chain_metrics:
                continue # Skip chains with oracle failure
                
            if self._satisfies_hard_constraints(intent, config, chain_metrics):
                feasible.append((name, config, chain_metrics))
        
        if not feasible:
            raise ValueError(f"No chain satisfies constraints (Privacy={intent.requires_privacy}, Sov={intent.requires_sovereignty})")

        # 4. SOFT OPTIMIZATION (Entropy-Greedy)
        # Sort by Utility Function: U = - (w_lat * log(lat) + w_cost * log(cost))
        ranked = sorted(feasible, key=lambda x: self._calculate_utility(intent, x[2]))
        
        best_chain = ranked[0] # (name, config, metrics)
        
        return RoutingDecision(
            chain=best_chain[0],
            target_bridge=best_chain[1].bridge_contract,
            reason=f"Optimal utility among {len(feasible)} feasible chains",
            metrics=best_chain[2],
            fee_estimate_usd=best_chain[2].gas_price_gwei * 21000 * 1e-9 * self.eth_price # Approx
        )

    def _check_permissions(self, intent: TransactionIntent, tier: TrustTier):
        """
        Enforce VAMS Trust Policy.
        """
        # Rule 1: High Value requires Verification
        if intent.value_usd > 1000 and tier == TrustTier.UNVERIFIED:
            raise PermissionError(f"Transaction value ${intent.value_usd} exceeds UNVERIFIED limit ($1000). Verification required.")

        # Rule 2: Institutional Value requires Gold/Platinum
        if intent.value_usd > 50_000 and tier < TrustTier.GOLD:
            raise PermissionError(f"Transaction value ${intent.value_usd} requires GOLD Tier (Sovereign/High-Lev). Current: {tier.name}")

        # Rule 3: Compliance Privacy (Midnight) requires Silver+ (to prevent abusive anon)
        if intent.requires_compliance_privacy and tier < TrustTier.SILVER:
            raise PermissionError("Access to ZK-SD (Compliance Privacy) requires SILVER Tier or higher.")

    def _satisfies_hard_constraints(self, intent: TransactionIntent, config: ChainConfig, metrics: ChainMetrics) -> bool:
        """
        Stage 0: Hard Filter
        """
        # A. Security
        if config.security_score < intent.min_security:
            return False

        # B. Privacy
        if intent.requires_compliance_privacy:
            if config.privacy_type != "ZK-SD": return False
        elif intent.requires_privacy:
            if config.privacy_type not in ["TEE", "ZK", "ZK-SD"]: return False
            
        # C. Sovereignty
        if intent.requires_sovereignty:
            if config.sovereignty != "Sovereign": return False
            
        # D. Formal Verification
        if intent.requires_formal_verification:
            if not config.formally_verified: return False
            
        # E. Latency (Soft-Hard constraint: if purely impossible, reject)
        # We use a 2x multiple to allow for network jitter, stricter check in utility
        if metrics.block_time_ms > intent.max_latency_ms * 3:
            return False

        return True

    def _calculate_utility(self, intent: TransactionIntent, metrics: ChainMetrics) -> float:
        """
        Stage 1: Utility Score (Higher is better)
        Scales inverted cost and latency.
        """
        # Normalize inputs to prevent log(0)
        lat = max(1.0, float(metrics.block_time_ms))
        congestion = max(1.0, float(metrics.congestion_pct))
        
        # Weights vary by intent

        w_lat = 2.0 if intent.max_latency_ms < 5000 else 0.5
        w_cost = 2.0 if intent.value_usd < 100 else 0.5
        
        # Utility = - CostPenalty - LatencyPenalty - CongestionPenalty
        # Using Log scale for diminishing returns
        score = - (w_lat * math.log(lat)) - (w_cost * congestion / 20.0) 
        
        return score

# =============================================================================
# CLI USAGE
# =============================================================================

if __name__ == "__main__":
    # Demo Run
    import time
    
    print("Initializing VAMS CLRouter...")
    router = CLRouter()
    
    # Mock Intent: Arbitrage Bot
    intent = TransactionIntent(
        value_usd=5000.0,
        max_latency_ms=2000,
        requires_privacy=False,
        requires_sovereignty=False
    )
    
    tier = TrustTier.GOLD
    
    print(f"\nRouting Intent: Value=${intent.value_usd}, Latency<{intent.max_latency_ms}ms")
    print(f"Agent Tier: {tier.name}")
    
    try:
        decision = router.route(intent, tier)
        print(f"\n✅ ROUTING SUCCESS")
        print(f"Target Chain:   {decision.chain}")
        print(f"Est Block Time: {decision.metrics.block_time_ms} ms")
        print(f"Est Fee:        ${decision.fee_estimate_usd:.4f}")
        print(f"Reason:         {decision.reason}")
    except Exception as e:
        print(f"\n❌ ROUTING FAILED: {e}")
