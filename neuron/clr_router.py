"""
VAMS Neuron - Conditional L1 Router (CLR) v3.1
================================================
Production implementation of the neuro-symbolic router.

Architecture Reference: ARCHITECTURE_v0-3-0.md Section 14

Routes agent transactions to optimal chains using a 7-priority
decision tree:
    P0: Compliance Privacy        -> Midnight (ZK-SD)
    P1: Confidential Compute      -> Phala TEE
    P2: High-Value Security       -> Ethereum via AggLayer
    P3: Institutional Compliance  -> Polygon CDK KYC Layer
    P4: Formal Verification       -> Cardano L1 (Ouroboros)
    P5: Velocity (<1s)            -> Hydra / SEI / Solana
    P6: Default                   -> VAMS L3 Polygon CDK Validium

Integrates with:
    - Chain Oracle (Live Data) — chain_oracle.py
    - Trust Aggregator (Access Control)
    - MEV Protection — mev_protection.py
    - Bridge Executor — bridge_executor.py
"""

import logging
import math
import time
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import IntEnum, Enum

try:
    from neuron.chain_oracle import OracleManager, ChainMetrics
except ImportError:
    from chain_oracle import OracleManager, ChainMetrics

try:
    from neuron.config import (
        CLR_SECURITY_THRESHOLD, CLR_VELOCITY_THRESHOLD,
    )
except ImportError:
    try:
        from config import CLR_SECURITY_THRESHOLD, CLR_VELOCITY_THRESHOLD
    except ImportError:
        CLR_SECURITY_THRESHOLD = 10_000
        CLR_VELOCITY_THRESHOLD = 1_000


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


class RoutingPriority(Enum):
    """v3.1 Routing Priority Levels (Architecture Section 14.3)."""
    P0_COMPLIANCE_PRIVACY = "compliance_privacy"
    P1_CONFIDENTIAL_COMPUTE = "confidential_compute"
    P2_HIGH_VALUE_SECURITY = "high_value_security"
    P3_INSTITUTIONAL_COMPLIANCE = "institutional_compliance"
    P4_FORMAL_VERIFICATION = "formal_verification"
    P5_VELOCITY = "velocity"
    P6_DEFAULT = "default"


@dataclass
class VAMSTransactionMetadata:
    """
    Full v3.1 Transaction Metadata.
    Matches the Solidity struct in Architecture Section 14.1.
    """
    use_case_id: str = ""                        # e.g. "high_freq_trading"
    value_usd: float = 0.0                       # Estimated value for risk
    max_latency_ms: int = 30_000                 # Maximum acceptable latency
    requires_privacy: bool = False                # Trigger for TEE routing
    required_finality: str = "probabilistic"      # "probabilistic" or "deterministic"
    # v3.1 additions
    requires_confidential_compute: bool = False   # Agent needs TEE (Phala)
    requires_institutional_compliance: bool = False  # KYC/AML requirements
    requires_compliance_privacy: bool = False      # ZK-SD (-> Midnight)
    requires_formal_verification: bool = False     # Ouroboros proofs (-> Cardano)
    requires_sub_second_settle: bool = False       # Hydra state channels
    max_finality_ms: int = 0                       # Max economic irreversibility (0=don't care)


@dataclass
class TransactionIntent:
    """
    Legacy-compatible intent (wraps VAMSTransactionMetadata).
    Kept for backwards compatibility with existing code.
    """
    value_usd: float
    max_latency_ms: int
    requires_privacy: bool
    requires_sovereignty: bool = False
    requires_compliance_privacy: bool = False
    requires_formal_verification: bool = False
    requires_confidential_compute: bool = False
    requires_institutional_compliance: bool = False
    requires_sub_second_settle: bool = False
    max_finality_ms: int = 0
    min_security: float = 0.5
    use_case_id: str = ""

    def to_metadata(self) -> VAMSTransactionMetadata:
        """Convert to v3.1 metadata."""
        return VAMSTransactionMetadata(
            use_case_id=self.use_case_id,
            value_usd=self.value_usd,
            max_latency_ms=self.max_latency_ms,
            requires_privacy=self.requires_privacy,
            requires_confidential_compute=self.requires_confidential_compute,
            requires_institutional_compliance=self.requires_institutional_compliance,
            requires_compliance_privacy=self.requires_compliance_privacy,
            requires_formal_verification=self.requires_formal_verification,
            requires_sub_second_settle=self.requires_sub_second_settle,
            max_finality_ms=self.max_finality_ms,
        )


@dataclass
class RoutingDecision:
    """Final routing decision with full audit trail."""
    chain: str
    target_bridge: str
    reason: str
    priority: RoutingPriority
    metrics: Optional[ChainMetrics]
    fee_estimate_usd: float
    # Audit trail
    routing_hash: str = ""           # H(metadata + decision) for ZK proof
    feasible_chains: int = 0         # How many chains satisfied hard constraints
    timestamp: float = 0.0


# =============================================================================
# CHAIN CONFIGURATION (Static Properties)
# =============================================================================

@dataclass
class ChainConfig:
    """Static chain properties (combined with Oracle data at runtime)."""
    name: str
    privacy_type: str        # Public, TEE, ZK, ZK-SD
    sovereignty: str         # Shared, Sovereign
    security_score: float    # 0.0 - 1.0
    formally_verified: bool  # True for Cardano/Midnight
    bridge_transport: str    # Primary bridge protocol
    # v3.1 additions
    evm_compatible: bool = True
    supports_hydra: bool = False
    kyc_layer: bool = False
    chain_type: str = "L1"   # L1, L2, Sidechain, StateChannel


# Architecture Section 14 + 15C + 16.3: Full chain registry
STATIC_CHAINS = {
    # Account-model L1s
    "Ethereum": ChainConfig(
        "Ethereum", "Public", "Shared", 0.99, False,
        "AggLayer", evm_compatible=True, chain_type="L1"
    ),
    "Avalanche": ChainConfig(
        "Avalanche", "Public", "Sovereign", 0.95, False,
        "Hyperlane", evm_compatible=True, chain_type="L1"
    ),
    "Solana": ChainConfig(
        "Solana", "Public", "Shared", 0.85, False,
        "Hyperlane", evm_compatible=False, chain_type="L1"
    ),
    "SEI": ChainConfig(
        "SEI", "Public", "Shared", 0.90, False,
        "LayerZero", evm_compatible=True, chain_type="L1"
    ),
    # L2 Rollups
    "Polygon": ChainConfig(
        "Polygon", "Public", "Shared", 0.92, False,
        "AggLayer", evm_compatible=True, chain_type="L2",
        kyc_layer=True  # Polygon CDK KYC Layer
    ),
    "Arbitrum": ChainConfig(
        "Arbitrum", "Public", "Shared", 0.94, False,
        "AggLayer", evm_compatible=True, chain_type="L2"
    ),
    "Base": ChainConfig(
        "Base", "Public", "Shared", 0.91, False,
        "AggLayer", evm_compatible=True, chain_type="L2"
    ),
    # Privacy chains
    "Phala": ChainConfig(
        "Phala", "TEE", "Shared", 0.90, False,
        "Hyperlane", evm_compatible=False, chain_type="L1"
    ),
    "Oasis": ChainConfig(
        "Oasis", "ZK", "Sovereign", 0.88, False,
        "Hyperlane", evm_compatible=True, chain_type="L1"
    ),
    # Cardano Ecosystem (Section 15C)
    "Cardano": ChainConfig(
        "Cardano", "Public", "Sovereign", 0.97, True,
        "RosenBridge", evm_compatible=False, chain_type="L1"
    ),
    "Midnight": ChainConfig(
        "Midnight", "ZK-SD", "Sovereign", 0.93, True,
        "HyperlaneZKISM", evm_compatible=False, chain_type="Sidechain"
    ),
    "Hydra": ChainConfig(
        "Hydra", "Public", "Sovereign", 0.97, True,
        "DirectStateChannel", evm_compatible=False,
        chain_type="StateChannel", supports_hydra=True
    ),
}


# =============================================================================
# CLR v3.1 ROUTER IMPLEMENTATION
# =============================================================================

class CLRouter:
    """
    Conditional L1 Router v3.1

    Implements the 7-priority decision tree from Architecture Section 14.3
    with full audit trail for ZK routing proofs (Section 18.1).
    """

    def __init__(self, oracle: Optional[OracleManager] = None):
        self.oracle = oracle or OracleManager()
        self.eth_price = 3000.0  # Fallback USD price
        self._routing_log: List[RoutingDecision] = []
        self._stats = {
            "total_routed": 0,
            "by_priority": {p.value: 0 for p in RoutingPriority},
            "by_chain": {},
            "denied": 0,
        }

    # ─────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────

    def route(
        self,
        intent: TransactionIntent,
        agent_tier: TrustTier
    ) -> RoutingDecision:
        """
        Main routing function (v3.1 Decision Tree).
        Returns optimal chain or raises ValueError/PermissionError.
        """
        metadata = intent.to_metadata()
        return self.route_v3(metadata, agent_tier, intent)

    def route_v3(
        self,
        metadata: VAMSTransactionMetadata,
        agent_tier: TrustTier,
        intent: Optional[TransactionIntent] = None,
    ) -> RoutingDecision:
        """
        v3.1 routing with full VAMSTransactionMetadata.
        """
        # 0. ACCESS CONTROL
        self._check_permissions(metadata, agent_tier)

        # 1. FETCH LIVE METRICS
        metrics = self.oracle.get_all_metrics()

        # 2. PRIORITY-ORDERED DECISION TREE (Section 14.3)
        decision = None

        # P0: Compliance Privacy -> Midnight (ZK-SD)
        if metadata.requires_compliance_privacy:
            decision = self._route_midnight(metadata, metrics)

        # P1: Confidential Compute -> Phala TEE
        elif metadata.requires_confidential_compute or (
            metadata.requires_privacy and not metadata.requires_compliance_privacy
        ):
            decision = self._route_phala(metadata, metrics)

        # P2: High-Value Security -> Ethereum via AggLayer
        elif metadata.value_usd > CLR_SECURITY_THRESHOLD:
            decision = self._route_ethereum(metadata, metrics)

        # P3: Institutional Compliance -> Polygon CDK KYC
        elif metadata.requires_institutional_compliance:
            decision = self._route_polygon_kyc(metadata, metrics)

        # P4: Formal Verification -> Cardano L1
        elif metadata.requires_formal_verification:
            decision = self._route_cardano(metadata, metrics)

        # P5: Velocity (<1s latency requirement)
        elif metadata.max_latency_ms < CLR_VELOCITY_THRESHOLD:
            decision = self._route_velocity(metadata, metrics)

        # P6: DEFAULT -> VAMS L3 Polygon CDK Validium
        if decision is None:
            decision = self._route_default(metadata, metrics, intent)

        # 3. GENERATE ROUTING HASH (for ZK proofs, Section 18.1)
        decision.routing_hash = self._compute_routing_hash(metadata, decision)
        decision.timestamp = time.time()

        # 4. UPDATE STATS
        self._stats["total_routed"] += 1
        self._stats["by_priority"][decision.priority.value] = (
            self._stats["by_priority"].get(decision.priority.value, 0) + 1
        )
        self._stats["by_chain"][decision.chain] = (
            self._stats["by_chain"].get(decision.chain, 0) + 1
        )
        self._routing_log.append(decision)

        logger.info(
            f"Routed tx ({metadata.use_case_id or 'unknown'}) -> {decision.chain} "
            f"via {decision.priority.value} "
            f"(fee=${decision.fee_estimate_usd:.4f})"
        )

        return decision

    def get_stats(self) -> dict:
        """Return routing statistics."""
        return {**self._stats, "log_size": len(self._routing_log)}

    def get_routing_log(self, last_n: int = 10) -> List[RoutingDecision]:
        """Return last N routing decisions for audit."""
        return self._routing_log[-last_n:]

    # ─────────────────────────────────────────────────────────────
    # ACCESS CONTROL
    # ─────────────────────────────────────────────────────────────

    def _check_permissions(
        self,
        metadata: VAMSTransactionMetadata,
        tier: TrustTier
    ):
        """Enforce VAMS Trust Policy (Architecture Section 14)."""

        # Rule 1: >$1K requires identity verification
        if metadata.value_usd > 1_000 and tier == TrustTier.UNVERIFIED:
            self._stats["denied"] += 1
            raise PermissionError(
                f"Transaction value ${metadata.value_usd} exceeds "
                f"UNVERIFIED limit ($1000). Verification required."
            )

        # Rule 2: >$50K requires Gold/Platinum
        if metadata.value_usd > 50_000 and tier < TrustTier.GOLD:
            self._stats["denied"] += 1
            raise PermissionError(
                f"Transaction value ${metadata.value_usd} requires "
                f"GOLD Tier. Current: {tier.name}"
            )

        # Rule 3: Compliance Privacy (Midnight) requires Silver+
        if metadata.requires_compliance_privacy and tier < TrustTier.SILVER:
            self._stats["denied"] += 1
            raise PermissionError(
                "ZK-SD (Compliance Privacy) requires SILVER Tier or higher."
            )

        # Rule 4: Institutional compliance requires Platinum
        if metadata.requires_institutional_compliance and tier < TrustTier.PLATINUM:
            self._stats["denied"] += 1
            raise PermissionError(
                "Institutional compliance routing requires PLATINUM Tier."
            )

    # ─────────────────────────────────────────────────────────────
    # PRIORITY ROUTING METHODS
    # ─────────────────────────────────────────────────────────────

    def _route_midnight(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics]
    ) -> RoutingDecision:
        """P0: Route to Midnight for ZK-SD Compliance Privacy."""
        m = metrics.get("Midnight")
        config = STATIC_CHAINS["Midnight"]
        return RoutingDecision(
            chain="Midnight",
            target_bridge=config.bridge_transport,
            reason="P0: Compliance Privacy requires ZK-SD (Midnight)",
            priority=RoutingPriority.P0_COMPLIANCE_PRIVACY,
            metrics=m,
            fee_estimate_usd=self._estimate_fee(m, "Midnight"),
            feasible_chains=1,
        )

    def _route_phala(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics]
    ) -> RoutingDecision:
        """P1: Route to Phala for TEE Confidential Compute."""
        m = metrics.get("Phala")
        config = STATIC_CHAINS["Phala"]
        return RoutingDecision(
            chain="Phala",
            target_bridge=config.bridge_transport,
            reason="P1: Confidential compute requires TEE (Phala Network)",
            priority=RoutingPriority.P1_CONFIDENTIAL_COMPUTE,
            metrics=m,
            fee_estimate_usd=self._estimate_fee(m, "Phala"),
            feasible_chains=1,
        )

    def _route_ethereum(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics]
    ) -> RoutingDecision:
        """P2: Route high-value txs to Ethereum via AggLayer + Mithril."""
        m = metrics.get("Ethereum")
        config = STATIC_CHAINS["Ethereum"]
        return RoutingDecision(
            chain="Ethereum",
            target_bridge=config.bridge_transport,
            reason=(
                f"P2: High value (${metadata.value_usd:,.0f}) exceeds "
                f"${CLR_SECURITY_THRESHOLD:,} threshold -> Ethereum L1 via AggLayer"
            ),
            priority=RoutingPriority.P2_HIGH_VALUE_SECURITY,
            metrics=m,
            fee_estimate_usd=self._estimate_fee(m, "Ethereum"),
            feasible_chains=1,
        )

    def _route_polygon_kyc(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics]
    ) -> RoutingDecision:
        """P3: Route institutional compliance to Polygon CDK KYC Layer."""
        m = metrics.get("Polygon")
        config = STATIC_CHAINS["Polygon"]
        return RoutingDecision(
            chain="Polygon",
            target_bridge=config.bridge_transport,
            reason="P3: Institutional compliance -> Polygon CDK KYC Layer",
            priority=RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE,
            metrics=m,
            fee_estimate_usd=self._estimate_fee(m, "Polygon"),
            feasible_chains=1,
        )

    def _route_cardano(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics]
    ) -> RoutingDecision:
        """P4: Route to Cardano L1 for formal verification."""
        m = metrics.get("Cardano")
        config = STATIC_CHAINS["Cardano"]
        return RoutingDecision(
            chain="Cardano",
            target_bridge=config.bridge_transport,
            reason="P4: Formal verification -> Cardano L1 (Ouroboros Praos)",
            priority=RoutingPriority.P4_FORMAL_VERIFICATION,
            metrics=m,
            fee_estimate_usd=self._estimate_fee(m, "Cardano"),
            feasible_chains=1,
        )

    def _route_velocity(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics]
    ) -> RoutingDecision:
        """P5: High-velocity routing — Hydra, SEI, or Solana."""

        # P5a: Sub-second settlement -> Hydra State Channels
        if metadata.requires_sub_second_settle:
            m = metrics.get("Hydra")
            return RoutingDecision(
                chain="Hydra",
                target_bridge=STATIC_CHAINS["Hydra"].bridge_transport,
                reason="P5a: Sub-second settlement -> Cardano Hydra State Channels",
                priority=RoutingPriority.P5_VELOCITY,
                metrics=m,
                fee_estimate_usd=0.0001,  # Near-zero in state channels
                feasible_chains=1,
            )

        # P5b: EVM-compatible fast execution -> SEI (380ms finality)
        if self._is_evm_payload(metadata):
            m = metrics.get("SEI")
            return RoutingDecision(
                chain="SEI",
                target_bridge=STATIC_CHAINS["SEI"].bridge_transport,
                reason=(
                    f"P5b: EVM fast-lane ({metadata.max_latency_ms}ms req) "
                    f"-> SEI Twin-Turbo (380ms)"
                ),
                priority=RoutingPriority.P5_VELOCITY,
                metrics=m,
                fee_estimate_usd=self._estimate_fee(m, "SEI"),
                feasible_chains=1,
            )

        # P5c: Non-EVM velocity -> Solana
        m = metrics.get("Solana")
        return RoutingDecision(
            chain="Solana",
            target_bridge=STATIC_CHAINS["Solana"].bridge_transport,
            reason=(
                f"P5c: Non-EVM velocity ({metadata.max_latency_ms}ms req) "
                f"-> Solana (400ms)"
            ),
            priority=RoutingPriority.P5_VELOCITY,
            metrics=m,
            fee_estimate_usd=self._estimate_fee(m, "Solana"),
            feasible_chains=1,
        )

    def _route_default(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: Dict[str, ChainMetrics],
        intent: Optional[TransactionIntent] = None,
    ) -> RoutingDecision:
        """
        P6: Default route — apply utility scoring across feasible chains.
        Uses entropy-greedy optimization from the original CLR.
        """
        min_security = intent.min_security if intent else 0.5

        feasible = []
        for name, config in STATIC_CHAINS.items():
            # Skip specialized chains
            if name in ("Hydra", "Midnight"):
                continue

            chain_metrics = metrics.get(name)
            if not chain_metrics:
                continue

            if self._satisfies_constraints(metadata, config, chain_metrics, min_security):
                feasible.append((name, config, chain_metrics))

        if not feasible:
            # Fallback: VAMS L3 Polygon CDK (always available)
            m = metrics.get("Polygon")
            return RoutingDecision(
                chain="Polygon",
                target_bridge="AggLayer",
                reason="P6: Default fallback -> VAMS L3 Polygon CDK Validium",
                priority=RoutingPriority.P6_DEFAULT,
                metrics=m,
                fee_estimate_usd=self._estimate_fee(m, "Polygon"),
                feasible_chains=0,
            )

        # Rank by utility function
        ranked = sorted(
            feasible,
            key=lambda x: self._calculate_utility(metadata, x[2]),
        )
        best = ranked[0]

        return RoutingDecision(
            chain=best[0],
            target_bridge=best[1].bridge_transport,
            reason=(
                f"P6: Optimal utility among {len(feasible)} feasible chains"
            ),
            priority=RoutingPriority.P6_DEFAULT,
            metrics=best[2],
            fee_estimate_usd=self._estimate_fee(best[2], best[0]),
            feasible_chains=len(feasible),
        )

    # ─────────────────────────────────────────────────────────────
    # CONSTRAINT CHECKING & UTILITY
    # ─────────────────────────────────────────────────────────────

    def _satisfies_constraints(
        self,
        metadata: VAMSTransactionMetadata,
        config: ChainConfig,
        metrics: ChainMetrics,
        min_security: float = 0.5,
    ) -> bool:
        """Stage 0: Hard filter for default routing."""
        # Security
        if config.security_score < min_security:
            return False

        # Privacy
        if metadata.requires_privacy:
            if config.privacy_type not in ("TEE", "ZK", "ZK-SD"):
                return False

        # Latency (allow 3x jitter margin)
        if metrics.block_time_ms > metadata.max_latency_ms * 3:
            return False

        # Finality
        if metadata.max_finality_ms > 0:
            if metrics.finality_ms > metadata.max_finality_ms:
                return False

        return True

    def _calculate_utility(
        self,
        metadata: VAMSTransactionMetadata,
        metrics: ChainMetrics
    ) -> float:
        """
        Stage 1: Utility Score (lower is better for sort).
        U = -(w_lat * log(lat) + w_cost * congestion/20)
        """
        lat = max(1.0, float(metrics.block_time_ms))
        congestion = max(1.0, float(metrics.congestion_pct))

        w_lat = 2.0 if metadata.max_latency_ms < 5000 else 0.5
        w_cost = 2.0 if metadata.value_usd < 100 else 0.5

        return -(w_lat * math.log(lat)) - (w_cost * congestion / 20.0)

    # ─────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────

    def _is_evm_payload(self, metadata: VAMSTransactionMetadata) -> bool:
        """Check if the transaction requires EVM-compatible execution."""
        evm_hints = ("swap", "defi", "evm", "trade", "transfer", "nft")
        use_case = metadata.use_case_id.lower()
        return any(hint in use_case for hint in evm_hints) or not use_case

    def _estimate_fee(
        self,
        metrics: Optional[ChainMetrics],
        chain: str
    ) -> float:
        """Estimate transaction fee in USD."""
        if not metrics or metrics.stale:
            # Fallback estimates per chain
            defaults = {
                "Ethereum": 5.00, "Polygon": 0.01, "Arbitrum": 0.05,
                "Base": 0.02, "Solana": 0.001, "SEI": 0.002,
                "Avalanche": 0.10, "Phala": 0.05, "Oasis": 0.03,
                "Cardano": 0.20, "Midnight": 0.30, "Hydra": 0.0001,
            }
            return defaults.get(chain, 0.10)

        gas_gwei = metrics.gas_price_gwei
        # EVM chains: gas_price * 21000 * eth_price
        if chain in ("Ethereum", "Polygon", "Arbitrum", "Base", "Avalanche", "Oasis"):
            return gas_gwei * 21000 * 1e-9 * self.eth_price
        # Solana: direct fee in lamports
        if chain == "Solana":
            return gas_gwei * 0.001
        # SEI: similar to EVM but lower
        if chain == "SEI":
            return gas_gwei * 21000 * 1e-9 * 0.50  # SEI price approx
        # Cardano: fee already normalized
        if chain in ("Cardano", "Midnight"):
            return gas_gwei * 0.001
        # Hydra: near-zero
        if chain == "Hydra":
            return 0.0001
        return 0.10

    def _compute_routing_hash(
        self,
        metadata: VAMSTransactionMetadata,
        decision: RoutingDecision
    ) -> str:
        """
        Compute H(metadata + decision) for ZK routing proof verification.
        Architecture Section 18.1: RoutingProofVerifier.
        """
        payload = (
            f"{metadata.use_case_id}:{metadata.value_usd}:"
            f"{metadata.max_latency_ms}:{metadata.requires_privacy}:"
            f"{metadata.requires_compliance_privacy}:"
            f"{metadata.requires_formal_verification}:"
            f"{decision.chain}:{decision.priority.value}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# =============================================================================
# CLI DEMO
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("  VAMS CLR v3.1 — 7-Priority Decision Tree Demo")
    print("=" * 70)

    router = CLRouter()

    scenarios = [
        (
            "Compliance Privacy (GDPR Agent)",
            TransactionIntent(
                value_usd=5000, max_latency_ms=60_000,
                requires_privacy=True,
                requires_compliance_privacy=True,
            ),
            TrustTier.SILVER,
        ),
        (
            "Confidential AI Inference",
            TransactionIntent(
                value_usd=200, max_latency_ms=10_000,
                requires_privacy=True,
                requires_confidential_compute=True,
            ),
            TrustTier.GOLD,
        ),
        (
            "High-Value DeFi Settlement",
            TransactionIntent(
                value_usd=50_000, max_latency_ms=30_000,
                requires_privacy=False,
            ),
            TrustTier.GOLD,
        ),
        (
            "Cardano Formal Verification",
            TransactionIntent(
                value_usd=2000, max_latency_ms=60_000,
                requires_privacy=False,
                requires_formal_verification=True,
            ),
            TrustTier.GOLD,
        ),
        (
            "HFT Bot (Sub-Second)",
            TransactionIntent(
                value_usd=100, max_latency_ms=500,
                requires_privacy=False,
                requires_sub_second_settle=True,
                use_case_id="high_freq_trading",
            ),
            TrustTier.GOLD,
        ),
        (
            "Fast EVM Swap",
            TransactionIntent(
                value_usd=50, max_latency_ms=800,
                requires_privacy=False,
                use_case_id="defi_swap",
            ),
            TrustTier.BRONZE,
        ),
        (
            "Standard Agent Task (Default)",
            TransactionIntent(
                value_usd=10, max_latency_ms=30_000,
                requires_privacy=False,
            ),
            TrustTier.BRONZE,
        ),
    ]

    for name, intent, tier in scenarios:
        print(f"\n--- {name} ---")
        print(f"  Tier: {tier.name} | Value: ${intent.value_usd:,.0f} | "
              f"Latency: {intent.max_latency_ms}ms")
        try:
            d = router.route(intent, tier)
            print(f"  -> Chain:    {d.chain}")
            print(f"  -> Priority: {d.priority.value}")
            print(f"  -> Bridge:   {d.target_bridge}")
            print(f"  -> Fee:      ${d.fee_estimate_usd:.4f}")
            print(f"  -> Hash:     {d.routing_hash}")
            print(f"  -> Reason:   {d.reason}")
        except (PermissionError, ValueError) as e:
            print(f"  -> DENIED: {e}")

    print(f"\n{'=' * 70}")
    stats = router.get_stats()
    print(f"  Total Routed: {stats['total_routed']} | Denied: {stats['denied']}")
    print(f"  By Priority: {stats['by_priority']}")
    print(f"  By Chain:    {stats['by_chain']}")
    print(f"{'=' * 70}")
