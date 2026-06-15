"""
VAMS Neuron - Cross-Chain Bridge Executor
==========================================
Architecture Reference: ARCHITECTURE_v0-3-0.md Sections 16, 20.5

Python-side SDK for the ICB (Inter-Chain Bridge) Aiken contract
(cardano/lib/vams/icb.ak). Implements:

1. Transport Matrix — Selects optimal bridge per source/dest pair
2. ICB Client — Python mirror of on-chain BridgeMessage + verification
3. Bridge Fallback — Timeout cascade: Primary(30s) -> Secondary(60s) -> Manual
4. Multi-ISM Verification — 2/3 threshold (Phala + Oracle + Multisig)

Transport Matrix (Section 16.3):
    VAMS L3 -> Ethereum:  AggLayer          (~5min)
    VAMS L3 -> Other CDK: AggLayer          (~1min)
    VAMS L3 -> Solana:    Hyperlane          (~400ms)
    VAMS L3 -> SEI:       LayerZero v2       (~380ms)
    VAMS L3 -> Cosmos:    Union Labs         (~1s)
    VAMS L3 -> Cardano:   Rosen Bridge + ICB (~2min)
    VAMS L3 -> Midnight:  Hyperlane ZK-ISM   (~1min)
"""

import hashlib
import time
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum

logger = logging.getLogger("VAMS-Bridge")

try:
    from neuron.config import (
        BRIDGE_PRIMARY_TIMEOUT_MS, BRIDGE_SECONDARY_TIMEOUT_MS,
    )
except ImportError:
    try:
        from config import BRIDGE_PRIMARY_TIMEOUT_MS, BRIDGE_SECONDARY_TIMEOUT_MS
    except ImportError:
        BRIDGE_PRIMARY_TIMEOUT_MS = 30_000
        BRIDGE_SECONDARY_TIMEOUT_MS = 60_000


# =============================================================================
# DATA MODELS
# =============================================================================

class BridgeTransport(Enum):
    """Available bridge transport protocols."""
    AGGLAYER = "AggLayer"
    TRAILS = "Trails"
    HYPERLANE = "Hyperlane"
    LAYERZERO = "LayerZero"
    ROSEN_BRIDGE = "RosenBridge"
    HYPERLANE_ZK_ISM = "HyperlaneZKISM"
    UNION_LABS = "UnionLabs"
    DIRECT_STATE_CHANNEL = "DirectStateChannel"


class BridgeStatus(Enum):
    """Bridge execution lifecycle."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    RELAYED = "relayed"
    VERIFIED = "verified"
    SETTLED = "settled"
    FAILED = "failed"
    FALLBACK = "fallback"
    MANUAL_QUEUE = "manual_queue"


class ISMType(Enum):
    """Interchain Security Module types (Section 20.5)."""
    TEE_PHALA = "tee_phala"          # Hardware attestation
    ORACLE_CHAINLINK = "oracle_ccip"  # Economic stake (DON)
    MULTISIG_DAO = "multisig_dao"     # Social consensus (5/9 threshold)


# =============================================================================
# ICB CLIENT (Python mirror of cardano/lib/vams/icb.ak)
# =============================================================================

@dataclass
class BridgeMessage:
    """
    Python mirror of ICB Aiken BridgeMessage type.

    Maps to cardano/lib/vams/icb.ak:
        pub type BridgeMessage {
            source_chain: ByteArray,
            dest_chain: ByteArray,
            payload_hash: ByteArray,
            sequence: Int,
            timestamp: Int,
        }
    """
    source_chain: str
    dest_chain: str
    payload_hash: str       # SHA-256 hex of payload
    sequence: int           # Monotonic nonce
    timestamp: int          # Unix timestamp

    def to_bytes(self) -> bytes:
        """Serialize for on-chain submission."""
        return (
            f"{self.source_chain}:{self.dest_chain}:"
            f"{self.payload_hash}:{self.sequence}:{self.timestamp}"
        ).encode()

    def to_hex(self) -> str:
        """Hex encoding for Aiken ByteArray compatibility."""
        return self.to_bytes().hex()


class ICBClient:
    """
    Python-side client for the ICB (Inter-Chain Bridge) Aiken contract.
    Mirrors verification logic from cardano/lib/vams/icb.ak.
    """

    def __init__(self):
        self._nonce_tracker: Dict[str, int] = {}  # dest_chain -> last_nonce
        self._stats = {
            "messages_built": 0,
            "proofs_verified": 0,
            "nonces_validated": 0,
            "replay_attempts_blocked": 0,
        }

    def build_bridge_message(
        self,
        source_chain: str,
        dest_chain: str,
        payload: bytes,
    ) -> BridgeMessage:
        """
        Construct an ICB-compatible bridge message with auto-incrementing nonce.
        """
        payload_hash = hashlib.sha256(payload).hexdigest()

        # Auto-increment nonce per destination (mirrors icb.ak/is_valid_nonce)
        last_nonce = self._nonce_tracker.get(dest_chain, 0)
        new_nonce = last_nonce + 1
        self._nonce_tracker[dest_chain] = new_nonce

        msg = BridgeMessage(
            source_chain=source_chain,
            dest_chain=dest_chain,
            payload_hash=payload_hash,
            sequence=new_nonce,
            timestamp=int(time.time()),
        )

        self._stats["messages_built"] += 1
        logger.debug(
            f"ICB message: {source_chain}->{dest_chain} "
            f"seq={new_nonce} hash={payload_hash[:12]}..."
        )

        return msg

    def verify_bridge_proof(
        self,
        proof: bytes,
        expected_payload_hash: str,
    ) -> bool:
        """
        Verify a bridge proof is well-formed.
        Mirrors cardano/lib/vams/icb.ak:verify_bridge_proof

        In production: verifies Mithril certificate or Rosen Bridge proof.
        Current: structural verification (proof >= 64 bytes, hash non-empty).
        """
        self._stats["proofs_verified"] += 1

        # Mirror Aiken: proof_len >= 64 && payload_hash_len > 0
        if len(proof) < 64:
            logger.warning(f"Bridge proof too short: {len(proof)} < 64 bytes")
            return False

        if not expected_payload_hash:
            logger.warning("Empty payload hash in bridge proof")
            return False

        return True

    def verify_mithril_proof(self, proof: bytes) -> bool:
        """
        Verify a Mithril finality proof.
        Mirrors cardano/lib/vams/icb.ak:verify_mithril_proof

        Production: verify Mithril certificate chain.
        Current: verify proof >= 32 bytes.
        """
        return len(proof) >= 32

    def verify_nonce(self, new_nonce: int, dest_chain: str) -> bool:
        """
        Anti-replay: verify nonce is strictly greater than last processed.
        Mirrors cardano/lib/vams/icb.ak:is_valid_nonce
        """
        self._stats["nonces_validated"] += 1
        last_nonce = self._nonce_tracker.get(dest_chain, 0)

        if new_nonce <= last_nonce:
            self._stats["replay_attempts_blocked"] += 1
            logger.warning(
                f"Replay attempt blocked: nonce {new_nonce} <= "
                f"last {last_nonce} for {dest_chain}"
            )
            return False

        return True

    def is_from_polygon(self, source: str) -> bool:
        """Mirror icb.ak/is_from_polygon."""
        return source.lower() == "polygon"

    def is_to_cardano(self, dest: str) -> bool:
        """Mirror icb.ak/is_to_cardano."""
        return dest.lower() == "cardano"

    def get_stats(self) -> dict:
        return {**self._stats}


# =============================================================================
# MULTI-ISM VERIFICATION (Section 20.5)
# =============================================================================

@dataclass
class ISMVerification:
    """Result of a single ISM verification."""
    ism_type: ISMType
    verified: bool
    latency_ms: float
    attestation: str = ""


class MultiISMVerifier:
    """
    Multi-ISM verification with 2/3 threshold.

    Architecture Section 20.5:
        contract VAMSMultiISM:
            phalaISM, oracleISM, multisigISM
            THRESHOLD = 2  // 2/3 required

    ISM Provider Diversity:
        | ISM Type     | Provider         | Trust Model            |
        | TEE-Based    | Phala Network    | Hardware attestation   |
        | Oracle-Based | Chainlink CCIP   | Economic stake (DON)   |
        | Multisig     | VAMS DAO Signers | Social consensus (5/9) |
    """

    THRESHOLD = 2  # 2/3 ISMs must verify

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self._stats = {
            "verifications": 0,
            "passed": 0,
            "failed": 0,
        }

    def verify(self, message_hash: str) -> Tuple[bool, List[ISMVerification]]:
        """
        Verify a cross-chain message through all 3 ISMs.
        Returns (passed, individual_results).
        """
        self._stats["verifications"] += 1
        results = []

        # ISM 1: Phala TEE attestation
        phala_result = self._verify_phala(message_hash)
        results.append(phala_result)

        # ISM 2: Chainlink CCIP oracle
        oracle_result = self._verify_oracle(message_hash)
        results.append(oracle_result)

        # ISM 3: VAMS DAO multisig
        multisig_result = self._verify_multisig(message_hash)
        results.append(multisig_result)

        # Check threshold
        validations = sum(1 for r in results if r.verified)
        passed = validations >= self.THRESHOLD

        if passed:
            self._stats["passed"] += 1
        else:
            self._stats["failed"] += 1
            logger.warning(
                f"Multi-ISM FAILED: {validations}/{self.THRESHOLD} "
                f"for message {message_hash[:12]}..."
            )

        return passed, results

    def _verify_phala(self, message_hash: str) -> ISMVerification:
        """TEE-based verification via Phala Network."""
        if self.mock_mode:
            return ISMVerification(
                ism_type=ISMType.TEE_PHALA,
                verified=True,
                latency_ms=45.0,
                attestation=f"phala_att_{message_hash[:8]}",
            )
        # Production: call Phala TEE attestation API
        self.logger.error("Live Phala ISM not yet integrated")
        return ISMVerification(
            ism_type=ISMType.TEE_PHALA,
            verified=False,
            latency_ms=0.0,
            attestation="",
        )

    def _verify_oracle(self, message_hash: str) -> ISMVerification:
        """Oracle-based verification via Chainlink CCIP."""
        if self.mock_mode:
            return ISMVerification(
                ism_type=ISMType.ORACLE_CHAINLINK,
                verified=True,
                latency_ms=120.0,
                attestation=f"ccip_att_{message_hash[:8]}",
            )
        self.logger.error("Live Chainlink CCIP ISM not yet integrated")
        return ISMVerification(
            ism_type=ISMType.ORACLE_CHAINLINK,
            verified=False,
            latency_ms=0.0,
            attestation="",
        )

    def _verify_multisig(self, message_hash: str) -> ISMVerification:
        """Multisig verification via VAMS DAO signers (5/9 threshold)."""
        if self.mock_mode:
            return ISMVerification(
                ism_type=ISMType.MULTISIG_DAO,
                verified=True,
                latency_ms=200.0,
                attestation=f"dao_att_{message_hash[:8]}",
            )
        self.logger.error("Live DAO multisig ISM not yet integrated")
        return ISMVerification(
            ism_type=ISMType.MULTISIG_DAO,
            verified=False,
            latency_ms=0.0,
            attestation="",
        )

    def get_stats(self) -> dict:
        return {**self._stats}


# =============================================================================
# TRANSPORT MATRIX (Section 16.3)
# =============================================================================

@dataclass
class TransportRoute:
    """A specific bridge route configuration."""
    source: str
    destination: str
    primary_transport: BridgeTransport
    secondary_transport: Optional[BridgeTransport]
    estimated_latency_ms: int
    security_model: str
    requires_icb: bool = False      # Needs ICB verification (Cardano routes)
    requires_multi_ism: bool = False  # Needs Multi-ISM (Hyperlane routes)


# Architecture Section 16.3: Transport Matrix
TRANSPORT_MATRIX: Dict[str, TransportRoute] = {
    "VAMS_L3->Ethereum": TransportRoute(
        "VAMS_L3", "Ethereum", BridgeTransport.TRAILS,
        BridgeTransport.AGGLAYER, 5_000, "Validity Proofs"
    ),
    "VAMS_L3->Polygon": TransportRoute(
        "VAMS_L3", "Polygon", BridgeTransport.TRAILS,
        BridgeTransport.AGGLAYER, 5_000, "Unified Bridge"
    ),
    "VAMS_L3->Arbitrum": TransportRoute(
        "VAMS_L3", "Arbitrum", BridgeTransport.TRAILS,
        BridgeTransport.AGGLAYER, 5_000, "Unified Bridge"
    ),
    "VAMS_L3->Base": TransportRoute(
        "VAMS_L3", "Base", BridgeTransport.TRAILS,
        BridgeTransport.AGGLAYER, 5_000, "Unified Bridge"
    ),
    "VAMS_L3->Solana": TransportRoute(
        "VAMS_L3", "Solana", BridgeTransport.HYPERLANE,
        BridgeTransport.LAYERZERO, 400,
        "ISM verification", requires_multi_ism=True
    ),
    "VAMS_L3->SEI": TransportRoute(
        "VAMS_L3", "SEI", BridgeTransport.LAYERZERO,
        BridgeTransport.HYPERLANE, 380,
        "DVN consensus"
    ),
    "VAMS_L3->Avalanche": TransportRoute(
        "VAMS_L3", "Avalanche", BridgeTransport.HYPERLANE,
        BridgeTransport.LAYERZERO, 2_000,
        "ISM verification", requires_multi_ism=True
    ),
    "VAMS_L3->Cardano": TransportRoute(
        "VAMS_L3", "Cardano", BridgeTransport.ROSEN_BRIDGE,
        None, 120_000,
        "Ouroboros finality + bridge validators",
        requires_icb=True
    ),
    "VAMS_L3->Midnight": TransportRoute(
        "VAMS_L3", "Midnight", BridgeTransport.HYPERLANE_ZK_ISM,
        None, 60_000,
        "ZK-SD proofs + ISM verification",
        requires_multi_ism=True
    ),
    "VAMS_L3->Hydra": TransportRoute(
        "VAMS_L3", "Hydra", BridgeTransport.DIRECT_STATE_CHANNEL,
        None, 100,
        "Direct state channel (no bridge needed)"
    ),
}


# =============================================================================
# BRIDGE EXECUTOR
# =============================================================================

@dataclass
class BridgeResult:
    """Result of a cross-chain bridge execution."""
    route_key: str
    transport_used: BridgeTransport
    status: BridgeStatus
    icb_message: Optional[BridgeMessage]
    ism_verified: bool
    latency_ms: float
    tx_hash: str = ""
    error: str = ""


try:
    from neuron.sdk.trails_client import TrailsClient
except ImportError:
    from sdk.trails_client import TrailsClient


class TrailsTransportHandler:
    def __init__(self, mock_mode: bool = True):
        self.client = TrailsClient(mock_mode=mock_mode)
        
    def execute_intent(self, source: str, dest: str, payload: bytes) -> BridgeResult:
        start_time = time.time()
        receipt = self.client.submit_intent(source, dest, payload)
        status = self.client.get_status(receipt.intent_id)
        elapsed_ms = (time.time() - start_time) * 1000
        
        return BridgeResult(
            route_key=f"{source}->{dest}",
            transport_used=BridgeTransport.TRAILS,
            status=BridgeStatus.VERIFIED,
            icb_message=None,
            ism_verified=True,  # Handled by Trails natively
            latency_ms=elapsed_ms,
            tx_hash=status.tx_hash
        )


class BridgeExecutor:
    """
    Cross-chain bridge executor with ICB integration
    and Multi-ISM verification.
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.icb = ICBClient()
        self.ism_verifier = MultiISMVerifier(mock_mode=mock_mode)
        self.trails_handler = TrailsTransportHandler(mock_mode=mock_mode)
        self._stats = {
            "executions": 0,
            "successful": 0,
            "failed": 0,
            "fallbacks_used": 0,
        }

    def execute(
        self,
        destination: str,
        payload: bytes,
        source: str = "VAMS_L3",
    ) -> BridgeResult:
        """
        Execute a cross-chain bridge transaction.

        1. Look up transport route from the matrix
        2. Build ICB message if required (Cardano routes)
        3. Verify via Multi-ISM if required (Hyperlane routes)
        4. Submit and return result
        """
        self._stats["executions"] += 1
        route_key = f"{source}->{destination}"
        route = TRANSPORT_MATRIX.get(route_key)

        if not route:
            self._stats["failed"] += 1
            return BridgeResult(
                route_key=route_key,
                transport_used=BridgeTransport.AGGLAYER,
                status=BridgeStatus.FAILED,
                icb_message=None,
                ism_verified=False,
                latency_ms=0,
                error=f"No route found: {route_key}",
            )
            
        if route.primary_transport == BridgeTransport.TRAILS:
            try:
                result = self.trails_handler.execute_intent(source, destination, payload)
                self._stats["successful"] += 1
                return result
            except Exception as e:
                # Let BridgeFallbackHandler handle the fallback to AGGLAYER
                return BridgeResult(
                    route_key=route_key,
                    transport_used=BridgeTransport.TRAILS,
                    status=BridgeStatus.FAILED,
                    icb_message=None,
                    ism_verified=False,
                    latency_ms=0,
                    error=f"Trails transport failed: {e}",
                )

        start_time = time.time()

        # Build ICB message if needed (Cardano ecosystem routes)
        icb_message = None
        if route.requires_icb:
            icb_message = self.icb.build_bridge_message(
                source_chain=source.lower().replace("_", ""),
                dest_chain=destination.lower(),
                payload=payload,
            )

            # Verify bridge proof (mock: generate valid proof)
            mock_proof = b'\x00' * 64  # 64 bytes minimum
            proof_valid = self.icb.verify_bridge_proof(
                mock_proof, icb_message.payload_hash
            )
            if not proof_valid:
                self._stats["failed"] += 1
                return BridgeResult(
                    route_key=route_key,
                    transport_used=route.primary_transport,
                    status=BridgeStatus.FAILED,
                    icb_message=icb_message,
                    ism_verified=False,
                    latency_ms=0,
                    error="ICB bridge proof verification failed",
                )

        # Multi-ISM verification if required (Hyperlane routes)
        ism_verified = True
        if route.requires_multi_ism:
            msg_hash = hashlib.sha256(payload).hexdigest()
            ism_verified, _ = self.ism_verifier.verify(msg_hash)
            if not ism_verified:
                self._stats["failed"] += 1
                return BridgeResult(
                    route_key=route_key,
                    transport_used=route.primary_transport,
                    status=BridgeStatus.FAILED,
                    icb_message=icb_message,
                    ism_verified=False,
                    latency_ms=0,
                    error="Multi-ISM verification failed (< 2/3 threshold)",
                )

        # Execute bridge (mock: simulate latency)
        if self.mock_mode:
            # Simulate transport latency
            simulated_latency = route.estimated_latency_ms * 0.001  # Scale down
            time.sleep(min(simulated_latency, 0.1))  # Cap at 100ms

        elapsed_ms = (time.time() - start_time) * 1000
        tx_hash = hashlib.sha256(
            f"{route_key}:{time.time()}:{payload[:16].hex()}".encode()
        ).hexdigest()[:16]

        self._stats["successful"] += 1

        logger.info(
            f"Bridge {route_key}: {route.primary_transport.value} "
            f"({elapsed_ms:.1f}ms) tx={tx_hash}"
        )

        return BridgeResult(
            route_key=route_key,
            transport_used=route.primary_transport,
            status=BridgeStatus.VERIFIED,
            icb_message=icb_message,
            ism_verified=ism_verified,
            latency_ms=elapsed_ms,
            tx_hash=tx_hash,
        )

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "icb": self.icb.get_stats(),
            "ism": self.ism_verifier.get_stats(),
        }


# =============================================================================
# BRIDGE FALLBACK HANDLER (Section 20.5)
# =============================================================================

class BridgeFallbackHandler:
    """
    Timeout-based bridge fallback cascade.

    Architecture Section 20.5:
        Primary: Hyperlane with Multi-ISM (30s timeout)
        Secondary: LayerZero v2 (60s timeout)
        Tertiary: Queue for manual resolution
    """

    def __init__(
        self,
        executor: Optional[BridgeExecutor] = None,
        primary_timeout_ms: int = None,
        secondary_timeout_ms: int = None,
    ):
        self.executor = executor or BridgeExecutor()
        self.primary_timeout_ms = primary_timeout_ms or BRIDGE_PRIMARY_TIMEOUT_MS
        self.secondary_timeout_ms = secondary_timeout_ms or BRIDGE_SECONDARY_TIMEOUT_MS
        self._manual_queue: List[dict] = []
        self._stats = {
            "primary_success": 0,
            "secondary_success": 0,
            "manual_queued": 0,
        }

    def bridge_with_fallback(
        self,
        destination: str,
        payload: bytes,
        source: str = "VAMS_L3",
    ) -> BridgeResult:
        """
        Execute bridge with timeout-based fallback cascade.
        """
        # Primary attempt
        result = self.executor.execute(destination, payload, source)

        if result.status == BridgeStatus.VERIFIED:
            self._stats["primary_success"] += 1
            return result

        # Check if secondary transport available
        route_key = f"{source}->{destination}"
        route = TRANSPORT_MATRIX.get(route_key)

        if route and route.secondary_transport:
            logger.warning(
                f"Primary bridge failed for {route_key}, "
                f"trying secondary: {route.secondary_transport.value}"
            )
            
            # AUDIT FIX OFC02: Actually use the secondary transport.
            # Previously, this code re-called executor.execute() which just
            # re-selected the same primary transport from the matrix.
            # Create a temporary route override with the secondary as primary.
            original_primary = route.primary_transport
            try:
                # Temporarily swap primary/secondary so executor uses the fallback
                route.primary_transport = route.secondary_transport
                route.secondary_transport = None
                
                result2 = self.executor.execute(destination, payload, source)
            finally:
                # Restore original route configuration
                route.secondary_transport = route.primary_transport
                route.primary_transport = original_primary
            
            if result2.status == BridgeStatus.VERIFIED:
                self._stats["secondary_success"] += 1
                result2.status = BridgeStatus.FALLBACK
                self.executor._stats["fallbacks_used"] = self.executor._stats.get("fallbacks_used", 0) + 1
                return result2

        # Tertiary: manual queue
        logger.error(
            f"All bridge transports failed for {route_key}, "
            f"queuing for manual resolution"
        )
        self._manual_queue.append({
            "destination": destination,
            "payload_hash": hashlib.sha256(payload).hexdigest()[:16],
            "timestamp": time.time(),
            "original_error": result.error,
        })
        self._stats["manual_queued"] += 1

        return BridgeResult(
            route_key=route_key,
            transport_used=BridgeTransport.AGGLAYER,
            status=BridgeStatus.MANUAL_QUEUE,
            icb_message=None,
            ism_verified=False,
            latency_ms=0,
            error="Queued for manual resolution after all transports failed",
        )

    def get_manual_queue(self) -> List[dict]:
        return list(self._manual_queue)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "queue_size": len(self._manual_queue),
            "executor": self.executor.get_stats(),
        }
